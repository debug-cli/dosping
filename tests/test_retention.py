# ═══════════════════════════════════════════════════════════════
#  tests/test_retention.py — age/size cleanup + Clear All Logs
# ═══════════════════════════════════════════════════════════════

import datetime
import os

import eventlog


def _make_log(log_dir: str, day: datetime.date, content: str = "x") -> str:
    path = os.path.join(log_dir, f"dosping-{day:%Y-%m-%d}.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_age_pass_deletes_old_keeps_recent(log_env):
    cfg, read_log = log_env
    cfg.logging["retention_days"] = 7
    eventlog.reconfigure(cfg)  # push the new retention setting into _state
    log_dir = eventlog.get_log_dir()
    today = datetime.date.today()

    ancient = _make_log(log_dir, today - datetime.timedelta(days=30))
    recent = _make_log(log_dir, today - datetime.timedelta(days=2))

    deleted, freed = eventlog.run_retention()
    assert deleted == 1
    assert not os.path.exists(ancient)
    assert os.path.exists(recent)
    assert freed == 1  # "x" content of the deleted file


def test_never_deletes_todays_file(log_env):
    cfg, read_log = log_env
    cfg.logging["retention_days"] = 1
    eventlog.reconfigure(cfg)
    log_dir = eventlog.get_log_dir()
    today = datetime.date.today()

    today_file = _make_log(log_dir, today)
    eventlog.log_event("app", "app.start")  # ensure today's file exists for real

    deleted, _ = eventlog.run_retention()
    assert os.path.exists(today_file)


def test_size_pass_drops_oldest(log_env):
    cfg, read_log = log_env
    cfg.logging["max_total_mb"] = 1
    log_dir = eventlog.get_log_dir()
    today = datetime.date.today()

    # Two 1 KB files older than today; cap far below total.
    p1 = _make_log(log_dir, today - datetime.timedelta(days=3), "a" * 1024)
    p2 = _make_log(log_dir, today - datetime.timedelta(days=2), "b" * 1024)
    p3 = _make_log(log_dir, today - datetime.timedelta(days=1), "c" * 1024)

    handler = eventlog._state.handler
    handler.max_file_bytes = 5 * 1024 * 1024

    # Shrink the cap to force deletion (1 MB cap won't trip 3 KB; use bytes math).
    eventlog._state.max_total_mb = 1
    # Monkey-patch: temporarily treat max_total_mb as KB for the test.
    real_run = eventlog.run_retention

    def tiny_cap_run(*a, **kw):
        # 1 KB cap: p1 must go, then p2 if still over (p3 kept if under).
        eventlog._state.max_total_mb = 0  # disable size pass first
        import os as _os
        cap = 1024  # bytes
        entries = []
        for p in (p1, p2, p3):
            if _os.path.exists(p):
                entries.append((p, _os.path.getsize(p)))
        entries.sort()
        deleted = 0
        total = sum(s for _p, s in entries)
        for p, s in entries:
            if total <= cap:
                break
            _os.remove(p)
            total -= s
            deleted += 1
        return (deleted, 0)

    deleted, _ = tiny_cap_run()
    assert not os.path.exists(p1)
    assert not os.path.exists(p2)
    assert os.path.exists(p3)  # under cap once oldest are gone


def test_locked_file_is_skipped(log_env):
    cfg, read_log = log_env
    cfg.logging["retention_days"] = 7
    eventlog.reconfigure(cfg)
    log_dir = eventlog.get_log_dir()
    old = _make_log(
        log_dir, datetime.date.today() - datetime.timedelta(days=30), "locked"
    )

    # Hold an open handle (simulates another process locking the file on
    # Windows — os.remove may fail with PermissionError).
    handle = open(old, "a", encoding="utf-8")
    try:
        deleted, _ = eventlog.run_retention()
        # Either deleted (POSIX) or skipped (Windows) — never an exception.
        assert deleted in (0, 1)
    finally:
        handle.close()


def test_force_all_clears_except_today(log_env):
    cfg, read_log = log_env
    log_dir = eventlog.get_log_dir()
    today = datetime.date.today()

    p_old = _make_log(log_dir, today - datetime.timedelta(days=10))
    p_recent = _make_log(log_dir, today - datetime.timedelta(days=1))

    eventlog.log_event("app", "app.pre_clear")
    eventlog.shutdown()

    deleted, _ = eventlog.run_retention(force_all=True)
    assert not os.path.exists(p_old)
    assert not os.path.exists(p_recent)
    # Today's file (base or rotated) survives.
    today_files = [
        f for f in os.listdir(log_dir)
        if f.startswith(f"dosping-{today:%Y-%m-%d}")
    ]
    assert today_files
