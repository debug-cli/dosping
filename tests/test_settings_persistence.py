# ═══════════════════════════════════════════════════════════════
#  tests/test_settings_persistence.py — config schema, migration,
#  and the Config.save() changed-keys event log
# ═══════════════════════════════════════════════════════════════

import json
import os

import config as C
import eventlog


def _fresh_state(monkeypatch):
    eventlog.shutdown()
    monkeypatch.setattr(eventlog, "_state", eventlog._State(), raising=False)


def test_default_logging_schema():
    d = C._default_config()
    lg = d["advanced"]["logging"]
    assert lg == {
        "enabled": True,
        "level": "normal",
        "retention_days": 30,
        "max_total_mb": 50,
        "max_file_mb": 5,
    }
    # Legacy UI-log keys stay untouched at their original place.
    assert d["advanced"]["flood_log_lines"] == 2000
    assert d["advanced"]["timestamped_logs"] is True


def test_migration_adds_logging_section(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"theme": {"name": "monochrome"}}))
    cfg = C.Config(str(cfg_path))
    lg = cfg.get("advanced.logging")
    assert lg["enabled"] is True
    assert lg["level"] == "normal"
    assert cfg.get("advanced.flood_log_lines") == 2000


def test_migration_clamps_bad_values(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "advanced": {
            "logging": {
                "level": "bogus",
                "retention_days": 5,
                "max_total_mb": 33,
                "max_file_mb": 999,
            }
        }
    }))
    cfg = C.Config(str(cfg_path))
    lg = cfg.get("advanced.logging")
    assert lg["level"] == "normal"
    assert lg["retention_days"] == 30
    assert lg["max_total_mb"] == 50
    assert lg["max_file_mb"] == 50


def test_default_update_schema():
    d = C._default_config()
    upd = d["advanced"]["update"]
    assert upd == {
        "channel": "stable",
        "auto_check": True,
        "last_checked": "",
        "last_check_status": "",
    }


def test_migration_adds_update_section(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"theme": {"name": "monochrome"}}))
    cfg = C.Config(str(cfg_path))
    upd = cfg.get("advanced.update")
    assert upd["channel"] == "stable"
    assert upd["auto_check"] is True


def test_migration_clamps_bad_update_channel(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "advanced": {"update": {"channel": "nightly", "auto_check": "yes"}}
    }))
    cfg = C.Config(str(cfg_path))
    assert cfg.get("advanced.update.channel") == "stable"
    assert cfg.get("advanced.update.auto_check") is True


def test_migration_recovers_from_garbage_update_section(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"advanced": {"update": "garbage"}}))
    cfg = C.Config(str(cfg_path))
    upd = cfg.get("advanced.update")
    assert isinstance(upd, dict)
    assert upd["channel"] == "stable"
    assert upd["last_check_status"] == ""


def test_version_bumped():
    assert C.APP_VERSION == "3.8.0"
    assert C.APP_CODENAME == "Code Red"


def test_save_logs_changed_keys(tmp_path, monkeypatch):
    _fresh_state(monkeypatch)
    cfg_path = tmp_path / "config.json"
    cfg = C.Config(str(cfg_path))
    eventlog.init(cfg, version="3.7.1", codename="Code Red")

    cfg.set("attacker.threads", 555)
    cfg.set("advanced.logging.level", "verbose")
    assert cfg.save() is True

    eventlog.shutdown()
    import glob
    files = glob.glob(os.path.join(eventlog.get_log_dir(), "*.log"))
    text = "\n".join(open(f, encoding="utf-8").read() for f in files)
    assert "config.save" in text
    assert "changed_keys=2" in text
    assert "advanced.logging.level" in text
    # Persisted values verify round-trip.
    cfg2 = C.Config(str(cfg_path))
    assert cfg2.get("attacker.threads") == 555
    assert cfg2.get("advanced.logging.level") == "verbose"


def test_reset_all_logs_event(tmp_path, monkeypatch):
    _fresh_state(monkeypatch)
    cfg_path = tmp_path / "config.json"
    cfg = C.Config(str(cfg_path))
    eventlog.init(cfg, version="3.7.1", codename="Code Red")

    cfg.reset_all()
    cfg.save()
    eventlog.shutdown()

    import glob
    files = glob.glob(os.path.join(eventlog.get_log_dir(), "*.log"))
    text = "\n".join(open(f, encoding="utf-8").read() for f in files)
    assert "config.reset_all" in text
