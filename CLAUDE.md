# BlackBook - Claude Code Instructions

## Project Overview
BlackBook is a self-hosted personal CRM for managing professional relationships with investors, advisors, lawyers, bankers, and other business contacts.

## Tech Stack
- **Backend:** Python 3.11, FastAPI
- **Database:** PostgreSQL (database name: `perunsblackbook`)
- **Frontend:** HTMX, TailwindCSS
- **Hosting:** Synology DS220+ via Docker

## Development Location
- **ONLY edit code in:** `C:\BlackBook`
- **NEVER edit on:** OneDrive or Synology network share

## Development Workflow

### 1. Start Local Server
```bash
cd C:\BlackBook
python -m uvicorn app.main:app --reload --port 8000
```

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

### Local PostgreSQL
```bash
psql -U blackbook -d perunsblackbook
```

### Synology PostgreSQL (via SSH)
```bash
ssh xrisnyc@bearcave
sudo docker exec -it blackbook-db psql -U blackbook -d perunsblackbook
```

### Run Migrations
```bash
# Local
cd C:\BlackBook
alembic upgrade head

# Synology (via SSH)
sudo docker exec blackbook-app alembic upgrade head
```

## Important Rules
1. **NEVER** edit code directly on Synology via network share (`\\BearCave`)
2. **ALWAYS** edit in `C:\BlackBook`, test locally, then deploy
3. **ALWAYS** create database backup before schema changes
4. Documentation version format: `YYYY.MM.DD.V`

## Key Directories
- `app/` - Main application code
- `app/routers/` - API endpoints
- `app/models/` - SQLAlchemy models
- `app/templates/` - Jinja2 HTML templates
- `app/static/` - CSS, JS, images
- `alembic/versions/` - Database migrations
- `docs/` - Project documentation

## Common Issues
- If server won't start, check `.env` file exists and has correct DATABASE_URL
- If migrations fail, check Alembic version history: `alembic history`
- If Docker issues on Synology, check logs: `sudo docker logs blackbook-app`
