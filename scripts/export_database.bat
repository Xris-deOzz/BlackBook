@echo off
REM Export BlackBook PostgreSQL database for migration to Synology
REM Run from: C:\Users\ossow\OneDrive\PerunsBlackBook

setlocal enabledelayedexpansion

echo.
echo ========================================
echo  BlackBook Database Export
echo ========================================
echo.

REM Set variables
set BACKUP_DIR=%~dp0..\backups
set TIMESTAMP=%date:~-4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set BACKUP_FILE=%BACKUP_DIR%\blackbook_export_%TIMESTAMP%.sql

REM Create backup directory if it doesn't exist
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo Exporting database to: %BACKUP_FILE%
echo.

REM Check if pg_dump is available
where pg_dump >nul 2>&1
if errorlevel 1 (
    echo ERROR: pg_dump not found in PATH
    echo.
    echo Please add PostgreSQL bin directory to PATH, e.g.:
    echo   C:\Program Files\PostgreSQL\15\bin
    echo.
    echo Or run pg_dump directly:
    echo   "C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" -h localhost -U blackbook -d perunsblackbook -f "%BACKUP_FILE%"
    pause
    exit /b 1
)

REM Export database (adjust connection details if needed)
echo Running pg_dump...
pg_dump -h localhost -U blackbook -d perunsblackbook -F p -f "%BACKUP_FILE%"

if errorlevel 1 (
    echo.
    echo ERROR: Database export failed!
    echo Check your PostgreSQL connection settings.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Export Complete!
echo ========================================
echo.
echo Backup file: %BACKUP_FILE%
echo.
echo Next steps:
echo 1. Copy this file to your Synology NAS
echo 2. Place it in /volume1/docker/blackbook/backups/
echo.

pause
