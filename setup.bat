@echo off
setlocal EnableDelayedExpansion
title DOSping v3.5 Setup

:: ── ANSI color support ─────────────────────────────────────
::    Works on Windows 10 1903+ (PowerShell provides ESC char)
::    Falls back gracefully to plain ASCII on older terminals.
set "E="
for /f "delims=" %%E in ('powershell -NoProfile -Command "[char]27" 2^>nul') do set "E=%%E"

if defined E (
    set "GRN=!E![32m"
    set "AMB=!E![33m"
    set "RED=!E![31m"
    set "DIM=!E![90m"
    set "BLD=!E![1m"
    set "RST=!E![0m"
    set "CHK=!E![32m ^v!E![0m"
    set "ERR=!E![31m ^x!E![0m"
    set "RUN=!E![33m ^.!E![0m"
    set "WRN=!E![33m ^!!E![0m"
) else (
    set "GRN=" & set "AMB=" & set "RED="
    set "DIM=" & set "BLD=" & set "RST="
    set "CHK= [OK] " & set "ERR=[FAIL]" & set "RUN= [ ] " & set "WRN= [!]  "
)

:: ── Auto-clone if run outside the repo ────────────────────
if not exist requirements.txt (
    echo.
    echo   Cloning DOSping from GitHub...
    git clone https://github.com/debug-cli/dosping.git dosping
    cd dosping
    call setup.bat
    exit /b
)

:: ── Header ─────────────────────────────────────────────────
cls
echo.
echo   !BLD!!AMB!DOSping v3.5!RST!   !DIM!Network Stress Tester!RST!
echo   !DIM!────────────────────────────────────────────!RST!
echo   !DIM!For penetration testing / education only.!RST!
echo   !DIM!Use at your own risk.!RST!
echo.

:: ── [1/5] Python ───────────────────────────────────────────
echo   !BLD![1/5]!RST! Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   !ERR! Python not found in PATH.
    echo.
    echo         Install Python 3.12+ from https://python.org
    echo         Tip: check "Add Python to PATH" during setup.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   !CHK! Python !PYVER!
echo.

:: ── [2/5] Virtual environment ──────────────────────────────
echo   !BLD![2/5]!RST! Virtual environment...
if exist .venv (
    echo   !CHK! .venv already exists
) else (
    echo   !RUN! Creating .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo   !ERR! Failed to create virtual environment.
        pause & exit /b 1
    )
    echo   !CHK! Created .venv
)
echo.

:: ── [3/5] Install ──────────────────────────────────────────
echo   !BLD![3/5]!RST! Installing DOSping...
echo   !RUN! Running pip install ^(this may take a moment^)...
echo.
.venv\Scripts\pip install -e . --quiet
if errorlevel 1 (
    echo   !ERR! pip install failed.
    echo         Try manually: .venv\Scripts\pip install -e .
    pause & exit /b 1
)
echo   !CHK! DOSping installed
echo.

:: ── [4/5] PATH registration ────────────────────────────────
echo   !BLD![4/5]!RST! Registering 'dosping' command...
set "DOSPING_DIR=%LOCALAPPDATA%\dosping\bin"
if not exist "!DOSPING_DIR!" mkdir "!DOSPING_DIR!"
copy /Y ".venv\Scripts\dosping.exe" "!DOSPING_DIR!\dosping.exe" >nul 2>&1

echo %PATH% | findstr /I /C:"!DOSPING_DIR!" >nul 2>&1
if errorlevel 1 (
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USERPATH=%%B"
    if defined USERPATH (
        echo !USERPATH! | findstr /I /C:"!DOSPING_DIR!" >nul 2>&1
        if errorlevel 1 (
            setx PATH "!USERPATH!;!DOSPING_DIR!" >nul 2>&1
        )
    ) else (
        setx PATH "!DOSPING_DIR!" >nul 2>&1
    )
    set "PATH=%PATH%;!DOSPING_DIR!"
    echo   !CHK! Added to PATH
    echo   !WRN! Open a new terminal for the 'dosping' command to work globally.
) else (
    echo   !CHK! Already in PATH
)
echo.

:: ── [5/5] Launch ───────────────────────────────────────────
echo   !BLD![5/5]!RST! Launching DOSping...
echo.
echo   !DIM!Press Ctrl+C to abort.!RST!
echo.

.venv\Scripts\dosping.exe

echo.
echo   !DIM!DOSping exited.!RST!
pause >nul
