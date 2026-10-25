@echo off
setlocal enabledelayedexpansion
REM ==============================================================================
REM  JARVIS AI PERSONAL ASSISTANT - 1-CLICK WINDOWS SETUP SCRIPT
REM  Based on Jarvis Executive Edition Installation & Configuration Guide
REM ==============================================================================

title Jarvis AI Assistant - Installation

echo.
echo ==================================================================
echo           [+] WELCOME TO JARVIS AI ASSISTANT SETUP
echo ==================================================================
echo.

REM 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python is not installed or not in PATH.
    echo     Please install Python 3.10 or newer from https://python.org
    pause
    exit /b 1
)

echo [OK] Python detected:
python --version

REM 2. Create and Activate Virtual Environment (.venv)
if not exist ".venv" (
    echo [*] Creating isolated Python virtual environment (.venv)...
    python -m venv .venv
)

echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat

REM 3. Upgrade pip and install dependencies
echo [*] Installing required dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

REM 4. Setup Free Groq API Key (Step 3 from Setup Guide)
set "CONFIG_DIR=%USERPROFILE%\.openjarvis"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

if not exist "%CONFIG_DIR%\free.key" (
    echo.
    echo ==================================================================
    echo  [Key Setup] Free Groq API Key (from https://console.groq.com/keys)
    echo ==================================================================
    set /p API_KEY="Paste your Groq API Key (or press Enter to skip & use local mode): "
    if defined API_KEY (
        echo !API_KEY!> "%CONFIG_DIR%\free.key"
        echo [OK] API Key successfully saved.
    ) else (
        echo [!] Skipping API key. Jarvis will operate in local offline mode.
    )
) else (
    echo [OK] Found existing Groq API key in %CONFIG_DIR%\free.key.
)

echo.
echo ==================================================================
echo           [+] JARVIS SETUP COMPLETED SUCCESSFULLY!
echo ==================================================================
echo.
echo  To start Jarvis at any time:
echo      run.bat
echo    or:
echo      call .venv\Scripts\activate.bat
echo      python jarvis_app.py
echo.
echo  Holographic HUD Dashboard:
echo      Open jarvis_workplace.html in Chrome or Edge
echo.

set /p LAUNCH="Do you want to launch Jarvis now? (Y/N): "
if /i "%LAUNCH%"=="N" (
    echo You can start Jarvis anytime by running run.bat
    pause
    exit /b 0
)

echo.
echo [*] Launching Jarvis Executive Assistant...
python jarvis_app.py
pause
