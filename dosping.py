# ═══════════════════════════════════════════════════════════════
#  dosping.py  —  DOSping v2.0 Network Stress Testing TUI
# ═══════════════════════════════════════════════════════════════
#  Cross-platform Terminal UI for network stress testing with
#  multi-tab sessions, live split-panel monitoring, command
#  palette actions, and a real-time stats sidebar.
#
#  Stack:  Python 3.12+  ·  textual  ·  rich  ·  asyncio
#
#  Layout (per tab):
#  ┌─────────────────┬──────────────────┬────────────┐
#  │ FLOOD OUTPUT     │ CONNECTIVITY     │ LIVE STATS │
#  │ (TCP flood log)  │ (ICMP + TCP)     │ conn/s     │
#  │                  │                  │ rate %     │
#  │ ProgressBar      │                  │ bytes sent │
#  │ KITT Scanner     │                  │ uptime     │
#  └─────────────────┴──────────────────┴────────────┘
#
#  Screens:
#    SplashScreen  →  SessionScreen (TabbedContent)
#                       └─ SetupModal (ModalScreen overlay)
#                       └─ TestTabPane(s) with TestPanel(s)
#
#  FOR PENETRATION TESTING / EDUCATIONAL PURPOSES ONLY.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Center
from textual.widgets import (
    Header, Footer, Static, RichLog, ProgressBar,
    Input, Button, Label, Rule, TabbedContent, TabPane,
)
from textual.screen import Screen, ModalScreen
from textual import work, on
from textual.theme import Theme
from textual.command import Provider, Hit, Hits
from rich.text import Text
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import asyncio
import platform
import socket
import random
import time
import os
import webbrowser
import subprocess
from datetime import datetime

import requests

from flooder import Flooder


# ═══════════════════════════════════════════════════════════════
#  COLOR PALETTE
# ═══════════════════════════════════════════════════════════════

CLR_BG          = "#0b0b0b"
CLR_SURFACE     = "#111110"
CLR_PANEL       = "#0e0e0c"

CLR_AMBER       = "#c8a050"
CLR_SAGE        = "#7a9a6a"
CLR_SAGE_DIM    = "#6a8a5a"
CLR_OLIVE       = "#9a8a40"
CLR_BRICK       = "#8a5a4a"

CLR_BORDER_A    = "#3a3a2a"
CLR_BORDER_B    = "#2a3a2a"
CLR_HEADER_A    = "#1e1e16"
CLR_HEADER_B    = "#141e14"
CLR_MUTED       = "#555550"
CLR_LOGO_EDGE   = "#2a2a1a"
CLR_TEXT        = "#c8c8b8"
CLR_KHAKI       = "#7a7a5a"

SPINNER_FRAMES  = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
MAX_TABS        = 4


# ═══════════════════════════════════════════════════════════════
#  THEME
# ═══════════════════════════════════════════════════════════════

THEME_DOSPING_MATRIX = Theme(
    name="dosping-matrix",
    dark=True,
    primary=CLR_AMBER,
    secondary=CLR_SAGE,
    background=CLR_BG,
    surface=CLR_SURFACE,
    panel=CLR_PANEL,
    accent=CLR_AMBER,
    success=CLR_SAGE_DIM,
    warning=CLR_OLIVE,
    error=CLR_BRICK,
)


# ═══════════════════════════════════════════════════════════════
#  ASCII ART LOGO
# ═══════════════════════════════════════════════════════════════

LOGO = (
    f"[{CLR_BORDER_A}]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▸[/]\n"
    f"[{CLR_LOGO_EDGE}]░▒▓[/]  [bold {CLR_TEXT}]____    ___   ____        _                       [/] [{CLR_LOGO_EDGE}]▓▒░[/]\n"
    f"[{CLR_LOGO_EDGE}]░▒▓[/]  [bold {CLR_TEXT}]|  _ \\  / _ \\ / ___|_ __  (_) _ __    __ _  [/] [{CLR_KHAKI}]≫≫≫[/] [{CLR_LOGO_EDGE}]▓▒░[/]\n"
    f"[{CLR_LOGO_EDGE}]░▒▓[/]  [bold {CLR_TEXT}]| | | || | | |\\___ \\ '_ \\ | || '_ \\  / _` |  [/][{CLR_KHAKI}]≫≫[/] [{CLR_LOGO_EDGE}]▓▒░[/]\n"
    f"[{CLR_LOGO_EDGE}]░▒▓[/]  [bold {CLR_TEXT}]| |_| || |_| | ___) | |_) || || | | || (_| |  [/] [{CLR_KHAKI}]≫[/] [{CLR_LOGO_EDGE}]▓▒░[/]\n"
    f"[{CLR_LOGO_EDGE}]░▒▓[/]  [bold {CLR_TEXT}]|____/  \\___/ |____/| .__/ |_||_| |_| \\__, |     [/] [{CLR_LOGO_EDGE}]▓▒░[/]\n"
    f"[{CLR_LOGO_EDGE}]░▒▓[/]  [bold {CLR_TEXT}]                    |_|              |___/      [/] [{CLR_LOGO_EDGE}]▓▒░[/]\n"
    f"[{CLR_BORDER_A}]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▸[/]\n"
    f"[{CLR_MUTED}]              ⚡ Network Stress Tester v2.0 ⚡[/]"
)

LOGO_PLAIN_LINES = [
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▸",
    "░▒▓  ____    ___   ____        _                        ▓▒░",
    "░▒▓ |  _ \\  / _ \\ / ___|_ __  (_) _ __    __ _   ≫≫≫  ▓▒░",
    "░▒▓ | | | || | | |\\___ \\ '_ \\ | || '_ \\  / _` |  ≫≫   ▓▒░",
    "░▒▓ | |_| || |_| | ___) | |_) || || | | || (_| |   ≫   ▓▒░",
    "░▒▓ |____/  \\___/ |____/| .__/ |_||_| |_| \\__, |       ▓▒░",
    "░▒▓                     |_|              |___/        ▓▒░",
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▸",
    "              ⚡ Network Stress Tester v2.0 ⚡",
]

GLITCH_CHARS = "!@#$%^&*01█▓▒░╬╠╣╦╩╗╔╝╚│─┐┘┌└├┤┬┴┼~><{}[]"


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def valid_ip(ip: str) -> bool:
    """Return True if *ip* is a valid IPv4 address string."""
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except (AttributeError, socket.error):
        return False


def _strip_markup(line: str) -> str:
    """Remove Rich markup tags, return plain text."""
    try:
        return Text.from_markup(line).plain
    except Exception:
        return line


def _format_bytes(n: int) -> str:
    """Human-readable byte count (1024-based)."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    mins, secs = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {secs}s"
    elif mins:
        return f"{mins}m {secs}s"
    return f"{secs}s"


# ═══════════════════════════════════════════════════════════════
#  KITT SCANNER WIDGET
# ═══════════════════════════════════════════════════════════════

class KITTScanner(Static):
    """Animated KITT-style bouncing light scanner bar."""

    DEFAULT_CSS = """
    KITTScanner {
        height: 1;
        width: 100%;
        content-align: center middle;
    }
    """

    def __init__(self, bar_width: int = 56, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.bar_width = bar_width
        self.light_pos = 0
        self.light_dir = 1
        self._timer = None
        self._running = True

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / 30, self._tick)

    def on_unmount(self) -> None:
        self.halt()

    def _tick(self) -> None:
        if not self._running:
            return
        self.light_pos += self.light_dir
        if self.light_pos >= self.bar_width - 1:
            self.light_dir = -1
        elif self.light_pos <= 0:
            self.light_dir = 1
        self._render_bar()

    def _render_bar(self) -> None:
        bar = Text()
        for i in range(self.bar_width):
            dist = abs(i - self.light_pos)
            if dist == 0:
                bar.append("━", style="bold #e8c060")
            elif dist == 1:
                bar.append("━", style="#c8a050")
            elif dist == 2:
                bar.append("━", style="#a88040")
            elif dist == 3:
                bar.append("─", style="#7a5a20")
            elif dist == 4:
                bar.append("─", style="#4a3810")
            elif dist == 5:
                bar.append("─", style="#2a2010")
            else:
                bar.append("─", style="#181408")
        self.update(bar)

    def halt(self) -> None:
        self._running = False
        if self._timer:
            self._timer.stop()
            self._timer = None

    def restart(self) -> None:
        """Restart the animation after a halt."""
        self._running = True
        self.light_pos = 0
        self.light_dir = 1
        if self._timer is None:
            self._timer = self.set_interval(1 / 30, self._tick)

    def show_complete(self) -> None:
        self.halt()
        done = Text()
        half = self.bar_width // 2 - 5
        for _ in range(half):
            done.append("━", style=CLR_SAGE_DIM)
        done.append(" COMPLETE ", style=f"bold {CLR_TEXT} on #1a1a1a")
        for _ in range(half):
            done.append("━", style=CLR_SAGE_DIM)
        self.update(done)


# ═══════════════════════════════════════════════════════════════
#  STATS PANEL WIDGET
# ═══════════════════════════════════════════════════════════════

class StatsPanel(Static):
    """Narrow sidebar showing live flood statistics."""

    DEFAULT_CSS = f"""
    StatsPanel {{
        width: 26;
        padding: 1;
        border-left: solid {CLR_BORDER_A};
        background: {CLR_PANEL};
        color: {CLR_TEXT};
    }}
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)

    def refresh_stats(
        self,
        flooder: Flooder | None,
        start_time: float,
        icmp_on: bool,
        tcp_on: bool,
    ) -> None:
        """Rebuild the display from current flooder data."""
        if not flooder:
            self.update(f"[{CLR_MUTED}]Waiting for flood...[/]")
            return

        elapsed = time.time() - start_time if start_time else 0
        total = flooder.successful + flooder.failed
        rate = (flooder.successful / total * 100) if total > 0 else 0.0
        cps = flooder.connections_per_sec()
        sent = _format_bytes(flooder.bytes_sent)
        dur = _format_duration(elapsed)

        if rate >= 75:
            rc = CLR_SAGE_DIM
        elif rate >= 40:
            rc = CLR_OLIVE
        else:
            rc = CLR_BRICK

        # Visual rate bar (10 chars wide)
        bar_w = 10
        filled = int(bar_w * rate / 100)
        bar = "█" * filled + "░" * (bar_w - filled)

        icmp_st = f"[{CLR_SAGE_DIM}]ON[/]" if icmp_on else f"[{CLR_BRICK}]OFF[/]"
        tcp_st = f"[{CLR_SAGE_DIM}]ON[/]" if tcp_on else f"[{CLR_BRICK}]OFF[/]"

        text = (
            f"[{CLR_BORDER_A}]{'━' * 22}[/]\n"
            f"[bold {CLR_AMBER}]  LIVE STATS[/]\n"
            f"[{CLR_BORDER_A}]{'━' * 22}[/]\n\n"
            f" [{CLR_MUTED}]Conn/s [/] [{CLR_TEXT}]{cps:>7.1f}[/]\n"
            f" [{CLR_MUTED}]Rate   [/] [{rc}]{bar} {rate:>5.1f}%[/]\n"
            f" [{CLR_MUTED}]Hits   [/] [{CLR_SAGE_DIM}]{flooder.successful:>7}[/]\n"
            f" [{CLR_MUTED}]Fails  [/] [{CLR_BRICK}]{flooder.failed:>7}[/]\n"
            f" [{CLR_MUTED}]Sent   [/] [{CLR_TEXT}]{sent:>7}[/]\n"
            f" [{CLR_MUTED}]Time   [/] [{CLR_TEXT}]{dur:>7}[/]\n\n"
            f"[{CLR_BORDER_A}]{'━' * 22}[/]\n"
            f"[bold {CLR_AMBER}]  MONITORS[/]\n"
            f"[{CLR_BORDER_A}]{'━' * 22}[/]\n\n"
            f" [{CLR_MUTED}]ICMP   [/] {icmp_st}\n"
            f" [{CLR_MUTED}]TCP    [/] {tcp_st}\n"
        )
        self.update(text)


# ═══════════════════════════════════════════════════════════════
#  SPLASH SCREEN
# ═══════════════════════════════════════════════════════════════

class SplashScreen(Screen):
    """Matrix-style character reveal animation on launch."""

    DEFAULT_CSS = f"""
    SplashScreen {{
        align: center middle;
        background: {CLR_BG};
    }}

    #splash-container {{
        width: auto;
        height: auto;
        content-align: center middle;
        padding: 2 4;
    }}

    #splash-art {{
        width: 100%;
        content-align: center middle;
        min-height: 10;
    }}

    #splash-scanner {{
        margin-top: 1;
        width: 58;
        content-align: center middle;
    }}

    #splash-hint {{
        margin-top: 1;
        text-align: center;
        color: {CLR_MUTED};
    }}
    """

    def __init__(self) -> None:
        super().__init__()
        self.reveal_col = 0
        self.revealed = False
        self._advancing = False
        self._anim_timer = None

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="splash-container"):
                yield Static("", id="splash-art")
                yield KITTScanner(bar_width=58, id="splash-scanner")
                yield Static("", id="splash-hint", markup=True)

    def on_mount(self) -> None:
        self._anim_timer = self.set_interval(1 / 25, self._tick)

    def _tick(self) -> None:
        if self.revealed:
            return

        art_widget = self.query_one("#splash-art", Static)
        result = Text()
        max_width = max(len(line) for line in LOGO_PLAIN_LINES)

        for li, line in enumerate(LOGO_PLAIN_LINES):
            padded = line.ljust(max_width)
            for ci, ch in enumerate(padded):
                if ci < self.reveal_col:
                    result.append(ch, style=CLR_TEXT)
                elif ci < self.reveal_col + 3 and ch != " ":
                    if random.random() < 0.40:
                        result.append(ch, style="#88ff44")
                    else:
                        result.append(
                            random.choice(GLITCH_CHARS), style="#44cc22"
                        )
                elif ch in (" ", "\t"):
                    result.append(ch)
                else:
                    if random.random() < 0.18:
                        result.append(
                            random.choice(GLITCH_CHARS), style="#22bb22"
                        )
                    else:
                        result.append(
                            random.choice(GLITCH_CHARS), style="#0d4a0d"
                        )
            if li < len(LOGO_PLAIN_LINES) - 1:
                result.append("\n")

        art_widget.update(result)
        self.reveal_col += 1

        if self.reveal_col > max_width + 6:
            art_widget.update(LOGO)
            self.query_one("#splash-hint", Static).update(
                f"[{CLR_MUTED}]press any key to continue...[/]"
            )
            self.revealed = True

    def on_key(self, event) -> None:
        self._go_to_session()

    def _go_to_session(self) -> None:
        if self._advancing:
            return
        self._advancing = True
        if self._anim_timer:
            self._anim_timer.stop()
        self.app.pop_screen()
        self.app.push_screen(SessionScreen())


# ═══════════════════════════════════════════════════════════════
#  SETUP MODAL  —  overlay config form
# ═══════════════════════════════════════════════════════════════

class SetupModal(ModalScreen[dict | None]):
    """Modal overlay for configuring a new test session.

    Returns a dict with keys 'target', 'ports', 'bots' on
    success, or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = f"""
    SetupModal {{
        align: center middle;
    }}

    #setup-box {{
        width: 72;
        max-height: 90%;
        padding: 1 2;
        border: heavy {CLR_BORDER_A};
        background: {CLR_SURFACE};
    }}

    #logo-small {{
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }}

    .field-label {{
        margin-top: 1;
        color: {CLR_TEXT};
        text-style: bold;
    }}

    .field-hint {{
        color: {CLR_MUTED};
    }}

    Input {{
        margin: 0 0 1 0;
        background: {CLR_PANEL};
        border: tall {CLR_BORDER_A};
        color: {CLR_TEXT};
    }}

    Input:focus {{
        border: tall {CLR_SAGE};
    }}

    #launch-btn {{
        width: 100%;
        margin-top: 1;
        background: {CLR_PANEL};
        border: tall {CLR_BRICK};
        color: {CLR_AMBER};
    }}

    #launch-btn:hover {{
        background: {CLR_SURFACE};
        border: tall {CLR_AMBER};
    }}

    #cancel-btn {{
        width: 100%;
        margin-top: 0;
        background: {CLR_PANEL};
        border: tall {CLR_BORDER_A};
        color: {CLR_MUTED};
    }}
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-box"):
            yield Static(LOGO, id="logo-small", markup=True)
            yield Rule()

            yield Label("[bold]Target IP Address[/]", classes="field-label")
            yield Label(
                "[dim](IPv4 address of the target)[/]", classes="field-hint"
            )
            yield Input(placeholder="e.g. 178.79.134.182", id="ip-input")

            yield Label("[bold]Target Port(s)[/]", classes="field-label")
            yield Label(
                "[dim](comma-separated, e.g. 80,443,8080)[/]",
                classes="field-hint",
            )
            yield Input(placeholder="80", id="port-input", value="80")

            yield Label("[bold]Number of Bots[/]", classes="field-label")
            yield Label(
                "[dim](concurrent connections to flood)[/]",
                classes="field-hint",
            )
            yield Input(placeholder="200", id="bots-input", value="200")

            yield Rule()
            yield Button(
                "⚡ LAUNCH ATTACK ⚡", variant="error", id="launch-btn"
            )
            yield Button("Cancel", id="cancel-btn")

    # ── Enter-key navigation ─────────────────────────────────

    @on(Input.Submitted, "#ip-input")
    def _ip_submitted(self) -> None:
        self.query_one("#port-input", Input).focus()

    @on(Input.Submitted, "#port-input")
    def _port_submitted(self) -> None:
        self.query_one("#bots-input", Input).focus()

    @on(Input.Submitted, "#bots-input")
    def _bots_submitted(self) -> None:
        self._validate_and_launch()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "launch-btn":
            self._validate_and_launch()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ── Validation ───────────────────────────────────────────

    def _validate_and_launch(self) -> None:
        ip = self.query_one("#ip-input", Input).value.strip()
        ports_str = self.query_one("#port-input", Input).value.strip()
        bots_str = self.query_one("#bots-input", Input).value.strip()

        if not valid_ip(ip):
            self.notify("Invalid IPv4 address!", severity="error")
            self.query_one("#ip-input", Input).focus()
            return

        try:
            ports = [int(p.strip()) for p in ports_str.split(",")]
            for p in ports:
                if p < 1 or p > 65535:
                    raise ValueError
        except ValueError:
            self.notify(
                "Invalid port(s)! Use 1-65535, comma-separated.",
                severity="error",
            )
            self.query_one("#port-input", Input).focus()
            return

        try:
            bots = int(bots_str)
            if bots < 1:
                raise ValueError
        except ValueError:
            self.notify("Invalid bot count!", severity="error")
            self.query_one("#bots-input", Input).focus()
            return

        self.dismiss({"target": ip, "ports": ports, "bots": bots})


# ═══════════════════════════════════════════════════════════════
#  TEST PANEL  —  self-contained test session widget
# ═══════════════════════════════════════════════════════════════
#  Each TestPanel runs its own:
#    - Flooder instance
#    - ICMP ping subprocess
#    - TCP probe loop
#    - Stats timer
#    - Log buffers for export
# ───────────────────────────────────────────────────────────────

class TestPanel(Vertical):
    """A complete test session: flood + ping + stats."""

    DEFAULT_CSS = f"""
    TestPanel {{
        height: 1fr;
    }}

    .test-panels {{
        height: 1fr;
    }}

    .flood-container {{
        width: 1fr;
        border: heavy {CLR_BORDER_A};
        margin: 0 1 0 0;
        background: {CLR_PANEL};
    }}

    .ping-container {{
        width: 1fr;
        border: heavy {CLR_BORDER_B};
        background: {CLR_PANEL};
        margin: 0 1 0 0;
    }}

    .panel-header {{
        text-align: center;
        text-style: bold;
        padding: 0 1;
        background: {CLR_HEADER_A};
        color: {CLR_AMBER};
        border-bottom: solid {CLR_BORDER_A};
    }}

    .panel-header-ping {{
        text-align: center;
        text-style: bold;
        padding: 0 1;
        background: {CLR_HEADER_B};
        color: {CLR_SAGE};
        border-bottom: solid {CLR_BORDER_B};
    }}

    .flood-log, .ping-log {{
        height: 1fr;
        background: {CLR_BG};
        color: {CLR_TEXT};
    }}

    .progress-bar {{
        margin: 0 1;
    }}

    .attack-scanner {{
        height: 1;
        margin: 0 1;
    }}
    """

    def __init__(self, target: str, ports: list[int], bots: int) -> None:
        super().__init__()
        self.target = target
        self.ports = ports
        self.bots = bots
        self.flooder: Flooder | None = None
        self.ping_process: asyncio.subprocess.Process | None = None
        self.start_time: float = 0.0
        self._is_running: bool = True
        self.icmp_enabled: bool = True
        self.tcp_enabled: bool = True

        # Log buffers for export
        self._flood_lines: list[str] = []
        self._ping_lines: list[str] = []

        self._stats_timer = None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="test-panels"):
            # ── LEFT: Flood output ───────────────────────────
            with Vertical(classes="flood-container"):
                yield Static(
                    f"⚡ FLOOD OUTPUT ── {self.target}:"
                    f"{','.join(map(str, self.ports))}",
                    classes="panel-header",
                )
                yield RichLog(
                    classes="flood-log", highlight=True, markup=True
                )
                yield ProgressBar(classes="progress-bar", total=self.bots)
                yield KITTScanner(bar_width=50, classes="attack-scanner")

            # ── CENTER: Live connectivity monitor ────────────
            with Vertical(classes="ping-container"):
                yield Static(
                    f"📡 CONNECTIVITY ── {self.target}",
                    classes="panel-header-ping",
                )
                yield RichLog(
                    classes="ping-log",
                    highlight=True,
                    markup=True,
                    auto_scroll=True,
                )

            # ── RIGHT: Live stats sidebar ────────────────────
            yield StatsPanel(classes="stats-panel")

    def on_mount(self) -> None:
        self.start_time = time.time()
        self._stats_timer = self.set_interval(1.0, self._update_stats)
        self._start_ping()
        self._start_flood()

    # ── Logging helpers (write to widget + buffer) ───────────

    def _log_flood(self, msg: str) -> None:
        self._flood_lines.append(msg)
        try:
            self.query_one(".flood-log", RichLog).write(msg)
        except Exception:
            pass

    def _log_ping(self, msg: str) -> None:
        self._ping_lines.append(msg)
        try:
            self.query_one(".ping-log", RichLog).write(msg)
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════
    #  WORKER: Connectivity monitor
    # ═════════════════════════════════════════════════════════

    @work(exclusive=True, group="ping")
    async def _start_ping(self) -> None:
        log_write = self._log_ping

        log_write(f"[{CLR_BORDER_A}]{'─' * 44}[/]")
        log_write(f"[bold {CLR_AMBER}]  CONNECTIVITY MONITOR[/]")
        log_write(f"[{CLR_BORDER_A}]{'─' * 44}[/]")
        log_write(f"  [{CLR_TEXT}]ICMP[/] [{CLR_MUTED}]= system ping[/]")
        log_write(f"  [{CLR_TEXT}]TCP [/] [{CLR_MUTED}]= port probe[/]")
        log_write(f"[{CLR_BORDER_A}]{'─' * 44}[/]")
        log_write("")

        await asyncio.gather(
            self._icmp_loop(),
            self._tcp_loop(),
        )

    async def _icmp_loop(self) -> None:
        while True:
            if not self.icmp_enabled:
                await asyncio.sleep(1.0)
                continue

            if platform.system().lower() == "windows":
                cmd = ["ping", "-t", self.target]
            else:
                cmd = ["ping", self.target]

            try:
                self.ping_process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                while True:
                    line = await self.ping_process.stdout.readline()
                    if not line:
                        break
                    if not self.icmp_enabled:
                        break
                    decoded = line.decode(errors="replace").strip()
                    if not decoded:
                        continue

                    lower = decoded.lower()
                    if "reply from" in lower or "bytes from" in lower:
                        self._log_ping(
                            f"[{CLR_SAGE_DIM}]  [ICMP] ● {decoded}[/]"
                        )
                    elif "timed out" in lower or "unreachable" in lower:
                        self._log_ping(
                            f"[{CLR_OLIVE}]  [ICMP] ⚠ {decoded} "
                            f"[{CLR_MUTED}](ICMP may be blocked)[/]"
                        )
                    elif "pinging" in lower or "ping" in lower:
                        self._log_ping(
                            f"[{CLR_SAGE}]  [ICMP] ▸ {decoded}[/]"
                        )
                    else:
                        self._log_ping(
                            f"[{CLR_MUTED}]  [ICMP] {decoded}[/]"
                        )
            except Exception as e:
                self._log_ping(f"[{CLR_BRICK}]  [ICMP] Error: {e}[/]")

            # Small pause before restarting the ping process
            await asyncio.sleep(1.0)

    async def _tcp_loop(self) -> None:
        probe_num = 0
        while True:
            if not self.tcp_enabled:
                await asyncio.sleep(1.0)
                continue

            probe_num += 1
            for port in self.ports:
                t_start = time.monotonic()
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self.target, port),
                        timeout=3.0,
                    )
                    writer.close()
                    await writer.wait_closed()
                    latency_ms = (time.monotonic() - t_start) * 1000
                    self._log_ping(
                        f"[{CLR_SAGE_DIM}]  [TCP:{port}] ● OPEN[/] "
                        f"[{CLR_MUTED}]({latency_ms:.1f}ms) #{probe_num}[/]"
                    )
                except asyncio.TimeoutError:
                    self._log_ping(
                        f"[{CLR_BRICK}]  [TCP:{port}] ✖ TIMEOUT[/] "
                        f"[{CLR_MUTED}]#{probe_num}[/]"
                    )
                except OSError as e:
                    if "refused" in str(e).lower() or "10061" in str(e):
                        self._log_ping(
                            f"[{CLR_OLIVE}]  [TCP:{port}] ↩ REFUSED[/] "
                            f"[{CLR_MUTED}]#{probe_num}[/]"
                        )
                    else:
                        self._log_ping(
                            f"[{CLR_BRICK}]  [TCP:{port}] ✖ {e}[/] "
                            f"[{CLR_MUTED}]#{probe_num}[/]"
                        )
                except Exception as e:
                    self._log_ping(
                        f"[{CLR_BRICK}]  [TCP:{port}] Error: {e}[/]"
                    )
            await asyncio.sleep(2.0)

    # ═════════════════════════════════════════════════════════
    #  WORKER: TCP Flood
    # ═════════════════════════════════════════════════════════

    @work(exclusive=True, group="flood")
    async def _start_flood(self) -> None:
        progress = self.query_one(".progress-bar", ProgressBar)
        scanner = self.query_one(".attack-scanner", KITTScanner)

        def on_log(msg: str) -> None:
            self._log_flood(msg)

        def on_progress(current: int, total: int) -> None:
            progress.progress = current

        self.flooder = Flooder(
            target=self.target,
            ports=self.ports,
            bots=self.bots,
            concurrency=50,
            on_progress=on_progress,
            on_log=on_log,
        )

        self._log_flood(f"[{CLR_BORDER_A}]{'═' * 42}[/]")
        self._log_flood(f"[bold {CLR_AMBER}]  FLOOD STARTING[/]")
        self._log_flood(f"[{CLR_BORDER_A}]{'═' * 42}[/]")
        self._log_flood(
            f"  [{CLR_MUTED}]Target      :[/] [{CLR_TEXT}]{self.target}[/]"
        )
        self._log_flood(
            f"  [{CLR_MUTED}]Ports       :[/] "
            f"[{CLR_TEXT}]{', '.join(map(str, self.ports))}[/]"
        )
        self._log_flood(
            f"  [{CLR_MUTED}]Bots        :[/] [{CLR_TEXT}]{self.bots}[/]"
        )
        self._log_flood(
            f"  [{CLR_MUTED}]Concurrency :[/] [{CLR_TEXT}]50[/]"
        )
        self._log_flood("")

        await self.flooder.run()

        # ── Post-flood summary ───────────────────────────────
        self._log_flood("")
        self._log_flood(f"[{CLR_BORDER_B}]{'═' * 42}[/]")
        self._log_flood(f"[bold {CLR_SAGE}]  FLOOD COMPLETE[/]")
        self._log_flood(f"[{CLR_BORDER_B}]{'═' * 42}[/]")
        self._log_flood(
            f"  [{CLR_SAGE_DIM}]Connected :[/] "
            f"[{CLR_TEXT}]{self.flooder.successful}[/]"
        )
        self._log_flood(
            f"  [{CLR_BRICK}]Failed    :[/] "
            f"[{CLR_TEXT}]{self.flooder.failed}[/]"
        )

        scanner.show_complete()
        self._is_running = False

        # ── HTTP health check ────────────────────────────────
        self._log_flood("")
        self._log_flood(f"[{CLR_MUTED}]Running HTTP health check...[/]")
        try:
            resp = requests.head(f"http://{self.target}", timeout=3)
            self._log_flood(
                f"[{CLR_SAGE_DIM}]  ● HTTP {resp.status_code}[/]"
            )
        except requests.RequestException:
            self._log_flood(
                f"[{CLR_BRICK}]  ✖ HTTP check failed[/]"
            )

    # ═════════════════════════════════════════════════════════
    #  Stats timer
    # ═════════════════════════════════════════════════════════

    def _update_stats(self) -> None:
        try:
            panel = self.query_one(StatsPanel)
            panel.refresh_stats(
                self.flooder, self.start_time,
                self.icmp_enabled, self.tcp_enabled,
            )
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════
    #  Public actions (called from commands / palette)
    # ═════════════════════════════════════════════════════════

    def stop_flood(self) -> None:
        if self.flooder:
            self.flooder.stop()
        try:
            self.query_one(".attack-scanner", KITTScanner).halt()
        except Exception:
            pass
        self._is_running = False

    def reset(self) -> None:
        """Stop everything, clear logs, restart."""
        self.stop_flood()
        self._kill_ping()

        try:
            self.query_one(".flood-log", RichLog).clear()
            self.query_one(".ping-log", RichLog).clear()
            pb = self.query_one(".progress-bar", ProgressBar)
            pb.progress = 0
            scanner = self.query_one(".attack-scanner", KITTScanner)
            scanner.restart()
        except Exception:
            pass

        self.flooder = None
        self.start_time = time.time()
        self._is_running = True
        self._flood_lines.clear()
        self._ping_lines.clear()

        self._start_flood()
        self._start_ping()

    def export_log(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dosping_{self.target}_{timestamp}.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("DOSping Session Log\n")
                f.write(f"Target: {self.target}\n")
                f.write(
                    f"Ports: {', '.join(map(str, self.ports))}\n"
                )
                f.write(f"Bots: {self.bots}\n")
                f.write(f"{'=' * 50}\n\n")

                f.write("FLOOD LOG:\n")
                f.write("-" * 30 + "\n")
                for line in self._flood_lines:
                    f.write(_strip_markup(line) + "\n")

                f.write("\n\nCONNECTIVITY LOG:\n")
                f.write("-" * 30 + "\n")
                for line in self._ping_lines:
                    f.write(_strip_markup(line) + "\n")

            self.app.notify(f"Exported: {filename}", severity="information")
        except OSError as e:
            self.app.notify(f"Export failed: {e}", severity="error")

    def toggle_icmp(self) -> None:
        self.icmp_enabled = not self.icmp_enabled
        if not self.icmp_enabled:
            self._kill_ping()
        label = "enabled" if self.icmp_enabled else "disabled"
        self.app.notify(f"ICMP monitor {label}")

    def toggle_tcp(self) -> None:
        self.tcp_enabled = not self.tcp_enabled
        label = "enabled" if self.tcp_enabled else "disabled"
        self.app.notify(f"TCP monitor {label}")

    def clear_flood_log(self) -> None:
        try:
            self.query_one(".flood-log", RichLog).clear()
        except Exception:
            pass

    def clear_ping_log(self) -> None:
        try:
            self.query_one(".ping-log", RichLog).clear()
        except Exception:
            pass

    def get_stats(self) -> dict:
        """Return current session stats as a dict."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        hits = self.flooder.successful if self.flooder else 0
        misses = self.flooder.failed if self.flooder else 0
        total = hits + misses
        pct = (hits / total * 100) if total > 0 else 0.0
        return {
            "target": self.target,
            "ports": self.ports,
            "bots": self.bots,
            "hits": hits,
            "misses": misses,
            "total": total,
            "success_pct": pct,
            "elapsed": elapsed,
            "stopped": self.flooder._stopped if self.flooder else False,
        }

    # ── Cleanup ──────────────────────────────────────────────

    def _kill_ping(self) -> None:
        if self.ping_process:
            try:
                self.ping_process.kill()
            except ProcessLookupError:
                pass
            self.ping_process = None

    def cleanup(self) -> None:
        """Full teardown: stop flood, kill ping, stop stats."""
        self.stop_flood()
        self._kill_ping()
        if self._stats_timer:
            self._stats_timer.stop()
            self._stats_timer = None


# ═══════════════════════════════════════════════════════════════
#  TEST TAB PANE  —  TabPane subclass with compose
# ═══════════════════════════════════════════════════════════════

class TestTabPane(TabPane):
    """A TabPane wrapping a single TestPanel."""

    def __init__(
        self,
        target: str,
        ports: list[int],
        bots: int,
        label: str,
        **kwargs,
    ) -> None:
        super().__init__(label, **kwargs)
        self._target = target
        self._ports = ports
        self._bots = bots

    def compose(self) -> ComposeResult:
        yield TestPanel(self._target, self._ports, self._bots)


# ═══════════════════════════════════════════════════════════════
#  SESSION SCREEN  —  tab management
# ═══════════════════════════════════════════════════════════════

class SessionScreen(Screen):
    """Main screen holding TabbedContent with test sessions."""

    BINDINGS = [
        Binding("ctrl+n", "new_test", "New Test"),
        Binding("ctrl+w", "close_tab", "Close Tab"),
        Binding("s", "stop_flood", "Stop Flood"),
        Binding("q", "quit_app", "Quit"),
    ]

    DEFAULT_CSS = f"""
    SessionScreen {{
        layout: vertical;
        background: {CLR_BG};
    }}

    #session-tabs {{
        height: 1fr;
    }}

    .session-status {{
        height: auto;
        max-height: 3;
        padding: 0 1;
        background: {CLR_SURFACE};
        color: {CLR_MUTED};
        dock: bottom;
        border-top: solid {CLR_LOGO_EDGE};
    }}

    .empty-state {{
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
        color: {CLR_MUTED};
    }}
    """

    _tab_counter = 0

    def __init__(self) -> None:
        super().__init__()
        self._spinner_idx = 0
        self._spinner_timer = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield TabbedContent(id="session-tabs")
        yield Static(
            f"  [{CLR_MUTED}]Ctrl+N[/] [{CLR_TEXT}]new test[/]  "
            f"[{CLR_MUTED}]Ctrl+W[/] [{CLR_TEXT}]close tab[/]  "
            f"[{CLR_MUTED}]Ctrl+P[/] [{CLR_TEXT}]commands[/]  "
            f"[{CLR_MUTED}]s[/] [{CLR_TEXT}]stop[/]  "
            f"[{CLR_MUTED}]q[/] [{CLR_TEXT}]quit[/]",
            classes="session-status",
        )
        yield Footer()

    def on_mount(self) -> None:
        # Start spinner animation for tab labels
        self._spinner_timer = self.set_interval(1 / 10, self._tick_spinners)
        # Auto-open setup for the first test
        self.set_timer(0.2, self.action_new_test)

    # ── Tab management ───────────────────────────────────────

    def action_new_test(self) -> None:
        if self._tab_count() >= MAX_TABS:
            self.notify(
                f"Max {MAX_TABS} concurrent tests", severity="warning"
            )
            return
        self.app.push_screen(SetupModal(), callback=self._on_setup)

    def _on_setup(self, result: dict | None) -> None:
        if result is not None:
            self._add_test(
                result["target"], result["ports"], result["bots"]
            )

    def _add_test(
        self, target: str, ports: list[int], bots: int
    ) -> None:
        SessionScreen._tab_counter += 1
        tab_id = f"tab-{SessionScreen._tab_counter}"

        port_str = (
            f":{ports[0]}" if len(ports) == 1
            else f" ({','.join(map(str, ports))})"
        )
        label = f"● {target}{port_str}"

        pane = TestTabPane(
            target, ports, bots, label=label, id=tab_id
        )
        tc = self.query_one("#session-tabs", TabbedContent)
        tc.add_pane(pane)
        tc.active = tab_id

    def action_close_tab(self) -> None:
        tc = self.query_one("#session-tabs", TabbedContent)
        active = tc.active
        if not active:
            return

        # Cleanup the test panel before removing
        try:
            pane = tc.query_one(f"#{active}", TabPane)
            panel = pane.query_one(TestPanel)
            panel.cleanup()
        except Exception:
            pass

        tc.remove_pane(active)

    def _tab_count(self) -> int:
        tc = self.query_one("#session-tabs", TabbedContent)
        return len(tc.query(TabPane))

    # ── Spinner animation for tab labels ─────────────────────

    def _tick_spinners(self) -> None:
        self._spinner_idx = (self._spinner_idx + 1) % len(SPINNER_FRAMES)
        char = SPINNER_FRAMES[self._spinner_idx]

        tc = self.query_one("#session-tabs", TabbedContent)
        for pane in tc.query(TestTabPane):
            try:
                panel = pane.query_one(TestPanel)
            except Exception:
                continue

            port_str = (
                f":{panel.ports[0]}" if len(panel.ports) == 1
                else f" ({','.join(map(str, panel.ports))})"
            )

            if panel._is_running:
                new_label = f"{char} {panel.target}{port_str}"
            else:
                new_label = f"✓ {panel.target}{port_str}"

            # Update the internal Tab widget label
            tab_id = f"--content-tab-{pane.id}"
            try:
                tab_widget = tc.query_one(f"#{tab_id}")
                tab_widget.label = new_label
            except Exception:
                pass

    # ── Actions ──────────────────────────────────────────────

    def action_stop_flood(self) -> None:
        panel = self._get_active_panel()
        if panel:
            panel.stop_flood()
            self.notify("Stop signal sent.", severity="warning")

    def action_quit_app(self) -> None:
        # Save stats from the active panel
        panel = self._get_active_panel()
        if panel:
            self.app.session_stats = panel.get_stats()

        # Cleanup all tabs
        tc = self.query_one("#session-tabs", TabbedContent)
        for pane in tc.query(TestTabPane):
            try:
                p = pane.query_one(TestPanel)
                p.cleanup()
            except Exception:
                pass

        self.app.exit()

    def _get_active_panel(self) -> TestPanel | None:
        tc = self.query_one("#session-tabs", TabbedContent)
        active = tc.active
        if not active:
            return None
        try:
            pane = tc.query_one(f"#{active}", TabPane)
            return pane.query_one(TestPanel)
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════
#  COMMAND PALETTE PROVIDER
# ═══════════════════════════════════════════════════════════════

class DOSPingCommandProvider(Provider):
    """Custom commands for the Ctrl+P command palette."""

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)

        commands = [
            (
                "New Test",
                "Start a new test in a new tab (Ctrl+N)",
                self._new_test,
            ),
            (
                "Stop Flood",
                "Stop the active tab's flood",
                self._stop_flood,
            ),
            (
                "Reset Current Test",
                "Stop, clear, and restart the active test",
                self._reset_test,
            ),
            (
                "Export Log",
                "Save flood and ping logs to a .txt file",
                self._export_log,
            ),
            (
                "Clear Flood Log",
                "Clear the left panel's log",
                self._clear_flood,
            ),
            (
                "Clear Ping Log",
                "Clear the right panel's log",
                self._clear_ping,
            ),
            (
                "Toggle ICMP Monitor",
                "Enable/disable ICMP ping subprocess",
                self._toggle_icmp,
            ),
            (
                "Toggle TCP Monitor",
                "Enable/disable TCP port probes",
                self._toggle_tcp,
            ),
            (
                "Close Tab",
                "Close the active test tab (Ctrl+W)",
                self._close_tab,
            ),
            (
                "Open Documentation",
                "Open HTML docs in your browser",
                self._open_docs,
            ),
            (
                "Open Terminal",
                "Launch a system terminal window",
                self._open_terminal,
            ),
        ]

        for name, help_text, callback in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    help=help_text,
                )

    # ── Callbacks ────────────────────────────────────────────

    def _get_session(self) -> SessionScreen | None:
        screen = self.app.screen
        if isinstance(screen, SessionScreen):
            return screen
        return None

    def _get_panel(self) -> TestPanel | None:
        session = self._get_session()
        if session:
            return session._get_active_panel()
        return None

    async def _new_test(self) -> None:
        s = self._get_session()
        if s:
            s.action_new_test()

    async def _stop_flood(self) -> None:
        p = self._get_panel()
        if p:
            p.stop_flood()
            self.app.notify("Flood stopped.", severity="warning")

    async def _reset_test(self) -> None:
        p = self._get_panel()
        if p:
            p.reset()
            self.app.notify("Test reset.", severity="information")

    async def _export_log(self) -> None:
        p = self._get_panel()
        if p:
            p.export_log()

    async def _clear_flood(self) -> None:
        p = self._get_panel()
        if p:
            p.clear_flood_log()

    async def _clear_ping(self) -> None:
        p = self._get_panel()
        if p:
            p.clear_ping_log()

    async def _toggle_icmp(self) -> None:
        p = self._get_panel()
        if p:
            p.toggle_icmp()

    async def _toggle_tcp(self) -> None:
        p = self._get_panel()
        if p:
            p.toggle_tcp()

    async def _close_tab(self) -> None:
        s = self._get_session()
        if s:
            s.action_close_tab()

    async def _open_docs(self) -> None:
        docs_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "docs", "index.html",
        )
        if os.path.exists(docs_path):
            webbrowser.open(f"file://{docs_path}")
        else:
            self.app.notify("docs/index.html not found", severity="warning")

    async def _open_terminal(self) -> None:
        system = platform.system().lower()
        try:
            if system == "windows":
                subprocess.Popen("start cmd.exe", shell=True)
            elif system == "darwin":
                subprocess.Popen(["open", "-a", "Terminal"])
            else:
                for term in [
                    "gnome-terminal", "xfce4-terminal",
                    "konsole", "xterm",
                ]:
                    try:
                        subprocess.Popen([term])
                        return
                    except FileNotFoundError:
                        continue
                self.app.notify(
                    "No terminal emulator found", severity="warning"
                )
        except Exception as e:
            self.app.notify(f"Failed to open terminal: {e}", severity="error")


# ═══════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════

class DOSPingApp(App):
    """DOSping v2.0 — Network Stress Testing TUI."""

    TITLE = "DOSping"
    SUB_TITLE = "Network Stress Tester v2.0"

    DARK = True

    # Register the custom command provider alongside defaults
    COMMANDS = App.COMMANDS | {DOSPingCommandProvider}

    DEFAULT_CSS = f"""
    Screen {{
        background: {CLR_BG};
    }}

    Header {{
        background: {CLR_SURFACE};
        color: {CLR_SAGE};
        border-bottom: solid {CLR_LOGO_EDGE};
    }}

    Footer {{
        background: {CLR_SURFACE};
        color: {CLR_MUTED};
        border-top: solid {CLR_LOGO_EDGE};
    }}
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session_stats: dict = {}

    def on_mount(self) -> None:
        self.register_theme(THEME_DOSPING_MATRIX)
        self.theme = "dosping-matrix"
        self.push_screen(SplashScreen())


# ═══════════════════════════════════════════════════════════════
#  POST-EXIT SESSION SUMMARY
# ═══════════════════════════════════════════════════════════════

def print_session_summary(stats: dict) -> None:
    """Render a formatted session summary to the terminal."""
    console = Console()

    elapsed = stats.get("elapsed", 0)
    duration = _format_duration(elapsed)

    if stats.get("stopped"):
        status = f"[bold {CLR_AMBER}]STOPPED BY USER[/]"
    elif stats.get("total", 0) >= stats.get("bots", 0):
        status = f"[bold {CLR_SAGE_DIM}]COMPLETED[/]"
    else:
        status = f"[bold {CLR_OLIVE}]PARTIAL[/]"

    pct = stats.get("success_pct", 0)
    bar_w = 20
    filled = int(bar_w * pct / 100)
    bar_str = "█" * filled + "░" * (bar_w - filled)
    if pct >= 75:
        rate_colour = CLR_SAGE_DIM
    elif pct >= 40:
        rate_colour = CLR_OLIVE
    else:
        rate_colour = CLR_BRICK

    table = Table(
        show_header=False, show_edge=False,
        pad_edge=False, box=None, padding=(0, 2),
    )
    table.add_column("key", style=CLR_MUTED, no_wrap=True)
    table.add_column("val", style=CLR_TEXT)

    table.add_row("Target", stats.get("target", "—"))
    table.add_row(
        "Ports", ", ".join(map(str, stats.get("ports", [])))
    )
    table.add_row("Bots", str(stats.get("bots", "—")))
    table.add_row("Duration", duration)
    table.add_row("", "")
    table.add_row(
        "Hits (success)",
        f"[{CLR_SAGE_DIM}]{stats.get('hits', 0)}[/]",
    )
    table.add_row(
        "Misses (fail)",
        f"[{CLR_BRICK}]{stats.get('misses', 0)}[/]",
    )
    table.add_row("Total Attempts", str(stats.get("total", 0)))
    table.add_row(
        "Success Rate",
        f"[{rate_colour}]{bar_str}  {pct:.1f}%[/]",
    )
    table.add_row("", "")
    table.add_row("Status", status)

    panel = Panel(
        table,
        title=f"[bold {CLR_TEXT}]DOSping Session Summary[/]",
        subtitle=f"[{CLR_MUTED}]pentest toolkit[/]",
        border_style=CLR_BORDER_A,
        padding=(1, 3),
    )

    console.print()
    console.print(panel)
    console.print()


# ═════════════════════════════════════════════════════════════

def main():
    """Entry point for the ``dosping`` console command."""
    app = DOSPingApp()
    app.run()

    if app.session_stats:
        print_session_summary(app.session_stats)


if __name__ == "__main__":
    main()
