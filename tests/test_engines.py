# ═══════════════════════════════════════════════════════════════
#  tests/test_engines.py — flooder + scanner event-log integration
# ═══════════════════════════════════════════════════════════════

import asyncio
import socket

from flooder import Flooder, _error_class
from scanner import PortScannerEngine


def test_error_class_mapping():
    import asyncio as aio

    assert _error_class(ConnectionRefusedError()) == "refused"
    assert _error_class(aio.TimeoutError()) == "timeout"
    assert _error_class(aio.CancelledError()) == "cancel"
    assert _error_class(OSError("generic")) == "other"


def test_flooder_emits_aggregates_not_per_packet(log_env):
    _, read_log = log_env

    async def run():
        f = Flooder(
            target="127.0.0.1", ports=[1], bots=6, concurrency=3,
            packet_size=64, connect_timeout=0.4, session_id="tab-9",
            stats_interval=1.0,
        )
        await f.run()
        await asyncio.sleep(0.05)

    asyncio.run(run())
    text = read_log()
    assert "flood.workers_spawned" in text
    assert "bots=6" in text
    assert "flood.stats" in text
    # Closed loopback port -> refused or timeout classes only.
    assert "flood.error_sample" in text
    # No per-packet event lines (there is no such event name).
    assert "flood.packet" not in text


def test_flooder_stop_event(log_env):
    _, read_log = log_env

    async def run():
        f = Flooder(
            target="127.0.0.1", ports=[1], bots=3, concurrency=2,
            packet_size=64, connect_timeout=0.3, session_id="tab-8",
        )
        task = asyncio.create_task(f.run())
        await asyncio.sleep(0)
        f.stop()
        await task

    asyncio.run(run())
    assert "flood.stopped" in read_log()
    assert "actor=user" in read_log()


def test_scanner_lifecycle_events(log_env):
    _, read_log = log_env

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    open_port = srv.getsockname()[1]

    async def run():
        eng = PortScannerEngine(
            host="127.0.0.1", ports=[open_port, open_port + 1],
            session_id="scan-5",
        )
        return await eng.scan()

    try:
        results = asyncio.run(run())
    finally:
        srv.close()

    text = read_log()
    assert "scan.started" in text
    assert "session_id" not in text  # session id lives in [scan-5] column
    assert "[scan-5]" in text
    assert "scan.progress" in text
    assert "scan.open_port" in text
    assert f"port={open_port}" in text
    assert "scan.finished" in text
    assert any(r.port == open_port and r.state != "offline" for r in results)
