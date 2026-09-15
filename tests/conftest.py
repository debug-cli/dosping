# ═══════════════════════════════════════════════════════════════
#  tests/conftest.py — shared fixtures for DOSping event-log tests
# ═══════════════════════════════════════════════════════════════
#  Every test gets a fresh eventlog instance writing into a tmp
#  logs/ dir.  Config is faked (same .get()/.path surface as
#  config.Config) so no test ever touches the real config.json.

import os

import pytest

import eventlog


class FakeConfig:
    """Minimal stand-in for config.Config."""

    def __init__(self, base_dir: str, logging: dict | None = None) -> None:
        self.path = os.path.join(base_dir, "config.json")
        self.logging = {
            "enabled": True,
            "level": "normal",
            "retention_days": 0,      # tests opt out of age deletion
            "max_total_mb": 0,        # and size deletion by default
            "max_file_mb": 5,
        }
        if logging:
            self.logging.update(logging)

    def get(self, dotted: str, default=None):
        if dotted == "advanced.logging.enabled":
            return self.logging["enabled"]
        if dotted == "advanced.logging.level":
            return self.logging["level"]
        if dotted == "advanced.logging.retention_days":
            return self.logging["retention_days"]
        if dotted == "advanced.logging.max_total_mb":
            return self.logging["max_total_mb"]
        if dotted == "advanced.logging.max_file_mb":
            return self.logging["max_file_mb"]
        return default


@pytest.fixture()
def log_env(tmp_path, monkeypatch):
    """Fresh eventlog writing to tmp_path/logs; returns (cfg, read_log)."""
    # Ensure a clean module state per test (atexit from prior runs etc.)
    eventlog.shutdown()
    monkeypatch.setattr(eventlog, "_state", eventlog._State(), raising=False)

    cfg = FakeConfig(str(tmp_path))
    eventlog.init(cfg, version="3.7.1", codename="Code Red")

    import glob

    def read_log() -> str:
        eventlog.shutdown()
        files = sorted(glob.glob(os.path.join(eventlog.get_log_dir(), "*.log*")))
        return "\n".join(open(f, encoding="utf-8").read() for f in files)

    yield cfg, read_log

    eventlog.shutdown()
