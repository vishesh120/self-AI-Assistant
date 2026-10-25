@echo off
REM ==============================================================================
REM  JARVIS AI PERSONAL ASSISTANT - 1-CLICK LAUNCH SCRIPT
REM ==============================================================================
title Jarvis AI Assistant
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Running install.bat first...
    call install.bat
)

call .venv\Scripts\activate.bat
python jarvis_app.py
pause
