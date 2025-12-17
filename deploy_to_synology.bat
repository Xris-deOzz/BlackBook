@echo off
echo Deploying BlackBook to Synology BearCave...
echo.

REM Sync code files to Synology (excludes .env, backups, .git)
echo Copying files...
xcopy /E /Y /I "app" "\\BearCave\docker\blackbook\app"
xcopy /E /Y /I "alembic" "\\BearCave\docker\blackbook\alembic"
xcopy /E /Y /I "scripts" "\\BearCave\docker\blackbook\scripts"
xcopy /E /Y /I "docs" "\\BearCave\docker\blackbook\docs"
xcopy /E /Y /I "tests" "\\BearCave\docker\blackbook\tests"
copy /Y "Dockerfile" "\\BearCave\docker\blackbook\"
copy /Y "docker-compose.prod.yml" "\\BearCave\docker\blackbook\"
copy /Y "docker-compose.yml" "\\BearCave\docker\blackbook\"
copy /Y "requirements.txt" "\\BearCave\docker\blackbook\"
copy /Y "alembic.ini" "\\BearCave\docker\blackbook\"
copy /Y "README.md" "\\BearCave\docker\blackbook\"
copy /Y ".gitignore" "\\BearCave\docker\blackbook\"

echo.
echo Files synced! Now rebuild on Synology:
echo   ssh admin@bearcave
echo   cd /volume1/docker/blackbook
echo   sudo docker-compose -f docker-compose.prod.yml up -d --build
echo.
pause
