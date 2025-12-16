@echo off
echo Starting Perun's BlackBook...
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop first, then run this script again.
    pause
    exit /b 1
)

echo Docker is running - OK
echo.

REM Change to project directory
cd /d "%~dp0"

REM Start the server
echo Starting FastAPI server on http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

pause
