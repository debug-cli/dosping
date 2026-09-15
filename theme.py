# ═══════════════════════════════════════════════════════════════
#  theme.py  —  DOSping 3.7.0 "Code Red" Theme Layer
# ═══════════════════════════════════════════════════════════════
#  Semantic colour layer for the whole TUI.  Every screen/widget
#  references THEME["accent"], THEME["text"], THEME["dim"], etc.
#  — never hardcoded escapes — so swapping themes is trivial.
#
#  Design:
#    • Base       — monochrome (white / light grey on black)
#    • Accent     — red for active elements, borders, highlights
#    • Background — fully transparent via Textual's `transparent`
#                   colour so blur-enabled terminals (e.g. Windows
#                   Terminal with acrylic) show the desktop natively.
#                   The ONLY opaque surface is the command/hint bar.
#
#  FOR PENETRATION TESTING / EDUCATIONAL PURPOSES ONLY.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

from typing import Dict

# ── Monochrome + red palette ──────────────────────────────────

RED = "#ff3333"
RED_DIM = "#a02020"
RED_DARK = "#5a1414"
RED_GLOW = "#ff5544"

WHITE = "#f2f2f2"
BRIGHT_WHITE = "#ffffff"
LIGHT_GREY = "#c8c8c8"
GREY = "#8a8a8a"
DIM_GREY = "#555555"
FAINT_GREY = "#333333"

BAR_BG = "#1a1a1a"  # command bar only opaque surface (configurable)


def _shade(hex_color: str, factor: float) -> str:
    """Darken a hex colour by *factor* (0.0 = unchanged, 1.0 = black)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = int(r * (1 - factor)), int(g * (1 - factor)), int(b * (1 - factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def _tint(hex_color: str, amount: float) -> str:
    """Blend a hex colour toward white by *amount* (0.0 = unchanged)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def build_theme(accent: str = RED, transparent_background: bool = True) -> Dict[str, str]:
    """Return the semantic THEME dict.

    Keys are referenced across the TUI (THEME["accent"], etc.).
    ``bg``/``surface``/``panel`` resolve to ``transparent`` when
    *transparent_background* is on, giving native blur support.

    All accent-derived shades (dim/dark/bright/borders/warn/error) are
    computed FROM the accent colour, so a grey accent (``monochrome``
    theme) yields pure greys everywhere — zero red traces.
    """
    bg = "transparent" if transparent_background else "#0a0a0a"
    surface = "transparent" if transparent_background else "#111111"
    panel = "transparent" if transparent_background else "#0e0e0e"
    accent_dim = _shade(accent, 0.35)
    accent_dark = _shade(accent, 0.65)
    accent_bright = _tint(accent, 0.25)
    return {
        # backgrounds
        "bg": bg,
        "surface": surface,
        "panel": panel,
        "bar_bg": BAR_BG,  # the one opaque element (command/hint bar)
        # core text
        "text": WHITE,
        "text_bright": BRIGHT_WHITE,
        "dim": GREY,
        "muted": DIM_GREY,
        "faint": FAINT_GREY,
        "placeholder": DIM_GREY,
        "disabled": FAINT_GREY,
        # accents (derived from the accent so themes stay pure)
        "accent": accent,
        "accent_dim": accent_dim,
        "accent_dark": accent_dark,
        "accent_bright": accent_bright,
        # structural
        "border": accent,
        "border_dim": accent_dark,
        "border_faint": FAINT_GREY,
        "title": accent,
        "highlight": accent,
        # states
        "ok": WHITE,
        "on": accent,
        "off": DIM_GREY,
        "warn": accent_bright,
        "error": accent,
        # art
        "art": LIGHT_GREY,
        "art_glow": accent,
    }


# Default theme used by both the TUI and the standalone settings editor.
THEME: Dict[str, str] = build_theme()

# Glitch/animation glyph pool (shared by splash + menu effects).
GLITCH_CHARS = "!@#$%^&*01█▓▒░╬╠╣╦╩╗╔╝╚│─┐┘┌└├┤┬┴┼~><{}[]"

# Character-speed multiplier per UI animation_speed setting.
ANIM_SPEED = {"slow": 0.5, "normal": 1.0, "fast": 2.0}


def get_anim_interval(base_interval: float, speed: str = "normal") -> float:
    """Scale a base animation interval by the configured speed."""
    return base_interval / ANIM_SPEED.get(speed, 1.0)


# ── Live theming helpers (3.7.0) ─────────────────────────────

def theme_palettes() -> Dict[str, tuple]:
    """Theme name -> (accent, accent_bright, accent_dim)."""
    return {
        "monochrome-red": (RED, RED_GLOW, RED_DIM),
        "monochrome": (LIGHT_GREY, BRIGHT_WHITE, GREY),
    }


def css_vars(theme: Dict[str, str] | None = None) -> Dict[str, str]:
    """THEME dict -> Textual CSS variables ($accent, $bar-bg, ...).

    Apps merge these in ``get_css_variables`` so stylesheets reference
    ``$accent``/``$text``/etc. and restyle live when the theme changes.
    """
    t = theme or THEME
    return {
        "bg": t["bg"],
        "surface": t["surface"],
        "panel": t["panel"],
        "bar-bg": t["bar_bg"],
        "accent": t["accent"],
        "accent-dim": t["accent_dim"],
        "accent-bright": t["accent_bright"],
        "accent-dark": t["accent_dark"],
        "text": t["text"],
        "text-bright": t["text_bright"],
        "dim": t["dim"],
        "muted": t["muted"],
        "faint": t["faint"],
        "border-faint": t["border_faint"],
        "border-dim": t["border_dim"],
        "placeholder": t["placeholder"],
        "error": t["error"],
    }


def textual_theme(name: str, t: Dict[str, str] | None = None) -> "Theme":
    """Build a Textual registered-theme from the semantic THEME dict.

    Theme *variables* stay solid (transparent variables degenerate built-in
    widget colors); screen transparency comes from $bg in our own CSS.
    """
    from textual.theme import Theme

    t = t or THEME
    return Theme(
        name=name,
        dark=True,
        primary=t["accent"],
        secondary=t["text"],
        foreground=t["text"],
        background="#0a0a0a",
        surface="#141414",
        panel="#101010",
        boost="#1a1a1a",
        accent=t["accent"],
        success=t["text"],
        warning=t["accent_bright"],
        error=t["error"],
    )


def rebuild_from_config(cfg=None) -> Dict[str, str]:
    """Rebuild the module-level THEME in place from config.json values.

    All ``THEME["key"]`` readers see the new palette immediately; pair
    with ``apply_live`` to restyle a running app.
    """
    if cfg is None:
        from config import get_config

        cfg = get_config()
    name = cfg.get("theme.name", "monochrome-red")
    default_accent = theme_palettes().get(name, (RED,))[0]
    accent = cfg.get("theme.accent") or default_accent
    transparent = bool(cfg.get("theme.transparent_background", True))
    THEME.clear()
    THEME.update(build_theme(accent, transparent))
    return THEME


def apply_live(app) -> None:
    """Re-apply the (rebuilt) THEME to a running Textual app.

    Re-registers the live theme (register_theme overrides by name),
    activates it, and forces a CSS refresh so ``$variables`` and chrome
    restyle instantly.
    """
    name = "dosping-live"
    app.register_theme(textual_theme(name))
    if app.theme != name:
        app.theme = name
    app.refresh_css()
