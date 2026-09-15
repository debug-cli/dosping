#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  DOSping 3.7.1 "Code Red" — Quick Start Installer (Linux / macOS)
# ═══════════════════════════════════════════════════════════
#  Usage:
#    bash setup.sh              # install + launch
#    bash setup.sh --no-run     # install only, don't launch
#    bash setup.sh --reinstall  # recreate .venv from scratch
#
#  curl | bash is also supported — the repo is cloned
#  automatically when requirements.txt is not found.
# ═══════════════════════════════════════════════════════════

set -eu

REPO="https://github.com/debug-cli/dosping.git"
MIN_PY_MAJOR=3
MIN_PY_MINOR=12

NO_RUN=0
REINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --no-run)    NO_RUN=1 ;;
        --reinstall) REINSTALL=1 ;;
        -h|--help)
            sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
    esac
done

# ── Auto-clone if run outside the repo (curl | bash) ────
if [ ! -f "requirements.txt" ]; then
    echo ""
    echo "  DOSping not found here — cloning from GitHub..."
    command -v git >/dev/null 2>&1 || {
        echo "  ERROR: git is required to auto-clone. Install git or clone manually:" >&2
        echo "    git clone $REPO && cd dosping && bash setup.sh" >&2
        exit 1
    }
    git clone --depth 1 "$REPO" dosping
    cd dosping
fi

# ── Colors ───────────────────────────────────────────────
if [ -t 1 ]; then
    GREEN='\033[0;32m'; AMBER='\033[0;33m'; RED='\033[0;31m'
    DIM='\033[2m'; BOLD='\033[1m'; RESET='\033[0m'
else
    GREEN=''; AMBER=''; RED=''; DIM=''; BOLD=''; RESET=''
fi

ok()   { printf "  ${GREEN}✓${RESET} %s\n" "$1"; }
fail() { printf "  ${RED}✖${RESET} %s\n" "$1"; }
warn() { printf "  ${AMBER}!${RESET} %s\n" "$1"; }
step() { printf "\n  ${BOLD}[%s]%s ${RESET}%s\n" "$1" "/5" "$2"; }

# ── Spinner helper ───────────────────────────────────────
# Uses ASCII-only |/-+ frames so any terminal font works.
spin() {
    local pid=$1 msg=$2 frames='|/-+' i=0 rc
    # Disable job control messages for the background job.
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${AMBER}${frames:$((i%4)):1}${RESET} %s" "$msg"
        i=$((i + 1))
        sleep 0.1
    done
    wait "$pid"; rc=$?
    if [ $rc -eq 0 ]; then
        printf "\r  ${GREEN}✓${RESET} %s\n" "$msg"
    else
        printf "\r  ${RED}✖${RESET} %s\n" "$msg"
    fi
    return $rc
}

echo ""
echo -e "  ${BOLD}════════════════════════════════════════${RESET}"
echo -e "  ${BOLD}${AMBER} DOSping 3.7.1 “Code Red” — Quick Start Installer${RESET}"
echo -e "  ${BOLD}════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${DIM}For penetration testing / education only.${RESET}"
echo -e "  ${DIM}Use at your own risk.${RESET}"

# ── Step 1: Check Python ────────────────────────────────
step 1 "Checking Python..."

PYTHON=""
for cmd in python3 python python3.13 python3.12 python3.11 python3.10; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python not found."
    echo "    Install Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ from https://python.org"
    echo "    (or: apt install python3 python3-venv / brew install python)"
    exit 1
fi

PYVER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || echo 0)
PYMAJOR=${PYVER%%.*}
PYMINOR=${PYVER##*.}
if [ "$PYMAJOR" -lt $MIN_PY_MAJOR ] || { [ "$PYMAJOR" -eq $MIN_PY_MAJOR ] && [ "$PYMINOR" -lt $MIN_PY_MINOR ]; }; then
    fail "Python $PYVER found — DOSping needs ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+."
    exit 1
fi
ok "Found Python $PYVER ($("$PYTHON" --version 2>&1 | cut -d' ' -f1) at $(command -v "$PYTHON"))"

# ── Step 2: Create venv ─────────────────────────────────
step 2 "Virtual environment..."

if [ "$REINSTALL" -eq 1 ] && [ -d .venv ]; then
    warn "--reinstall: removing old .venv"
    rm -rf .venv
fi

if [ -d .venv ] && [ -x .venv/bin/python ]; then
    ok ".venv already exists"
else
    rm -rf .venv    # clear a broken venv if present
    "$PYTHON" -m venv .venv &
    spin $! "Creating .venv" || {
        fail "venv creation failed. On Debian/Ubuntu install: sudo apt install python3-venv"
        exit 1
    }
fi

# Sanity: the venv interpreter must actually run (broken venvs happen
# when the base interpreter was upgraded/removed after creation).
if ! .venv/bin/python -c 'import sys' >/dev/null 2>&1; then
    warn ".venv is broken — recreating it"
    rm -rf .venv
    "$PYTHON" -m venv .venv
fi

# ── Step 3: Install deps ────────────────────────────────
step 3 "Installing DOSping..."

.venv/bin/python -m pip install --upgrade pip --quiet &
spin $! "Upgrading pip" || warn "pip upgrade failed (continuing)"

.venv/bin/python -m pip install -e . --quiet &
spin $! "Installing package + dependencies" || {
    fail "pip install failed — run manually for details:"
    echo "    .venv/bin/pip install -e ."
    exit 1
}

# Verify the entry point actually imports.
if ! .venv/bin/python -c "import dosping" >/dev/null 2>&1; then
    fail "dosping installed but failed to import — dependencies missing?"
    echo "    Try: .venv/bin/pip install -e . --no-cache-dir"
    exit 1
fi
ok "dosping imports cleanly"

# ── Step 4: System-wide command ──────────────────────────
step 4 "Registering 'dosping' command..."

DOSPING_BIN="$(cd .venv/bin && pwd)/dosping"
INSTALL_DIR="$HOME/.local/bin"

if [ -d "$INSTALL_DIR" ] || mkdir -p "$INSTALL_DIR" 2>/dev/null; then
    :
else
    INSTALL_DIR=""
    if [ -d /usr/local/bin ] && [ -w /usr/local/bin ]; then
        INSTALL_DIR="/usr/local/bin"
    fi
fi

if [ -n "$INSTALL_DIR" ] && ln -sf "$DOSPING_BIN" "$INSTALL_DIR/dosping" 2>/dev/null; then
    ok "Linked dosping → $INSTALL_DIR/dosping"
    case ":$PATH:" in
        *":$INSTALL_DIR:"*) ;;
        *)
            warn "$INSTALL_DIR is not in your PATH."
            echo -e "  ${DIM}  Add this to your shell profile (~/.bashrc, ~/.zshrc, ...):${RESET}"
            echo -e "  ${DIM}  export PATH=\"$INSTALL_DIR:\$PATH\"${RESET}"
            ;;
    esac
else
    warn "Could not symlink. You can still run: .venv/bin/dosping"
fi
echo -e "  ${DIM}Config lives in config.json next to the source · edit with: python settings.py${RESET}"

# ── Step 5: Launch ───────────────────────────────────────
if [ "$NO_RUN" -eq 1 ]; then
    echo ""
    ok "Install complete. Launch with:"
    echo -e "  ${BOLD}  .venv/bin/dosping${RESET}   (or just: dosping)"
    exit 0
fi

step 5 "Launching DOSping..."
echo ""
echo -e "  ${DIM}Starting TUI. Press Ctrl+C or Q to quit.${RESET}"
echo ""

# Run from a real TTY when possible so Textual gets proper size/colors.
if command -v script >/dev/null 2>&1 && [ ! -t 0 ]; then
    script -qec ".venv/bin/dosping" /dev/null || .venv/bin/dosping
else
    .venv/bin/dosping || .venv/bin/python dosping.py
fi

echo ""
echo -e "  ${DIM}DOSping exited.${RESET}"
