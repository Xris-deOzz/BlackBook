# BlackBook - Claude Code Instructions

## IMPORTANT: Current Date
**Today's date is: 2025-12-21**
Always use **2025** (not 2024) when creating dated files or documentation.

## Project Overview
BlackBook is a self-hosted personal CRM for managing professional relationships with investors, advisors, lawyers, bankers, and other business contacts.

## Tech Stack
- **Backend:** Python 3.11, FastAPI
- **Database:** PostgreSQL (database name: `perunsblackbook`)
- **Frontend:** HTMX, TailwindCSS
- **Hosting:** Synology DS220+ via Docker

## Development Location
- **ONLY edit code in:** `C:\BlackBook`
- **NEVER edit on:** OneDrive or Synology network share (`\\BearCave`)

## Documentation Standards
- **Version format:** `YYYY.MM.DD.V` (e.g., `2025.12.21.1`)
- **File naming:** `FEATURE_NAME_YYYY.MM.DD.V.md`
- **Changelogs:** `CHANGELOG_YYYY.MM.DD.md`
- **ALWAYS use year 2025** for current work
- Completed task docs should be moved to `docs/archive/`

## Two-Tool Workflow
This project uses **Claude.ai** and **Claude Code** together:
- **Claude.ai:** Planning, architecture, multi-file analysis, task lists
- **Claude Code:** Code edits, implementation, testing, git operations
- **Handoff:** Claude Code writes summaries to `docs/` for Claude.ai reference
- **Checkpoints:** Git commits between tool transitions

## Development Workflow

### 1. Start Local Server
```bash
cd C:\BlackBook
python -m uvicorn app.main:app --reload --port 8000
```
Local server connects to Synology database via Tailscale (DB_HOST=bearcave, DB_PORT=5433)

### 2. Test Locally
Open browser: http://localhost:8000

### 3. Commit Changes
```bash
cd C:\BlackBook
git add .
git commit -m "Description of changes"
git push origin main
```

### 4. Deploy to Synology
```bash
# SSH to Synology
ssh xrisnyc@bearcave

# Navigate to project
cd /volume1/docker/blackbook

# Pull latest code
git pull origin main

# Restart containers
sudo docker-compose -f docker-compose.prod.yml down
sudo docker-compose -f docker-compose.prod.yml up --build -d

# Check logs if needed
sudo docker logs blackbook-app --tail 50
```

## Database Commands

### Synology PostgreSQL (via SSH)
```bash
ssh xrisnyc@bearcave
sudo docker exec -it blackbook-db psql -U blackbook -d perunsblackbook
```

### Create Backup (before schema changes)
```bash
ssh xrisnyc@bearcave
sudo docker exec blackbook-db pg_dump -U blackbook -d perunsblackbook > /volume1/docker/blackbook/backups/backup_YYYY.MM.DD.sql
```

### Run Migrations
```bash
# Synology (via SSH)
ssh xrisnyc@bearcave
sudo docker exec blackbook-app alembic upgrade head
```

## Important Rules
1. **NEVER** edit code directly on Synology via network share (`\\BearCave`)
2. **ALWAYS** edit in `C:\BlackBook`, test locally, then deploy
3. **ALWAYS** create database backup before schema changes
4. **ALWAYS** use year 2025 in documentation filenames
5. Ask detailed questions and draft task lists before writing code

## Key Directories
- `app/` - Main application code
- `app/routers/` - API endpoints
- `app/models/` - SQLAlchemy models
- `app/templates/` - Jinja2 HTML templates
- `app/static/` - CSS, JS, images
- `alembic/versions/` - Database migrations
- `docs/` - Project documentation
- `docs/archive/` - Completed/old documentation

## Common Issues
- If server won't start, check `.env` file exists with correct database settings
- If migrations fail, check Alembic version: `alembic history`
- If Docker issues on Synology, check logs: `sudo docker logs blackbook-app`
- If Claude Code uses wrong paths, ensure VS Code opened `C:\BlackBook` folder
