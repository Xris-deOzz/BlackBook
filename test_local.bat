@echo off
echo =============================================
echo   Perun's BlackBook - LOCAL TESTING MODE
echo =============================================
echo.

REM Change to project directory
cd /d "%~dp0"

REM Check if Docker is running (needed for database)
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop first.
    pause
    exit /b 1
)
echo [OK] Docker is running

REM Start just the database container
echo.
echo Starting PostgreSQL database container...
docker-compose up -d db
if errorlevel 1 (
    echo ERROR: Failed to start database container!
    pause
    exit /b 1
)

REM Wait for database to be ready
echo Waiting for database to be ready...
timeout /t 5 /nobreak >nul

REM Check database is accepting connections
:check_db
docker exec blackbook-db pg_isready -U blackbook -d perunsblackbook >nul 2>&1
if errorlevel 1 (
    echo Still waiting for database...
    timeout /t 2 /nobreak >nul
    goto check_db
)
echo [OK] Database is ready

REM Backup original .env and use local version
echo.
echo Switching to local configuration...
if exist .env.backup del .env.backup
copy .env .env.backup >nul
copy /Y .env.local .env >nul

REM Activate virtual environment
call .\venv\Scripts\activate.bat

REM Clear the settings cache (pydantic lru_cache)
set PYTHONDONTWRITEBYTECODE=1

REM Run migrations
echo.
echo Running database migrations...
python -m alembic upgrade head
if errorlevel 1 (
    echo.
    echo WARNING: Migration may have issues. Check output above.
    echo Press any key to continue anyway, or Ctrl+C to abort...
    pause >nul
)

REM Start the application
echo.
echo =============================================
echo   Starting BlackBook on http://localhost:8000
echo   Press Ctrl+C to stop
echo =============================================
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

REM Restore original .env
echo.
echo Restoring production configuration...
copy /Y .env.backup .env >nul
del .env.backup

echo.
echo Local testing session ended.
pause
