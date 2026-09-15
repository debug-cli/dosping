# ═══════════════════════════════════════════════════════════════
#  scanner.py  —  DOSping 3.7.1 Async Port Scanner
# ═══════════════════════════════════════════════════════════════
#  Pure Python TCP scanner for DOSping's Port Scanner mode.
#  No nmap dependency. No administrator requirement.

from __future__ import annotations

import asyncio
import ipaddress
import time
from dataclasses import dataclass
from typing import Iterable, Optional

try:
    import eventlog
except Exception:  # scanner must work even if the logger is missing
    eventlog = None  # type: ignore[assignment]


# Progress milestones logged as scan.progress (percent done).
_PROGRESS_MILESTONES = (10, 25, 50, 75, 100)


@dataclass(frozen=True)
class ScanResult:
    host: str
    port: int
    state: str
    protocol: str
    device: str
    banner: str
    latency_ms: float


def parse_port_spec(spec: str) -> list[int]:
    """Parse comma-separated ports and ranges into a sorted unique list."""
    ports: set[int] = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if start <= 0 or end > 65535 or start > end:
                raise ValueError(f"invalid port range: {part}")
            ports.update(range(start, end + 1))
        else:
            port = int(part)
            if port < 1 or port > 65535:
                raise ValueError(f"invalid port: {part}")
            ports.add(port)
    if not ports:
        raise ValueError("no ports provided")
    return sorted(ports)


class PortScannerEngine:
    """Async TCP scanner with banner grabbing and fingerprinting."""

    def __init__(
        self,
        host: str,
        ports: Iterable[int],
        timeout: float = 0.75,
        banner_timeout: float = 0.45,
        concurrency: int = 128,
        banner_grab: bool = True,
        session_id: Optional[str] = None,
    ) -> None:
        self.host = host
        self.ports = sorted(set(int(p) for p in ports))
        self.timeout = timeout
        self.banner_timeout = banner_timeout
        self.concurrency = concurrency
        self.banner_grab = banner_grab
        self.session_id = session_id
        self.semaphore = asyncio.Semaphore(concurrency)

    async def scan(self) -> list[ScanResult]:
        t_start = time.monotonic()
        if eventlog is not None:
            eventlog.log_event(
                "scanner", "scan.started", session=self.session_id,
                mode="host", target=self.host, port_count=len(self.ports),
                concurrency=self.concurrency, timeout=self.timeout,
                banner_timeout=self.banner_timeout, banner_grab=self.banner_grab,
            )
        tasks = [asyncio.create_task(self._scan_port(port)) for port in self.ports]
        results: list[ScanResult] = []
        done = 0
        next_milestone = 0
        for fut in asyncio.as_completed(tasks):
            results.append(await fut)
            done += 1
            if eventlog is not None and next_milestone < len(_PROGRESS_MILESTONES):
                pct = int(done * 100 / len(self.ports)) if self.ports else 100
                if pct >= _PROGRESS_MILESTONES[next_milestone]:
                    eventlog.log_event(
                        "scanner", "scan.progress", session=self.session_id,
                        percent=_PROGRESS_MILESTONES[next_milestone],
                        checked=done, total=len(self.ports),
                    )
                    # Skip any milestones already passed.
                    while (
                        next_milestone < len(_PROGRESS_MILESTONES)
                        and int(done * 100 / len(self.ports))
                        >= _PROGRESS_MILESTONES[next_milestone]
                    ):
                        next_milestone += 1
        results.sort(key=lambda item: item.port)
        if eventlog is not None:
            open_count = sum(1 for r in results if r.state != "offline")
            hosts = len({r.host for r in results if r.state != "offline"})
            for r in results:
                if r.state == "offline":
                    continue
                eventlog.log_event(
                    "scanner", "scan.open_port", session=self.session_id,
                    host=r.host, port=r.port, state=r.state,
                    protocol=r.protocol, device=r.device,
                    latency=f"{r.latency_ms:.1f}ms",
                )
                if r.banner:
                    eventlog.log_event(
                        "scanner", "scan.banner", level="debug",
                        session=self.session_id, port=r.port,
                        banner=r.banner,
                    )
            eventlog.log_event(
                "scanner", "scan.finished", session=self.session_id,
                duration=eventlog._fmt_duration(time.monotonic() - t_start),
                checked=len(results), open=open_count, hosts=hosts,
            )
        return results

    async def _scan_port(self, port: int) -> ScanResult:
        async with self.semaphore:
            start = asyncio.get_running_loop().time()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, port),
                    timeout=self.timeout,
                )
            except (asyncio.TimeoutError, OSError):
                return ScanResult(
                    host=self.host,
                    port=port,
                    state="offline",
                    protocol="filtered/closed",
                    device="Unknown",
                    banner="",
                    latency_ms=self._elapsed_ms(start),
                )

            if self.banner_grab:
                protocol, banner = await self._grab_banner(reader, writer, port)
            else:
                protocol, banner = "unknown", ""
            device = self._fingerprint_device(port, protocol, banner)
            state = "accessible" if protocol != "unknown" else "online"
            return ScanResult(
                host=self.host,
                port=port,
                state=state,
                protocol=protocol,
                device=device,
                banner=banner,
                latency_ms=self._elapsed_ms(start),
            )

    async def _grab_banner(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        port: int,
    ) -> tuple[str, str]:
        probe = self._probe_for_port(port)
        try:
            if probe:
                writer.write(probe)
                await writer.drain()
            data = await asyncio.wait_for(reader.read(512), timeout=self.banner_timeout)
        except Exception:
            data = b""
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

        text = self._clean_banner(data.decode("utf-8", errors="replace"))
        protocol = self._fingerprint_protocol(port, text)
        return protocol, text

    def _probe_for_port(self, port: int) -> bytes:
        if port in {80, 443, 8000, 8080, 8081, 8443}:
            return b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        if port in {25, 587}:
            return b"EHLO localhost\r\n"
        if port == 554:
            return b"OPTIONS * RTSP/1.0\r\nCSeq: 1\r\n\r\n"
        if port == 23:
            return b"\xff\xfd\x01"
        if port in {110, 143, 21, 22}:
            return b""
        return b"\r\n"

    def _fingerprint_protocol(self, port: int, banner: str) -> str:
        lower = banner.lower()
        if port in {80, 443, 8000, 8080, 8081, 8443} or "http/" in lower:
            return "https" if port == 443 or "ssl" in lower else "http"
        if "ssh-" in lower or port == 22:
            return "ssh"
        if "ftp" in lower or port == 21:
            return "ftp"
        if "smtp" in lower or port in {25, 587, 465}:
            return "smtp"
        if "+ok pop" in lower or port == 110:
            return "pop3"
        if "* ok" in lower or port == 143:
            return "imap"
        if "rtsp" in lower or port == 554:
            return "rtsp"
        if "telnet" in lower or port == 23:
            return "telnet"
        return "unknown"

    def _fingerprint_device(self, port: int, protocol: str, banner: str) -> str:
        lower = banner.lower()
        if any(word in lower for word in ["router", "openwrt", "mikrotik"]):
            return "Router"
        if any(word in lower for word in ["camera", "ipc", "hikvision", "dahua"]):
            return "Camera"
        if any(
            word in lower for word in ["tv", "roku", "chromecast", "webos", "smart-tv"]
        ):
            return "TV"
        if any(word in lower for word in ["android", "iphone", "mobile"]):
            return "Phone"
        if any(word in lower for word in ["playstation", "xbox", "nintendo"]):
            return "Gaming Console"
        if protocol in {"http", "https"} and port in {80, 443, 8080, 8443}:
            return "Web Server"
        if protocol == "rtsp":
            return "Camera"
        if protocol == "ftp" and port == 21:
            return "Server"
        return "Unknown"

    def _clean_banner(self, text: str) -> str:
        text = text.replace("\x00", "")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return " | ".join(lines[:4])[:180]

    def _elapsed_ms(self, start: float) -> float:
        return (asyncio.get_running_loop().time() - start) * 1000


class NetworkScanEngine:
    """Scan all live hosts in a subnet for open ports.

    Uses one PortScannerEngine per host, gated by a host-level semaphore so
    at most `host_concurrency` hosts are scanned in parallel.  Only results
    with state != "offline" are returned.
    """

    def __init__(
        self,
        subnet: str,
        ports: Iterable[int],
        timeout: float = 0.75,
        banner_timeout: float = 0.45,
        concurrency: int = 64,
        host_concurrency: int = 20,
        banner_grab: bool = True,
        session_id: Optional[str] = None,
    ) -> None:
        self.network = ipaddress.ip_network(subnet, strict=False)
        self.ports = sorted(set(int(p) for p in ports))
        self.timeout = timeout
        self.banner_timeout = banner_timeout
        self.concurrency = concurrency
        self.host_concurrency = host_concurrency
        self.banner_grab = banner_grab
        self.session_id = session_id

    async def scan(self) -> list[ScanResult]:
        """Return flat sorted list of open/accessible ports across all hosts."""
        t_start = time.monotonic()
        hosts = [str(ip) for ip in self.network.hosts()]
        if eventlog is not None:
            eventlog.log_event(
                "scanner", "scan.started", session=self.session_id,
                mode="network", target=str(self.network),
                host_count=len(hosts), port_count=len(self.ports),
                concurrency=self.concurrency,
                host_concurrency=self.host_concurrency,
                timeout=self.timeout, banner_grab=self.banner_grab,
            )
        sem = asyncio.Semaphore(self.host_concurrency)

        async def scan_one(host: str) -> list[ScanResult]:
            async with sem:
                engine = PortScannerEngine(
                    host=host,
                    ports=self.ports,
                    timeout=self.timeout,
                    banner_timeout=self.banner_timeout,
                    concurrency=self.concurrency,
                    banner_grab=self.banner_grab,
                )
                results = await engine.scan()
                return [r for r in results if r.state != "offline"]

        tasks = [asyncio.create_task(scan_one(h)) for h in hosts]
        per_host = await asyncio.gather(*tasks)

        all_results: list[ScanResult] = []
        for results in per_host:
            all_results.extend(results)

        if eventlog is not None:
            open_results = [r for r in all_results if r.state != "offline"]
            for r in open_results:
                eventlog.log_event(
                    "scanner", "scan.open_port", session=self.session_id,
                    host=r.host, port=r.port, state=r.state,
                    protocol=r.protocol, device=r.device,
                    latency=f"{r.latency_ms:.1f}ms",
                )
                if r.banner:
                    eventlog.log_event(
                        "scanner", "scan.banner", level="debug",
                        session=self.session_id, port=r.port, banner=r.banner,
                    )
            eventlog.log_event(
                "scanner", "scan.finished", session=self.session_id,
                duration=eventlog._fmt_duration(time.monotonic() - t_start),
                hosts_scanned=len(hosts), checked=len(all_results),
                open=len(open_results),
            )

        def _sort_key(r: ScanResult) -> tuple:
            try:
                return (ipaddress.ip_address(r.host), r.port)
            except ValueError:
                return (r.host, r.port)  # type: ignore[return-value]

        return sorted(all_results, key=_sort_key)
