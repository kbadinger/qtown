@echo off
:: Start Ralph — the autonomous orchestrator loop
:: Run this directly or via Task Scheduler for auto-restart

cd /d D:\Projects\qtown

:: Activate venv if it exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

:: Ensure npm global bin is in PATH (for railway CLI)
set PATH=%PATH%;%APPDATA%\npm

:: Log startup
echo [%date% %time%] Ralph starting >> ralph.log

:: Run Ralph, appending output to log file
python -u -m ralph.ralph >> ralph.log 2>&1

:: If Ralph exits, log it
echo [%date% %time%] Ralph exited with code %errorlevel% >> ralph.log
