@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "PY=C:\Users\LDX\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"
echo ================================================
echo   Session Cache Cleanup - DEEP MODE
echo   Warning: also deletes projects\<slug> session data
echo ================================================
echo.
set /p confirm=Run deep cleanup? Type Y to continue, any other key to cancel:
if /i not "%confirm%"=="Y" (
    echo Canceled.
    pause
    exit /b
)
echo.
"%PY%" "%~dp0cleanup_wb_sessions.py" --apply --deep
echo.
pause
