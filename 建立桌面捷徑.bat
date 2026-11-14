@echo off
rem Creates a "Tandian" shortcut on the desktop that runs the launcher in this folder.
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\start.py --shortcut
) else (
  python tools\start.py --shortcut
)
pause
