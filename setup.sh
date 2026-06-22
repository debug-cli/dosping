#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  DOSping v3.5 — Quick Start Installer (Linux / macOS)
# ═══════════════════════════════════════════════════════════
#  Usage:  bash setup.sh
# ═══════════════════════════════════════════════════════════

set -e

REPO="https://github.com/debug-cli/dosping.git"

# ── Auto-clone if run outside the repo (curl | bash) ────
if [ ! -f "requirements.txt" ]; then
    echo ""
    echo "  Cloning DOSping from GitHub..."
    git clone "$REPO" dosping
    cd dosping
    exec bash setup.sh
fi

# ── Colors ───────────────────────────────────────────────
GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Spinner helper ───────────────────────────────────────
# Uses ASCII-only |/-+ frames so any terminal font works.
spin() {
    local pid=$1
    local msg=$2
    local frames='|/-+'
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${AMBER}${frames:$((i%4)):1}${RESET} %s" "$msg"
        i=$((i + 1))
        sleep 0.1
    done
    wait "$pid"
    local rc=$?
    if [ $rc -eq 0 ]; then
        printf "\r  ${GREEN}✓${RESET} %s\n" "$msg"
    else
        printf "\r  ${RED}✖${RESET} %s\n" "$msg"
        return $rc
    fi
}

echo ""
echo -e "  ${BOLD}════════════════════════════════════════${RESET}"
echo -e "  ${BOLD}${AMBER} DOSping v3.5 — Quick Start Installer${RESET}"
echo -e "  ${BOLD}════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${DIM}For penetration testing / education only.${RESET}"
echo -e "  ${DIM}Use at your own risk.${RESET}"
echo ""
echo -e "  ${DIM}────────────────────────────────────────${RESET}"
echo ""

# ── Step 1: Check Python ────────────────────────────────
echo -e "  ${BOLD}[1/5]${RESET} Checking Python..."

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}✖${RESET} Python not found."
    echo "    Install Python 3.12+ from https://python.org"
    exit 1
fi

PYVER=$($PYTHON --version 2>&1)
echo -e "  ${GREEN}✓${RESET} Found $PYVER"
echo ""

# ── Step 2: Create venv ─────────────────────────────────
echo -e "  ${BOLD}[2/5]${RESET} Virtual environment..."

if [ -d ".venv" ]; then
    echo -e "  ${GREEN}✓${RESET} .venv already exists"
else
    $PYTHON -m venv .venv &
    spin $! "Creating .venv"
fi
echo ""

# ── Step 3: Install deps ────────────────────────────────
echo -e "  ${BOLD}[3/5]${RESET} Installing DOSping..."

.venv/bin/pip install -e . --quiet &
spin $! "Installing package + dependencies"
echo ""

# ── Step 4: System-wide command ──────────────────────────
echo -e "  ${BOLD}[4/5]${RESET} Registering 'dosping' command..."

DOSPING_BIN="$(cd .venv/bin && pwd)/dosping"
INSTALL_DIR=""

if [ -d "$HOME/.local/bin" ]; then
    INSTALL_DIR="$HOME/.local/bin"
elif [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    INSTALL_DIR="/usr/local/bin"
else
    mkdir -p "$HOME/.local/bin"
    INSTALL_DIR="$HOME/.local/bin"
fi

ln -sf "$DOSPING_BIN" "$INSTALL_DIR/dosping" 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓${RESET} Linked dosping → $INSTALL_DIR/dosping"

    # Check if INSTALL_DIR is in PATH
    case ":$PATH:" in
        *":$INSTALL_DIR:"*) ;;
        *)
            echo -e "  ${AMBER}!${RESET} $INSTALL_DIR is not in your PATH."
            echo -e "  ${DIM}  Add this to your shell profile:${RESET}"
            echo -e "  ${DIM}  export PATH=\"$INSTALL_DIR:\$PATH\"${RESET}"
            ;;
    esac
else
    echo -e "  ${AMBER}!${RESET} Could not symlink. You can still run: .venv/bin/dosping"
fi
echo ""

# ── Step 5: Launch ───────────────────────────────────────
echo -e "  ${BOLD}[5/5]${RESET} Launching DOSping..."
echo ""
echo -e "  ${DIM}════════════════════════════════════════${RESET}"
echo -e "  ${DIM}Starting TUI. Press Ctrl+C to abort.${RESET}"
echo -e "  ${DIM}════════════════════════════════════════${RESET}"
echo ""

.venv/bin/dosping

echo ""
echo -e "  ${DIM}DOSping exited.${RESET}"
