# ═══════════════════════════════════════════════════════════════
#  eventlog.py  —  DOSping 3.7.1 "Code Red" Event Logger
# ═══════════════════════════════════════════════════════════════
#  Queue-backed structured event log for DOSping.
#
#  Design:
#    Callers (UI thread, asyncio tasks, worker threads) call
#    log_event()/log_error()/log_exception().  Each call does a
#    fast gate check (two integer compares when gated out) then
#    puts a pre-rendered line onto an unbounded SimpleQueue —
#    never blocking.  A QueueListener daemon thread owns the file:
#    it formats nothing (lines are pre-rendered), writes with
#    flush-per-record, rotates daily and by size, and is closed
#    on shutdown()/atexit.
#
#  Files:   logs/dosping-YYYY-MM-DD.log   (next to config.json)
#           size rotation adds .N suffix: dosping-2026-09-14.1.log
#
#  Line format:
#    {ts} [{level:<5}] [{category}] [{session}] {event} {key=value ...}
#
#  FOR PENETRATION TESTING / EDUCATIONAL PURPOSES ONLY.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

import atexit
import datetime
import logging
import logging.handlers
import os
import re
import socket
import subprocess
import sys
import threading
import traceback
from typing import Any, Optional

# ── Tuning constants ─────────────────────────────────────────
FLOOD_STATS_INTERVAL = 10.0   # seconds between flood.stats aggregates
ERROR_SAMPLE_LIMIT = 3        # per-class flood.error_sample lines
BANNER_TRUNC = 120            # max chars for banners/messages
EXC_TRUNC = 240               # max chars for exception summaries
FIELD_TRUNC = 240             # max chars for any single string field

LOG_DIR_NAME = "logs"
LOG_FILE_PREFIX = "dosping-"
LOG_FILE_SUFFIX = ".log"

_LEVEL_RANK = {"debug": 0, "info": 1, "warn": 2, "error": 3}
_LEVEL_PAD = {"debug": "DEBUG", "info": "INFO ", "warn": "WARN ", "error": "ERROR"}
_CONFIG_LEVELS = ("minimal", "normal", "verbose", "debug")  # config values

# Verbosity ladder: which categories/events a config level includes.
_LEVEL_CATEGORIES = {
    "minimal": {"app", "error"},
    "normal": {"app", "error", "config", "session", "flood", "scanner",
               "settings", "ui"},
    "verbose": {"app", "error", "config", "session", "flood", "scanner",
                "settings", "ui"},
    "debug": {"app", "error", "config", "session", "flood", "scanner",
              "settings", "ui"},
}

# Events always included (subject only to the master toggle).
_ALWAYS_EVENTS = {
    "app.start", "app.shutdown", "app.crash",
    "error.exception",
    "session.attack_started", "session.attack_finished",
    "session.attack_stopped", "session.scan_started",
    "scan.started", "scan.finished",
    "config.reset_all",
}

# Events only logged at verbose+.
_VERBOSE_ONLY_EVENTS = {
    "session.setup_validated", "session.monitor_toggled",
    "flood.health_check", "scan.banner", "settings.theme_changed",
    "ui.export_log",
}

# Events only logged at debug.
_DEBUG_ONLY_EVENTS = {
    "ui.geoip_result", "flood.latency_sample", "ui.queue_diagnostics",
}


# ── State ────────────────────────────────────────────────────

class _State:
    """Module-level logger state (guarded by _lock)."""

    def __init__(self) -> None:
        self.enabled: bool = False
        self.level: str = "normal"
        self.base_dir: str = ""
        self.log_dir: str = ""
        self.max_file_mb: int = 5
        self.retention_days: int = 30
        self.max_total_mb: int = 50
        self.version: str = ""
        self.codename: str = ""
        self.handler: Optional["_DailyFileHandler"] = None
        self.listener: Optional[logging.handlers.QueueListener] = None
        self.queue: Optional["queue.SimpleQueue"] = None
        self.retention_thread: Optional[threading.Thread] = None
        self.initialized: bool = False
        self._lock = threading.Lock()
        self._atexit_registered: bool = False
        self._pid: int = os.getpid()


_state = _State()

# Late import target (queue is stdlib; alias to avoid shadowing).
import queue  # noqa: E402  (stdlib queue — safe name here)


# ── Sanitization helpers ─────────────────────────────────────

def _sanitize(value: Any) -> str:
    """Render *value* as a single safe log token."""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    text = text.replace("\r\n", " ").replace("\n", "\\n").replace("\r", "\\n")
    text = text.replace("\t", "\\t")
    if len(text) > FIELD_TRUNC:
        text = text[:FIELD_TRUNC] + "…"
    if " " in text or not text:
        return f'"{text}"'
    return text


def _fmt_bytes(n: int) -> str:
    return f"{int(n)}B"


def _fmt_duration(seconds: float) -> str:
    return f"{float(seconds):.1f}s"


def _fmt_rate(cps: float) -> str:
    return f"{float(cps):.1f}"


def _fmt_pct(pct: float) -> str:
    return f"{float(pct):.1f}%"


# ── Level gate ───────────────────────────────────────────────

def _passes_gate(category: str, event: str, level: str) -> bool:
    """True when *event* is included by the configured verbosity."""
    cfg_level = _state.level
    if event in _ALWAYS_EVENTS:
        return True
    if event in _DEBUG_ONLY_EVENTS:
        return cfg_level == "debug"
    if event in _VERBOSE_ONLY_EVENTS:
        return cfg_level in ("verbose", "debug")
    cats = _LEVEL_CATEGORIES.get(cfg_level, _LEVEL_CATEGORIES["normal"])
    return category in cats


# ── Line rendering ───────────────────────────────────────────

def _render_line(ts: datetime.datetime, level: str, category: str,
                 session: str, event: str, fields: dict[str, Any]) -> str:
    lv = _LEVEL_PAD.get(level, "INFO ")
    parts = [
        f"[{ts:%Y-%m-%d %H:%M:%S}.{ts.microsecond // 1000:03d}]",
        f"[{lv}]",
        f"[{category}]",
        f"[{session}]",
        event,
    ]
    for key, val in fields.items():
        parts.append(f"{key}={_sanitize(val)}")
    return " ".join(parts)


# ── File handler with daily + size rotation ──────────────────

class _DailyFileHandler(logging.Handler):
    """Writes pre-rendered lines to logs/dosping-YYYY-MM-DD.log.

    Recomputes the filename from wall-clock on every emit; reopens
    when the date changes (daily rotation) or the active file has
    grown past max_file_mb (size rotation, .N suffix).
    """

    def __init__(self, log_dir: str, max_file_mb: int) -> None:
        super().__init__()
        self.log_dir = log_dir
        self.max_file_bytes = max(1, int(max_file_mb)) * 1024 * 1024
        self._day: Optional[datetime.date] = None
        self._path: str = ""
        self._fh = None
        self._written = 0

    # -- filename helpers ------------------------------------------------

    def _today(self) -> datetime.date:
        return datetime.datetime.now().date()

    def _base_path(self, day: datetime.date) -> str:
        return os.path.join(
            self.log_dir, f"{LOG_FILE_PREFIX}{day:%Y-%m-%d}{LOG_FILE_SUFFIX}"
        )

    def _rotate_suffix_path(self, base: str) -> str:
        """Return the first free .N path for *base* (base if under cap)."""
        if not os.path.exists(base) or os.path.getsize(base) < self.max_file_bytes:
            return base
        n = 1
        while True:
            cand = f"{base[:-len(LOG_FILE_SUFFIX)]}.{n}{LOG_FILE_SUFFIX}"
            if not os.path.exists(cand) or os.path.getsize(cand) < self.max_file_bytes:
                return cand
            n += 1

    # -- open / close -----------------------------------------------------

    def _open_for(self, path: str) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None
        self._path = path
        try:
            self._fh = open(path, "a", encoding="utf-8", buffering=1)
            self._written = os.path.getsize(path) if os.path.exists(path) else 0
        except OSError:
            self._fh = None

    def _maybe_header(self) -> None:
        if self._fh is None or self._written > 0:
            return
        ts = datetime.datetime.now()
        header = (
            f"# DOSping {_state.version} \"{_state.codename}\" log opened "
            f"{ts:%Y-%m-%d %H:%M:%S} pid={_state._pid} level={_state.level}\n"
        )
        try:
            self._fh.write(header)
            self._fh.flush()
            self._written += len(header.encode("utf-8"))
        except Exception:
            pass

    # -- logging.Handler API ----------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = record.getMessage()
        except Exception:
            return
        if not line:
            return
        today = self._today()
        if self._fh is None or today != self._day or self._written >= self.max_file_bytes:
            self._day = today
            base = self._base_path(today)
            path = self._rotate_suffix_path(base)
            self._open_for(path)
            self._maybe_header()
        if self._fh is None:
            return
        try:
            self._fh.write(line + "\n")
            self._fh.flush()  # flush per record: crash-safe
            self._written += len(line.encode("utf-8")) + 1
        except Exception:
            # Disk full / file locked / etc. — never crash the app for a log.
            pass

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None
        super().close()


# ── Init / reconfigure / shutdown ────────────────────────────

def init(cfg: Any, *, version: str, codename: str) -> None:
    """Initialise the event log from a Config instance.

    Reads advanced.logging.*; builds the queue + listener when
    enabled; starts the startup retention pass in a daemon thread;
    registers atexit shutdown.
    """
    with _state._lock:
        _state.version = version
        _state.codename = codename
        _state.base_dir = os.path.dirname(os.path.abspath(cfg.path)) if hasattr(cfg, "path") else os.getcwd()
        _state.log_dir = os.path.join(_state.base_dir, LOG_DIR_NAME)

        _apply_config_locked(cfg)

        if not _state.enabled:
            _state.initialized = True
            return

        if _state.listener is None:
            os.makedirs(_state.log_dir, exist_ok=True)
            _state.queue = queue.SimpleQueue()
            qh = logging.handlers.QueueHandler(_state.queue)
            qh.setLevel(logging.DEBUG)
            root = logging.Logger("dosping.eventlog", level=logging.DEBUG)
            root.addHandler(qh)
            root.propagate = False
            _state.handler = _DailyFileHandler(_state.log_dir, _state.max_file_mb)
            _state.listener = logging.handlers.QueueListener(
                _state.queue, _state.handler, respect_handler_level=False
            )
            _state.listener.start()

        if not _state._atexit_registered:
            atexit.register(shutdown)
            _state._atexit_registered = True

        _state.initialized = True

    # Retention after unlock (daemon thread; runs once per process).
    _state.retention_thread = threading.Thread(
        target=_safe_retention, name="dosping-log-retention", daemon=True
    )
    _state.retention_thread.start()


def _apply_config_locked(cfg: Any) -> None:
    """Copy advanced.logging.* values into _state (lock held)."""
    try:
        _state.enabled = bool(cfg.get("advanced.logging.enabled", True))
        level = str(cfg.get("advanced.logging.level", "normal")).lower()
        _state.level = level if level in _CONFIG_LEVELS else "normal"
        _state.retention_days = int(cfg.get("advanced.logging.retention_days", 30))
        _state.max_total_mb = int(cfg.get("advanced.logging.max_total_mb", 50))
        _state.max_file_mb = int(cfg.get("advanced.logging.max_file_mb", 5))
    except Exception:
        pass
    if _state.handler is not None:
        _state.handler.max_file_bytes = max(1, _state.max_file_mb) * 1024 * 1024


def reconfigure(cfg: Any) -> None:
    """Hot-apply enabled/level (called after settings save)."""
    with _state._lock:
        was_enabled = _state.enabled
        _apply_config_locked(cfg)
        if _state.enabled and not was_enabled and _state.listener is None:
            # Turning logging on from off: build the writer lazily.
            os.makedirs(_state.log_dir, exist_ok=True)
            _state.queue = queue.SimpleQueue()
            qh = logging.handlers.QueueHandler(_state.queue)
            qh.setLevel(logging.DEBUG)
            root = logging.Logger("dosping.eventlog.re", level=logging.DEBUG)
            root.addHandler(qh)
            root.propagate = False
            _state.handler = _DailyFileHandler(_state.log_dir, _state.max_file_mb)
            _state.listener = logging.handlers.QueueListener(
                _state.queue, _state.handler, respect_handler_level=False
            )
            _state.listener.start()


def shutdown() -> None:
    """Drain the queue, stop the listener, close the file."""
    with _state._lock:
        listener = _state.listener
        handler = _state.handler
        _state.listener = None
        _state.handler = None
    if listener is not None:
        try:
            listener.stop()
        except Exception:
            pass
    if handler is not None:
        try:
            handler.close()
        except Exception:
            pass


# ── Public logging API ───────────────────────────────────────

def log_event(category: str, event: str, *, level: str = "info",
              session: Optional[str] = None, **fields: Any) -> None:
    """Log one structured event.  Non-blocking; cheap when gated."""
    if not _state.enabled or not _state.initialized:
        return
    if not _passes_gate(category, event, level):
        return
    lvl = level if level in _LEVEL_RANK else "info"
    ts = datetime.datetime.now()
    line = _render_line(ts, lvl, category, session or "-", event, fields)
    q = _state.queue
    if q is not None:
        # QueueListener re-dispatches LogRecords to handlers, so wrap the
        # pre-rendered line in a minimal record; getMessage() returns it.
        rec = logging.LogRecord(
            "dosping.event", logging.INFO, __file__, 0, line, None, None
        )
        q.put(rec)


def log_error(component: str, context: str, exc: BaseException, *,
              session: Optional[str] = None) -> None:
    """Log a caught exception (bypasses the level gate, respects master toggle)."""
    if not _state.enabled or not _state.initialized:
        return
    tb = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    tb_full = traceback.format_exc().strip()
    # Compact traceback: last frame path + function.
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    tb_hint = f"{os.path.basename(frames[-1].filename)}:{frames[-1].name}" if frames else "-"
    log_event(
        "error", "error.exception", level="error", session=session,
        component=component, context=context,
        exc=type(exc).__name__,
        message=tb[:EXC_TRUNC],
        traceback=tb_hint,
    )
    del tb_full  # full traceback available in debug builds if ever needed


def log_exception(component: str, context: str, *,
                  session: Optional[str] = None) -> None:
    """Log the current exception being handled (except block helper)."""
    exc = sys.exc_info()[1]
    if exc is not None:
        log_error(component, context, exc, session=session)


# ── Path accessors ───────────────────────────────────────────

def get_log_dir() -> str:
    return _state.log_dir


def get_log_path() -> str:
    today = datetime.date.today()
    return os.path.join(
        _state.log_dir, f"{LOG_FILE_PREFIX}{today:%Y-%m-%d}{LOG_FILE_SUFFIX}"
    )


def is_enabled() -> bool:
    return _state.enabled


# ── Retention / cleanup ──────────────────────────────────────

_DATE_RE = re.compile(
    rf"^{re.escape(LOG_FILE_PREFIX)}(\d{{4}})-(\d{{2}})-(\d{{2}})"
)


def _file_date(path: str) -> Optional[datetime.date]:
    m = _DATE_RE.match(os.path.basename(path))
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _safe_retention() -> None:
    try:
        run_retention()
    except Exception:
        pass


def run_retention(force_all: bool = False) -> tuple[int, int]:
    """Apply age + size retention to the logs folder.

    Returns (files_deleted, bytes_freed).  Never deletes today's
    active file.  force_all=True deletes everything except today's
    file (manual Clear All Logs).
    """
    log_dir = _state.log_dir
    if not log_dir or not os.path.isdir(log_dir):
        return (0, 0)

    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=max(0, _state.retention_days))
    today_path = os.path.normcase(os.path.abspath(get_log_path()))

    entries: list[tuple[datetime.date, str, int]] = []
    try:
        names = os.listdir(log_dir)
    except OSError:
        return (0, 0)
    for name in names:
        if not name.startswith(LOG_FILE_PREFIX) or LOG_FILE_SUFFIX not in name:
            continue
        path = os.path.join(log_dir, name)
        if os.path.normcase(os.path.abspath(path)) == today_path:
            continue  # never touch today's active file
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        fdate = _file_date(path)
        if fdate is None:
            try:
                fdate = datetime.date.fromtimestamp(os.path.getmtime(path))
            except OSError:
                continue
        entries.append((fdate, path, size))

    deleted = 0
    freed = 0

    def _delete(path: str, size: int) -> None:
        nonlocal deleted, freed
        try:
            os.remove(path)
            deleted += 1
            freed += size
        except OSError:
            # Windows: file locked by another process — skip, retry next run.
            pass

    # Age pass
    if force_all:
        for _d, path, size in list(entries):
            _delete(path, size)
            entries = [(d, p, s) for (d, p, s) in entries if p != path]
    elif _state.retention_days > 0:
        keep: list[tuple[datetime.date, str, int]] = []
        for fdate, path, size in entries:
            if fdate < cutoff:
                _delete(path, size)
            else:
                keep.append((fdate, path, size))
        entries = keep

    # Size pass (oldest first)
    if _state.max_total_mb > 0:
        cap = _state.max_total_mb * 1024 * 1024
        entries.sort(key=lambda e: e[0])
        total = sum(s for _d, _p, s in entries)
        idx = 0
        while total > cap and idx < len(entries):
            _d, path, size = entries[idx]
            _delete(path, size)
            total -= size
            idx += 1

    if deleted and _state.enabled and _state.initialized and _state.queue is not None:
        log_event("ui", "ui.logs_cleanup", deleted=deleted, freed=_fmt_bytes(freed))
    return (deleted, freed)


# ── Open folder helper ───────────────────────────────────────

def open_logs_folder() -> bool:
    """Open the logs folder in the OS file manager.  Returns success."""
    log_dir = _state.log_dir
    if not log_dir or not os.path.isdir(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(log_dir)  # type: ignore[attr-defined]  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", log_dir])
        else:
            subprocess.Popen(["xdg-open", log_dir])
        return True
    except Exception:
        return False
