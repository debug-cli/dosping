# ═══════════════════════════════════════════════════════════════
#  settings.py  —  DOSping v3.7.1 "Code Red" Settings Editor
# ═══════════════════════════════════════════════════════════════
#  Run directly:   python settings.py
#  In-app:         Settings modal → Advanced → "Open…"
#                  (same editor pushed as a screen inside dosping.py)
#
#  Two levels:
#    BASIC     — theme, attacker, scanner, presets, UI
#    ADVANCED  — engine tuning, logging, safety, sessions, network
#
#  Every change shows a confirmation toast.  Dangerous actions
#  (reset section / reset all / delete preset) ask first.
#  Theme changes restyle this editor LIVE (no restart needed).
#
#  Keys:  ↑/↓ navigate · Enter edit · ESC save & exit
#         Tab next field · Ctrl+D discard & exit
#         Ctrl+A advanced/basic toggle
#
#  FOR PENETRATION TESTING / EDUCATIONAL PURPOSES ONLY.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Static

import eventlog
import updater

from config import (
    APP_CODENAME,
    APP_DOCS,
    APP_NAME,
    APP_REPO,
    APP_VERSION,
    CONN_DELAY_MAX,
    DEFAULT_PRESET,
    DISCLAIMER,
    LOG_LEVELS,
    LOG_LINES_MAX,
    LOG_LINES_MIN,
    LOG_MAX_TOTAL_CHOICES,
    LOG_RETENTION_CHOICES,
    SOCK_TIMEOUT_MAX,
    SOCK_TIMEOUT_MIN,
    THREADS_MAX,
    UPDATE_CHANNELS,
    get_config,
    valid_cidr,
    valid_hostname,
    valid_ip,
    valid_port_spec,
)
from theme import THEME, apply_live, css_vars, rebuild_from_config, theme_palettes

DISCALIMER_TEXT = f"[$muted]{DISCLAIMER}[/]"

ACCENT_CHOICES = ["#ff3333", "#ff5544", "#c02020", "#ffffff", "#ff8888"]
SPEED_CHOICES = ["slow", "normal", "fast"]
THEME_CHOICES = ["monochrome-red", "monochrome"]
METHOD_CHOICES = ["tcp-flood", "slowloris"]
SCANMODE_CHOICES = ["host", "network"]


class SectionTitle(Static):
    DEFAULT_CSS = """
    SectionTitle {
        width: 100%;
        height: 1;
        margin-top: 1;
        padding: 0 1;
        background: $bar-bg;
        color: $accent;
        text-style: bold;
    }
    """


class FieldLabel(Static):
    DEFAULT_CSS = """
    FieldLabel {
        width: 26;
        height: 3;
        content-align: left middle;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self, label: str, hint: str = "") -> None:
        super().__init__(f"{label}\n[dim]{hint}[/]" if hint else label, markup=True)


class ConfirmDialog(ModalScreen[bool]):
    """Yes/No confirmation for dangerous settings actions."""

    BINDINGS = [
        Binding("escape,left", "no", "No"),
        Binding("right", "focus_yes", "→", show=False),
    ]

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
        background: $bar-bg 80%;
    }

    #confirm-box {
        width: 56;
        height: auto;
        padding: 1 2;
        border: heavy $accent-dim;
        background: $bar-bg;
    }

    #confirm-msg {
        width: 100%;
        margin-bottom: 1;
        color: $text;
    }

    #confirm-btns {
        height: auto;
        align-horizontal: right;
    }

    #confirm-btns Button {
        margin-left: 1;
        min-width: 12;
        background: $bar-bg;
        border: tall $border-dim;
        color: $text;
    }

    #confirm-yes {
        border: tall $accent-dim;
        color: $accent-bright;
    }
    """

    def __init__(self, message: str, danger: bool = True) -> None:
        super().__init__()
        self._msg = message
        self._danger = danger

    def compose(self) -> ComposeResult:
        prefix = "$accent" if self._danger else "$text"
        with Vertical(id="confirm-box"):
            yield Static(
                f"[bold {prefix}]{'⚠ ' if self._danger else ''}{self._msg}[/]",
                id="confirm-msg",
                markup=True,
            )
            with Horizontal(id="confirm-btns"):
                yield Button("Cancel", id="confirm-no")
                yield Button("Confirm", id="confirm-yes")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_no(self) -> None:
        self.dismiss(False)

    def action_focus_yes(self) -> None:
        self.query_one("#confirm-yes", Button).focus()


class SettingsScreen(Screen):
    """Full configuration editor — pushed inside dosping.py or hosted
    standalone by :class:`SettingsApp`.  Dismisses with "saved" or
    "discarded"."""

    BINDINGS = [
        Binding("escape", "cancel", "Save & Exit"),
        # NOTE: Ctrl+Q is Textual's app-level quit binding, so discard
        # lives on Ctrl+D instead (works embedded and standalone).
        Binding("ctrl+d", "discard", "Discard", priority=True),
        Binding("ctrl+a", "toggle_advanced", "Advanced"),
        Binding("down", "focus_next", "Next field", show=False),
        Binding("up", "focus_prev", "Previous field", show=False),
    ]

    DEFAULT_CSS = """
    SettingsScreen {
        background: $bg;
    }

    #scroll {
        width: 100%;
        height: 1fr;
        padding: 1 2 0 2;
        align-horizontal: center;
    }

    /* height:auto is REQUIRED: a plain Vertical defaults to 1fr and
       would collapse to the viewport, leaving nothing to scroll. */
    #editor {
        width: 78;
        height: auto;
    }

    .row {
        width: 100%;
        height: auto;
    }

    Input {
        width: 1fr;
        background: $bar-bg;
        border: tall $border-faint;
        color: $text-bright;
    }

    Input:focus {
        border: tall $accent;
    }

    .choice-btn {
        width: 28;
        background: $bar-bg;
        border: tall $border-faint;
        color: $text;
    }

    .choice-btn:hover,
    .choice-btn:focus {
        border: tall $accent;
        color: $accent-bright;
    }

    .adv-only {
        display: none;
    }

    .show-advanced .adv-only {
        display: block;
    }

    .action-btn {
        width: 24;
        margin-right: 1;
        background: $bar-bg;
        border: tall $border-dim;
        color: $accent;
    }

    .action-btn:hover,
    .action-btn:focus {
        border: tall $accent;
        color: $text-bright;
    }

    .danger-btn {
        width: 28;
        margin-right: 1;
        background: $bar-bg;
        border: tall $accent-dim;
        color: $accent-bright;
    }

    .danger-btn:hover,
    .danger-btn:focus {
        border: tall $accent;
        color: $text-bright;
    }

    #about-box {
        display: none;
        height: auto;
        margin-top: 1;
        padding: 1 2;
        border: tall $border-faint;
        color: $dim;
    }

    #about-box.show-about {
        display: block;
    }

    #about-box .about-title {
        color: $accent;
        text-style: bold;
    }

    #about-box .about-link {
        color: $text;
    }

    #disclaimer {
        margin-top: 1;
        color: $muted;
        text-style: dim;
    }

    #hint-bar {
        dock: bottom;
        width: 100%;
        height: 1;
        padding: 0 2;
        background: $bar-bg;
        color: $dim;
    }

    #hint-bar .key {
        color: $accent;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cfg = get_config()
        # Cycle-button state: button-id -> current value
        self._choices: dict[str, Any] = {}
        self._advanced = False

    # ── Composition ──────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="scroll"):
            with Vertical(id="editor") as editor:
                if self._advanced:
                    editor.add_class("show-advanced")
                yield Static(
                    f"[bold $accent]{APP_NAME} Settings[/] "
                    f"[$dim]— v{APP_VERSION} “{APP_CODENAME}” · config.json[/]",
                    markup=True,
                )
                yield Button(
                    "⚙ Advanced Settings" if not self._advanced else "← Basic Settings",
                    id="btn-toggle-advanced",
                    classes="action-btn",
                )

                # ── Theme ────────────────────────────────────
                yield SectionTitle("── THEME ─────────────────")
                with Horizontal(classes="row"):
                    yield FieldLabel("Theme Name")
                    yield self._choice_btn("theme-name", THEME_CHOICES, self.cfg.get("theme.name"))
                with Horizontal(classes="row"):
                    yield FieldLabel("Accent Colour", "applies live")
                    yield self._choice_btn("theme-accent", ACCENT_CHOICES, self.cfg.get("theme.accent"))
                with Horizontal(classes="row"):
                    yield FieldLabel("Transparent BG", "blur-ready terminals")
                    yield self._choice_btn(
                        "theme-transparent",
                        [("on", True), ("off", False)],
                        self.cfg.get("theme.transparent_background"),
                    )

                # ── Attacker ─────────────────────────────────
                yield SectionTitle("── ATTACKER DEFAULTS ─────")
                with Horizontal(classes="row"):
                    yield FieldLabel("Target IP", "default target")
                    yield Input(
                        value=self.cfg.get("attacker.target_ip", ""),
                        placeholder="192.0.0.1",
                        id="in-attacker-ip",
                    )
                with Horizontal(classes="row"):
                    yield FieldLabel("Attack Method")
                    yield self._choice_btn("attacker-method", METHOD_CHOICES, self.cfg.get("attacker.attack_method"))
                with Horizontal(classes="row"):
                    yield FieldLabel("Threads", f"1–{THREADS_MAX}")
                    yield Input(value=str(self.cfg.get("attacker.threads", 200)), placeholder="200", id="in-attacker-threads")
                with Horizontal(classes="row"):
                    yield FieldLabel("Packet Size", "bytes, 8–8192")
                    yield Input(value=str(self.cfg.get("attacker.packet_size", 512)), placeholder="512", id="in-attacker-packet")

                # ── Scanner ──────────────────────────────────
                yield SectionTitle("── SCANNER DEFAULTS ──────")
                with Horizontal(classes="row"):
                    yield FieldLabel("Scan Mode")
                    yield self._choice_btn("scanner-mode", SCANMODE_CHOICES, self.cfg.get("scanner.scan_mode"))
                with Horizontal(classes="row"):
                    yield FieldLabel("Target", "IP / hostname / CIDR")
                    yield Input(value=self.cfg.get("scanner.target", ""), placeholder="192.168.1.1", id="in-scanner-target")
                with Horizontal(classes="row"):
                    yield FieldLabel("Ports", "e.g. 80,443 or 1-1024")
                    yield Input(value=self.cfg.get("scanner.ports", ""), placeholder="21,22,80,443,554", id="in-scanner-ports")
                with Horizontal(classes="row"):
                    yield FieldLabel("Connect Timeout", "seconds, 0.05–10")
                    yield Input(value=str(self.cfg.get("scanner.connect_timeout", 0.75)), placeholder="0.75", id="in-scanner-timeout")
                with Horizontal(classes="row"):
                    yield FieldLabel("Banner Timeout", "seconds, 0.05–10")
                    yield Input(value=str(self.cfg.get("scanner.banner_timeout", 0.45)), placeholder="0.45", id="in-scanner-banner")
                with Horizontal(classes="row"):
                    yield FieldLabel("Concurrency Slots", "1–2048")
                    yield Input(value=str(self.cfg.get("scanner.concurrency", 128)), placeholder="128", id="in-scanner-slots")

                # ── Presets ──────────────────────────────────
                yield SectionTitle("── STRENGTH PRESETS ──────")
                with Horizontal(classes="row"):
                    yield FieldLabel("Active Preset")
                    yield self._choice_btn("preset-select", self.cfg.all_preset_names(), self.cfg.get("presets.active"))
                with Horizontal(classes="row"):
                    yield FieldLabel("")
                    yield Button("⤓ Apply Preset", id="btn-apply-preset", classes="action-btn")
                    yield Button("✕ Delete Custom", id="btn-del-preset", classes="action-btn")
                with Horizontal(classes="row"):
                    yield FieldLabel("New Custom Preset", "name, then save")
                    yield Input(placeholder="my-preset", id="in-preset-name")
                with Horizontal(classes="row"):
                    yield FieldLabel("")
                    yield Button("✚ Save Custom From Current", id="btn-add-preset", classes="action-btn")

                # ── UI ───────────────────────────────────────
                yield SectionTitle("── UI PREFERENCES ────────")
                with Horizontal(classes="row"):
                    yield FieldLabel("Animation Speed")
                    yield self._choice_btn("ui-speed", SPEED_CHOICES, self.cfg.get("ui.animation_speed"))
                with Horizontal(classes="row"):
                    yield FieldLabel("ASCII Effects", "glitch animations")
                    yield self._choice_btn("ui-ascii", [("on", True), ("off", False)], self.cfg.get("ui.ascii_effects"))

                # ══ ADVANCED ═════════════════════════════════
                # ── Attack engine ────────────────────────────
                yield SectionTitle("── ADVANCED · ATTACK ENGINE ─", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Connect Timeout", f"socket timeout, {SOCK_TIMEOUT_MIN}–{SOCK_TIMEOUT_MAX} s")
                    yield Input(value=str(self.cfg.get("advanced.connect_timeout", 3.0)), placeholder="3.0", id="in-adv-connect-timeout")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Connection Delay", f"pause per bot launch, 0–{CONN_DELAY_MAX} s")
                    yield Input(value=str(self.cfg.get("advanced.conn_delay", 0.0)), placeholder="0.0", id="in-adv-conn-delay")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Reuse Payload", "one payload per run (faster)")
                    yield self._choice_btn("adv-reuse-payload", [("on", True), ("off", False)], self.cfg.get("advanced.reuse_payload"))
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Log Interval", "progress line every N conns")
                    yield Input(value=str(self.cfg.get("advanced.log_interval", 25)), placeholder="25", id="in-adv-log-interval")

                # ── Scanner engine ───────────────────────────
                yield SectionTitle("── ADVANCED · SCANNER ENGINE ─", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Banner Grab", "read protocol banner")
                    yield self._choice_btn("adv-banner-grab", [("on", True), ("off", False)], self.cfg.get("advanced.banner_grab"))

                # ── Logging ──────────────────────────────
                yield SectionTitle("── ADVANCED · LOGGING ─────", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Log To Disk", "event log file (logs/)")
                    yield self._choice_btn("adv-log-enabled", [("on", True), ("off", False)], self.cfg.get("advanced.logging.enabled", True))
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Verbosity", "event log detail level")
                    yield self._choice_btn("adv-log-level", [(lv, lv) for lv in LOG_LEVELS], self.cfg.get("advanced.logging.level", "normal"))
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Delete Logs After", "auto-cleanup at startup")
                    yield self._choice_btn(
                        "adv-log-retention",
                        [("never", 0)] + [(f"{d}d", d) for d in LOG_RETENTION_CHOICES if d],
                        self.cfg.get("advanced.logging.retention_days", 30),
                    )
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Max Log Storage", "cap on the logs/ folder")
                    yield self._choice_btn(
                        "adv-log-maxtotal",
                        [("unlimited", 0)] + [(f"{mb} MB", mb) for mb in LOG_MAX_TOTAL_CHOICES if mb],
                        self.cfg.get("advanced.logging.max_total_mb", 50),
                    )
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Flood Log Lines", "in-app panel cap, 100-100000")
                    yield Input(value=str(self.cfg.get("advanced.flood_log_lines", 2000)), placeholder="2000", id="in-adv-log-lines")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Timestamped Logs", "prefix [HH:MM:SS] (in-app panel)")
                    yield self._choice_btn("adv-timestamped", [("on", True), ("off", False)], self.cfg.get("advanced.timestamped_logs"))
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("")
                    yield Button("↗ Open Logs Folder", id="btn-open-logs", classes="action-btn")
                    yield Button("✕ Clear All Logs", id="btn-clear-logs", classes="danger-btn")

                # ── Interface ────────────────────────────────
                yield SectionTitle("── ADVANCED · INTERFACE ────", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Confirm Quit", "ask before quitting")
                    yield self._choice_btn("adv-confirm-quit", [("on", True), ("off", False)], self.cfg.get("advanced.confirm_quit"))
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Confirm Dangerous", "guard destructive actions")
                    yield self._choice_btn("adv-confirm-danger", [("on", True), ("off", False)], self.cfg.get("advanced.confirm_danger"))
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Toasts", "change confirmations")
                    yield self._choice_btn("adv-toasts", [("on", True), ("off", False)], self.cfg.get("advanced.toasts"))

                # ── Sessions ─────────────────────────────────
                yield SectionTitle("── ADVANCED · SESSIONS ─────", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Max Tabs", "concurrent sessions, 1–8")
                    yield Input(value=str(self.cfg.get("advanced.max_tabs", 4)), placeholder="4", id="in-adv-max-tabs")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Auto-start Session", "open setup modal immediately")
                    yield self._choice_btn("adv-auto-start", [("on", True), ("off", False)], self.cfg.get("advanced.auto_start_session"))

                # ── Network helpers ──────────────────────────
                yield SectionTitle("── ADVANCED · NETWORK ──────", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("GeoIP Lookup", "IT-mode panel")
                    yield self._choice_btn("adv-geoip", [("on", True), ("off", False)], self.cfg.get("advanced.geoip_lookup"))
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("GeoIP Timeout", f"HTTP timeout, {SOCK_TIMEOUT_MIN}–{SOCK_TIMEOUT_MAX} s")
                    yield Input(value=str(self.cfg.get("advanced.geoip_timeout", 3.0)), placeholder="3.0", id="in-adv-geoip-timeout")

                # ── Safety ───────────────────────────────────
                yield SectionTitle("── ADVANCED · SAFETY ───────", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Block Private Targets", "refuse loopback/RFC1918")
                    yield self._choice_btn("adv-block-private", [("on", True), ("off", False)], self.cfg.get("advanced.block_private_targets"))

                # ── Updates (v3.8.0) ─────────────────────────
                yield SectionTitle("── ADVANCED · UPDATES ──────", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Update Channel", "stable or dev")
                    yield self._choice_btn(
                        "adv-update-channel",
                        [(c, c) for c in UPDATE_CHANNELS],
                        self.cfg.get("advanced.update.channel", "stable"),
                    )
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Auto-Check on Launch", "non-blocking, never auto-applies")
                    yield self._choice_btn("adv-update-autocheck", [("on", True), ("off", False)], self.cfg.get("advanced.update.auto_check", True))
                with Horizontal(classes="row adv-only"):
                    yield Button("Check Now", id="btn-check-updates", classes="action-btn")
                    yield Button("Update Now", id="btn-apply-update", classes="action-btn")
                yield Static(self._update_status_text(), id="update-status", classes="adv-only")

                # ── Danger zone ──────────────────────────────
                yield SectionTitle("── ADVANCED · DANGER ZONE ──", classes="adv-only")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Reset advanced settings", "back to defaults")
                    yield Button("Reset Advanced", id="btn-reset-advanced", classes="danger-btn")
                with Horizontal(classes="row adv-only"):
                    yield FieldLabel("Reset EVERYTHING", "keeps custom presets")
                    yield Button("Factory Reset", id="btn-reset-all", classes="danger-btn")

                # ── About ────────────────────────────────────
                yield Button("ℹ About", id="btn-about", classes="action-btn")
                with Vertical(id="about-box"):
                    yield Static(
                        "[bold $accent]About[/]",
                        classes="about-title",
                        markup=True,
                    )
                    yield Static(
                        f"{APP_NAME} v{APP_VERSION} {APP_CODENAME}\n"
                        f"Repo: [$text]{APP_REPO}[/]\n"
                        f"Docs: [$text]{APP_DOCS}[/]\n"
                        f"Update channel: {self.cfg.get('advanced.update.channel', 'stable')}\n"
                        f"Python: 3.12+  ·  Framework: Textual + asyncio\n"
                        f"Config file: config.json (same folder as dosping.py)\n"
                        f"Log file: {eventlog.get_log_path() or 'logs/ (logging off)'}",
                        classes="about-link",
                        markup=True,
                    )

                # Subtle greyed disclaimer (same text as README top).
                yield Static(DISCALIMER_TEXT, id="disclaimer", markup=True)

        yield Static(
            "[$accent]↑/↓[/] navigate   [$accent]Enter[/] edit   "
            "[$accent]Tab[/] next field   [$accent]Ctrl+A[/] "
            f"{'basic' if self._advanced else 'advanced'}   "
            "[$accent]ESC[/] save & exit   [$accent]Ctrl+D[/] discard",
            id="hint-bar",
            markup=True,
        )

    # ── Standalone hosting (python settings.py) ──────────────

    def _dismiss(self, result: str) -> None:
        # Always pop the screen; the host's push callback handles the rest
        # (SettingsApp exits the app, dosping.py resumes and re-syncs).
        self.dismiss(result)

    def action_cancel(self) -> None:
        """ESC — save & close."""
        data, errors = self._validate_and_collect()
        if errors:
            self.notify(errors[0], severity="error", timeout=6)
            return
        self._log_setting_changes(data)
        for dotted, value in data.items():
            self.cfg.set(dotted, value)
        if self.cfg.save():
            # Hot-apply event-log settings (master toggle / verbosity / caps).
            try:
                eventlog.reconfigure(self.cfg)
            except Exception:
                pass
            rebuild_from_config(self.cfg)
            apply_live(self.app)
            self._dismiss("saved")
        else:
            self.notify("Could not write config.json", severity="error")

    def action_discard(self) -> None:
        """Ctrl+D — discard & close (revert any live-applied theme)."""
        self.cfg.reload()
        rebuild_from_config(self.cfg)
        apply_live(self.app)
        eventlog.log_event(
            "settings", "settings.editor_discarded", source="UI:settings-editor"
        )
        self._dismiss("discarded")

    def _log_setting_changes(self, data: dict[str, Any]) -> None:
        """Emit settings.changed (old → new) for every edited value."""
        for dotted, new in data.items():
            try:
                old = self.cfg.get(dotted)
            except Exception:
                continue
            if old != new:
                eventlog.log_event(
                    "settings", "settings.changed",
                    key=dotted, old=old, new=new,
                    source="UI:settings-editor",
                )

    # ── Toasts & confirmations ───────────────────────────────

    def _toast(self, message: str, severity: str = "information") -> None:
        """Notify only when toasts are enabled (info toasts only)."""
        if severity == "information":
            try:
                if not self.cfg.get("advanced.toasts", True):
                    return
            except Exception:
                pass
        self.app.notify(message, severity=severity, timeout=4)

    async def _confirm(self, message: str) -> bool:
        """Ask yes/no — skipped when confirm_danger is off."""
        if not self.cfg.get("advanced.confirm_danger", True):
            return True
        return await self.app.push_screen(ConfirmDialog(message), wait_for_dismiss=True)

    # ── Live theming ─────────────────────────────────────────

    def _apply_theme_now(self, accent: Optional[str] = None) -> None:
        """Persist theme choices and restyle this editor immediately."""
        if accent is not None:
            self.cfg.set("theme.accent", accent)
            # Keep the Accent Colour cycle-button in sync so a later
            # ESC-save doesn't overwrite the live accent with a stale one.
            entry = self._choices.get("theme-accent")
            if entry:
                values = [o[1] if isinstance(o, tuple) else o for o in entry["options"]]
                if accent in values:
                    entry["index"] = values.index(accent)
                else:
                    # Theme signature colours may not be in the choice list.
                    entry["options"].append((accent, accent))
                    entry["index"] = len(entry["options"]) - 1
                entry["dirty"] = True  # this button now mirrors the live value
                self.query_one("#btn-theme-accent", Button).label = accent
        for key, bid in (
            ("theme.name", "theme-name"),
            ("theme.transparent_background", "theme-transparent"),
        ):
            entry = self._choices.get(bid)
            if entry and entry.get("dirty"):
                opt = entry["options"][entry["index"]]
                self.cfg.set(key, opt[1] if isinstance(opt, tuple) else opt)
        rebuild_from_config(self.cfg)
        apply_live(self.app)

    # ── Focus navigation (↑/↓) ───────────────────────────────

    def action_focus_next(self) -> None:
        self._move_focus(1)

    def action_focus_prev(self) -> None:
        self._move_focus(-1)

    def _move_focus(self, direction: int) -> None:
        focusables = [w for w in self.query("Input, Button") if w.focusable]
        if not focusables:
            return
        try:
            idx = focusables.index(self.focused)
        except ValueError:
            idx = -1 if direction > 0 else 0
        nxt = focusables[(idx + direction) % len(focusables)]
        nxt.focus()

    # ── Advanced toggle ──────────────────────────────────────

    def action_toggle_advanced(self) -> None:
        self._advanced = not self._advanced
        editor = self.query_one("#editor")
        btn = self.query_one("#btn-toggle-advanced", Button)
        if self._advanced:
            editor.add_class("show-advanced")
            btn.label = "← Basic Settings"
            self._toast("Advanced settings shown")
        else:
            editor.remove_class("show-advanced")
            btn.label = "⚙ Advanced Settings"
            self._toast("Basic settings shown")
        self.app.refresh_css()

    def action_about(self) -> None:
        box = self.query_one("#about-box")
        if box.has_class("show-about"):
            box.remove_class("show-about")
        else:
            box.add_class("show-about")
        self.app.refresh_css()

    # ── Interactions ─────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "").removeprefix("btn-")

        if bid == "toggle-advanced":
            self.action_toggle_advanced()
            return
        if bid == "about":
            self.action_about()
            return
        if bid == "open-logs":
            ok = eventlog.open_logs_folder()
            eventlog.log_event(
                "ui", "ui.logs_folder_opened", source="UI:settings-editor", success=ok
            )
            self._toast(
                "Logs folder opened" if ok else "Could not open logs folder",
                severity="information" if ok else "error",
            )
            return
        if bid == "clear-logs":
            self.run_worker(self._clear_all_logs())
            return

        # Cycle buttons
        if bid in self._choices:
            entry = self._choices[bid]
            entry["index"] = (entry["index"] + 1) % len(entry["options"])
            entry["dirty"] = True  # user actually changed this control
            opt = entry["options"][entry["index"]]
            label = opt[0] if isinstance(opt, tuple) else str(opt)
            value = opt[1] if isinstance(opt, tuple) else opt
            event.button.label = label
            # Theme changes restyle the editor LIVE.
            if bid == "theme-name":
                # Switching themes resets the accent to its signature colour
                # (customize afterwards via Accent Colour).
                default_accent = theme_palettes().get(value, ("#ff3333",))[0]
                self._apply_theme_now(accent=default_accent)
                self._toast(f"Theme: {label} (live)")
            elif bid == "theme-accent":
                self._apply_theme_now(accent=value)
                self._toast(f"Accent colour {value} (live)")
            elif bid == "theme-transparent":
                self._apply_theme_now()
                self._toast(f"Transparent background: {'on' if value else 'off'} (live)")
            else:
                self._toast(f"{bid.removeprefix('adv-').replace('-', ' ').title()}: {label}")
            return

        if bid == "apply-preset":
            self.run_worker(self._apply_preset())
        elif bid == "add-preset":
            self.run_worker(self._save_custom_preset())
        elif bid == "del-preset":
            self.run_worker(self._delete_custom_preset())
        elif bid == "reset-advanced":
            self.run_worker(self._reset_advanced())
        elif bid == "reset-all":
            self.run_worker(self._reset_all())
        elif bid == "check-updates":
            self.run_worker(self._check_updates())
        elif bid == "apply-update":
            self.run_worker(self._apply_update())

    # ── Updates (v3.8.0) ─────────────────────────────────────

    def _update_status_text(self) -> str:
        channel = self.cfg.get("advanced.update.channel", "stable")
        last = self.cfg.get("advanced.update.last_checked", "") or "never"
        status = self.cfg.get("advanced.update.last_check_status", "") or "unknown"
        return f"Channel: {channel} · Last checked: {last} ({status})"

    def _refresh_update_status_line(self) -> None:
        try:
            self.query_one("#update-status", Static).update(self._update_status_text())
        except Exception:
            pass

    async def _check_updates(self) -> None:
        channel = self.cfg.get("advanced.update.channel", "stable")
        result = await asyncio.to_thread(
            updater.check_for_update, updater.repo_dir(), channel, APP_VERSION,
        )
        status = "error" if result.error else (
            "update_available" if result.update_available else "up_to_date"
        )
        self.cfg.set("advanced.update.last_checked", datetime.now().isoformat(timespec="seconds"))
        self.cfg.set("advanced.update.last_check_status", status)
        self.cfg.save()
        eventlog.log_event(
            "update", "update.check_result", channel=channel,
            current_version=APP_VERSION, remote_version=result.remote_version or "",
            available=result.update_available, error=result.error or "",
            source="UI:settings-editor",
        )
        if result.error:
            self._toast(f"Update check failed: {result.error}", severity="error")
        elif result.update_available:
            self._toast(f"Update available: {result.remote_version}", severity="warning")
        else:
            self._toast("Already up to date")
        self._refresh_update_status_line()

    async def _apply_update(self) -> None:
        channel = self.cfg.get("advanced.update.channel", "stable")
        if not await self._confirm(
            "Apply the latest update? You'll need to restart DOSping afterward."
        ):
            self._toast("Update cancelled")
            return
        result = await asyncio.to_thread(updater.apply_update, updater.repo_dir(), channel)
        eventlog.log_event(
            "update", "update.apply_result", channel=channel,
            success=result.success, new_version=result.new_version or "",
            error=result.error or "", source="UI:settings-editor",
        )
        if result.success:
            self._toast(
                f"Updated to {result.new_version or 'latest'} — restart DOSping to use it",
                severity="warning",
            )
        else:
            self._toast(f"Update failed: {result.error}", severity="error")

    def _choice_btn(self, btn_id: str, options: list, current: Any) -> Button:
        """Build a cycling button; store (options, value) for later."""
        options = list(options)
        values = [opt[1] if isinstance(opt, tuple) else opt for opt in options]
        try:
            idx = values.index(current)
        except ValueError:
            # The live config value isn't among the presets (e.g. a custom
            # accent set from dosping's quick panel).  Append it as an extra
            # option instead of falling back to index 0 — otherwise every
            # ESC-save would overwrite the real value with the stale one.
            options.append((str(current), current))
            idx = len(options) - 1
        self._choices[btn_id] = {
            "options": options,
            "index": idx,
            "dirty": False,  # set True when the user actually cycles
        }
        label = options[idx][0] if isinstance(options[idx], tuple) else str(options[idx])
        return Button(label, id=f"btn-{btn_id}", classes="choice-btn")

    def _current_preset(self) -> str:
        entry = self._choices.get("preset-select")
        if not entry:
            return DEFAULT_PRESET
        if not entry.get("dirty"):
            # Not cycled: keep whatever config says (may be a custom preset
            # name not present in this editor instance's option list).
            return str(self.cfg.get("presets.active", DEFAULT_PRESET))
        return entry["options"][entry["index"]][1]

    async def _apply_preset(self) -> None:
        name = self._current_preset()
        if self.cfg.apply_preset(name):
            eventlog.log_event(
                "settings", "settings.preset_applied", preset=name,
                source="UI:settings-editor",
            )
            self._reload_inputs()
            self._toast(f"Preset '{name}' applied to attacker/scanner")
        else:
            self._toast(f"Preset '{name}' not found", severity="error")

    async def _save_custom_preset(self) -> None:
        name_input = self.query_one("#in-preset-name", Input)
        name = name_input.value.strip()
        if not name:
            self._toast("Enter a preset name first", severity="warning")
            name_input.focus()
            return
        if self.cfg.set_preset(
            name,
            {
                "attacker_threads": self._int_input("in-attacker-threads", 200),
                "attacker_packet_size": self._int_input("in-attacker-packet", 512),
                "scanner_timeout": self._float_input("in-scanner-timeout", 0.75),
                "banner_timeout": self._float_input("in-scanner-banner", 0.45),
                "concurrency": self._int_input("in-scanner-slots", 128),
                "scanner_threads": self._int_input("in-scanner-slots", 256),
            },
        ):
            eventlog.log_event(
                "settings", "settings.preset_created", preset=name,
                source="UI:settings-editor",
            )
            names = self.cfg.all_preset_names()
            self._choices["preset-select"] = {"options": names, "index": names.index(name)}
            self.query_one("#btn-preset-select", Button).label = name
            self.cfg.set("presets.active", name)
            name_input.value = ""
            self._toast(f"Custom preset '{name}' saved")

    async def _delete_custom_preset(self) -> None:
        name = self._current_preset()
        if name in ("Low", "Medium", "High"):
            self._toast("Built-in presets cannot be deleted", severity="warning")
            return
        if not await self._confirm(f"Delete custom preset '{name}'?"):
            self._toast("Deletion cancelled")
            return
        if self.cfg.delete_preset(name):
            eventlog.log_event(
                "settings", "settings.preset_deleted", preset=name, confirmed=True,
                source="UI:settings-editor",
            )
            names = self.cfg.all_preset_names()
            active = self.cfg.get("presets.active", DEFAULT_PRESET)
            self._choices["preset-select"] = {"options": names, "index": names.index(active)}
            self.query_one("#btn-preset-select", Button).label = active
            self._toast(f"Custom preset '{name}' deleted")
        else:
            self._toast("Could not delete preset", severity="error")

    async def _clear_all_logs(self) -> None:
        """Danger zone: delete every saved log file except today's."""
        if not await self._confirm("Delete ALL saved log files (except today's)?"):
            self._toast("Log cleanup cancelled")
            return
        deleted, freed = eventlog.run_retention(force_all=True)
        eventlog.log_event(
            "ui", "ui.logs_cleared", deleted=deleted,
            freed=eventlog._fmt_bytes(freed), confirmed=True,
            source="UI:settings-editor",
        )
        self._toast(f"Deleted {deleted} log file(s) — {eventlog._fmt_bytes(freed)} freed", severity="warning")

    async def _reset_advanced(self) -> None:
        if not await self._confirm("Reset ALL advanced settings to defaults?"):
            self._toast("Reset cancelled")
            return
        self.cfg.reset_section("advanced")
        self.cfg.save()
        eventlog.log_event(
            "settings", "settings.reset_advanced", confirmed=True,
            source="UI:settings-editor",
        )
        self._rebuild_advanced_inputs()
        self._toast("Advanced settings restored to defaults")

    async def _reset_all(self) -> None:
        if not await self._confirm("FACTORY RESET — every setting back to defaults?"):
            self._toast("Factory reset cancelled")
            return
        self.cfg.reset_all()
        saved = self.cfg.save()
        if saved:
            eventlog.log_event(
                "settings", "settings.factory_reset", confirmed=True,
                source="UI:settings-editor",
            )
            rebuild_from_config(self.cfg)
            apply_live(self.app)
            self._reload_all_inputs()
            self._toast("Factory reset complete — config.json restored", severity="warning")
        else:
            self._toast("Reset applied but config.json could not be written", severity="error")

    def _reload_all_inputs(self) -> None:
        """Refresh every input/choice button from the (reset) config."""
        basic_inputs = {
            "in-attacker-ip": ("attacker.target_ip", ""),
            "in-attacker-threads": ("attacker.threads", "200"),
            "in-attacker-packet": ("attacker.packet_size", "512"),
            "in-scanner-target": ("scanner.target", ""),
            "in-scanner-ports": ("scanner.ports", "21,22,80,443,554"),
            "in-scanner-timeout": ("scanner.connect_timeout", "0.75"),
            "in-scanner-banner": ("scanner.banner_timeout", "0.45"),
            "in-scanner-slots": ("scanner.concurrency", "128"),
        }
        for wid, (dotted, default) in basic_inputs.items():
            try:
                self.query_one(f"#{wid}", Input).value = str(self.cfg.get(dotted) or default)
            except Exception:
                pass
        try:
            self.query_one("#in-preset-name", Input).value = ""
        except Exception:
            pass
        self._rebuild_advanced_inputs()
        self._reload_inputs()
        # Sync cycle buttons back to config values.
        choices_to_config = {
            "theme-name": "theme.name",
            "theme-accent": "theme.accent",
            "theme-transparent": "theme.transparent_background",
            "attacker-method": "attacker.attack_method",
            "scanner-mode": "scanner.scan_mode",
            "preset-select": "presets.active",
            "ui-speed": "ui.animation_speed",
            "ui-ascii": "ui.ascii_effects",
            "adv-reuse-payload": "advanced.reuse_payload",
            "adv-banner-grab": "advanced.banner_grab",
            "adv-log-enabled": "advanced.logging.enabled",
            "adv-log-level": "advanced.logging.level",
            "adv-log-retention": "advanced.logging.retention_days",
            "adv-log-maxtotal": "advanced.logging.max_total_mb",
            "adv-timestamped": "advanced.timestamped_logs",
            "adv-confirm-quit": "advanced.confirm_quit",
            "adv-confirm-danger": "advanced.confirm_danger",
            "adv-toasts": "advanced.toasts",
            "adv-auto-start": "advanced.auto_start_session",
            "adv-geoip": "advanced.geoip_lookup",
            "adv-block-private": "advanced.block_private_targets",
            "adv-update-channel": "advanced.update.channel",
            "adv-update-autocheck": "advanced.update.auto_check",
        }
        for key, dotted in choices_to_config.items():
            entry = self._choices.get(key)
            if not entry:
                continue
            values = [o[1] if isinstance(o, tuple) else o for o in entry["options"]]
            cur = self.cfg.get(dotted)
            if cur in values:
                entry["index"] = values.index(cur)
            else:
                # Custom live value (e.g. accent from dosping's quick panel):
                # append it rather than falling back to a stale default.
                entry["options"].append((str(cur), cur))
                entry["index"] = len(entry["options"]) - 1
            entry["dirty"] = False  # reset/reload makes buttons echo config
            opt = entry["options"][entry["index"]]
            try:
                self.query_one(f"#btn-{key}", Button).label = (
                    opt[0] if isinstance(opt, tuple) else str(opt)
                )
            except Exception:
                pass

    def _rebuild_advanced_inputs(self) -> None:
        mapping = {
            "in-adv-connect-timeout": "advanced.connect_timeout",
            "in-adv-conn-delay": "advanced.conn_delay",
            "in-adv-log-interval": "advanced.log_interval",
            "in-adv-log-lines": "advanced.flood_log_lines",
            "in-adv-max-tabs": "advanced.max_tabs",
            "in-adv-geoip-timeout": "advanced.geoip_timeout",
        }
        for wid, dotted in mapping.items():
            try:
                self.query_one(f"#{wid}", Input).value = str(self.cfg.get(dotted))
            except Exception:
                pass
        toggles = {
            "btn-adv-reuse-payload": "advanced.reuse_payload",
            "btn-adv-banner-grab": "advanced.banner_grab",
            "btn-adv-log-enabled": "advanced.logging.enabled",
            "btn-adv-log-level": "advanced.logging.level",
            "btn-adv-log-retention": "advanced.logging.retention_days",
            "btn-adv-log-maxtotal": "advanced.logging.max_total_mb",
            "btn-adv-timestamped": "advanced.timestamped_logs",
            "btn-adv-confirm-quit": "advanced.confirm_quit",
            "btn-adv-confirm-danger": "advanced.confirm_danger",
            "btn-adv-toasts": "advanced.toasts",
            "btn-adv-auto-start": "advanced.auto_start_session",
            "btn-adv-geoip": "advanced.geoip_lookup",
            "btn-adv-block-private": "advanced.block_private_targets",
            "btn-adv-update-channel": "advanced.update.channel",
            "btn-adv-update-autocheck": "advanced.update.auto_check",
        }
        for btn_id, dotted in toggles.items():
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                entry = self._choices.get(btn_id.removeprefix("btn-"))
                if entry:
                    values = [o[1] if isinstance(o, tuple) else o for o in entry["options"]]
                    cur = self.cfg.get(dotted)
                    entry["index"] = values.index(cur) if cur in values else 0
                    opt = entry["options"][entry["index"]]
                    btn.label = opt[0] if isinstance(opt, tuple) else str(opt)
            except Exception:
                pass

    # ── Input helpers ────────────────────────────────────────

    def _int_input(self, widget_id: str, default: int) -> int:
        raw = self.query_one(f"#{widget_id}", Input).value.strip()
        try:
            return int(float(raw))
        except ValueError:
            return default

    def _float_input(self, widget_id: str, default: float) -> float:
        raw = self.query_one(f"#{widget_id}", Input).value.strip()
        try:
            return float(raw)
        except ValueError:
            return default

    def _reload_inputs(self) -> None:
        """Push applied-preset values back into the Input widgets."""
        self.query_one("#in-attacker-threads", Input).value = str(
            self.cfg.get("attacker.threads")
        )
        self.query_one("#in-attacker-packet", Input).value = str(
            self.cfg.get("attacker.packet_size")
        )
        self.query_one("#in-scanner-timeout", Input).value = str(
            self.cfg.get("scanner.connect_timeout")
        )
        self.query_one("#in-scanner-banner", Input).value = str(
            self.cfg.get("scanner.banner_timeout")
        )
        self.query_one("#in-scanner-slots", Input).value = str(
            self.cfg.get("scanner.concurrency")
        )

    # ── Save / validation ────────────────────────────────────

    def _validate_and_collect(self) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        data: dict[str, Any] = {}

        # Theme (from cycle buttons) — untouched buttons echo the live
        # config value instead of a stale widget default.
        data["theme.name"] = self._live_opt_value("theme-name", "theme.name", "monochrome-red")
        data["theme.accent"] = self._live_opt_value("theme-accent", "theme.accent") or theme_palettes().get(
            data["theme.name"], ("#ff3333",)
        )[0]
        data["theme.transparent_background"] = self._live_opt_value(
            "theme-transparent", "theme.transparent_background", True
        )

        # Attacker
        ip = self.query_one("#in-attacker-ip", Input).value.strip()
        if ip and not valid_ip(ip):
            errors.append(f"Attacker target IP invalid: {ip}")
        data["attacker.target_ip"] = ip or "192.0.0.1"
        data["attacker.attack_method"] = self._live_opt_value(
            "attacker-method", "attacker.attack_method", "tcp-flood"
        )
        threads = self._int_input("in-attacker-threads", 200)
        if not 1 <= threads <= THREADS_MAX:
            errors.append(f"Threads must be 1–{THREADS_MAX}")
        data["attacker.threads"] = threads
        packet = self._int_input("in-attacker-packet", 512)
        if not 8 <= packet <= 8192:
            errors.append("Packet size must be 8–8192 bytes")
        data["attacker.packet_size"] = packet

        # Scanner
        data["scanner.scan_mode"] = self._live_opt_value(
            "scanner-mode", "scanner.scan_mode", "host"
        )
        target = self.query_one("#in-scanner-target", Input).value.strip()
        if target and self._opt_value("scanner-mode") == "network":
            if not valid_cidr(target):
                errors.append(f"Scanner target is not a valid CIDR: {target}")
        elif target and not (valid_ip(target) or valid_hostname(target)):
            errors.append(f"Scanner target is not a valid host: {target}")
        data["scanner.target"] = target
        ports = self.query_one("#in-scanner-ports", Input).value.strip()
        if ports and not valid_port_spec(ports):
            errors.append(f"Invalid port specification: {ports}")
        data["scanner.ports"] = ports or "21,22,80,443,554"
        cto = self._float_input("in-scanner-timeout", 0.75)
        bto = self._float_input("in-scanner-banner", 0.45)
        if not 0.05 <= cto <= 10.0:
            errors.append("Connect timeout must be 0.05–10.0 s")
        if not 0.05 <= bto <= 10.0:
            errors.append("Banner timeout must be 0.05–10.0 s")
        slots = self._int_input("in-scanner-slots", 128)
        if not 1 <= slots <= 2048:
            errors.append("Concurrency slots must be 1–2048")
        data["scanner.connect_timeout"] = cto
        data["scanner.banner_timeout"] = bto
        data["scanner.concurrency"] = slots

        # Presets + UI (untouched cycle buttons keep their config value)
        data["presets.active"] = self._current_preset()
        data["ui.animation_speed"] = self._live_opt_value("ui-speed", "ui.animation_speed", "normal")
        data["ui.ascii_effects"] = self._live_opt_value("ui-ascii", "ui.ascii_effects", True)

        # Advanced — only visible widgets hold values, but hidden ones
        # keep whatever is in config (they were saved or defaulted).
        if self._advanced:
            cta = self._float_input("in-adv-connect-timeout", 3.0)
            if not SOCK_TIMEOUT_MIN <= cta <= SOCK_TIMEOUT_MAX:
                errors.append(f"Advanced connect timeout must be {SOCK_TIMEOUT_MIN}–{SOCK_TIMEOUT_MAX} s")
            data["advanced.connect_timeout"] = cta
            cd = self._float_input("in-adv-conn-delay", 0.0)
            if not 0.0 <= cd <= CONN_DELAY_MAX:
                errors.append(f"Connection delay must be 0–{CONN_DELAY_MAX} s")
            data["advanced.conn_delay"] = cd
            li = self._int_input("in-adv-log-interval", 25)
            if not 1 <= li <= 500:
                errors.append("Log interval must be 1–500")
            data["advanced.log_interval"] = li
            fll = self._int_input("in-adv-log-lines", 2000)
            if not LOG_LINES_MIN <= fll <= LOG_LINES_MAX:
                errors.append(f"Flood log lines must be {LOG_LINES_MIN}–{LOG_LINES_MAX}")
            data["advanced.flood_log_lines"] = fll
            mt = self._int_input("in-adv-max-tabs", 4)
            if not 1 <= mt <= 8:
                errors.append("Max tabs must be 1–8")
            data["advanced.max_tabs"] = mt
            gto = self._float_input("in-adv-geoip-timeout", 3.0)
            if not SOCK_TIMEOUT_MIN <= gto <= SOCK_TIMEOUT_MAX:
                errors.append(f"GeoIP timeout must be {SOCK_TIMEOUT_MIN}–{SOCK_TIMEOUT_MAX} s")
            data["advanced.geoip_timeout"] = gto
            data["advanced.reuse_payload"] = self._live_opt_value(
                "adv-reuse-payload", "advanced.reuse_payload", True
            )
            data["advanced.banner_grab"] = self._live_opt_value(
                "adv-banner-grab", "advanced.banner_grab", True
            )
            data["advanced.timestamped_logs"] = self._live_opt_value(
                "adv-timestamped", "advanced.timestamped_logs", False
            )
            # ── Event log (advanced.logging, v3.7.1) ─────────
            data["advanced.logging.enabled"] = self._live_opt_value(
                "adv-log-enabled", "advanced.logging.enabled", True
            )
            data["advanced.logging.level"] = self._live_opt_value(
                "adv-log-level", "advanced.logging.level", "normal"
            )
            data["advanced.logging.retention_days"] = self._live_opt_value(
                "adv-log-retention", "advanced.logging.retention_days", 30
            )
            data["advanced.logging.max_total_mb"] = self._live_opt_value(
                "adv-log-maxtotal", "advanced.logging.max_total_mb", 50
            )
            data["advanced.confirm_quit"] = self._live_opt_value(
                "adv-confirm-quit", "advanced.confirm_quit", True
            )
            data["advanced.confirm_danger"] = self._live_opt_value(
                "adv-confirm-danger", "advanced.confirm_danger", True
            )
            data["advanced.toasts"] = self._live_opt_value("adv-toasts", "advanced.toasts", True)
            data["advanced.auto_start_session"] = self._live_opt_value(
                "adv-auto-start", "advanced.auto_start_session", True
            )
            data["advanced.geoip_lookup"] = self._live_opt_value(
                "adv-geoip", "advanced.geoip_lookup", True
            )
            data["advanced.block_private_targets"] = self._live_opt_value(
                "adv-block-private", "advanced.block_private_targets", False
            )
            data["advanced.update.channel"] = self._live_opt_value(
                "adv-update-channel", "advanced.update.channel", "stable"
            )
            data["advanced.update.auto_check"] = self._live_opt_value(
                "adv-update-autocheck", "advanced.update.auto_check", True
            )

        return data, errors

    def _opt_value(self, btn_id: str) -> Any:
        entry = self._choices[btn_id]
        opt = entry["options"][entry["index"]]
        return opt[1] if isinstance(opt, tuple) else opt

    def _live_opt_value(self, btn_id: str, dotted: str, default: Any = None) -> Any:
        """Cycle-button value — but only when the user actually cycled it.

        Untouched buttons fall back to the value already in config.json,
        so opening the editor and pressing ESC can never overwrite real
        settings with stale widget state (the dosping-quick-panel <->
        full-editor theme revert bug).
        """
        entry = self._choices.get(btn_id)
        if entry is not None and entry.get("dirty"):
            opt = entry["options"][entry["index"]]
            return opt[1] if isinstance(opt, tuple) else opt
        return self.cfg.get(dotted, default)


class SettingsApp(App):
    """Standalone host for :class:`SettingsScreen` (python settings.py)."""

    TITLE = f"{APP_NAME} Settings"
    SUB_TITLE = f"v{APP_VERSION} “{APP_CODENAME}” — config.json editor"

    def get_css_variables(self) -> dict[str, str]:
        return {**super().get_css_variables(), **css_vars()}

    def __init__(self) -> None:
        super().__init__()
        self._result: Any = None

    def on_mount(self) -> None:
        apply_live(self)

        def _done(result: Any) -> None:
            self._result = result
            self.exit(result=result)

        self.push_screen(SettingsScreen(), callback=_done)


def main() -> None:
    # Standalone runs get the event log too (same config as dosping.py).
    eventlog.init(get_config(), version=APP_VERSION, codename=APP_CODENAME)
    try:
        SettingsApp().run()
    finally:
        eventlog.shutdown()


if __name__ == "__main__":
    main()
