@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "PY=C:\Users\LDX\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"
echo ================================================
echo   Session Cache Cleanup - PREVIEW (read-only)
echo ================================================
echo.
"%PY%" "%~dp0cleanup_wb_sessions.py"
echo.
echo Above is preview only. To really clean, run 2_cleanup_apply.bat
echo.
pause
