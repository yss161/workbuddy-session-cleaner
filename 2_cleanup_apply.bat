@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "PY=C:\Users\LDX\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"
echo ================================================
echo   Session Cache Cleanup - APPLY (safe)
echo ================================================
echo.
"%PY%" "%~dp0cleanup_wb_sessions.py" --apply
echo.
pause
