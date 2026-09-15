# ═══════════════════════════════════════════════════════════════
#  tests/test_gates.py — master toggle + verbosity level gates
# ═══════════════════════════════════════════════════════════════

import os

import eventlog
from tests.conftest import FakeConfig


def test_disabled_writes_nothing(tmp_path, monkeypatch):
    eventlog.shutdown()
    monkeypatch.setattr(eventlog, "_state", eventlog._State(), raising=False)
    cfg = FakeConfig(str(tmp_path), logging={"enabled": False})
    cfg.path = os.path.join(str(tmp_path), "config.json")
    eventlog.init(cfg, version="3.7.1", codename="Code Red")

    eventlog.log_event("app", "app.start")
    eventlog.log_error("app", "ctx", RuntimeError("boom"))

    import glob
    log_dir = os.path.join(str(tmp_path), "logs")
    # No writer thread, no queue — nothing materializes on disk.
    assert eventlog._state.queue is None
    assert eventlog._state.listener is None
    assert glob.glob(os.path.join(log_dir, "*.log*")) == []


def test_minimal_hides_normal_events(log_env):
    cfg, read_log = log_env
    cfg.logging["level"] = "minimal"
    eventlog.reconfigure(cfg)

    eventlog.log_event("flood", "flood.stats", ok=1)         # gated out
    eventlog.log_event("session", "session.tab_opened")       # gated out
    eventlog.log_event("app", "app.start")                    # always
    eventlog.log_event("error", "error.exception", level="error")  # always

    text = read_log()
    assert "flood.stats" not in text
    assert "session.tab_opened" not in text
    assert "app.start" in text
    assert "error.exception" in text


def test_verbose_unlocks_verbose_events(log_env):
    cfg, read_log = log_env
    cfg.logging["level"] = "verbose"
    eventlog.reconfigure(cfg)

    eventlog.log_event("session", "session.setup_validated", kind="test")
    eventlog.log_event("scanner", "scan.banner", level="debug", banner="SSH-2.0")

    text = read_log()
    assert "session.setup_validated" in text
    assert "scan.banner" in text


def test_normal_hides_verbose_events(log_env):
    cfg, read_log = log_env
    cfg.logging["level"] = "normal"
    eventlog.reconfigure(cfg)

    eventlog.log_event("session", "session.setup_validated", kind="test")

    assert "session.setup_validated" not in read_log()


def test_debug_only_events(log_env):
    cfg, read_log = log_env
    cfg.logging["level"] = "debug"
    eventlog.reconfigure(cfg)
    eventlog.log_event("ui", "ui.geoip_result", country="NL")

    # Same event at verbose level must be filtered out.
    cfg.logging["level"] = "verbose"
    eventlog.reconfigure(cfg)
    eventlog.log_event("ui", "ui.geoip_result", country="NL")
    eventlog.log_event("session", "session.setup_validated")  # verbose: passes

    text = read_log()
    assert text.count("ui.geoip_result") == 1
    assert "session.setup_validated" in text


def test_log_error_bypasses_level_gate(log_env):
    cfg, read_log = log_env
    cfg.logging["level"] = "minimal"
    eventlog.reconfigure(cfg)

    try:
        raise ValueError("boom")
    except ValueError as e:
        eventlog.log_error("flood", "health_check", e)

    text = read_log()
    assert "error.exception" in text
    assert "exc=ValueError" in text
    assert "boom" in text
