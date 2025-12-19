# BlackBook Development Architecture & Workflow

**Document Version:** 2025.12.19.1  
**Status:** Active  
**Purpose:** Project memory for development workflow

---

## Repository Locations

| Location | Path | Purpose |
|----------|------|---------|
| **Local Development** | `C:\BlackBook` | Active development, testing |
| **GitHub** | `https://github.com/Xris-deOzz/BlackBook.git` | Version control, backup |
| **Synology Production** | `/volume1/docker/blackbook` | Production deployment |

> ⚠️ **DO NOT develop directly on Synology** - this caused divergence issues in Dec 2025

---

## Development Workflow

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
│        ───── git push ─────>      <───── git pull ─────                │
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
- **PostgreSQL** (installed on Windows)
- **Git** (for version control)

### Directory Structure

```
C:\BlackBook\
├── .git/                    # Git repository
├── .env                     # Local environment (not committed)
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
├── backups/                 # Database backups
├── docker-compose.yml       # Local Docker config
├── docker-compose.prod.yml  # Production Docker config
├── Dockerfile               # Container definition
└── requirements.txt         # Python dependencies
```

### Running Locally

**Option A: Direct Python (uses local PostgreSQL)**
```bash
cd C:\BlackBook
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Option B: Docker Compose (containerized everything)**
```bash
cd C:\BlackBook
docker-compose up --build
```

### Running Tests

```bash
cd C:\BlackBook
venv\Scripts\activate
pytest tests/ -v
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description_of_change"

# Apply migrations (local)
alembic upgrade head

# Check current version
alembic current
```

---

## Git Workflow

### Branching Strategy

```
main              ← Production-ready code
  │
  └── feature/*   ← New features (e.g., feature/google-sync-dedup)
  └── fix/*       ← Bug fixes (e.g., fix/duplicate-contacts)
  └── docs/*      ← Documentation updates
```

### Standard Commands

```bash
# Check status
git status

# Create feature branch
git checkout -b feature/my-new-feature

# Stage and commit
git add .
git commit -m "Descriptive commit message"

# Push to GitHub
git push origin feature/my-new-feature

# Merge to main (after testing)
git checkout main
git merge feature/my-new-feature
git push origin main
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

# 5. Run migrations
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

## Documentation Standards

### Version Format

All documentation uses: `YYYY.MM.DD.V`

- `YYYY` = Year
- `MM` = Month  
- `DD` = Day
- `V` = Version number for that day (1, 2, 3...)

Example: `2025.12.19.1` = First version on December 19, 2025

---

## Current State (December 2025)

### Completed
1. ✅ Move project from OneDrive to `C:\BlackBook`
2. ✅ Reconcile differences between OneDrive and Synology
3. ⬜ Push consolidated codebase to GitHub

### Next Steps
4. ⬜ Implement Google Contacts dedup fix
5. ⬜ Test locally before deploying to Synology

---

*Last Updated: 2025.12.19*
