#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  DOSping v2.0 — Quick Start Installer (Linux / macOS)
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
spin() {
    local pid=$1
    local msg=$2
    local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${AMBER}${frames:i%${#frames}:1}${RESET} %s" "$msg"
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
echo -e "  ${BOLD}${AMBER} DOSping v2.0 — Quick Start Installer${RESET}"
echo -e "  ${BOLD}════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${DIM}For penetration testing / education only.${RESET}"
echo -e "  ${DIM}Use at your own risk.${RESET}"
echo ""
echo -e "  ${DIM}────────────────────────────────────────${RESET}"
echo ""

# ── Step 1: Check Python ────────────────────────────────
echo -e "  ${BOLD}[1/4]${RESET} Checking Python..."

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
echo -e "  ${BOLD}[2/4]${RESET} Virtual environment..."

if [ -d ".venv" ]; then
    echo -e "  ${GREEN}✓${RESET} .venv already exists"
else
    $PYTHON -m venv .venv &
    spin $! "Creating .venv"
fi
echo ""

# ── Step 3: Install deps ────────────────────────────────
echo -e "  ${BOLD}[3/4]${RESET} Dependencies..."

.venv/bin/pip install -r requirements.txt --quiet &
spin $! "Installing packages"
echo ""

# ── Step 4: Launch ───────────────────────────────────────
echo -e "  ${BOLD}[4/4]${RESET} Launching DOSping..."
echo ""
echo -e "  ${DIM}════════════════════════════════════════${RESET}"
echo -e "  ${DIM}Starting TUI. Press Ctrl+C to abort.${RESET}"
echo -e "  ${DIM}════════════════════════════════════════${RESET}"
echo ""

.venv/bin/python dosping.py

echo ""
echo -e "  ${DIM}DOSping exited.${RESET}"
