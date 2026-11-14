@echo off
rem Tandian one-click launcher: sets up on first run, starts the website and opens the browser.
rem Keep this file ASCII-only; all messages are printed by tools\start.py.
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Tandian
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\start.py %*
) else (
  where python >nul 2>nul
  if errorlevel 1 goto nopython
  python tools\start.py %*
)
if errorlevel 1 pause
exit /b

:nopython
echo Python was not found.
echo Please install Python 3.12 from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during setup, then run this file again.
pause
exit /b 1
