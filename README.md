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

---

## What is DOSping?

A terminal-based network stress testing tool. Floods a target with concurrent TCP connections while monitoring connectivity through ICMP ping and TCP port probes in real time. Three-panel split layout. Multi-tab sessions. Built with Python, Textual, and asyncio.

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

> Requires Python 3.12+ and git. Setup scripts auto-clone the repo, create a venv, install deps, and launch.

---

## Features

- **Multi-tab sessions** — up to 4 simultaneous tests, each independent
- **Three-panel layout** — flood log, connectivity monitor, live stats sidebar
- **Live stats** — conn/s, success rate, bytes sent, uptime, updated every second
- **Dual monitoring** — ICMP ping + TCP port probes running in parallel
- **Command palette** (`Ctrl+P`) — 11 custom commands: new test, stop, reset, export, toggles, and more
- **Log export** — save session logs to timestamped .txt files
- **Tab spinners** — animated indicators on active tabs, checkmarks on completed
- **Themeable** — ships with DOSping Matrix, switch to nord/gruvbox/others via palette
- **Matrix splash** — animated character-reveal on launch with KITT scanner bar
- **Exit summary** — formatted report (target, hits/misses, success rate) on quit
- **Cross-platform** — Windows, Linux, macOS

---

## Key Shortcuts

| Key | Action |
|---|---|
| `Ctrl+P` | Command palette |
| `Ctrl+N` | New test tab |
| `Ctrl+W` | Close tab |
| `s` | Stop flood |
| `q` | Quit |

---

## Project Structure

```
dosping/
├── dosping.py          Main TUI
├── flooder.py          TCP flood engine
├── requirements.txt    Dependencies
├── setup.bat           Windows installer
├── setup.sh            Linux/macOS installer
├── README.md
└── docs/
    └── index.html      Full documentation
```

---

**FOR PENETRATION TESTING AND EDUCATIONAL PURPOSES ONLY.** If you use this to crash servers without written authorization, you will end up in jail. Have fun responsibly.
