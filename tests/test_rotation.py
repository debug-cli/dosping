# ═══════════════════════════════════════════════════════════════
#  tests/test_rotation.py — daily + size rotation of the log file
# ═══════════════════════════════════════════════════════════════

import datetime
import os

import eventlog
from tests.conftest import FakeConfig


def test_size_rotation_creates_suffix_files(log_env):
    cfg, read_log = log_env
    cfg.logging["max_file_mb"] = 1  # smallest allowed cap
    eventlog.reconfigure(cfg)

    handler = eventlog._state.handler
    # Force the byte cap down to something a test can exceed quickly.
    handler.max_file_bytes = 200

    for i in range(50):
        eventlog.log_event("app", "app.tick", i=i, pad="y" * 30)
    eventlog.shutdown()

    log_dir = eventlog.get_log_dir()
    files = sorted(os.listdir(log_dir))
    assert any(".1.log" in f for f in files), files
    today = f"dosping-{datetime.date.today():%Y-%m-%d}"
    assert f"{today}.log" in files  # active base file exists


def test_daily_rotation_on_date_change(tmp_path, monkeypatch):
    eventlog.shutdown()
    monkeypatch.setattr(eventlog, "_state", eventlog._State(), raising=False)
    cfg = FakeConfig(str(tmp_path))
    eventlog.init(cfg, version="3.7.1", codename="Code Red")

    handler = eventlog._state.handler
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    # Prime today's file, then write "yesterday's" line by making the
    # handler's clock return yesterday (simulates the date rolling over).
    eventlog.log_event("app", "app.new_day")
    monkeypatch.setattr(handler, "_today", lambda: yesterday)
    eventlog.log_event("app", "app.old_day")
    eventlog.shutdown()  # flush

    old_file = os.path.join(
        eventlog.get_log_dir(), f"dosping-{yesterday:%Y-%m-%d}.log"
    )
    assert os.path.exists(old_file)

    # Re-init and write on today's date -> new file, old one untouched.
    eventlog.init(cfg, version="3.7.1", codename="Code Red")
    eventlog.log_event("app", "app.new_day")
    eventlog.shutdown()

    new_file = os.path.join(
        eventlog.get_log_dir(), f"dosping-{today:%Y-%m-%d}.log"
    )
    assert os.path.exists(new_file)
    assert "app.old_day" in open(old_file, encoding="utf-8").read()
    assert "app.new_day" in open(new_file, encoding="utf-8").read()
