# Claude Code Prompt - BlackBook CRM Development

**Date:** December 16, 2025
**Project:** Perun's BlackBook (Personal CRM)
**Location:** `C:\BlackBook`

---

## Project Overview

BlackBook is a self-hosted personal CRM for managing professional relationships with investors, advisors, lawyers, bankers, and other contacts. Built with Python/FastAPI, PostgreSQL, HTMX, and TailwindCSS. Phases 1-5 are complete (Core CRM, Email, Calendar, Views, AI Assistant).

---

## Key Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| **Main Spec** | `docs/Peruns_BlackBook_Specification_2025.12.07.1.md` | Full project specification |
| **Phase 5 Tasks** | `docs/PHASE_5_TASK_LIST.md` | AI Assistant implementation (142 tasks, all complete) |
| **AI Setup Guide** | `docs/AI_SETUP.md` | API key configuration for Claude/OpenAI/Gemini |
| **Latest Changelog** | `docs/CHANGELOG_2025.12.16.md` | Today's changes |
| **README** | `README.md` | Feature overview and setup |

---

## Current Status

### ✅ Completed (Phases 1-5)
- Core CRM (People, Organizations, Tags, Interactions)
- Gmail integration with email history
- Google Calendar integration with attendee matching
- Google Contacts sync (saved + other contacts, both accounts)
- Saved Views and Graph visualization
- AI Research Assistant (Claude, OpenAI, Gemini)
- Duplicate detection with fuzzy matching and exclusions
- Christmas email list generator

### ⏳ Pending Migration
A migration to strip HTML from interaction notes was created but not run:
- File: `alembic/versions/z5v23w4x6y78_strip_html_from_interaction_notes.py`
- Alternative script: `cleanup_html_notes.py` (run with venv active)

---

## Next Tasks (Priority Order)

### 1. HTML Cleanup Migration (Quick Win)
Run the cleanup script to strip `<p>`, `</p>`, `<br>` tags from interaction notes:
```bash
# Activate virtual environment first, then:
python cleanup_html_notes.py
```

### 2. Phase 6: Synology Production Deployment
Deploy to Synology DS220+ NAS:
- [ ] Create production Docker Compose config
- [ ] Configure Tailscale VPN for remote access
- [ ] Set up automated PostgreSQL backups
- [ ] Update Google OAuth redirect URIs for production domain
- [ ] Add health check endpoint
- [ ] Create deployment documentation

### 3. Deferred Features (Optional)
| Feature | Description | Complexity |
|---------|-------------|------------|
| Ollama Integration | Local AI models for privacy mode | Medium |
| Snapshot Restore UI | View/restore historical record states | Medium |
| Auto-apply AI Suggestions | Direct write mode without approval | Low |
| Conversation Search | Search within AI chat history | Low |
| Bulk Date Fix | Fix interaction dates like "2108" → "2018" | Low |
| Inline Editing | Edit interactions directly in table | Medium |

---

## Tech Stack Reference

| Component | Technology |
|-----------|------------|
| Backend | Python 3.12, FastAPI |
| Database | PostgreSQL 15, SQLAlchemy 2.0, Alembic |
| Frontend | Jinja2, HTMX, Alpine.js, TailwindCSS |
| AI Providers | Anthropic Claude, OpenAI, Google Gemini |
| Integrations | Gmail API, Google Calendar API, Google People API |

---

## Project Structure

```
app/
├── models/          # SQLAlchemy models
├── routers/         # FastAPI route handlers
├── services/        # Business logic
│   └── ai/          # AI providers, context builder, tools
├── templates/       # Jinja2 HTML templates
└── static/          # CSS, JS, icons

docs/                # Project documentation
alembic/versions/    # Database migrations
tests/               # Test files
```

---

## User Preferences

- Primary language: Python
- Ask detailed questions before writing code
- Draft task list before implementation
- Documentation version format: YYYY.MM.DD.V

---

## Notes

- Google accounts connected: `ossowski.chris@gmail.com`, `chris@blackperun.com`
- ~3,500 contacts synced from Google
- AI providers configured: Claude (Anthropic), OpenAI, Google Gemini
- Listen Notes API access denied (podcast search unavailable)
