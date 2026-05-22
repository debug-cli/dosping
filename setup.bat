@echo off
setlocal enabledelayedexpansion
title DOSping Setup
color 0A

:: ── Auto-clone if run outside the repo ──────────────────────
if not exist requirements.txt (
    echo.
    echo   Cloning DOSping from GitHub...
    git clone https://github.com/debug-cli/dosping.git dosping
    cd dosping
    call setup.bat
    exit /b
)

echo.
echo  ========================================
echo   DOSping v2.0 - Quick Start Installer
echo  ========================================
echo.
echo   For penetration testing / education only.
echo   Use at your own risk.
echo.
echo  ----------------------------------------
echo.

:: ── Check Python ────────────────────────────────────────────
echo  [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: Python not found in PATH.
    echo   Install Python 3.12+ from https://python.org
    echo   Make sure "Add to PATH" is checked during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Found Python %PYVER%
echo.

:: ── Create virtual environment ──────────────────────────────
echo  [2/5] Creating virtual environment...
if exist .venv (
    echo   .venv already exists, skipping.
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo   ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo   Created .venv
)
echo.

:: ── Install package + dependencies ──────────────────────────
echo  [3/5] Installing DOSping...
echo.
.venv\Scripts\pip install -e . --quiet
if errorlevel 1 (
    echo.
    echo   ERROR: pip install failed.
    echo   Try running: .venv\Scripts\pip install -e .
    pause
    exit /b 1
)
echo.
echo   Package installed.
echo.

:: ── Register dosping command on PATH ────────────────────────
echo  [4/5] Registering 'dosping' command...

set "DOSPING_DIR=%LOCALAPPDATA%\dosping\bin"
if not exist "%DOSPING_DIR%" mkdir "%DOSPING_DIR%"

:: Copy the generated exe and its script into a stable directory
copy /Y ".venv\Scripts\dosping.exe" "%DOSPING_DIR%\dosping.exe" >nul 2>&1

:: Check if DOSPING_DIR is already in user PATH
echo %PATH% | findstr /I /C:"%DOSPING_DIR%" >nul 2>&1
if errorlevel 1 (
    :: Add to user PATH permanently via setx
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USERPATH=%%B"
    if defined USERPATH (
        echo !USERPATH! | findstr /I /C:"%DOSPING_DIR%" >nul 2>&1
        if errorlevel 1 (
            setx PATH "!USERPATH!;%DOSPING_DIR%" >nul 2>&1
        )
    ) else (
        setx PATH "%DOSPING_DIR%" >nul 2>&1
    )
    set "PATH=%PATH%;%DOSPING_DIR%"
    echo   Added %DOSPING_DIR% to your PATH.
    echo   Open a new terminal for the 'dosping' command to work.
) else (
    echo   PATH already contains %DOSPING_DIR%
)

:: Also copy the exe after any future update
echo   dosping.exe copied to %DOSPING_DIR%
echo.

:: ── Launch ──────────────────────────────────────────────────
echo  [5/5] Launching DOSping...
echo.
echo  ========================================
echo   Starting TUI. Press Ctrl+C to abort.
echo  ========================================
echo.

.venv\Scripts\dosping.exe

echo.
echo  DOSping exited. Press any key to close.
pause >nul

