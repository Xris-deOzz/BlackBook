@echo off
title Perun's BlackBook
cd /d "%~dp0"

echo.
echo  ========================================
echo   Perun's BlackBook - Personal CRM
echo  ========================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Run: python -m venv venv
    pause
    exit /b 1
)

REM Start browser after short delay (in background)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

echo Starting server at http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
