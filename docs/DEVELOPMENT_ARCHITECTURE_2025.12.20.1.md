# BlackBook Development Architecture & Workflow

**Document Version:** 2025.12.20.1  
**Status:** Active  
**Purpose:** Project memory for development workflow

---

## 🚨 CRITICAL: Development Workflow Rule

**All development MUST follow this workflow:**

```
C:\BlackBook (edit) → test locally → git push → SSH to Synology → git pull → restart Docker
```

**NEVER edit code directly on Synology network share (`\\BearCave\docker\blackbook`)**

This bypasses version control and causes codebase divergence.

---

## Repository Locations

| Location | Path | Purpose |
|----------|------|---------|
| **Local Development** | `C:\BlackBook` | Active development, testing |
| **GitHub** | `https://github.com/Xris-deOzz/BlackBook.git` | Version control, backup (CODE ONLY) |
| **Synology Production** | `/volume1/docker/blackbook` | Production deployment |

---

## Data Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        WHERE DATA LIVES                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   WINDOWS (C:\BlackBook)           SYNOLOGY (/volume1/docker/)         │
│   ──────────────────────           ────────────────────────────        │
│   • Code only                      • Code (pulled from GitHub)         │
│   • Empty/test database            • PRODUCTION DATABASE               │
│   • .env with localhost URI        • .env with Tailscale URI           │
│   • For development/testing        • 5,000+ people, 2,000 orgs         │
│                                                                         │
│   GITHUB (Private Repo)                                                 │
│   ─────────────────────                                                 │
│   • Code ONLY                                                           │
│   • NO .env file (excluded by .gitignore)                              │
│   • NO backups (excluded)                                               │
│   • NO data files (excluded)                                            │
│   • NO API keys or passwords                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### What's Excluded from GitHub (.gitignore)

- `.env` - Contains passwords, API keys, secrets
- `backups/` - Database backup files
- `data/*.csv` - Any data exports
- `venv/` - Python virtual environment
- `__pycache__/` - Python bytecode
- `.claude/` - Claude Code settings

### Database Locations

| Environment | DB_HOST | Database Location | Data |
|-------------|---------|-------------------|------|
| **Local Docker** | `db` | Docker container on Windows | Empty/test data |
| **Local Python** | `localhost` | Windows PostgreSQL | Empty/test data |
| **Synology** | `db` | Docker container on NAS | **PRODUCTION** (5,000+ contacts) |

> ⚠️ Your production data (5,000+ people, 2,000 orgs) lives ONLY on Synology. Local development uses empty/test databases.

---

## Development Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        STANDARD WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. LOCAL (C:\BlackBook)     2. GITHUB              3. SYNOLOGY       │
│   ───────────────────────    ─────────              ──────────────     │
│                                                                         │
│   • Write/modify code        • Version control      • Production       │
│   • Run local Docker         • Code backup          • Docker containers│
│   • Run pytest tests         • Change history       • PostgreSQL data  │
│   • Test migrations          • Rollback capability  • Tailscale access │
│                                                                         │
│        ───── git push ─────>      ───── git pull ─────>                │
│                                          │                              │
│                                          ▼                              │
│                                   docker-compose                        │
│                                   up --build -d                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Local Development Setup

### Prerequisites

- **Python 3.11** (installed)
- **Docker Desktop** (installed)
- **PostgreSQL** (installed on Windows - for non-Docker testing)
- **Git** (for version control)

### Directory Structure

```
C:\BlackBook\
├── .git/                    # Git repository
├── .env                     # Local environment (NOT in GitHub)
├── .env.example             # Template for .env
├── alembic/                 # Database migrations
├── app/                     # Application code
│   ├── models/              # SQLAlchemy models
│   ├── routers/             # FastAPI endpoints
│   ├── services/            # Business logic
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images
├── docs/                    # Documentation (versioned YYYY.MM.DD.V)
├── scripts/                 # Utility scripts
├── tests/                   # pytest tests
├── backups/                 # Database backups (NOT in GitHub)
├── docker-compose.yml       # Local Docker config
├── docker-compose.prod.yml  # Production Docker config
├── Dockerfile               # Container definition
└── requirements.txt         # Python dependencies
```

### Running Locally

**Option A: Docker Compose (recommended - matches production)**
```bash
cd C:\BlackBook
docker-compose up --build
# Access at http://localhost:8000
# Uses containerized PostgreSQL (empty database)
```

**Option B: Direct Python (uses local Windows PostgreSQL)**
```bash
cd C:\BlackBook
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# Edit .env: change DB_HOST=localhost
uvicorn app.main:app --reload --port 8000
```

### Running Tests

```bash
cd C:\BlackBook
venv\Scripts\activate
pytest tests/ -v
```

---

## Git Workflow

### Standard Commands

```bash
# Check status
git status

# Stage all changes
git add .

# Commit with descriptive message
git commit -m "fix: Tag dropdown now shows newly created tags with 0 associations"

# Push to GitHub
git push origin main
```

### Commit Message Format

```
<type>: <short description>

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- refactor: Code restructure
- test: Adding tests
- chore: Maintenance tasks
```

---

## Deployment to Synology

### Deployment Steps

```bash
# 1. SSH into Synology
ssh XrisNYC@bearcave

# 2. Navigate to project
cd /volume1/docker/blackbook

# 3. Pull latest from GitHub
git pull origin main

# 4. Rebuild and restart containers
sudo docker-compose -f docker-compose.prod.yml down
sudo docker-compose -f docker-compose.prod.yml up --build -d

# 5. Run migrations (if schema changed)
sudo docker exec blackbook-app alembic upgrade head

# 6. Check logs
sudo docker logs blackbook-app --tail 50
```

### Access URLs

| Environment | URL |
|-------------|-----|
| Local | `http://localhost:8000` |
| Synology (Tailscale) | `https://bearcave.tail1d5888.ts.net/` |

---

## Backup Strategy

### Production Database (Synology)

Automated via `scripts/backup.sh`:
- Runs daily at 3:00 AM
- Retains 7 days of backups
- Stores in `/volume1/docker/blackbook/backups/`

### Code Backup

All code is backed up to GitHub automatically when you push.

---

## Documentation Standards

### Version Format

All documentation uses: `YYYY.MM.DD.V`

- `YYYY` = Year
- `MM` = Month  
- `DD` = Day
- `V` = Version number for that day (1, 2, 3...)

Example: `2025.12.20.1` = First version on December 20, 2025

---

## Current State (December 2025)

### Recent Fixes

- ✅ **2025.12.20**: Fixed tag dropdown bug - newly created tags with 0 associations now appear in person profile dropdowns (changed INNER JOIN to direct filter on Tag.category)

### Known Issues

1. **Google Contacts Duplicates** - Sync creates duplicates (1,394 groups) due to inadequate matching logic
2. **Codebase was diverged** - Fixed by reconciling Synology → Local → GitHub

### Immediate Actions

1. ✅ Proper development workflow established
2. ✅ Tag dropdown fix applied to local codebase
3. ⬜ Commit and push tag fix to GitHub
4. ⬜ Pull to Synology and restart Docker
5. ⬜ Implement Google Contacts dedup fix (next priority)

---

*Last Updated: 2025.12.20*
