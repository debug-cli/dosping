# ═══════════════════════════════════════════════════════════════
#  dosping.py  —  DOSping v3.5 Network Stress Testing TUI
# ═══════════════════════════════════════════════════════════════
#  Cross-platform Terminal UI for network stress testing with
#  multi-tab sessions, live split-panel monitoring, command
#  palette actions, home routing, settings, view modes, and a
#  real-time stats sidebar.
#
#  Stack:  Python 3.12+  ·  textual  ·  rich  ·  asyncio
#
#  View Modes:
#    SKID     — minimal panels, no jargon
#    ADVANCED — standard panels + latency graph + health
#    IT       — every panel, every metric, raw data
#
#  Screens:
#    SplashScreen  →  HomeScreen
#                       ├─ SettingsModal
#                       ├─ SessionScreen attack flow
#                       │    └─ SetupModal
#                       │    └─ TestTabPane(s) with TestPanel(s)
#                       └─ SessionScreen scan flow
#                            └─ ScannerSetupModal
#                            └─ ScanTabPane(s) with ScanSessionPanel(s)
#
#  FOR PENETRATION TESTING / EDUCATIONAL PURPOSES ONLY.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import collections
import json
import math
import os
import platform
import random
import re
import socket
import statistics
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.containers import Center, Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Rule,
    Static,
    TabbedContent,
    TabPane,
)

from flooder import Flooder
from scanner import NetworkScanEngine, PortScannerEngine, ScanResult, parse_port_spec

# ═══════════════════════════════════════════════════════════════
#  VIEW MODES
# ═══════════════════════════════════════════════════════════════


class ViewMode(Enum):
    SKID = "skid"
    ADVANCED = "advanced"
    IT = "it"

    def next(self) -> "ViewMode":
        order = [ViewMode.SKID, ViewMode.ADVANCED, ViewMode.IT]
        idx = order.index(self)
        return order[(idx + 1) % len(order)]

    @property
    def display_name(self) -> str:
        names = {
            ViewMode.SKID: "Skid",
            ViewMode.ADVANCED: "Advanced",
            ViewMode.IT: "IT",
        }
        return names[self]


class SessionMode(Enum):
    ATTACK = "attack"
    SCAN = "scan"


# ═══════════════════════════════════════════════════════════════
#  COLOR PALETTE
# ═══════════════════════════════════════════════════════════════

CLR_BG = "#0b0b0b"
CLR_SURFACE = "#111110"
CLR_PANEL = "#0e0e0c"

CLR_AMBER = "#c8a050"
CLR_SAGE = "#7a9a6a"
CLR_SAGE_DIM = "#6a8a5a"
CLR_OLIVE = "#9a8a40"
CLR_BRICK = "#8a5a4a"

CLR_BORDER_A = "#3a3a2a"
CLR_BORDER_B = "#2a3a2a"
CLR_HEADER_A = "#1e1e16"
CLR_HEADER_B = "#141e14"
CLR_MUTED = "#555550"
CLR_LOGO_EDGE = "#2a2a1a"
CLR_TEXT = "#c8c8b8"
CLR_KHAKI = "#7a7a5a"

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
MAX_TABS = 4


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

THEME_DOSPING_BLUE = Theme(
    name="dosping-blue",
    dark=True,
    primary="#3f8cff",
    secondary="#20b2aa",
    background=CLR_BG,
    surface="#10131a",
    panel="#0d1117",
    accent="#3f8cff",
    success="#3ddc84",
    warning="#ffcc33",
    error="#ff5c5c",
)

THEME_DOSPING_RED = Theme(
    name="dosping-red",
    dark=True,
    primary="#ff6b35",
    secondary="#c8a050",
    background=CLR_BG,
    surface="#16100e",
    panel="#100c0b",
    accent="#ff6b35",
    success="#7a9a6a",
    warning="#c8a050",
    error="#ff6b35",
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
    f"[{CLR_MUTED}]              ⚡ Network Stress Tester v3.5 ⚡[/]"
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
    "              ⚡ Network Stress Tester v3.5 ⚡",
]

GLITCH_CHARS = "!@#$%^&*01█▓▒░╬╠╣╦╩╗╔╝╚│─┐┘┌└├┤┬┴┼~><{}[]"

# ═══════════════════════════════════════════════════════════════
#  HOME SCREEN ASCII ART
# ═══════════════════════════════════════════════════════════════

# Leading spaces removed — HomeTile centers each line via CSS text-align: center
PORT_SCANNER_ART = (
    ".\n"
    "/ \\\n"
    "/   \\\n"
    "/     \\\n"
    "/  . .  \\\n"
    "/  /   \\  \\\n"
    "/  /  .  \\  \\\n"
    "/  /       \\  \\\n"
    "(  (         )  )\n"
    "\\  \\       /  /\n"
    "\\  \\  .  /  /\n"
    "\\  \\   /  /\n"
    "\\     /\n"
    "\\   /\n"
    "\\ /"
)

# 2 blank lines top + 11 art lines + 2 blank lines bottom = 15 lines (== PORT_SCANNER_ART)
ATTACKER_ART = (
    "\n"
    "\n"
    "(\n"
    ") \\\n"
    "/   )\n"
    "(   /\n"
    ")  (\n"
    "/    \\\n"
    "(  ()  )\n"
    "/  /  \\  \\\n"
    "(  /    \\  )\n"
    "\\ \\____/ /\n"
    "\\______/\n"
    "\n"
    ""
)

SETTINGS_ART = "⚙ SETTINGS"

PORT_PRESETS: dict[str, str] = {
    "Web": "80,443,3000,3001,5000,8000,8080,8443,8888",
    "Devices": "22,23,80,443,554,3389,5900,8080",
    "Cameras": "80,443,554,8080,8554,9000,34567,37777",
    "Services": "21,22,23,25,53,80,110,143,389,443,445,993,995,3306,3389,5432",
    "Common": "1-1024",
    "Full": "1-65535",
}


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
        if getattr(self.app, "kitt_animation_enabled", True):
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

    def sync_enabled(self, enabled: bool) -> None:
        if enabled:
            self.restart()
        else:
            self.halt()

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
        peak_cps: float,
        view_mode: ViewMode,
    ) -> None:
        """Rebuild the display from current flooder data and view mode."""
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

        bar_w = 10
        filled = int(bar_w * rate / 100)
        bar = "█" * filled + "░" * (bar_w - filled)

        icmp_st = f"[{CLR_SAGE_DIM}]ON[/]" if icmp_on else f"[{CLR_BRICK}]OFF[/]"
        tcp_st = f"[{CLR_SAGE_DIM}]ON[/]" if tcp_on else f"[{CLR_BRICK}]OFF[/]"

        if view_mode == ViewMode.SKID:
            stats_text = (
                f" [{CLR_MUTED}]Conn/s [/] [{CLR_TEXT}]{cps:>7.1f}[/]\n"
                f" [{CLR_MUTED}]Success[/] [{rc}]{rate:>7.1f}%[/]\n"
                f" [{CLR_MUTED}]Time   [/] [{CLR_TEXT}]{dur:>7}[/]\n\n"
            )
        else:
            stats_text = (
                f" [{CLR_MUTED}]Conn/s [/] [{CLR_TEXT}]{cps:>7.1f}[/]\n"
                f" [{CLR_MUTED}]Peak   [/] [{CLR_TEXT}]{peak_cps:>7.1f}[/]\n"
                f" [{CLR_MUTED}]Rate   [/] [{rc}]{bar} {rate:>5.1f}%[/]\n"
                f" [{CLR_MUTED}]Hits   [/] [{CLR_SAGE_DIM}]{flooder.successful:>7}[/]\n"
                f" [{CLR_MUTED}]Fails  [/] [{CLR_BRICK}]{flooder.failed:>7}[/]\n"
                f" [{CLR_MUTED}]Sent   [/] [{CLR_TEXT}]{sent:>7}[/]\n"
                f" [{CLR_MUTED}]Time   [/] [{CLR_TEXT}]{dur:>7}[/]\n\n"
            )

        text = (
            f"[{CLR_BORDER_A}]{'━' * 22}[/]\n"
            f"[bold {CLR_AMBER}]  LIVE STATS[/]\n"
            f"[{CLR_BORDER_A}]{'━' * 22}[/]\n\n"
            f"{stats_text}"
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
                        result.append(random.choice(GLITCH_CHARS), style="#44cc22")
                elif ch in (" ", "\t"):
                    result.append(ch)
                else:
                    if random.random() < 0.18:
                        result.append(random.choice(GLITCH_CHARS), style="#22bb22")
                    else:
                        result.append(random.choice(GLITCH_CHARS), style="#0d4a0d")
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
        event.stop()
        self._go_to_session()

    def _go_to_session(self) -> None:
        if self._advancing:
            return
        self._advancing = True
        if self._anim_timer:
            self._anim_timer.stop()
        self.app.pop_screen()
        self.app.push_screen(HomeScreen())


class HomeHeader(Static):
    """Centered DOSping title with a live unstable right edge."""

    DEFAULT_CSS = f"""
    HomeHeader {{
        width: 64;
        height: 3;
        content-align: center middle;
        color: {CLR_TEXT};
        text-style: bold;
    }}
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._timer = None

    def on_mount(self) -> None:
        if getattr(self.app, "matrix_animation_enabled", True):
            self._timer = self.set_interval(1 / 18, self._tick)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def sync_enabled(self, enabled: bool) -> None:
        if enabled and self._timer is None:
            self._timer = self.set_interval(1 / 18, self._tick)
        elif not enabled and self._timer:
            self._timer.stop()
            self._timer = None
            # Reset to solid, mixed-case branding
            self.update(f"[bold {CLR_AMBER}]DOSping  v3.5[/]")

    def _tick(self) -> None:
        word = "DOSping"  # this part glitches
        version = "  v3.5"  # this part stays solid
        if not getattr(self.app, "matrix_animation_enabled", True):
            self.update(f"[bold {CLR_AMBER}]{word}{version}[/]")
            return

        noisy = "".join(
            random.choice(GLITCH_CHARS) if random.random() < 0.45 else ch for ch in word
        )
        self.update(f"[bold #22bb22]{noisy}[/][bold {CLR_AMBER}]{version}[/]")


class HomeTile(Widget, can_focus=True):
    """A focusable, clickable home-screen tile with a title bar and ASCII art body.

    Using a Widget (not a Button) so the art is rendered by a Static with
    text-align:center — each line is centered independently, which works
    perfectly for stripped (no leading-space) art strings.  A Button would
    double-center the label lines, morphing the art.
    """

    DEFAULT_CSS = f"""
    HomeTile {{
        width: 34;
        height: 24;
        margin: 0 2;
        border: heavy {CLR_BORDER_A};
        background: {CLR_PANEL};
        layout: vertical;
    }}

    HomeTile:hover {{
        border: heavy {CLR_AMBER};
        background: {CLR_SURFACE};
    }}

    HomeTile:focus {{
        border: heavy {CLR_AMBER};
        background: {CLR_PANEL};
    }}

    .tile-title-bar {{
        height: 2;
        text-align: center;
        text-style: bold;
        padding: 0 1;
        background: {CLR_HEADER_A};
        color: {CLR_TEXT};
        border-bottom: solid {CLR_BORDER_A};
    }}

    .tile-art-body {{
        height: 1fr;
        padding: 1 0 0 0;
        color: {CLR_TEXT};
        text-align: center;
    }}
    """

    class Activated(Message):
        """Posted when the tile is clicked or Enter is pressed."""

        def __init__(self, tile: "HomeTile") -> None:
            super().__init__()
            self.tile = tile

    def __init__(
        self,
        title: str,
        art: str,
        title_color: str,
        tile_id: str,
        animate: bool = False,
    ) -> None:
        super().__init__(id=tile_id)
        self._title = title
        self._art = art
        self._title_color = title_color
        self._animate = animate
        self._anim_timer = None

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold {self._title_color}]{self._title}[/]",
            classes="tile-title-bar",
            markup=True,
        )
        # markup=False prevents Rich from misinterpreting backslashes in art
        yield Static(self._art, classes="tile-art-body", markup=False)

    def _reset_art(self) -> None:
        """Restore the original art string, stopping any glitch frame."""
        try:
            self.query_one(".tile-art-body", Static).update(self._art)
        except Exception:
            pass

    def _stop_anim(self) -> None:
        if self._anim_timer:
            self._anim_timer.stop()
            self._anim_timer = None
        self._reset_art()

    # Animation starts only when this tile is focused, stops on blur.
    def on_focus(self) -> None:
        if self._animate and self._anim_timer is None:
            if getattr(self.app, "matrix_animation_enabled", True):
                self._anim_timer = self.set_interval(1 / 10, self._tick_anim)

    def on_blur(self) -> None:
        self._stop_anim()

    def on_unmount(self) -> None:
        self._stop_anim()

    def _tick_anim(self) -> None:
        if not getattr(self.app, "matrix_animation_enabled", True):
            self._stop_anim()
            return
        chars = list(self._art)
        for i, ch in enumerate(chars):
            if ch not in (" ", "\n") and random.random() < 0.12:
                chars[i] = random.choice(GLITCH_CHARS)
        try:
            self.query_one(".tile-art-body", Static).update("".join(chars))
        except Exception:
            pass

    def on_click(self) -> None:
        self.post_message(self.Activated(self))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Activated(self))
            event.stop()


class HomeScreen(Screen):
    """Landing screen with attack and scan entry points."""

    BINDINGS = [
        Binding("escape", "open_settings", "Settings"),
        Binding("s", "open_settings", "Settings"),
        Binding("a", "open_attack", "Attacker"),
        Binding("p", "open_scan", "Port Scanner"),
    ]

    DEFAULT_CSS = f"""
    HomeScreen {{
        layout: vertical;
        background: {CLR_BG};
    }}

    #home-top {{
        height: 5;
        width: 100%;
        align: center middle;
        border-bottom: solid {CLR_LOGO_EDGE};
        background: {CLR_SURFACE};
    }}

    #home-body {{
        height: 1fr;
        width: 100%;
        align: center middle;
        padding-top: 3;
    }}

    #home-tiles {{
        width: auto;
        height: auto;
    }}

    #home-bottom {{
        height: 4;
        width: 100%;
        align: center middle;
        border-top: solid {CLR_LOGO_EDGE};
        background: {CLR_SURFACE};
    }}

    #settings-btn {{
        width: 24;
        background: {CLR_PANEL};
        border: tall {CLR_BORDER_A};
        color: {CLR_TEXT};
    }}

    #settings-btn:hover {{
        border: tall {CLR_AMBER};
        color: {CLR_AMBER};
    }}

    #settings-btn:focus {{
        border: tall {CLR_AMBER};
        color: {CLR_AMBER};
    }}
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="home-top"):
            yield HomeHeader()
        with Vertical(id="home-body"):
            with Horizontal(id="home-tiles"):
                yield HomeTile(
                    title="PORT SCANNER",
                    art=PORT_SCANNER_ART,
                    title_color=CLR_AMBER,
                    tile_id="scanner-tile",
                    animate=True,
                )
                yield HomeTile(
                    title="ATTACKER",
                    art=ATTACKER_ART,
                    title_color=CLR_BRICK,
                    tile_id="attacker-tile",
                    animate=True,
                )
        with Horizontal(id="home-bottom"):
            yield Button(SETTINGS_ART, id="settings-btn", variant="default")

    def on_mount(self) -> None:
        # Small delay so a lingering splash-screen Enter key cannot fire a tile.
        self.set_timer(0.1, lambda: self.query_one("#scanner-tile", HomeTile).focus())

    def on_key(self, event) -> None:
        focused = self.focused
        fid = focused.id if focused else None
        if event.key in ("left", "h"):
            if fid == "attacker-tile":
                self.query_one("#scanner-tile", HomeTile).focus()
            event.stop()
        elif event.key in ("right", "l"):
            if fid == "scanner-tile":
                self.query_one("#attacker-tile", HomeTile).focus()
            event.stop()
        elif event.key == "down":
            if fid in ("scanner-tile", "attacker-tile"):
                self.query_one("#settings-btn", Button).focus()
                event.stop()
        elif event.key == "up":
            if fid == "settings-btn":
                self.query_one("#scanner-tile", HomeTile).focus()
                event.stop()

    def on_home_tile_activated(self, event: HomeTile.Activated) -> None:
        if event.tile.id == "scanner-tile":
            self.action_open_scan()
        elif event.tile.id == "attacker-tile":
            self.action_open_attack()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-btn":
            self.action_open_settings()

    def action_open_attack(self) -> None:
        self.app.push_screen(SessionScreen(mode=SessionMode.ATTACK, auto_start=True))

    def action_open_scan(self) -> None:
        self.app.push_screen(SessionScreen(mode=SessionMode.SCAN, auto_start=True))

    def action_open_settings(self) -> None:
        self.app.push_screen(SettingsModal())


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
            yield Label("[dim](IPv4 address of the target)[/]", classes="field-hint")
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
            yield Button("⚡ LAUNCH ATTACK ⚡", variant="error", id="launch-btn")
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


class ScannerSetupModal(ModalScreen[dict | None]):
    """Modal overlay for configuring a port scan or network scan session."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = f"""
    ScannerSetupModal {{ align: center middle; }}

    #scan-setup-box {{
        width: 76;
        max-height: 92%;
        overflow-y: auto;
        padding: 1 2;
        border: heavy {CLR_BORDER_A};
        background: {CLR_SURFACE};
    }}

    #scan-logo-small {{
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }}

    .scan-section-title {{
        margin-top: 1;
        color: {CLR_TEXT};
        text-style: bold;
    }}

    .scan-field-hint {{
        color: {CLR_MUTED};
        margin-bottom: 1;
    }}

    Input {{
        background: {CLR_PANEL};
        border: tall {CLR_BORDER_A};
        color: {CLR_TEXT};
        margin-bottom: 1;
    }}

    Input:focus {{ border: tall {CLR_SAGE}; }}

    .mode-btn {{
        width: 18;
        margin: 0 1 1 0;
        background: {CLR_PANEL};
        border: tall {CLR_BORDER_A};
        color: {CLR_TEXT};
    }}

    .mode-btn-active {{
        border: tall {CLR_AMBER};
        color: {CLR_AMBER};
    }}

    .preset-btn {{
        width: 11;
        margin: 0 1 1 0;
        background: {CLR_PANEL};
        border: tall {CLR_BORDER_A};
        color: {CLR_TEXT};
    }}

    .preset-btn:hover {{
        border: tall {CLR_SAGE};
        color: {CLR_AMBER};
    }}

    #params-row {{
        height: auto;
    }}

    .param-col {{
        width: 1fr;
        margin-right: 1;
    }}

    .param-col Static {{
        color: {CLR_MUTED};
        height: auto;
    }}

    #scan-launch-btn {{
        width: 100%;
        margin-top: 1;
        background: {CLR_PANEL};
        border: tall {CLR_SAGE};
        color: {CLR_AMBER};
    }}

    #scan-cancel-btn {{
        width: 100%;
        background: {CLR_PANEL};
        border: tall {CLR_BORDER_A};
        color: {CLR_MUTED};
    }}
    """

    def __init__(self) -> None:
        super().__init__()
        self._mode = "host"

    def compose(self) -> ComposeResult:
        with Vertical(id="scan-setup-box"):
            yield Static(LOGO, id="scan-logo-small", markup=True)
            yield Rule()

            # — Scan mode toggle —
            yield Static(
                f"[{CLR_TEXT}]Scan Mode[/]", classes="scan-section-title", markup=True
            )
            with Horizontal(id="mode-row"):
                yield Button(
                    Text("* Single Host", style=CLR_AMBER),
                    id="mode-host-btn",
                    classes="mode-btn mode-btn-active",
                )
                yield Button(
                    Text("  Network Scan", style=CLR_TEXT),
                    id="mode-net-btn",
                    classes="mode-btn",
                )

            # — Target —
            yield Static(
                f"[{CLR_TEXT}]Target[/]",
                id="target-label",
                classes="scan-section-title",
                markup=True,
            )
            yield Static(
                "[dim]IPv4 address or hostname — e.g. 192.168.1.1 or router.local[/]",
                id="target-hint",
                classes="scan-field-hint",
                markup=True,
            )
            yield Input(placeholder="192.168.1.1", id="scan-ip-input")

            # — Port presets —
            yield Static(
                f"[{CLR_TEXT}]Quick Presets[/]",
                classes="scan-section-title",
                markup=True,
            )
            yield Static(
                "[dim]Click to load a preset into the port field below[/]",
                classes="scan-field-hint",
                markup=True,
            )
            with Horizontal(id="preset-row"):
                for name in PORT_PRESETS:
                    yield Button(
                        Text(name, style=CLR_TEXT),
                        id=f"preset-{name.lower()}",
                        classes="preset-btn",
                    )

            # — Ports —
            yield Static(
                f"[{CLR_TEXT}]Ports[/]", classes="scan-section-title", markup=True
            )
            yield Static(
                "[dim]Comma-separated list or ranges — e.g. 80,443  ·  1-1024  ·  22,8000-8010[/]",
                classes="scan-field-hint",
                markup=True,
            )
            yield Input(
                placeholder="21,22,80,443,554",
                id="scan-ports-input",
                value="21,22,80,443,554",
            )

            # — Timeouts + Concurrency (3-column) —
            yield Static(
                f"[{CLR_TEXT}]Timeouts & Concurrency[/]",
                classes="scan-section-title",
                markup=True,
            )
            with Horizontal(id="params-row"):
                with Vertical(classes="param-col"):
                    yield Static(
                        f"[{CLR_MUTED}]Connect (s)[/]\n[dim]Seconds to wait for TCP handshake (0.1–5.0)[/]",
                        markup=True,
                    )
                    yield Input(
                        placeholder="0.75", id="scan-timeout-input", value="0.75"
                    )
                with Vertical(classes="param-col"):
                    yield Static(
                        f"[{CLR_MUTED}]Banner (s)[/]\n[dim]Wait for protocol response after connect (0.1–2.0)[/]",
                        markup=True,
                    )
                    yield Input(
                        placeholder="0.45", id="scan-banner-input", value="0.45"
                    )
                with Vertical(classes="param-col"):
                    yield Static(
                        f"[{CLR_MUTED}]Slots[/]\n[dim]Max parallel TCP connections (1–512)[/]",
                        markup=True,
                    )
                    yield Input(
                        placeholder="128", id="scan-concurrency-input", value="128"
                    )

            yield Rule()
            yield Button("📡 START SCAN 📡", variant="success", id="scan-launch-btn")
            yield Button("Cancel", id="scan-cancel-btn")

    # ─ Mode toggle ────────────────────────────────────────────
    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        try:
            host_btn = self.query_one("#mode-host-btn", Button)
            net_btn = self.query_one("#mode-net-btn", Button)
            ip_input = self.query_one("#scan-ip-input", Input)
            t_label = self.query_one("#target-label", Static)
            t_hint = self.query_one("#target-hint", Static)
            if mode == "host":
                host_btn.add_class("mode-btn-active")
                net_btn.remove_class("mode-btn-active")
                host_btn.label = Text("* Single Host", style=CLR_AMBER)
                net_btn.label = Text("  Network Scan", style=CLR_TEXT)
                t_label.update(f"[{CLR_TEXT}]Target[/]")
                t_hint.update(
                    "[dim]IPv4 address or hostname — e.g. 192.168.1.1 or router.local[/]"
                )
                ip_input.placeholder = "192.168.1.1"
                ip_input.value = ""
            else:
                net_btn.add_class("mode-btn-active")
                host_btn.remove_class("mode-btn-active")
                host_btn.label = Text("  Single Host", style=CLR_TEXT)
                net_btn.label = Text("* Network Scan", style=CLR_AMBER)
                t_label.update(f"[{CLR_TEXT}]Target Network (CIDR)[/]")
                t_hint.update(
                    "[dim]Subnet in CIDR notation — e.g. 192.168.1.0/24  ·  10.0.0.0/8[/]"
                )
                ip_input.placeholder = "192.168.1.0/24"
                ip_input.value = ""
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "mode-host-btn":
            self._set_mode("host")
        elif bid == "mode-net-btn":
            self._set_mode("network")
        elif bid and bid.startswith("preset-"):
            name_key = bid[len("preset-") :]
            # Normalise: the dict keys are title-cased, button IDs are lowercased
            for key in PORT_PRESETS:
                if key.lower() == name_key:
                    self.query_one("#scan-ports-input", Input).value = PORT_PRESETS[key]
                    break
        elif bid == "scan-launch-btn":
            self._validate_and_launch()
        elif bid == "scan-cancel-btn":
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _validate_and_launch(self) -> None:
        import ipaddress as _ip

        target = self.query_one("#scan-ip-input", Input).value.strip()
        ports_text = self.query_one("#scan-ports-input", Input).value.strip()
        timeout_text = self.query_one("#scan-timeout-input", Input).value.strip()
        banner_text = self.query_one("#scan-banner-input", Input).value.strip()
        concurrency_text = self.query_one(
            "#scan-concurrency-input", Input
        ).value.strip()

        if not target:
            self.notify("Target is required.", severity="error")
            self.query_one("#scan-ip-input", Input).focus()
            return

        if self._mode == "network":
            try:
                _ip.ip_network(target, strict=False)
            except ValueError:
                self.notify(
                    "Invalid CIDR notation — use format: 192.168.1.0/24",
                    severity="error",
                )
                self.query_one("#scan-ip-input", Input).focus()
                return
        else:
            if (
                not valid_ip(target)
                and not target.replace("-", "")
                .replace(".", "")
                .replace("_", "")
                .isalnum()
            ):
                self.notify("Invalid IP address or hostname.", severity="error")
                self.query_one("#scan-ip-input", Input).focus()
                return

        try:
            ports = parse_port_spec(ports_text)
        except ValueError as e:
            self.notify(str(e), severity="error")
            self.query_one("#scan-ports-input", Input).focus()
            return

        if len(ports) > 10000:
            self.notify(
                f"Large scan: {len(ports)} ports. This will take time.",
                severity="warning",
            )

        try:
            timeout = float(timeout_text)
            banner_timeout = float(banner_text)
            concurrency = int(concurrency_text)
            if timeout <= 0 or banner_timeout <= 0 or concurrency < 1:
                raise ValueError
        except ValueError:
            self.notify("Invalid timing or concurrency value.", severity="error")
            return

        self.dismiss(
            {
                "target": target,
                "ports": ports,
                "timeout": timeout,
                "banner_timeout": banner_timeout,
                "concurrency": concurrency,
                "scan_mode": self._mode,
            }
        )


class SettingsModal(ModalScreen[None]):
    """Command-box settings overlay for session defaults."""

    BINDINGS = [Binding("escape", "cancel", "Close")]

    _themes = ["matrix", "blue", "red"]

    DEFAULT_CSS = f"""
    SettingsModal {{
        align: center middle;
        background: {CLR_BG} 85%;
    }}

    #settings-box {{
        width: 60;
        max-height: 90%;
        padding: 1 2;
        border: heavy {CLR_BORDER_A};
        background: {CLR_SURFACE};
        color: {CLR_TEXT};
    }}

    #settings-title {{
        width: 100%;
        text-align: center;
        text-style: bold;
        color: {CLR_AMBER};
        margin-bottom: 1;
    }}

    .setting-row {{
        height: 3;
        margin: 0 0 1 0;
        align: left middle;
    }}

    .setting-label {{
        width: 26;
        color: {CLR_TEXT};
        text-style: bold;
        content-align: left middle;
    }}

    #settings-hint {{
        color: {CLR_MUTED};
        text-align: center;
        margin-top: 1;
    }}

    .mini-btn {{
        width: 20;
        margin: 0 0 0 1;
        background: {CLR_PANEL};
        border: tall {CLR_BORDER_A};
        color: {CLR_AMBER};
    }}

    .mini-btn:hover {{
        border: tall {CLR_AMBER};
        color: {CLR_TEXT};
    }}

    .mini-btn:focus {{
        border: tall {CLR_AMBER};
        color: {CLR_TEXT};
    }}
    """

    def __init__(self) -> None:
        super().__init__()
        self._mode: ViewMode = ViewMode.ADVANCED

    def compose(self) -> ComposeResult:
        # self.app is available during compose (called at mount time)
        self._mode = getattr(self.app, "view_mode", ViewMode.ADVANCED)
        matrix_on = getattr(self.app, "matrix_animation_enabled", True)
        kitt_on = getattr(self.app, "kitt_animation_enabled", True)
        theme_name = getattr(self.app, "theme_preset", "matrix").title()
        with Vertical(id="settings-box"):
            yield Static("[bold]⚙ SETTINGS[/]", id="settings-title", markup=True)
            yield Rule()
            with Horizontal(classes="setting-row"):
                yield Static(
                    f"[{CLR_TEXT}]Default View Mode[/]",
                    classes="setting-label",
                    markup=True,
                )
                yield Button(self._mode.display_name, id="mode-btn", classes="mini-btn")
            with Horizontal(classes="setting-row"):
                yield Static(
                    f"[{CLR_TEXT}]Matrix Animation[/]",
                    classes="setting-label",
                    markup=True,
                )
                yield Button(
                    "ON" if matrix_on else "OFF", id="matrix-btn", classes="mini-btn"
                )
            with Horizontal(classes="setting-row"):
                yield Static(
                    f"[{CLR_TEXT}]KITT Animation[/]",
                    classes="setting-label",
                    markup=True,
                )
                yield Button(
                    "ON" if kitt_on else "OFF", id="kitt-btn", classes="mini-btn"
                )
            with Horizontal(classes="setting-row"):
                yield Static(
                    f"[{CLR_TEXT}]Theme[/]",
                    classes="setting-label",
                    markup=True,
                )
                yield Button(theme_name, id="theme-btn", classes="mini-btn")
            yield Rule()
            yield Static(
                f"[{CLR_MUTED}]changes apply now for this session[/]",
                id="settings-hint",
                markup=True,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button
        if btn.id == "mode-btn":
            self._mode = self._mode.next()
            self.app.view_mode = self._mode
            btn.label = self._mode.display_name
            self.app.notify(
                f"View Mode: {self._mode.display_name}", severity="information"
            )
            self._update_panels()
        elif btn.id == "matrix-btn":
            self.app.matrix_animation_enabled = not getattr(
                self.app, "matrix_animation_enabled", True
            )
            btn.label = "ON" if self.app.matrix_animation_enabled else "OFF"
            for header in self.app.query(HomeHeader):
                header.sync_enabled(self.app.matrix_animation_enabled)
            self.app.notify("Matrix animation toggled", severity="information")
        elif btn.id == "kitt-btn":
            self.app.kitt_animation_enabled = not getattr(
                self.app, "kitt_animation_enabled", True
            )
            btn.label = "ON" if self.app.kitt_animation_enabled else "OFF"
            for scanner in self.app.query(KITTScanner):
                scanner.sync_enabled(self.app.kitt_animation_enabled)
            self.app.notify("KITT animation toggled", severity="information")
        elif btn.id == "theme-btn":
            self._cycle_theme()

    def _cycle_theme(self) -> None:
        themes = ["matrix", "blue", "red"]
        current = getattr(self.app, "theme_preset", "matrix")
        idx = themes.index(current) if current in themes else 0
        next_theme = themes[(idx + 1) % len(themes)]
        self.app.theme_preset = next_theme
        self.app.theme = f"dosping-{next_theme}"
        self.query_one("#theme-btn", Button).label = next_theme.title()
        self.app.notify(f"Theme: {next_theme.title()}", severity="information")

    def _update_panels(self) -> None:
        if isinstance(self.app.screen, SessionScreen):
            self.app.screen.update_status_bar()
            panel = self.app.screen._get_active_panel()
            if panel:
                panel._update_stats()

    def action_cancel(self) -> None:
        self.dismiss(None)


# ═══════════════════════════════════════════════════════════════
#  CHEAT SHEET MODAL
# ═══════════════════════════════════════════════════════════════


class CheatSheetModal(ModalScreen[None]):
    """Overlay showing all keyboard shortcuts."""

    BINDINGS = [Binding("escape", "cancel", "Close")]

    DEFAULT_CSS = f"""
    CheatSheetModal {{
        align: center middle;
        background: {CLR_BG} 80%;
    }}

    #cheat-box {{
        width: 54;
        height: auto;
        border: solid {CLR_LOGO_EDGE};
        background: {CLR_SURFACE};
        padding: 1 2;
        color: {CLR_TEXT};
    }}

    .center {{
        text-align: center;
    }}
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="cheat-box"):
            table = Table(
                title=f"[bold {CLR_TEXT}]DOSPING CHEAT SHEET[/]",
                show_header=False,
                box=box.SIMPLE,
                padding=(0, 2),
            )
            table.add_column("Key", style=f"bold {CLR_AMBER}")
            table.add_column("Action", style=CLR_TEXT)

            table.add_row(f"[{CLR_SAGE}]GENERAL[/]", "")
            table.add_row("Ctrl+P", "Command palette")
            table.add_row("Ctrl+N", "New test tab")
            table.add_row("Ctrl+W", "Close current tab")
            table.add_row("Ctrl+M", "Cycle view mode")
            table.add_row("? / F1", "This cheat sheet")
            table.add_row("q", "Quit")
            table.add_row("", "")
            table.add_row(f"[{CLR_SAGE}]FLOOD CONTROL[/]", "")
            table.add_row("s", "Stop active flood")
            table.add_row("r", "Reset current test")
            table.add_row("", "")
            table.add_row(f"[{CLR_SAGE}]MONITORS[/]", "")
            table.add_row("i", "Toggle ICMP monitor")
            table.add_row("t", "Toggle TCP monitor")
            table.add_row("", "")
            table.add_row(f"[{CLR_SAGE}]LOGS[/]", "")
            table.add_row("e", "Export session log")

            yield Static(table)
            yield Rule()
            yield Static(f"[{CLR_MUTED}]Press ESC to close[/]", classes="center")

    def action_cancel(self) -> None:
        self.dismiss(None)


# ═══════════════════════════════════════════════════════════════
#  ADVANCED / IT PANELS
# ═══════════════════════════════════════════════════════════════


class LatencyGraph(Static):
    """Shows an ASCII sparkline of recent ICMP ping times."""

    DEFAULT_CSS = f"""
    LatencyGraph {{
        height: 4;
        padding: 0 1;
        border-bottom: solid {CLR_BORDER_B};
        background: {CLR_PANEL};
        color: {CLR_SAGE};
    }}
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.history: list[float] = []

    def refresh_graph(self, latencies: list[float], view_mode: ViewMode) -> None:
        if view_mode == ViewMode.SKID:
            self.display = False
            return
        self.display = True

        if not latencies:
            self.update(f"[{CLR_MUTED}]Waiting for latency data...[/]")
            return

        chars = " ▂▃▄▅▆▇█"
        width = self.size.width - 2
        if width < 10:
            width = 30

        data = latencies[-width:]
        if len(data) < width:
            data = [0.0] * (width - len(data)) + data

        m_max = max(data) if data else 0.0
        spark_str = ""
        for v in data:
            if m_max <= 0:
                spark_str += " "
            else:
                idx = int((v / m_max) * 7)
                idx = max(0, min(7, idx))
                spark_str += chars[idx]

        avg = statistics.mean(latencies) if latencies else 0.0
        cur = latencies[-1] if latencies else 0.0

        text = (
            f"[bold {CLR_SAGE}]Latency History[/]  "
            f"[{CLR_MUTED}]Cur:[/] {cur:.1f}ms  "
            f"[{CLR_MUTED}]Avg:[/] {avg:.1f}ms  "
            f"[{CLR_MUTED}]Max:[/] {m_max:.1f}ms\n"
            f"[{CLR_SAGE_DIM}]{spark_str}[/]"
        )
        self.update(text)


class TargetHealthDashboard(Static):
    """Shows consecutive failures and health status."""

    DEFAULT_CSS = f"""
    TargetHealthDashboard {{
        height: 3;
        padding: 0 1;
        border-bottom: solid {CLR_BORDER_B};
        background: {CLR_PANEL};
    }}
    """

    def refresh_health(
        self, icmp_fails: int, tcp_fails: int, view_mode: ViewMode
    ) -> None:
        if view_mode == ViewMode.SKID:
            self.display = False
            return
        self.display = True

        icmp_st = (
            f"[{CLR_BRICK}]{icmp_fails} fails[/]"
            if icmp_fails > 0
            else f"[{CLR_SAGE_DIM}]OK[/]"
        )
        tcp_st = (
            f"[{CLR_BRICK}]{tcp_fails} fails[/]"
            if tcp_fails > 0
            else f"[{CLR_SAGE_DIM}]OK[/]"
        )

        if icmp_fails >= 5 or tcp_fails >= 5:
            status = f"[bold {CLR_BRICK}]DOWN / CRITICAL[/]"
        elif icmp_fails > 0 or tcp_fails > 0:
            status = f"[bold {CLR_OLIVE}]DEGRADED[/]"
        else:
            status = f"[bold {CLR_SAGE_DIM}]HEALTHY[/]"

        text = (
            f"[bold {CLR_AMBER}]Target Health:[/] {status}\n"
            f"  [{CLR_MUTED}]ICMP:[/] {icmp_st}    "
            f"[{CLR_MUTED}]TCP:[/] {tcp_st}"
        )
        self.update(text)


class GeoIPPanel(Static):
    """Shows GeoIP and ASN information (IT mode only)."""

    DEFAULT_CSS = f"""
    GeoIPPanel {{
        height: 2;
        padding: 0 1;
        border-bottom: solid {CLR_BORDER_B};
        background: {CLR_PANEL};
        color: {CLR_TEXT};
    }}
    """

    def __init__(self, target: str, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.target = target
        self._fetched = False

    def refresh_panel(self, view_mode: ViewMode) -> None:
        if view_mode != ViewMode.IT:
            self.display = False
            return
        self.display = True

        if not self._fetched:
            self._fetched = True
            self.update(f"[{CLR_MUTED}]Fetching GeoIP data...[/]")
            self.run_worker(self._fetch_geoip())

    async def _fetch_geoip(self) -> None:
        try:
            resp = await asyncio.to_thread(
                requests.get,
                f"http://ip-api.com/json/{self.target}?fields=status,message,country,city,isp",
                timeout=3,
            )
            data = resp.json()
            if data.get("status") == "success":
                self.update(
                    f"[bold {CLR_SAGE}]Target Info:[/] "
                    f"[{CLR_AMBER}]{data.get('city', 'Unknown')}, {data.get('country', 'Unknown')}[/] • "
                    f"[{CLR_TEXT}]{data.get('isp', 'Unknown ISP')}[/]"
                )
            else:
                self.update(
                    f"[{CLR_BRICK}]GeoIP Failed:[/] {data.get('message', 'Unknown')}"
                )
        except Exception as e:
            self.update(f"[{CLR_BRICK}]GeoIP Error:[/] {e}")


class PortScannerPanel(Static):
    """Background scanner for common ports (IT mode only)."""

    DEFAULT_CSS = f"""
    PortScannerPanel {{
        height: 2;
        padding: 0 1;
        border-bottom: solid {CLR_BORDER_B};
        background: {CLR_PANEL};
        color: {CLR_TEXT};
    }}
    """

    def __init__(self, target: str, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.target = target
        self.open_ports: list[int] = []
        self._scanned = False
        self.COMMON_PORTS = [
            21,
            22,
            23,
            25,
            53,
            80,
            110,
            143,
            443,
            445,
            3306,
            3389,
            8080,
        ]

    def refresh_panel(self, view_mode: ViewMode) -> None:
        if view_mode != ViewMode.IT:
            self.display = False
            return
        self.display = True

        if not self._scanned:
            self._scanned = True
            self.update(f"[{CLR_MUTED}]Scanning common ports...[/]")
            self.run_worker(self._scan_ports())
        else:
            ports_str = (
                ", ".join(map(str, self.open_ports)) if self.open_ports else "None"
            )
            self.update(f"[bold {CLR_SAGE}]Open Ports:[/] [{CLR_AMBER}]{ports_str}[/]")

    async def _scan_ports(self) -> None:
        for port in self.COMMON_PORTS:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.target, port), timeout=0.5
                )
                writer.close()
                await writer.wait_closed()
                self.open_ports.append(port)
                self.refresh_panel(ViewMode.IT)
            except Exception:
                pass


class PacketInspectorPanel(Static):
    """Detailed view of packet data (IT mode only)."""

    DEFAULT_CSS = f"""
    PacketInspectorPanel {{
        height: 2;
        padding: 0 1;
        border-bottom: solid {CLR_BORDER_A};
        background: {CLR_PANEL};
    }}
    """

    def refresh_panel(
        self, view_mode: ViewMode, bytes_sent: int, successful: int
    ) -> None:
        if view_mode != ViewMode.IT:
            self.display = False
            return
        self.display = True

        avg_pkt = (bytes_sent / successful) if successful > 0 else 0
        self.update(
            f"[bold {CLR_AMBER}]Packet Inspector:[/] "
            f"[{CLR_MUTED}]Avg Payload:[/] {avg_pkt:.1f} bytes  "
            f"[{CLR_MUTED}]Raw Stream:[/] Active"
        )


class PortDisplayer(Static):
    """Port Scanner result panel with status circles and device icons."""

    DEFAULT_CSS = f"""
    PortDisplayer {{
        height: 1fr;
        background: {CLR_BG};
        color: {CLR_TEXT};
        padding: 0 1;
    }}
    """

    _icons = {
        "Phone": "📱",
        "TV": "📺",
        "Camera": "📷",
        "Router": "📶",
        "Web Server": "🌐",
        "Server": "🖥",
        "Gaming Console": "🎮",
        "Unknown": "❓",
    }

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.results: list[ScanResult] = []

    def set_results(self, results: list[ScanResult]) -> None:
        self.results = results
        self.refresh_view(getattr(self.app, "view_mode", ViewMode.ADVANCED))

    def refresh_view(self, view_mode: ViewMode) -> None:
        if not self.results:
            self.update(f"[{CLR_MUTED}]waiting for scan results...[/]")
            return

        unique_hosts = list(dict.fromkeys(r.host for r in self.results))
        if len(unique_hosts) > 1:
            self._render_network(unique_hosts, view_mode)
        else:
            self._render_host(view_mode)

    def _render_host(self, view_mode: ViewMode) -> None:
        """Single-host flat list view."""
        total = len(self.results)
        online = sum(1 for r in self.results if r.state == "online")
        accessible = sum(1 for r in self.results if r.state == "accessible")
        offline = sum(1 for r in self.results if r.state == "offline")
        lines = [
            f"[{CLR_BORDER_A}]{'═' * 42}[/]",
            f"[bold {CLR_AMBER}]  PORT SCANNER RESULTS[/]",
            f"[{CLR_BORDER_A}]{'═' * 42}[/]",
            f"  [{CLR_TEXT}]Total:[/] {total}  "
            f"[{CLR_SAGE_DIM}]Online:[/] {online}  "
            f"[{CLR_AMBER}]Accessible:[/] {accessible}  "
            f"[{CLR_BRICK}]Offline:[/] {offline}",
            f"[{CLR_BORDER_A}]{'─' * 42}[/]",
        ]
        for result in self.results:
            color = (
                CLR_SAGE_DIM
                if result.state == "online"
                else CLR_AMBER
                if result.state == "accessible"
                else CLR_BRICK
            )
            icon = self._icons.get(result.device, "❓")
            protocol = result.protocol if view_mode != ViewMode.SKID else ""
            latency = (
                f" {result.latency_ms:.1f}ms" if view_mode != ViewMode.SKID else ""
            )
            lines.append(
                f"  [{color}]●[/] [{CLR_TEXT}]{result.port:>5}[/]  "
                f"[bold]{icon} {result.device:<15}[/]"
                f"[{CLR_MUTED}]{protocol}{latency}[/]"
            )
            if view_mode == ViewMode.IT and result.banner:
                lines.append(f"      [{CLR_MUTED}]banner:[/] {result.banner}")
        self.update("\n".join(lines))

    def _render_network(self, unique_hosts: list[str], view_mode: ViewMode) -> None:
        """Multi-host grouped view for network scans."""
        import ipaddress as _ip

        by_host: dict[str, list[ScanResult]] = {}
        for r in self.results:
            by_host.setdefault(r.host, []).append(r)

        def _host_key(h: str):
            try:
                return _ip.ip_address(h)
            except ValueError:
                return h

        total_ports = len(self.results)
        total_hosts = len(by_host)
        lines = [
            f"[{CLR_BORDER_A}]{'═' * 42}[/]",
            f"[bold {CLR_AMBER}]  NETWORK SCAN RESULTS[/]",
            f"[{CLR_BORDER_A}]{'═' * 42}[/]",
            f"  [{CLR_TEXT}]Active Hosts:[/] [{CLR_SAGE_DIM}]{total_hosts}[/]   "
            f"[{CLR_TEXT}]Open Ports:[/] [{CLR_AMBER}]{total_ports}[/]",
            f"[{CLR_BORDER_A}]{'─' * 42}[/]",
        ]
        for host in sorted(by_host.keys(), key=_host_key):
            results = sorted(by_host[host], key=lambda r: r.port)
            lines.append(
                f"[bold {CLR_AMBER}]  ● {host}[/]  [{CLR_MUTED}]({len(results)} ports)[/]"
            )
            for result in results:
                color = (
                    CLR_SAGE_DIM
                    if result.state == "online"
                    else CLR_AMBER
                    if result.state == "accessible"
                    else CLR_BRICK
                )
                icon = self._icons.get(result.device, "❓")
                detail = (
                    ""
                    if view_mode == ViewMode.SKID
                    else (
                        f" [{CLR_MUTED}]{result.protocol} {result.latency_ms:.0f}ms[/]"
                    )
                )
                lines.append(
                    f"    [{color}]●[/] [{CLR_TEXT}]{result.port:>5}[/]  "
                    f"[bold]{icon} {result.device:<13}[/]{detail}"
                )
                if view_mode == ViewMode.IT and result.banner:
                    lines.append(f"        [{CLR_MUTED}]banner:[/] {result.banner}")
        self.update("\n".join(lines))


class ScanStatsPanel(Static):
    """Right sidebar for scan sessions."""

    DEFAULT_CSS = f"""
    ScanStatsPanel {{
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
        results: list[ScanResult],
        elapsed: float,
        view_mode: ViewMode,
    ) -> None:
        total = len(results)
        online = sum(1 for r in results if r.state == "online")
        accessible = sum(1 for r in results if r.state == "accessible")
        offline = sum(1 for r in results if r.state == "offline")
        dur = _format_duration(elapsed)
        if view_mode == ViewMode.SKID:
            lines = [
                f"[{CLR_BORDER_A}]{'━' * 22}[/]",
                f"[bold {CLR_AMBER}]  SCAN STATS[/]",
                f"[{CLR_BORDER_A}]{'━' * 22}[/]",
                f" [{CLR_MUTED}]Total  [/] [{CLR_TEXT}]{total:>7}[/]",
                f" [{CLR_SAGE_DIM}]Open   [/] [{CLR_TEXT}]{online:>7}[/]",
                f" [{CLR_AMBER}]Access [/] [{CLR_TEXT}]{accessible:>7}[/]",
                f" [{CLR_BRICK}]Closed [/] [{CLR_TEXT}]{offline:>7}[/]",
                f" [{CLR_MUTED}]Time   [/] [{CLR_TEXT}]{dur:>7}[/]",
            ]
        else:
            lines = [
                f"[{CLR_BORDER_A}]{'━' * 22}[/]",
                f"[bold {CLR_AMBER}]  SCAN STATS[/]",
                f"[{CLR_BORDER_A}]{'━' * 22}[/]",
                f" [{CLR_TEXT}]Total  [/] [{CLR_TEXT}]{total:>7}[/]",
                f" [{CLR_SAGE_DIM}]Online [/] [{CLR_TEXT}]{online:>7}[/]",
                f" [{CLR_AMBER}]Access [/] [{CLR_TEXT}]{accessible:>7}[/]",
                f" [{CLR_BRICK}]Closed [/] [{CLR_TEXT}]{offline:>7}[/]",
                f" [{CLR_MUTED}]Elapsed[/] [{CLR_TEXT}]{dur:>7}[/]",
                "",
                f"[{CLR_BORDER_A}]{'━' * 22}[/]",
                f"[bold {CLR_AMBER}]  MONITORS[/]",
                f"[{CLR_BORDER_A}]{'━' * 22}[/]",
                f" [{CLR_MUTED}]ICMP   [/] [{('ON' if self._icmp_on else 'OFF'):>7}]",
                f" [{CLR_MUTED}]TCP    [/] [{('ON' if self._tcp_on else 'OFF'):>7}]",
            ]
        self.update("\n".join(lines))

    def set_monitor_state(self, icmp_on: bool, tcp_on: bool) -> None:
        self._icmp_on = icmp_on
        self._tcp_on = tcp_on


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
        self.peak_cps: float = 0.0
        self.latency_history: list[float] = []
        self.consecutive_icmp_fails: int = 0
        self.consecutive_tcp_fails: int = 0

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
                yield PacketInspectorPanel(id="packet-inspector")
                yield RichLog(classes="flood-log", highlight=True, markup=True)
                yield ProgressBar(classes="progress-bar", total=self.bots)
                yield KITTScanner(bar_width=50, classes="attack-scanner")

            # ── CENTER: Live connectivity monitor ────────────
            with Vertical(classes="ping-container"):
                yield Static(
                    f"📡 CONNECTIVITY ── {self.target}",
                    classes="panel-header-ping",
                )
                yield TargetHealthDashboard(id="target-health")
                yield LatencyGraph(id="latency-graph")
                yield GeoIPPanel(self.target, id="geoip-panel")
                yield PortScannerPanel(self.target, id="port-scanner")
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

                    # Extract latency
                    m = re.search(r"time[=<]([0-9.]+)", lower)
                    if m:
                        try:
                            latency = float(m.group(1))
                            self.latency_history.append(latency)
                            if len(self.latency_history) > 100:
                                self.latency_history.pop(0)
                        except ValueError:
                            pass

                    if "reply from" in lower or "bytes from" in lower:
                        self.consecutive_icmp_fails = 0
                        self._log_ping(f"[{CLR_SAGE_DIM}]  [ICMP] ● {decoded}[/]")
                    elif "timed out" in lower or "unreachable" in lower:
                        self.consecutive_icmp_fails += 1
                        self._log_ping(
                            f"[{CLR_OLIVE}]  [ICMP] ⚠ {decoded} "
                            f"[{CLR_MUTED}](ICMP may be blocked)[/]"
                        )
                    elif "pinging" in lower or "ping" in lower:
                        self._log_ping(f"[{CLR_SAGE}]  [ICMP] ▸ {decoded}[/]")
                    else:
                        self._log_ping(f"[{CLR_MUTED}]  [ICMP] {decoded}[/]")
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
                    self.consecutive_tcp_fails = 0
                    latency_ms = (time.monotonic() - t_start) * 1000
                    self._log_ping(
                        f"[{CLR_SAGE_DIM}]  [TCP:{port}] ● OPEN[/] "
                        f"[{CLR_MUTED}]({latency_ms:.1f}ms) #{probe_num}[/]"
                    )
                except asyncio.TimeoutError:
                    self.consecutive_tcp_fails += 1
                    self._log_ping(
                        f"[{CLR_BRICK}]  [TCP:{port}] ✖ TIMEOUT[/] "
                        f"[{CLR_MUTED}]#{probe_num}[/]"
                    )
                except OSError as e:
                    self.consecutive_tcp_fails += 1
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
                    self.consecutive_tcp_fails += 1
                    self._log_ping(f"[{CLR_BRICK}]  [TCP:{port}] Error: {e}[/]")
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
        self._log_flood(f"  [{CLR_MUTED}]Target      :[/] [{CLR_TEXT}]{self.target}[/]")
        self._log_flood(
            f"  [{CLR_MUTED}]Ports       :[/] "
            f"[{CLR_TEXT}]{', '.join(map(str, self.ports))}[/]"
        )
        self._log_flood(f"  [{CLR_MUTED}]Bots        :[/] [{CLR_TEXT}]{self.bots}[/]")
        self._log_flood(f"  [{CLR_MUTED}]Concurrency :[/] [{CLR_TEXT}]50[/]")
        self._log_flood("")

        await self.flooder.run()

        # ── Post-flood summary ───────────────────────────────
        self._log_flood("")
        self._log_flood(f"[{CLR_BORDER_B}]{'═' * 42}[/]")
        self._log_flood(f"[bold {CLR_SAGE}]  FLOOD COMPLETE[/]")
        self._log_flood(f"[{CLR_BORDER_B}]{'═' * 42}[/]")
        self._log_flood(
            f"  [{CLR_SAGE_DIM}]Connected :[/] [{CLR_TEXT}]{self.flooder.successful}[/]"
        )
        self._log_flood(
            f"  [{CLR_BRICK}]Failed    :[/] [{CLR_TEXT}]{self.flooder.failed}[/]"
        )

        scanner.show_complete()
        self._is_running = False

        # ── HTTP health check ────────────────────────────────
        self._log_flood("")
        self._log_flood(f"[{CLR_MUTED}]Running HTTP health check...[/]")
        try:
            resp = requests.head(f"http://{self.target}", timeout=3)
            self._log_flood(f"[{CLR_SAGE_DIM}]  ● HTTP {resp.status_code}[/]")
        except requests.RequestException:
            self._log_flood(f"[{CLR_BRICK}]  ✖ HTTP check failed[/]")

    # ═════════════════════════════════════════════════════════
    #  Stats timer
    # ═════════════════════════════════════════════════════════

    def _update_stats(self) -> None:
        try:
            if self.flooder:
                cps = self.flooder.connections_per_sec()
                self.peak_cps = max(self.peak_cps, cps)

            panel = self.query_one(StatsPanel)
            view_mode = getattr(self.app, "view_mode", ViewMode.ADVANCED)
            panel.refresh_stats(
                self.flooder,
                self.start_time,
                self.icmp_enabled,
                self.tcp_enabled,
                self.peak_cps,
                view_mode,
            )

            try:
                self.query_one("#target-health", TargetHealthDashboard).refresh_health(
                    self.consecutive_icmp_fails, self.consecutive_tcp_fails, view_mode
                )
                self.query_one("#latency-graph", LatencyGraph).refresh_graph(
                    self.latency_history, view_mode
                )
                self.query_one("#geoip-panel", GeoIPPanel).refresh_panel(view_mode)
                self.query_one("#port-scanner", PortScannerPanel).refresh_panel(
                    view_mode
                )

                if self.flooder:
                    self.query_one(
                        "#packet-inspector", PacketInspectorPanel
                    ).refresh_panel(
                        view_mode, self.flooder.bytes_sent, self.flooder.successful
                    )
            except Exception:
                pass
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
                f.write(f"Ports: {', '.join(map(str, self.ports))}\n")
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


class ScanSessionPanel(Vertical):
    """A complete port scan session: scanner + ping + stats."""

    DEFAULT_CSS = f"""
    ScanSessionPanel {{
        height: 1fr;
    }}

    .scan-panels {{
        height: 1fr;
    }}

    .scan-container {{
        width: 1fr;
        border: heavy {CLR_BORDER_A};
        margin: 0 1 0 0;
        background: {CLR_PANEL};
    }}

    .ping-container-scan {{
        width: 1fr;
        border: heavy {CLR_BORDER_B};
        background: {CLR_PANEL};
        margin: 0 1 0 0;
    }}

    .scan-header {{
        text-align: center;
        text-style: bold;
        padding: 0 1;
        background: {CLR_HEADER_A};
        color: {CLR_AMBER};
        border-bottom: solid {CLR_BORDER_A};
    }}

    .ping-log-scan {{
        height: 1fr;
        background: {CLR_BG};
        color: {CLR_TEXT};
    }}
    """

    def __init__(
        self,
        target: str,
        ports: list[int],
        timeout: float,
        banner_timeout: float,
        concurrency: int,
        scan_mode: str = "host",
    ) -> None:
        super().__init__()
        self.target = target
        self.ports = ports
        self.timeout = timeout
        self.banner_timeout = banner_timeout
        self.concurrency = concurrency
        self.scan_mode = scan_mode  # "host" or "network"
        self.ping_process: asyncio.subprocess.Process | None = None
        self.start_time: float = 0.0
        self.icmp_enabled: bool = True
        self.tcp_enabled: bool = True
        self.results: list[ScanResult] = []
        self._stats_timer = None

    def compose(self) -> ComposeResult:
        displayer_header = (
            f"🌐 NETWORK SCAN ── {self.target}"
            if self.scan_mode == "network"
            else f"📡 PORT DISPLAYER ── {self.target}"
        )
        with Horizontal(classes="scan-panels"):
            with Vertical(classes="scan-container"):
                yield Static(displayer_header, classes="scan-header")
                yield PortDisplayer(id="port-displayer")
            with Vertical(classes="ping-container-scan"):
                yield Static(
                    f"📡 CONNECTIVITY ── {self.target}",
                    classes="scan-header",
                )
                yield TargetHealthDashboard(id="target-health")
                yield LatencyGraph(id="latency-graph")
                yield GeoIPPanel(self.target, id="geoip-panel")
                yield RichLog(
                    classes="ping-log-scan",
                    highlight=True,
                    markup=True,
                    auto_scroll=True,
                )
            yield ScanStatsPanel(id="scan-stats")

    def on_mount(self) -> None:
        self.start_time = time.time()
        self._stats_timer = self.set_interval(1.0, self._update_stats)
        self._start_ping()
        self._start_scan()

    def _log_ping(self, msg: str) -> None:
        try:
            self.query_one(".ping-log-scan", RichLog).write(msg)
        except Exception:
            pass

    @work(exclusive=True, group="scan")
    async def _start_scan(self) -> None:
        self._log_ping(f"[{CLR_BORDER_A}]{'─' * 44}[/]")
        self._log_ping(
            f"[bold {CLR_AMBER}]  "
            + (
                "NETWORK SCAN ENGINE"
                if self.scan_mode == "network"
                else "PORT SCANNER ENGINE"
            )
            + "[/]"
        )
        self._log_ping(f"[{CLR_BORDER_A}]{'─' * 44}[/]")
        self._log_ping(f"  [{CLR_TEXT}]Target      :[/] [{CLR_TEXT}]{self.target}[/]")
        self._log_ping(
            f"  [{CLR_TEXT}]Mode        :[/] [{CLR_TEXT}]{self.scan_mode.upper()}[/]"
        )
        self._log_ping(
            f"  [{CLR_TEXT}]Ports       :[/] [{CLR_TEXT}]{len(self.ports)} selected[/]"
        )
        self._log_ping(
            f"  [{CLR_TEXT}]Concurrency :[/] [{CLR_TEXT}]{self.concurrency}[/]"
        )
        self._log_ping(f"  [{CLR_MUTED}]Scanning...[/]")

        if self.scan_mode == "network":
            engine: NetworkScanEngine | PortScannerEngine = NetworkScanEngine(
                subnet=self.target,
                ports=self.ports,
                timeout=self.timeout,
                banner_timeout=self.banner_timeout,
                concurrency=self.concurrency,
            )
        else:
            engine = PortScannerEngine(
                host=self.target,
                ports=self.ports,
                timeout=self.timeout,
                banner_timeout=self.banner_timeout,
                concurrency=self.concurrency,
            )
        self.results = await engine.scan()
        if self.scan_mode == "network":
            unique_hosts = len({r.host for r in self.results})
            self._log_ping(
                f"  [{CLR_SAGE_DIM}]Scan complete:[/] "
                f"{unique_hosts} active hosts, {len(self.results)} open ports"
            )
        else:
            self._log_ping(
                f"  [{CLR_SAGE_DIM}]Scan complete:[/] {len(self.results)} ports checked"
            )
        self.query_one("#port-displayer", PortDisplayer).set_results(self.results)

    @work(exclusive=True, group="ping")
    async def _start_ping(self) -> None:
        self._log_ping(f"[{CLR_BORDER_A}]{'─' * 44}[/]")
        self._log_ping(f"[bold {CLR_AMBER}]  CONNECTIVITY MONITOR[/]")
        self._log_ping(f"[{CLR_BORDER_A}]{'─' * 44}[/]")
        if self.scan_mode == "network":
            self._log_ping(
                f"  [{CLR_MUTED}]Connectivity monitor skipped in network scan mode.[/]"
            )
            return
        await asyncio.gather(
            self._icmp_loop(),
            self._tcp_loop(),
        )

    async def _icmp_loop(self) -> None:
        while True:
            if not self.icmp_enabled:
                await asyncio.sleep(1.0)
                continue
            cmd = (
                ["ping", "-t", self.target]
                if platform.system().lower() == "windows"
                else ["ping", self.target]
            )
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
                    decoded = line.decode(errors="replace").strip()
                    if not decoded:
                        continue
                    lower = decoded.lower()
                    m = re.search(r"time[=<]([0-9.]+)", lower)
                    if m:
                        try:
                            latency = float(m.group(1))
                            graph = self.query_one("#latency-graph", LatencyGraph)
                            graph.history.append(latency)
                            if len(graph.history) > 100:
                                graph.history.pop(0)
                        except ValueError:
                            pass
                    if "reply from" in lower or "bytes from" in lower:
                        self._log_ping(f"[{CLR_SAGE_DIM}]  [ICMP] ● {decoded}[/]")
                    elif "timed out" in lower or "unreachable" in lower:
                        self._log_ping(f"[{CLR_OLIVE}]  [ICMP] ⚠ {decoded}[/]")
                    else:
                        self._log_ping(f"[{CLR_MUTED}]  [ICMP] {decoded}[/]")
            except Exception as e:
                self._log_ping(f"[{CLR_BRICK}]  [ICMP] Error: {e}[/]")
            await asyncio.sleep(1.0)

    async def _tcp_loop(self) -> None:
        probe_num = 0
        while True:
            if not self.tcp_enabled:
                await asyncio.sleep(1.0)
                continue
            probe_num += 1
            for port in self.ports[:8]:
                t_start = time.monotonic()
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self.target, port),
                        timeout=min(1.5, self.timeout),
                    )
                    writer.close()
                    await writer.wait_closed()
                    latency_ms = (time.monotonic() - t_start) * 1000
                    self._log_ping(
                        f"[{CLR_SAGE_DIM}]  [TCP:{port}] ● OPEN[/] "
                        f"[{CLR_MUTED}]({latency_ms:.1f}ms) #{probe_num}[/]"
                    )
                except Exception as e:
                    self._log_ping(
                        f"[{CLR_BRICK}]  [TCP:{port}] ✖ {type(e).__name__}[/]"
                    )
            await asyncio.sleep(3.0)

    def _update_stats(self) -> None:
        try:
            view_mode = getattr(self.app, "view_mode", ViewMode.ADVANCED)
            elapsed = time.time() - self.start_time if self.start_time else 0
            self.query_one("#port-displayer", PortDisplayer).refresh_view(view_mode)
            stats = self.query_one("#scan-stats", ScanStatsPanel)
            stats.set_monitor_state(self.icmp_enabled, self.tcp_enabled)
            stats.refresh_stats(self.results, elapsed, view_mode)
            try:
                health = self.query_one("#target-health", TargetHealthDashboard)
                graph = self.query_one("#latency-graph", LatencyGraph)
                health.refresh_health(0, 0, view_mode)
                graph.refresh_graph(graph.history, view_mode)
                self.query_one("#geoip-panel", GeoIPPanel).refresh_panel(view_mode)
            except Exception:
                pass
        except Exception:
            pass

    def toggle_icmp(self) -> None:
        self.icmp_enabled = not self.icmp_enabled
        if not self.icmp_enabled:
            self._kill_ping()
        self.app.notify(
            f"ICMP monitor {'enabled' if self.icmp_enabled else 'disabled'}"
        )

    def toggle_tcp(self) -> None:
        self.tcp_enabled = not self.tcp_enabled
        self.app.notify(f"TCP monitor {'enabled' if self.tcp_enabled else 'disabled'}")

    def export_log(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dosping_scan_{self.target}_{timestamp}.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("DOSping Port Scan Log\n")
                f.write(f"Target: {self.target}\n")
                f.write(f"Ports: {', '.join(map(str, self.ports))}\n")
                f.write(f"{'=' * 50}\n\n")
                for result in self.results:
                    f.write(
                        f"{result.port} | {result.state} | "
                        f"{result.protocol} | {result.device} | "
                        f"{result.latency_ms:.1f}ms\n"
                    )
                    if result.banner:
                        f.write(f"banner: {result.banner}\n")
            self.app.notify(f"Exported: {filename}", severity="information")
        except OSError as e:
            self.app.notify(f"Export failed: {e}", severity="error")

    def clear_ping_log(self) -> None:
        try:
            self.query_one(".ping-log-scan", RichLog).clear()
        except Exception:
            pass

    def _kill_ping(self) -> None:
        if self.ping_process:
            try:
                self.ping_process.kill()
            except ProcessLookupError:
                pass
            self.ping_process = None

    def cleanup(self) -> None:
        self._kill_ping()
        if self._stats_timer:
            self._stats_timer.stop()
            self._stats_timer = None


class ScanTabPane(TabPane):
    """A TabPane wrapping a single ScanSessionPanel."""

    def __init__(
        self,
        target: str,
        ports: list[int],
        timeout: float,
        banner_timeout: float,
        concurrency: int,
        scan_mode: str = "host",
        label: str = "",
        **kwargs,
    ) -> None:
        super().__init__(label, **kwargs)
        self._target = target
        self._ports = ports
        self._timeout = timeout
        self._banner_timeout = banner_timeout
        self._concurrency = concurrency
        self._scan_mode = scan_mode

    def compose(self) -> ComposeResult:
        yield ScanSessionPanel(
            self._target,
            self._ports,
            self._timeout,
            self._banner_timeout,
            self._concurrency,
            scan_mode=self._scan_mode,
        )


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
        Binding("ctrl+shift+n", "new_scan", "New Scan"),
        Binding("ctrl+w", "close_tab", "Close Tab"),
        Binding("s", "stop_flood", "Stop Flood"),
        Binding("r", "reset_test", "Reset Test"),
        Binding("i", "toggle_icmp", "Toggle ICMP"),
        Binding("t", "toggle_tcp", "Toggle TCP"),
        Binding("e", "export_log", "Export Log"),
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
        height: 1;
        padding: 0 1;
        background: {CLR_SURFACE};
        color: {CLR_MUTED};
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

    def __init__(
        self,
        mode: SessionMode = SessionMode.ATTACK,
        auto_start: bool = False,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.auto_start = auto_start
        self._spinner_idx = 0
        self._spinner_timer = None

    def _build_status_text(self) -> str:
        mode_name = getattr(self.app, "view_mode", ViewMode.ADVANCED).display_name
        session_name = "SCAN" if self.mode == SessionMode.SCAN else "ATTACK"
        return (
            f"  [{CLR_MUTED}]Mode:[/] [{CLR_AMBER}]{mode_name}[/]  "
            f"[{CLR_MUTED}]Session:[/] [{CLR_SAGE_DIM}]{session_name}[/]  "
            f"[{CLR_MUTED}]Ctrl+M[/] [{CLR_TEXT}]cycle[/]  "
            f"[{CLR_MUTED}]?[/] [{CLR_TEXT}]help[/]  "
            f"[{CLR_MUTED}]Ctrl+N[/] [{CLR_TEXT}]new test[/]  "
            f"[{CLR_MUTED}]Ctrl+Shift+N[/] [{CLR_TEXT}]new scan[/]  "
            f"[{CLR_MUTED}]Ctrl+W[/] [{CLR_TEXT}]close tab[/]  "
            f"[{CLR_MUTED}]Ctrl+P[/] [{CLR_TEXT}]commands[/]  "
            f"[{CLR_MUTED}]s[/] [{CLR_TEXT}]stop[/]  "
            f"[{CLR_MUTED}]q[/] [{CLR_TEXT}]quit[/]"
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield TabbedContent(id="session-tabs")
        yield Static(
            self._build_status_text(),
            classes="session-status",
            id="status-bar",
        )

    def update_status_bar(self) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
            bar.update(self._build_status_text())
        except Exception:
            pass

    def on_mount(self) -> None:
        # Start spinner animation for tab labels
        self._spinner_timer = self.set_interval(1 / 10, self._tick_spinners)
        if self.auto_start:
            self.set_timer(
                0.2,
                self.action_new_test
                if self.mode == SessionMode.ATTACK
                else self.action_new_scan,
            )

    # ── Tab management ───────────────────────────────────────

    def action_new_test(self) -> None:
        if self._tab_count() >= MAX_TABS:
            self.notify(f"Max {MAX_TABS} concurrent tests", severity="warning")
            return
        self.app.push_screen(SetupModal(), callback=self._on_setup)

    def _on_setup(self, result: dict | None) -> None:
        if result is not None:
            self._add_test(result["target"], result["ports"], result["bots"])
        elif self._tab_count() == 0:
            # Cancelled with no active sessions — go back to Home Screen
            self.app.pop_screen()

    def action_new_scan(self) -> None:
        if self._tab_count() >= MAX_TABS:
            self.notify(f"Max {MAX_TABS} concurrent tests", severity="warning")
            return
        self.app.push_screen(ScannerSetupModal(), callback=self._on_scan_setup)

    def _on_scan_setup(self, result: dict | None) -> None:
        if result is not None:
            self._add_scan(
                result["target"],
                result["ports"],
                result["timeout"],
                result["banner_timeout"],
                result["concurrency"],
                result.get("scan_mode", "host"),
            )
        elif self._tab_count() == 0:
            # Cancelled with no active sessions — go back to Home Screen
            self.app.pop_screen()

    def _add_test(self, target: str, ports: list[int], bots: int) -> None:
        SessionScreen._tab_counter += 1
        tab_id = f"tab-{SessionScreen._tab_counter}"

        port_str = (
            f":{ports[0]}" if len(ports) == 1 else f" ({','.join(map(str, ports))})"
        )
        label = f"● {target}{port_str}"

        pane = TestTabPane(target, ports, bots, label=label, id=tab_id)
        tc = self.query_one("#session-tabs", TabbedContent)
        tc.add_pane(pane)
        tc.active = tab_id

    def _add_scan(
        self,
        target: str,
        ports: list[int],
        timeout: float,
        banner_timeout: float,
        concurrency: int,
        scan_mode: str = "host",
    ) -> None:
        SessionScreen._tab_counter += 1
        tab_id = f"scan-{SessionScreen._tab_counter}"
        port_str = f":{ports[0]}" if len(ports) == 1 else f" ({len(ports)} ports)"
        icon = "🌐" if scan_mode == "network" else "📡"
        label = f"{icon} {target}{port_str}"
        pane = ScanTabPane(
            target,
            ports,
            timeout,
            banner_timeout,
            concurrency,
            scan_mode=scan_mode,
            label=label,
            id=tab_id,
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
            try:
                pane = tc.query_one(f"#{active}", TabPane)
                panel = pane.query_one(ScanSessionPanel)
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
                f":{panel.ports[0]}"
                if len(panel.ports) == 1
                else f" ({','.join(map(str, panel.ports))})"
            )

            if panel._is_running:
                new_label = f"{char} {panel.target}{port_str}"
            else:
                new_label = f"✓ {panel.target}{port_str}"

            tab_id = f"--content-tab-{pane.id}"
            try:
                tab_widget = tc.query_one(f"#{tab_id}")
                tab_widget.label = new_label
            except Exception:
                pass

        for pane in tc.query(ScanTabPane):
            try:
                panel = pane.query_one(ScanSessionPanel)
            except Exception:
                continue

            port_str = (
                f":{panel.ports[0]}"
                if len(panel.ports) == 1
                else f" ({len(panel.ports)} ports)"
            )
            new_label = f"{char} {panel.target}{port_str}"
            tab_id = f"--content-tab-{pane.id}"
            try:
                tab_widget = tc.query_one(f"#{tab_id}")
                tab_widget.label = new_label
            except Exception:
                pass

    # ── Actions ──────────────────────────────────────────────

    def action_stop_flood(self) -> None:
        panel = self._get_active_panel()
        if isinstance(panel, TestPanel):
            panel.stop_flood()
            self.notify("Stop signal sent.", severity="warning")
        elif isinstance(panel, ScanSessionPanel):
            self.notify(
                "Scan sessions do not use flood control.", severity="information"
            )

    def action_reset_test(self) -> None:
        panel = self._get_active_panel()
        if isinstance(panel, TestPanel):
            panel.reset()
            self.notify("Test reset.", severity="information")
        elif isinstance(panel, ScanSessionPanel):
            self.notify(
                "Restart the scan from the home screen.", severity="information"
            )

    def action_toggle_icmp(self) -> None:
        panel = self._get_active_panel()
        if panel:
            panel.toggle_icmp()

    def action_toggle_tcp(self) -> None:
        panel = self._get_active_panel()
        if panel:
            panel.toggle_tcp()

    def action_export_log(self) -> None:
        panel = self._get_active_panel()
        if panel:
            panel.export_log()

    def action_quit_app(self) -> None:
        # Save stats from the active panel
        panel = self._get_active_panel()
        if isinstance(panel, TestPanel):
            self.app.session_stats = panel.get_stats()

        # Cleanup all tabs
        tc = self.query_one("#session-tabs", TabbedContent)
        for pane in tc.query(TestTabPane):
            try:
                p = pane.query_one(TestPanel)
                p.cleanup()
            except Exception:
                pass
        for pane in tc.query(ScanTabPane):
            try:
                p = pane.query_one(ScanSessionPanel)
                p.cleanup()
            except Exception:
                pass

        self.app.exit()

    def _get_active_panel(self) -> TestPanel | ScanSessionPanel | None:
        tc = self.query_one("#session-tabs", TabbedContent)
        active = tc.active
        if not active:
            return None
        try:
            pane = tc.query_one(f"#{active}", TabPane)
            return pane.query_one(TestPanel)
        except Exception:
            try:
                pane = tc.query_one(f"#{active}", TabPane)
                return pane.query_one(ScanSessionPanel)
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
                "Switch to Skid Mode",
                "Minimal view",
                self._switch_mode_skid,
            ),
            (
                "Switch to Advanced Mode",
                "Standard view",
                self._switch_mode_advanced,
            ),
            (
                "Switch to IT Mode",
                "Full density view",
                self._switch_mode_it,
            ),
            (
                "Cycle View Mode",
                "Rotate through modes (Ctrl+M)",
                self._cycle_view_mode,
            ),
            (
                "Cheat Sheet",
                "Show keybinds overlay (?)",
                self._show_cheat_sheet,
            ),
            (
                "New Test",
                "Start a new test in a new tab (Ctrl+N)",
                self._new_test,
            ),
            (
                "New Scan",
                "Start a new port scan in a new tab (Ctrl+Shift+N)",
                self._new_scan,
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

    def _get_panel(self) -> TestPanel | ScanSessionPanel | None:
        session = self._get_session()
        if session:
            return session._get_active_panel()
        return None

    def _update_stats_if_possible(self) -> None:
        p = self._get_panel()
        if p:
            p._update_stats()

    async def _switch_mode_skid(self) -> None:
        self.app.view_mode = ViewMode.SKID
        self.app.notify("View Mode: Skid", severity="information")
        self._update_stats_if_possible()

    async def _switch_mode_advanced(self) -> None:
        self.app.view_mode = ViewMode.ADVANCED
        self.app.notify("View Mode: Advanced", severity="information")
        self._update_stats_if_possible()

    async def _switch_mode_it(self) -> None:
        self.app.view_mode = ViewMode.IT
        self.app.notify("View Mode: IT", severity="information")
        self._update_stats_if_possible()

    async def _cycle_view_mode(self) -> None:
        self.app.action_cycle_view_mode()

    async def _show_cheat_sheet(self) -> None:
        self.app.action_show_cheat_sheet()

    async def _new_test(self) -> None:
        s = self._get_session()
        if s:
            s.action_new_test()

    async def _new_scan(self) -> None:
        s = self._get_session()
        if s:
            s.action_new_scan()

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
            "docs",
            "index.html",
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
                    "gnome-terminal",
                    "xfce4-terminal",
                    "konsole",
                    "xterm",
                ]:
                    try:
                        subprocess.Popen([term])
                        return
                    except FileNotFoundError:
                        continue
                self.app.notify("No terminal emulator found", severity="warning")
        except Exception as e:
            self.app.notify(f"Failed to open terminal: {e}", severity="error")


# ═══════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════


class DOSPingApp(App):
    """DOSping v3.5 — Network Stress Testing TUI."""

    TITLE = "DOSping"
    SUB_TITLE = "Network Stress Tester v3.5"

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
        Binding("ctrl+m", "cycle_view_mode", "Cycle View Mode"),
        Binding("?", "show_cheat_sheet", "Cheat Sheet"),
        Binding("f1", "show_cheat_sheet", "Cheat Sheet"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session_stats: dict = {}
        self.view_mode = ViewMode.ADVANCED
        self.animations_enabled = True
        self.matrix_animation_enabled = True
        self.kitt_animation_enabled = True
        self.theme_preset = "matrix"

    def action_cycle_view_mode(self) -> None:
        self.view_mode = self.view_mode.next()
        self.notify(f"View Mode: {self.view_mode.display_name}", severity="information")
        # Notify active panel if there is one
        if isinstance(self.screen, SessionScreen):
            self.screen.update_status_bar()
            panel = self.screen._get_active_panel()
            if panel:
                panel._update_stats()

    def action_show_cheat_sheet(self) -> None:
        self.push_screen(CheatSheetModal())

    def on_mount(self) -> None:
        self.register_theme(THEME_DOSPING_MATRIX)
        self.register_theme(THEME_DOSPING_BLUE)
        self.register_theme(THEME_DOSPING_RED)
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
        show_header=False,
        show_edge=False,
        pad_edge=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column("key", style=CLR_MUTED, no_wrap=True)
    table.add_column("val", style=CLR_TEXT)

    table.add_row("Target", stats.get("target", "—"))
    table.add_row("Ports", ", ".join(map(str, stats.get("ports", []))))
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
