# Welcome to the repository of...

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▸
░▒▓  ____    ___   ____        _                        ▓▒░
░▒▓ |  _ \  / _ \ / ___|_ __  (_) _ __    __ _   ≫≫≫  ▓▒░
░▒▓ | | | || | | |\___ \ '_ \ | || '_ \  / _` |  ≫≫   ▓▒░
░▒▓ | |_| || |_| | ___) | |_) || || | | || (_| |   ≫   ▓▒░
░▒▓ |____/  \___/ |____/| .__/ |_||_| |_| \__, |       ▓▒░
░▒▓                     |_|              |___/        ▓▒░
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▸
              ⚡ Network Stress Tester ⚡
```

Made by saint. Made for a close friend.

> **FOR PENETRATION TESTING AND EDUCATIONAL PURPOSES ONLY.** Unauthorized use against systems you don't own or have permission to test is illegal. You accept full responsibility. Use at your own risk.
Always use a VPN when unauthorized, watch out for honeypots.

---

## What is DOSping?

A terminal-based network stress testing tool. Floods a target with concurrent TCP connections while monitoring connectivity through ICMP ping and TCP port probes in real time. Three-panel split layout. Multi-tab sessions. Built with Python, Textual, and asyncio.

**DOSping 3.7.1 “Code Red”** adds **Advanced Settings** — open the full editor in-app (`⚙ SETTINGS → Advanced → Open…`) or standalone (`python settings.py`) — with **live theme switching**, confirmation dialogs, change toasts, and an About panel. On top of v3.5's foundations: a full **configuration system** (`config.json`), a **monochrome/red theme** with a **fully transparent background** (acrylic/blur-friendly), **strength presets**, and **glitching ASCII art** on the home screen.  
New in 3.7.1: a verbose **event log** (`logs/dosping-YYYY-MM-DD.log`) recording every significant action — see [Event log](#event-log) below.

📖 **[Full documentation →](https://dosping-docs.vercel.app)**

---

## Quick Start

**Linux / macOS:**

```bash
curl -fsSL https://raw.githubusercontent.com/debug-cli/dosping/main/setup.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/debug-cli/dosping/main/setup.bat -OutFile setup.bat; .\setup.bat
```

**Ubuntu / Debian** (includes Python install):

```bash
sudo apt update && sudo apt install -y git python3 python3-pip python3-venv && curl -fsSL https://raw.githubusercontent.com/debug-cli/dosping/main/setup.sh | bash
```

**"I use Arch btw":**

```bash
sudo pacman -Sy --noconfirm git python python-pip && curl -fsSL https://raw.githubusercontent.com/debug-cli/dosping/main/setup.sh | bash
```

**Termux:**

```bash
pkg update -y && pkg install -y git python && curl -fsSL https://raw.githubusercontent.com/debug-cli/dosping/main/setup.sh | bash
```

**Windows CMD:**

```cmd
git clone https://github.com/debug-cli/dosping.git && cd dosping && setup.bat
```

**Manual install:**

```bash
git clone https://github.com/debug-cli/dosping.git && cd dosping
python3 -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
.venv/bin/dosping                    # Windows: .venv\Scripts\dosping
```

> Requires **Python 3.12+** and git. The setup scripts auto-clone the repo, create a venv, verify the install, register the `dosping` command, and launch.
>
> **Installer options:** `--no-run` (install without launching) and `--reinstall` (recreate the venv from scratch).

### Best viewed in a transparent terminal

DOSping renders on a **fully transparent background** — no hardcoded blacks. For the full effect, enable acrylic/blur in your terminal:

- **Windows Terminal** → Settings → your profile → Appearance → **Transparency** (drag to ~60%) and enable **Acrylic**
- **Kitty** → `background_opacity 0.85`
- **Alacritty** → `opacity: 0.85` (`background_opacity` pre-0.13)

The only opaque surface is the bottom command bar, so text stays readable.

---

## Configuration

Everything is configurable via **`config.json`** (auto-created next to `dosping.py` on first save). Open the editor **inside the app** via `⚙ SETTINGS → Advanced → Open…`, or standalone:

```bash
python settings.py
```

The editor (same code either way) covers every option with arrow/Tab navigation, input validation, ESC to save & exit (Ctrl+D discards and reverts the live theme), change toasts, and confirmation dialogs for dangerous actions. Theme changes restyle the editor **live** — no restart needed. Every value (theme, accent, view mode, attacker/scanner defaults, advanced keys, active preset) persists to `config.json` — even opening the editor and pressing ESC without touching anything will never overwrite your saved settings.

| Section | Options |
|---|---|
| **Theme** | Theme (monochrome-red / monochrome), accent colour, background transparency — applied live |
| **Attacker** | Default target IP, attack method, thread count, packet size (8–8192 B), connect timeout |
| **Scanner** | Scan mode (single host / CIDR network), default target, port list, connect/banner timeouts, concurrency slots |
| **Presets** | Built-in strength presets + your own custom presets |
| **UI** | Animation speed (slow / normal / fast), ASCII glitch effects on/off |
| **Advanced** | Attack engine tuning (timeouts, per-bot delay, payload reuse), scanner banner grab, logging caps + timestamps, session limits, GeoIP, safety guards — see below |

### Advanced settings

Toggle with `Ctrl+A` (or the `⚙ Advanced Settings` button). Sections: **Attack Engine**, **Scanner Engine**, **Logging**, **Interface**, **Sessions**, **Network**, **Safety**, and a **Danger Zone** (Reset Advanced / Factory Reset — both behind confirmation dialogs). The Advanced view also has an **About** panel (version, repo + docs links, config path) and the disclaimer.

Everything you change — theme, presets, advanced switches, and the **Default View Mode** from the in-app settings modal — is written straight to `config.json` and restored on the next launch.

The **Logging** section now controls the on-disk event log too: **Log To Disk** (master toggle), **Verbosity** (minimal / normal / verbose / debug), **Delete Logs After** (1–90 days / never), **Max Log Storage** (10–250 MB / unlimited), plus **↗ Open Logs Folder** and **✕ Clear All Logs** (confirmation-protected).

### Event log

DOSping 3.7.1 keeps a structured event log next to `config.json`:

- **Location** — `logs/dosping-YYYY-MM-DD.log` (daily files, size-rotated with a `.N` suffix past 5 MB).
- **Format** — one plain-text event per line:
  `[2026-09-14 21:04:29.140] [INFO ] [flood] [tab-1] flood.workers_spawned bots=200 concurrency=200 packet_size=512B reuse_payload=true ports=80,443`
  Fields are `key=value` (grep-friendly); strings with spaces are quoted; banners are truncated and sanitized.
- **Coverage** — app startup/shutdown (version, OS, Python, terminal size), config load/save/reset (with changed keys), session tabs opened/closed, setup validation and rejections, attack started/stopped/finished (duration, connections, success rate), flood-engine aggregate stats every 10 s with error classes (refused / timeout / DNS), scanner milestones, open ports and banners, every settings change (old → new), and every caught exception with component and context.
- **Verbosity levels** — `minimal` (lifecycle + errors only) · `normal` (default, day-to-day events) · `verbose` (+ full setup params, monitor toggles, health checks, banners) · `debug` (+ GeoIP results, latency samples).
- **Retention** — files older than *Delete Logs After* are removed at startup (never today's file), and the folder is capped at *Max Log Storage*; **Clear All Logs** wipes everything except today's file behind a confirmation.
- **Privacy** — logs record the targets *you* test (IPs, open ports, banners) and never your full `config.json`. Turn the whole thing off with **Log To Disk = off**.

### Strength presets

One-click strength levels, selectable in the scanner setup **and** in `settings.py`:

| Preset | Scanner Threads | Scanner Timeout | Attacker Threads | Attacker Packet Size |
|--------|-----------------|-----------------|------------------|----------------------|
| Low    | 64              | 1.5 s           | 50               | 64 B                 |
| Medium | 256             | 0.75 s          | 200              | 512 B                |
| High   | 1024            | 0.3 s           | 1000             | 1024 B               |

You can also save the current values as a **custom preset** (`✚ Save Custom From Current` in `settings.py`) — custom presets are stored in `config.json` and can be deleted later.

> On this screen every interactive element now carries a visible label: **Scan Mode**, **Target**, **Quick Presets**, **Ports**, **Strength Preset**, and **Timeouts & Concurrency** are all rendered with readable buttons.

---

## Features

- **Config everything** — `config.json` + the settings editor (in-app or `python settings.py`), Basic + Advanced levels, live theming
- **Strength presets** — Low / Medium / High for scanner and attacker, plus custom presets
- **Transparent background** — monochrome + red ANSI theme; blur-enabled terminals show through natively
- **Multi-tab sessions** — up to 4 simultaneous tests, each independent
- **Three-panel layout** — flood log, connectivity monitor, live stats sidebar
- **Live stats** — conn/s, success rate, bytes sent, uptime, updated every second
- **Dual monitoring** — ICMP ping + TCP port probes running in parallel
- **Host & network scanning** — single-host port scans or full CIDR subnet sweeps with banner grabbing
- **Command palette** (`Ctrl+P`) — opens with all 17 commands listed (type to filter): new test/scan, stop, reset, export, monitor toggles, view modes, docs and more
- **Glitching ASCII** — splash reveal, KITT scanner bar, and per-tile glitch effects (toggleable, speed-configurable)
- **Log export** — save session logs to timestamped .txt files
- **Keyboard-first** — persistent key-hint bar on every screen; ESC always goes back
- **Exit summary** — formatted report (target, hits/misses, success rate) on quit
- **Cross-platform** — Windows, Linux, macOS

---

## Key Shortcuts

| Key | Action |
|---|---|
| `↑/↓/←/→` | Navigate tiles / fields |
| `Tab` | Cycle fields (config screens) |
| `Enter` | Select / confirm |
| `ESC` | Back (any submenu / settings) |
| `Ctrl+P` | Command palette |
| `Ctrl+N` | New test tab |
| `Ctrl+Shift+N` | New scan tab |
| `Ctrl+W` | Close tab |
| `s` | Stop flood |
| `r` | Reset test |
| `i` / `t` | Toggle ICMP / TCP monitors |
| `e` | Export session log |
| `Ctrl+M` | Cycle view mode (SKID / ADVANCED / IT) |
| `?` / `F1` | Cheat sheet |
| `q` | Quit |

Every screen shows the shortcuts available in its context in the bar at the bottom.

---

## Project Structure

```
dosping/
├── dosping.py          Main TUI
├── flooder.py          TCP flood engine (config-driven packet size)
├── scanner.py          Port + network scan engines
├── config.py           config.json load/save/repair + presets API
├── theme.py            Semantic THEME dict (monochrome + red, transparent bg)
├── settings.py         Standalone settings TUI (python settings.py)
├── config.json         Auto-generated at runtime (gitignored)
├── requirements.txt    Dependencies
├── setup.bat           Windows installer
├── setup.sh            Linux/macOS installer
├── README.md
└── docs/
    └── index.html      Full documentation
```
