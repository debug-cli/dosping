# ═══════════════════════════════════════════════════════════════
#  config.py  —  DOSping 3.7.0 "Code Red" Configuration Layer
# ═══════════════════════════════════════════════════════════════
#  Loads and saves config.json next to dosping.py.  A missing or
#  partially-invalid file is auto-repaired from defaults so the TUI
#  never crashes on a hand-edited config.
#
#  Structure:
#    theme      — theme name, accent colour, background transparency
#    attacker   — target IP / method / threads / packet size
#    scanner    — scan mode / target / ports / timeouts / slots
#    presets    — built-in strength presets + user customs
#    ui         — animation speed, ASCII effects
#    advanced   — engine tuning, logging, safety, sessions, geoip
#
#  FOR PENETRATION TESTING / EDUCATIONAL PURPOSES ONLY.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

import ipaddress
import json
import os
import re
import threading
from typing import Any, Optional

APP_NAME = "DOSping"
APP_VERSION = "3.7.0"
APP_CODENAME = "Code Red"
APP_REPO = "https://github.com/debug-cli/dosping"
APP_DOCS = "https://dosping-docs.vercel.app"
DISCLAIMER = (
    "FOR PENETRATION TESTING AND EDUCATIONAL PURPOSES ONLY. Unauthorized use "
    "against systems you don't own or have permission to test is illegal. "
    "You accept full responsibility. Use at your own risk."
)

# ── File location ─────────────────────────────────────────────
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# ── Numeric guardrails (mirrored in the UI validation) ────────
IPV4_RE = re.compile(
    r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    r"(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
)
PORT_MIN, PORT_MAX = 1, 65535
THREADS_MIN, THREADS_MAX = 1, 4096
SLOTS_MIN, SLOTS_MAX = 1, 2048
TIMEOUT_MIN, TIMEOUT_MAX = 0.05, 10.0
PACKET_MIN, PACKET_MAX = 8, 8192
CONN_DELAY_MIN, CONN_DELAY_MAX = 0.0, 2.0
LOG_LINES_MIN, LOG_LINES_MAX = 100, 100000
SOCK_TIMEOUT_MIN, SOCK_TIMEOUT_MAX = 0.5, 30.0

BUILTIN_PRESET_NAMES = ("Low", "Medium", "High")
DEFAULT_PRESET = "Medium"

# Preset table (scanner/attacker strength levels).
BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
    "Low": {
        "scanner_threads": 64,
        "scanner_timeout": 1.5,
        "attacker_threads": 50,
        "attacker_packet_size": 64,
        "banner_timeout": 1.0,
        "concurrency": 32,
    },
    "Medium": {
        "scanner_threads": 256,
        "scanner_timeout": 0.75,
        "attacker_threads": 200,
        "attacker_packet_size": 512,
        "banner_timeout": 0.45,
        "concurrency": 128,
    },
    "High": {
        "scanner_threads": 1024,
        "scanner_timeout": 0.3,
        "attacker_threads": 1000,
        "attacker_packet_size": 1024,
        "banner_timeout": 0.3,
        "concurrency": 512,
    },
}


def valid_ip(ip: str) -> bool:
    """True if *ip* is a dotted-quad IPv4 address."""
    if not isinstance(ip, str):
        return False
    return bool(IPV4_RE.match(ip.strip()))


def valid_cidr(cidr: str) -> bool:
    """True if *cidr* is a valid IPv4 CIDR network."""
    try:
        ipaddress.ip_network(cidr.strip(), strict=False)
        return True
    except (ValueError, AttributeError):
        return False


def valid_hostname(host: str) -> bool:
    """True if *host* is a plausible hostname."""
    if not isinstance(host, str) or not (1 <= len(host) <= 253):
        return False
    if valid_ip(host):
        return True
    host = host.strip().rstrip(".")
    labels = host.split(".")
    if any(len(label) > 63 for label in labels):
        return False
    label_re = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$")
    return all(label_re.match(label) for label in labels)


def valid_port_spec(spec: str) -> bool:
    """True if *spec* is a comma list of ports/ranges, e.g. 80,443 or 1-1024."""
    if not isinstance(spec, str) or not spec.strip():
        return False
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a_str, b_str = part.split("-", 1)
                a, b = int(a_str.strip()), int(b_str.strip())
            except ValueError:
                return False
            if a < PORT_MIN or b > PORT_MAX or a > b:
                return False
        else:
            try:
                port = int(part)
            except ValueError:
                return False
            if port < PORT_MIN or port > PORT_MAX:
                return False
    return True


def clamp(value: Any, lo: float, hi: float, default: float) -> float:
    """Coerce *value* into [lo, hi]; return *default* when unparseable."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    return max(lo, min(hi, v))


def clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    """Coerce *value* into [lo, hi] as an int; *default* when unparseable."""
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return int(default)
    return max(lo, min(hi, v))


# ── Defaults ──────────────────────────────────────────────────


def _default_config() -> dict[str, Any]:
    return {
        "theme": {
            "name": "monochrome-red",
            "accent": "#ff3333",
            "transparent_background": True,
        },
        "attacker": {
            "target_ip": "192.0.0.1",
            "attack_method": "tcp-flood",
            "threads": 200,
            "packet_size": 512,
            "connect_timeout": 3.0,
        },
        "scanner": {
            "scan_mode": "host",
            "target": "",
            "ports": "21,22,80,443,554",
            "connect_timeout": 0.75,
            "banner_timeout": 0.45,
            "concurrency": 128,
        },
        "presets": {
            "active": DEFAULT_PRESET,
            "custom": {},
        },
        "ui": {
            "animation_speed": "normal",
            "ascii_effects": True,
            "default_view_mode": "advanced",  # skid | advanced | it
        },
        "advanced": {
            # ── Attack engine ─────────────────────────────
            "connect_timeout": 3.0,     # per-socket TCP connect timeout (s)
            "conn_delay": 0.0,          # pause between launches per bot (s)
            "reuse_payload": True,      # one payload per run vs per packet
            "log_interval": 25,         # flood-log progress line frequency
            # ── Scanner engine ────────────────────────────
            "banner_grab": True,        # fetch protocol banner after connect
            # ── Interface ─────────────────────────────────
            "confirm_quit": True,       # confirmation dialog before quitting
            "confirm_danger": True,     # confirmations for destructive actions
            "toasts": True,             # notification toasts for changes
            "flood_log_lines": 2000,    # RichLog max lines (memory cap)
            "timestamped_logs": True,   # prefix log lines with [HH:MM:SS]
            # ── Sessions ──────────────────────────────────
            "max_tabs": 4,              # concurrent session tabs (1–8)
            "auto_start_session": True, # session modal opens immediately
            # ── Network helpers ───────────────────────────
            "geoip_lookup": True,       # GeoIP panel fetches in IT mode
            "geoip_timeout": 3.0,       # GeoIP HTTP timeout (s)
            # ── Safety ────────────────────────────────────
            "block_private_targets": False,  # refuse RFC1918/loopback targets
        },
    }


def _migrate(data: Any) -> dict[str, Any]:
    """Return *data* merged over defaults, with every field clamped."""
    base = _default_config()
    if not isinstance(data, dict):
        return base

    def merge(dst: dict, src: dict) -> None:
        for key, val in src.items():
            if key in dst and isinstance(dst[key], dict) and isinstance(val, dict):
                merge(dst[key], val)
            elif key in dst:
                dst[key] = val

    merge(base, data)

    # ── Field-level repair / clamping ────────────────────────
    t = base["theme"]
    if t["name"] not in ("monochrome-red", "monochrome"):
        t["name"] = "monochrome-red"
    if not isinstance(t["accent"], str) or not t["accent"]:
        t["accent"] = "#ff3333"
    t["transparent_background"] = bool(t["transparent_background"])

    a = base["attacker"]
    if not isinstance(a["target_ip"], str):
        a["target_ip"] = "192.0.0.1"
    if a["attack_method"] not in ("tcp-flood", "slowloris"):
        a["attack_method"] = "tcp-flood"
    a["threads"] = clamp_int(a["threads"], THREADS_MIN, THREADS_MAX, 200)
    a["packet_size"] = clamp_int(a["packet_size"], PACKET_MIN, PACKET_MAX, 512)
    a["connect_timeout"] = clamp(a["connect_timeout"], TIMEOUT_MIN, TIMEOUT_MAX, 3.0)

    s = base["scanner"]
    if s["scan_mode"] not in ("host", "network"):
        s["scan_mode"] = "host"
    if not isinstance(s["target"], str):
        s["target"] = ""
    if not isinstance(s["ports"], str):
        s["ports"] = "21,22,80,443,554"
    s["connect_timeout"] = clamp(s["connect_timeout"], TIMEOUT_MIN, TIMEOUT_MAX, 0.75)
    s["banner_timeout"] = clamp(s["banner_timeout"], TIMEOUT_MIN, TIMEOUT_MAX, 0.45)
    s["concurrency"] = clamp_int(s["concurrency"], SLOTS_MIN, SLOTS_MAX, 128)

    p = base["presets"]
    if not isinstance(p["custom"], dict):
        p["custom"] = {}
    if p["active"] not in BUILTIN_PRESET_NAMES and p["active"] not in p["custom"]:
        p["active"] = DEFAULT_PRESET

    u = base["ui"]
    if u["animation_speed"] not in ("slow", "normal", "fast"):
        u["animation_speed"] = "normal"
    u["ascii_effects"] = bool(u["ascii_effects"])

    # ── Advanced (additive: unknown keys dropped, missing defaulted) ─
    adv = base["advanced"]
    adv["connect_timeout"] = clamp(
        adv["connect_timeout"], SOCK_TIMEOUT_MIN, SOCK_TIMEOUT_MAX, 3.0
    )
    adv["conn_delay"] = clamp(adv["conn_delay"], CONN_DELAY_MIN, CONN_DELAY_MAX, 0.0)
    adv["reuse_payload"] = bool(adv["reuse_payload"])
    adv["log_interval"] = clamp_int(adv["log_interval"], 1, 500, 25)
    adv["banner_grab"] = bool(adv["banner_grab"])
    adv["confirm_quit"] = bool(adv["confirm_quit"])
    adv["confirm_danger"] = bool(adv["confirm_danger"])
    adv["toasts"] = bool(adv["toasts"])
    adv["flood_log_lines"] = clamp_int(
        adv["flood_log_lines"], LOG_LINES_MIN, LOG_LINES_MAX, 2000
    )
    adv["timestamped_logs"] = bool(adv["timestamped_logs"])
    adv["max_tabs"] = clamp_int(adv["max_tabs"], 1, 8, 4)
    adv["auto_start_session"] = bool(adv["auto_start_session"])
    adv["geoip_lookup"] = bool(adv["geoip_lookup"])
    adv["geoip_timeout"] = clamp(
        adv["geoip_timeout"], SOCK_TIMEOUT_MIN, SOCK_TIMEOUT_MAX, 3.0
    )
    adv["block_private_targets"] = bool(adv["block_private_targets"])

    return base


class Config:
    """Thread-safe wrapper around config.json with schema repair."""

    def __init__(self, path: str = CONFIG_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._dirty = False
        self._data: dict[str, Any] = {}
        self.reload()

    # ── Loading / saving ─────────────────────────────────────

    def reload(self) -> None:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except FileNotFoundError:
                raw = {}
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                raw = {}
            self._data = _migrate(raw)
            self._dirty = False

    def save(self) -> bool:
        """Atomically persist to config.json.  Returns False on OSError."""
        with self._lock:
            try:
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
                os.replace(tmp, self.path)
                self._dirty = False
                return True
            except OSError:
                return False

    # ── Generic accessors ────────────────────────────────────

    def get(self, dotted: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._data
            for part in dotted.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node

    def set(self, dotted: str, value: Any) -> None:
        with self._lock:
            parts = dotted.split(".")
            node = self._data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
            self._dirty = True

    @property
    def dirty(self) -> bool:
        with self._lock:
            return self._dirty

    # ── Presets ──────────────────────────────────────────────

    def all_preset_names(self) -> list[str]:
        with self._lock:
            return list(BUILTIN_PRESET_NAMES) + sorted(self._data["presets"]["custom"])

    def get_preset(self, name: str) -> Optional[dict[str, Any]]:
        with self._lock:
            if name in BUILTIN_PRESETS:
                preset = dict(BUILTIN_PRESETS[name])
            elif name in self._data["presets"]["custom"]:
                preset = dict(self._data["presets"]["custom"][name])
            else:
                return None
            preset["name"] = name
            return preset

    def set_preset(self, name: str, values: dict[str, Any]) -> bool:
        """Create/update a *custom* preset.  Returns False for built-ins."""
        if not name or name in BUILTIN_PRESET_NAMES:
            return False
        cleaned = {
            "scanner_threads": clamp_int(
                values.get("scanner_threads", 256), SLOTS_MIN, SLOTS_MAX, 256
            ),
            "scanner_timeout": clamp(
                values.get("scanner_timeout", 0.75), TIMEOUT_MIN, TIMEOUT_MAX, 0.75
            ),
            "attacker_threads": clamp_int(
                values.get("attacker_threads", 200), THREADS_MIN, THREADS_MAX, 200
            ),
            "attacker_packet_size": clamp_int(
                values.get("attacker_packet_size", 512), PACKET_MIN, PACKET_MAX, 512
            ),
            "banner_timeout": clamp(
                values.get("banner_timeout", 0.45), TIMEOUT_MIN, TIMEOUT_MAX, 0.45
            ),
            "concurrency": clamp_int(
                values.get("concurrency", 128), SLOTS_MIN, SLOTS_MAX, 128
            ),
        }
        with self._lock:
            self._data["presets"]["custom"][name] = cleaned
            self._data["presets"]["active"] = name
            self._dirty = True
        return True

    def delete_preset(self, name: str) -> bool:
        if name in BUILTIN_PRESET_NAMES:
            return False
        with self._lock:
            if name in self._data["presets"]["custom"]:
                del self._data["presets"]["custom"][name]
                if self._data["presets"]["active"] == name:
                    self._data["presets"]["active"] = DEFAULT_PRESET
                self._dirty = True
                return True
        return False

    def apply_preset(self, name: str) -> bool:
        """Copy a preset's values into attacker/scanner settings."""
        preset = self.get_preset(name)
        if preset is None:
            return False
        with self._lock:
            self._data["attacker"]["threads"] = preset["attacker_threads"]
            self._data["attacker"]["packet_size"] = preset["attacker_packet_size"]
            self._data["scanner"]["connect_timeout"] = preset["scanner_timeout"]
            self._data["scanner"]["banner_timeout"] = preset["banner_timeout"]
            self._data["scanner"]["concurrency"] = preset["concurrency"]
            self._data["presets"]["active"] = name
            self._dirty = True
        return True

    # ── Reset helpers (Advanced settings) ───────────────────

    def reset_section(self, section: str) -> None:
        """Restore one top-level config section to its defaults."""
        defaults = _default_config()
        with self._lock:
            if section in defaults:
                self._data[section] = defaults[section]
                self._dirty = True

    def reset_all(self) -> None:
        """Restore the entire configuration to defaults (keeps custom presets)."""
        defaults = _default_config()
        with self._lock:
            custom = self._data.get("presets", {}).get("custom", {})
            self._data = defaults
            self._data["presets"]["custom"] = custom
            self._dirty = True

    def is_private_target(self, ip: str) -> bool:
        """True if *ip* is loopback or RFC1918 private space."""
        try:
            addr = ipaddress.ip_address(ip.strip())
        except ValueError:
            return False
        return addr.is_loopback or addr.is_private


# ── Module-level singleton ────────────────────────────────────

_config: Optional[Config] = None
_config_lock = threading.Lock()


def get_config(path: str = CONFIG_PATH) -> Config:
    """Return the shared Config instance (created on first call)."""
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = Config(path)
    return _config
