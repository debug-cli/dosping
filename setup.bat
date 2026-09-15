@echo off
setlocal EnableDelayedExpansion
title DOSping 3.7.1 Setup

:: ═══════════════════════════════════════════════════════════
::  DOSping 3.7.1 "Code Red" — Quick Start Installer (Windows)
:: ═══════════════════════════════════════════════════════════
::  Usage:
::    setup.bat              install + launch
::    setup.bat --no-run     install only, don't launch
::    setup.bat --reinstall  recreate .venv from scratch
:: ═══════════════════════════════════════════════════════════

set "NO_RUN=0"
set "REINSTALL=0"
if /i "%1"=="--no-run"    set "NO_RUN=1"
if /i "%1"=="--reinstall" set "REINSTALL=1"
if /i "%1"=="-h"          goto :usage
if /i "%1"=="--help"      goto :usage

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
    where git >nul 2>&1
    if errorlevel 1 (
        echo   %ERR% git is required to auto-clone. Install git or clone manually:
        echo         git clone https://github.com/debug-cli/dosping.git ^&^& cd dosping ^&^& setup.bat
        pause
        exit /b 1
    )
    git clone --depth 1 https://github.com/debug-cli/dosping.git dosping
    cd dosping
)

:: ── Header ─────────────────────────────────────────────────
cls
echo.
echo   !BLD!!AMB!DOSping 3.7.1 "Code Red"!RST!   !DIM!Network Stress Tester!RST!
echo   !DIM!────────────────────────────────────────────!RST!
echo   !DIM!For penetration testing / education only.!RST!
echo   !DIM!Use at your own risk.!RST!
echo.

:: ── [1/5] Python ───────────────────────────────────────────
echo   !BLD![1/5]!RST! Checking Python...
set "PYEXE="
for %%P in (py python) do (
    if not defined PYEXE (
        %%P --version >nul 2>&1
        if not errorlevel 1 set "PYEXE=%%P"
    )
)
if not defined PYEXE (
    echo   %ERR% Python not found in PATH.
    echo.
    echo         Install Python 3.12+ from https://python.org
    echo         Tip: check "Add Python to PATH" during setup.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('!PYEXE! --version 2^>^&1') do set PYVER=%%v
:: Minimum version check: 3.12+
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set "PYMAJOR=%%a"
    set "PYMINOR=%%b"
)
if !PYMAJOR! LSS 3 goto :pytooold
if !PYMAJOR! EQU 3 if !PYMINOR! LSS 12 goto :pytooold
echo   !CHK! Python !PYVER!
echo.
goto :venv

:pytooold
echo   %ERR% Python !PYVER! found — DOSping needs 3.12+.
echo.
pause
exit /b 1

:venv
:: ── [2/5] Virtual environment ──────────────────────────────
echo   !BLD![2/5]!RST! Virtual environment...
if "!REINSTALL!"=="1" (
    if exist .venv (
        echo   !WRN! --reinstall: removing old .venv
        rmdir /s /q .venv
    )
)
if exist .venv\Scripts\python.exe (
    :: Sanity: venv interpreter must actually run (broken venvs happen
    :: when the base Python was upgraded after creation).
    .venv\Scripts\python.exe -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo   !WRN! .venv is broken — recreating it
        rmdir /s /q .venv
        goto :mkvenv
    )
    echo   !CHK! .venv already exists
) else (
    :mkvenv
    echo   !RUN! Creating .venv...
    if defined PYEXE if "!PYEXE!"=="py" (
        py -3 -m venv .venv
    ) else (
        !PYEXE! -m venv .venv
    )
    if errorlevel 1 (
        echo   %ERR% Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo   !CHK! Created .venv
)
echo.

:: ── [3/5] Install ──────────────────────────────────────────
echo   !BLD![3/5]!RST! Installing DOSping...
echo   !RUN! Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
echo   !RUN! Running pip install ^(this may take a moment^)...
.venv\Scripts\python.exe -m pip install -e . --quiet
if errorlevel 1 (
    echo   %ERR% pip install failed.
    echo         Try manually: .venv\Scripts\pip install -e .
    pause
    exit /b 1
)
:: Verify the entry point actually imports.
.venv\Scripts\python.exe -c "import dosping" >nul 2>&1
if errorlevel 1 (
    echo   %ERR% dosping installed but failed to import.
    echo         Try: .venv\Scripts\pip install -e . --no-cache-dir
    pause
    exit /b 1
)
echo   !CHK! DOSping installed and imports cleanly
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
echo   !DIM!Config lives in config.json next to the source. Edit with: python settings.py!RST!
echo.

:: ── [5/5] Launch ───────────────────────────────────────────
if "!NO_RUN!"=="1" (
    echo   !CHK! Install complete. Launch with:
    echo           .venv\Scripts\dosping.exe   ^(or just: dosping^)
    echo.
    pause
    exit /b 0
)

echo   !BLD![5/5]!RST! Launching DOSping...
echo.
echo   !DIM!Press Ctrl+C to abort.!RST!
echo.

.venv\Scripts\dosping.exe
if errorlevel 1 (
    echo   !WRN! dosping.exe failed — retrying via python...
    .venv\Scripts\python.exe dosping.py
)

echo.
echo   !DIM!DOSping exited.!RST!
pause >nul
exit /b 0

:usage
echo DOSping 3.7.1 "Code Red" setup
echo.
echo Usage: setup.bat [option]
echo   --no-run     install only, don't launch
echo   --reinstall  recreate .venv from scratch
echo   --help       show this help
exit /b 0
