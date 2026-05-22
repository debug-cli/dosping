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
echo  [1/4] Checking Python...
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
echo  [2/4] Creating virtual environment...
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

:: ── Install dependencies ────────────────────────────────────
echo  [3/4] Installing dependencies...
echo.
.venv\Scripts\pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo   ERROR: pip install failed.
    echo   Try running: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo.
echo   Dependencies installed.
echo.

:: ── Launch ──────────────────────────────────────────────────
echo  [4/4] Launching DOSping...
echo.
echo  ========================================
echo   Starting TUI. Press Ctrl+C to abort.
echo  ========================================
echo.

.venv\Scripts\python dosping.py

echo.
echo  DOSping exited. Press any key to close.
pause >nul
