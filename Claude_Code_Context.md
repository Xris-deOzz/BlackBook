# Perun's BlackBook - Claude Code Context

**Document Version:** 2025.12.16.2
**Last Updated:** 2025-12-16
**Application Version:** 0.5.3
**Current Phase:** Phase 5.5 - Gmail Integration
**Next Phase:** Phase 6 - Production Deployment (Manual)

---

## Quick Status

| Component | Status |
|-----------|--------|
| Phase 1: Database + Import | ✅ Complete |
| Phase 2: Web Application | ✅ Complete |
| Phase 3A: Gmail Integration | ✅ Complete |
| Phase 3B: Calendar Integration | ✅ Complete |
| Phase 4: PWA + Deployment Prep | ✅ Complete |
| **Phase 5A: AI Infrastructure** | ✅ **Complete** |
| **Phase 5B: Chat UI & Context** | ✅ **Complete** |
| **Phase 5C: Research Tools** | ✅ **Complete** |
| **Phase 5D: Suggestions & Snapshots** | ✅ **Complete** |
| **Phase 5E: Polish & Integration** | ✅ **Complete** |
| **Phase 5.5: Gmail Integration** | 🔄 **In Progress** |
| Phase 6: Synology Deployment | ⏳ Pending |
| Tests Passing | 570+ |
| Docker Containers | blackbook-db (PostgreSQL 15) |

---

## Project Overview

Perun's BlackBook is a self-hosted personal CRM system for managing professional relationships. It replaces an Airtable-based contact management system and provides:

- **People & Organizations Management** - Full CRUD with tags, relationships, notes
- **Interaction Tracking** - Meetings, calls, emails logged with history
- **Gmail Integration** - Email history search, log emails as interactions
- **Calendar Integration** - Meeting sync, attendee matching, pending contacts
- **Social Graph** - Visual network visualization (vis.js)
- **Mobile-Ready PWA** - Progressive Web App with home screen support
- **AI Research Assistant** - Multi-provider AI chat with web search and profile suggestions

---

## Phase 5: AI Research Assistant (COMPLETE)

### Overview
AI-powered research assistant to help populate CRM with information about people and companies.

### Key Features
- Multi-provider AI chat (Claude, OpenAI/GPT-4, Google Gemini, Ollama local)
- Standalone chat page + contextual sidebar on entity pages
- Real-time web search (Brave Search API)
- YouTube and podcast interview discovery (Listen Notes API)
- AI-suggested CRM field updates with approval workflow
- Record snapshots for undo/restore functionality
- Privacy controls (emails/phones never sent to external APIs)

### Documentation
- **Setup Guide:** `docs/AI_SETUP.md`
- **Overview & Architecture:** `docs/PHASE_5_AI_ASSISTANT.md`
- **Detailed Task List:** `docs/PHASE_5_TASK_LIST.md`

### Sub-Phases Progress
| Sub-Phase | Tasks | Focus | Status |
|-----------|-------|-------|--------|
| 5A | 32 | Database schema, provider abstraction, API keys | ✅ Complete |
| 5B | 35 | Chat UI, context builder, privacy filter | ✅ Complete |
| 5C | 31 | Web search, YouTube, podcasts, research tools | ✅ Complete |
| 5D | 27 | Suggestions, snapshots, data population | ✅ Complete |
| 5E | 17 | Dashboard integration, polish, docs | ✅ Complete |
| **Total** | **142** | | ✅ All Complete |

### What's Been Implemented

#### Phase 5A - AI Infrastructure (COMPLETE)
**Database Models** (`app/models/`):
- `ai_provider.py` - AI provider configuration (OpenAI, Anthropic, Google, Ollama)
- `ai_api_key.py` - Encrypted API key storage with validation status
- `ai_conversation.py` - Chat conversations linked to persons/organizations
- `ai_message.py` - Chat messages with role, tokens, tool calls
- `ai_suggestion.py` - AI-suggested field updates with approval workflow
- `ai_data_access.py` - Singleton settings for what AI can access
- `record_snapshot.py` - Entity snapshots for undo/restore

**AI Services** (`app/services/ai/`):
- `base_provider.py` - Abstract provider interface
- `openai_provider.py` - OpenAI GPT-4/GPT-3.5 implementation
- `anthropic_provider.py` - Claude 3 implementation (validated working)
- `google_provider.py` - Google Gemini implementation
- `provider_factory.py` - Provider instantiation and caching
- `models.py` - Pydantic models for AI operations
- `token_utils.py` - Token counting utilities

**Settings UI** (`app/templates/settings/`):
- `ai_providers.html` - AI Providers tab in Settings
- `_ai_provider_card.html` - Provider card partial with key management
- Settings router extended with AI endpoints

**Migration**:
- `alembic/versions/m2i90j1k3l45_add_ai_tables.py` - All AI tables

#### Phase 5B - Chat UI & Context (COMPLETE)
**Context Building** (`app/services/ai/`):
- `context_builder.py` - Builds CRM context for AI conversations
- `privacy_filter.py` - Strips emails/phones from AI context
- `chat_service.py` - Chat conversation management

#### Phase 5C - Research Tools (COMPLETE)
**Search Services** (`app/services/ai/search/`):
- `base.py` - Abstract search interface
- `brave.py` - Brave Search API integration
- `youtube.py` - YouTube Data API integration
- `listen_notes.py` - Listen Notes podcast search
- `search_service.py` - Unified search service

**Research Services** (`app/services/ai/research/`):
- `person_researcher.py` - Person research workflows
- `company_researcher.py` - Company research workflows
- `workflow.py` - Research workflow orchestration

**Tools** (`app/services/ai/tools/`):
- `base.py` - Tool interface
- `definitions.py` - Tool schemas for function calling
- `executor.py` - Tool execution dispatcher

#### Phase 5D - AI Profile Suggestions (COMPLETE)
**Suggestion Service** (`app/services/ai/`):
- `suggestion_service.py` - Parses AI responses for structured suggestions, manages suggestion lifecycle

**API Endpoints** (`app/routers/ai_chat.py`):
- `GET /ai-chat/suggestions/{entity_type}/{entity_id}` - Get pending suggestions
- `POST /ai-chat/suggestions/{id}/accept` - Accept and apply a suggestion
- `POST /ai-chat/suggestions/{id}/reject` - Reject a suggestion
- `POST /ai-chat/suggestions/{entity_type}/{entity_id}/accept-all` - Bulk accept
- `POST /ai-chat/suggestions/{entity_type}/{entity_id}/reject-all` - Bulk reject
- `GET /ai-chat/suggestions/{entity_type}/{entity_id}/stats` - Suggestion statistics

**UI Components** (`app/templates/partials/_ai_sidebar.html`):
- Pending Suggestions Panel with Accept/Reject buttons
- Animated card removal on action
- Accept All / Reject All bulk actions
- Toast notifications for user feedback

**AI System Prompt** (`app/services/ai/context_builder.py`):
- Updated system prompt instructs AI to output structured JSON suggestions
- Format: `{"suggestions": [{"field": "...", "value": "...", "confidence": 0.9, "source": "..."}]}`
- Confidence scores (0.0-1.0) and source URLs

**Suggestable Fields**:
- **Person**: title, linkedin, twitter, website, location, notes
- **Organization**: website, category, description, notes

#### Phase 5E - Polish & Integration (COMPLETE)
**Navigation & Dashboard**:
- AI Chat link in main navigation (desktop and mobile)
- Pending Suggestions badge counter in nav (auto-updates)
- Recent AI Conversations widget on dashboard
- AI Suggestions widget on dashboard
- Quick-start research buttons (Research Person / Research Company)
- Research modal for selecting entity to research

**UX Improvements**:
- Keyboard shortcuts (Enter to send, Escape to close, Shift+Enter for newline)
- Typing indicator with animated dots and status updates
- Auto-resizing textarea input
- User-friendly error messages with retry button
- Last message retry functionality

**Usage Statistics**:
- Usage widget in Settings > AI Providers tab
- Total conversations, messages, tokens (in/out)
- Suggestions stats (pending/accepted/rejected)
- Per-provider token tracking
- JSON API endpoint: `GET /ai-chat/usage`

**Documentation**:
- `docs/AI_SETUP.md` - Setup guide with API key instructions
- Updated `Claude_Code_Context.md` with Phase 5 completion

### Installed Dependencies
```
anthropic>=0.75.0     # Claude API
openai>=2.9.0         # OpenAI GPT API
google-generativeai   # Google Gemini API
tiktoken              # Token counting for OpenAI
httpx                 # Async HTTP client for search APIs
```

### Validated API Keys
- **Claude (Anthropic)**: ✅ Valid - tested with `claude-3-haiku-20240307`
- **OpenAI**: ✅ Valid - connection tested successfully
- **Google Gemini**: ✅ Valid - tested with `gemini-2.5-pro` (tool calling working)

### Search API Status
- **Brave Search**: Code ready, needs API key
- **YouTube Data API**: Code ready, needs API key
- **Listen Notes**: API access denied (application rejected)

### What's Working Now
- **AI Chat**: Full chat with Claude, OpenAI, or Gemini from person/organization detail pages
- **Tool/Function Calling**: AI can call tools during conversations (web search ready when API keys added)
- **Streaming Responses**: Real-time streaming with tool status updates
- **Profile Suggestions**: AI suggests field updates, user can accept/reject
- **Record Snapshots**: Automatic backup before AI applies changes
- **Privacy Filter**: Emails and phone numbers automatically stripped before sending to AI
- **Dashboard Integration**: Recent conversations and suggestions widgets
- **Navigation**: AI Chat link with pending badge in nav
- **Usage Tracking**: Token counts and statistics per provider

### Future Enhancements (Post-Phase 5)
- [ ] Batch research multiple contacts at once
- [ ] Custom prompts/templates for research
- [ ] Export AI conversation history
- [ ] Snapshot viewer UI and restore functionality
- [ ] Alternative podcast search API (Listen Notes unavailable)

---

## Development Environment

### Prerequisites
- Python 3.11+ (Windows)
- Docker Desktop
- PostgreSQL 15 (via Docker)

### Database Connection
```
Host: localhost
Port: 5432
Database: perunsblackbook
User: blackbook
Password: BlackBook2024!
```

### Project Location
```
C:\Users\ossow\OneDrive\PerunsBlackBook\
```

### Start Development Server
```powershell
# 1. Start Docker Desktop (needed for PostgreSQL)

# 2. Start ONLY the database container (NOT the app container)
docker start blackbook-db

# 3. Activate virtual environment
cd C:\Users\ossow\OneDrive\PerunsBlackBook
.\venv\Scripts\Activate.ps1

# 4. Run development server
uvicorn app.main:app --reload --port 8000

# Access at: http://localhost:8000
```

### Important: Docker Container Management
```powershell
# Check running containers
docker ps

# The blackbook-app container contains an OLD version of the code
# For development, STOP it and use local uvicorn:
docker stop blackbook-app

# Keep only the database running:
docker start blackbook-db
```

### Run Tests
```powershell
pytest tests/ -v
```

### Create Database Migration
```powershell
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## Current Data Statistics

| Table | Records |
|-------|---------|
| persons | ~1,012 |
| organizations | ~1,259 |
| tags | 77 |
| interactions | 130+ |
| person_tags | 992 |
| organization_tags | 1,448 |

### Connected Google Accounts
- ossowski.chris@gmail.com (primary)
- chris@blackperun.com
- xris.chosser@gmail.com

### Google OAuth Scopes (Updated 2025-12-16)

The following scopes are configured in Google Cloud Console. **Code update required** in `app/services/google_auth.py` to request these.

#### All Scopes Implemented in Code (22 Total)

As of 2025-12-16, all scopes are configured in `app/services/google_auth.py` and Google Cloud Console.

| Category | Scope | Purpose | Status |
|----------|-------|---------|--------|
| **User Info** | `userinfo.email` | User identity | ✅ Working |
| | `userinfo.profile` | User profile display | ✅ Working |
| **Gmail** | `gmail.readonly` | Read email history | ✅ Working |
| | `gmail.send` | Send emails on behalf | ✅ Ready |
| | `gmail.compose` | Manage drafts, send | ✅ Ready |
| | `gmail.labels` | Manage email labels | ✅ Ready |
| | `gmail.settings.basic` | Email settings/filters | ✅ Ready |
| **Calendar** | `calendar.readonly` | View calendar events | ✅ Working |
| | `calendar.events` | Create/edit events | ✅ Ready |
| | `calendar.events.readonly` | View events only | ✅ Ready |
| | `calendar.calendarlist` | Manage calendar list | ✅ Ready |
| | `calendar.calendarlist.readonly` | List calendars | ✅ Ready |
| | `calendar.calendars` | Create calendars | ✅ Ready |
| | `calendar.events.freebusy` | Check availability | ✅ Ready |
| **Contacts** | `contacts.readonly` | Read Google Contacts | ✅ Working |
| | `contacts` | Full contacts access | ✅ Ready |
| | `contacts.other.readonly` | "Other contacts" | ✅ Ready |
| **People API** | `user.organization.read` | **Work history** | ✅ Ready |
| | `user.phonenumbers.read` | Phone numbers | ✅ Ready |
| | `user.emails.read` | All email addresses | ✅ Ready |
| | `user.birthday.read` | Birthday | ✅ Ready |
| | `profile.emails.read` | Profile emails | ✅ Ready |

**Note:** `tasks` scope is NOT in Google Cloud Console and has been removed from code.

**See:** `docs/GOOGLE_SETUP.md` for complete scope reference, Workspace admin setup, and troubleshooting.

---

## Project Structure

```
PerunsBlackBook/
├── app/                           # Main application
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings & environment vars
│   ├── database.py                # SQLAlchemy setup
│   │
│   ├── models/                    # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── person.py              # Person model
│   │   ├── person_email.py        # Multiple emails per person
│   │   ├── person_phone.py        # Phone numbers
│   │   ├── organization.py        # Organization model
│   │   ├── tag.py                 # Tags + junction tables
│   │   ├── interaction.py         # Interaction tracking
│   │   ├── saved_view.py          # Saved filter views
│   │   ├── google_account.py      # OAuth credentials (encrypted)
│   │   ├── email_cache.py         # Gmail search cache
│   │   ├── email_ignore.py        # Email ignore patterns
│   │   ├── calendar_event.py      # Calendar event cache
│   │   ├── pending_contact.py     # Unknown attendee queue
│   │   ├── import_history.py      # LinkedIn/Google import logs
│   │   ├── ai_provider.py         # ✅ Phase 5: AI provider config
│   │   ├── ai_api_key.py          # ✅ Phase 5: Encrypted API keys
│   │   ├── ai_conversation.py     # ✅ Phase 5: Chat conversations
│   │   ├── ai_message.py          # ✅ Phase 5: Chat messages
│   │   ├── ai_suggestion.py       # ✅ Phase 5: AI suggestions
│   │   ├── ai_data_access.py      # ✅ Phase 5: Data access settings
│   │   └── record_snapshot.py     # ✅ Phase 5: Entity snapshots
│   │
│   ├── routers/                   # API endpoints
│   │   ├── __init__.py
│   │   ├── persons.py             # /people/* routes
│   │   ├── organizations.py       # /organizations/* routes
│   │   ├── interactions.py        # /interactions/* routes
│   │   ├── tags.py                # /tags/* routes
│   │   ├── views.py               # /views/* (saved views)
│   │   ├── graph.py               # /graph (social network)
│   │   ├── auth.py                # /auth/* (Google OAuth)
│   │   ├── emails.py              # /people/{id}/emails
│   │   ├── settings.py            # /settings (8 tabs, incl. AI)
│   │   ├── calendar.py            # /calendar/* routes
│   │   ├── pending_contacts.py    # /pending-contacts/*
│   │   └── import_contacts.py     # /import/* (LinkedIn CSV)
│   │
│   ├── services/                  # Business logic
│   │   ├── __init__.py
│   │   ├── encryption.py          # AES-256 token encryption
│   │   ├── google_auth.py         # OAuth flow handling
│   │   ├── gmail_service.py       # Gmail API integration
│   │   ├── calendar_service.py    # Calendar API integration
│   │   ├── contacts_service.py    # Google Contacts sync
│   │   ├── person_merge.py        # Duplicate merging
│   │   ├── duplicate_service.py   # Duplicate detection
│   │   ├── linkedin_import.py     # CSV import logic
│   │   └── ai/                    # ✅ Phase 5: AI Services
│   │       ├── __init__.py
│   │       ├── base_provider.py       # Abstract provider interface
│   │       ├── openai_provider.py     # OpenAI GPT implementation
│   │       ├── anthropic_provider.py  # Claude implementation
│   │       ├── google_provider.py     # Gemini implementation
│   │       ├── provider_factory.py    # Provider instantiation
│   │       ├── context_builder.py     # CRM context for AI
│   │       ├── privacy_filter.py      # Strip sensitive data
│   │       ├── chat_service.py        # Chat management
│   │       ├── suggestion_service.py  # ✅ AI suggestion management
│   │       ├── models.py              # Pydantic models
│   │       ├── token_utils.py         # Token counting
│   │       ├── search/                # Search integrations
│   │       │   ├── base.py
│   │       │   ├── brave.py           # Brave Search API
│   │       │   ├── youtube.py         # YouTube Data API
│   │       │   ├── listen_notes.py    # Podcast search
│   │       │   └── search_service.py  # Unified search
│   │       ├── research/              # Research workflows
│   │       │   ├── person_researcher.py
│   │       │   ├── company_researcher.py
│   │       │   └── workflow.py
│   │       └── tools/                 # Function calling
│   │           ├── base.py
│   │           ├── definitions.py
│   │           └── executor.py
│   │
│   ├── templates/                 # Jinja2 HTML templates
│   │   ├── base.html              # Base layout + navigation
│   │   ├── dashboard.html         # Home dashboard
│   │   ├── persons/               # Person pages
│   │   ├── organizations/         # Organization pages
│   │   ├── interactions/          # Interaction pages
│   │   ├── tags/                  # Tag management
│   │   ├── views/                 # Saved views
│   │   ├── graph/                 # Social graph
│   │   ├── settings/              # Settings (8 tabs)
│   │   │   ├── index.html         # Main settings page
│   │   │   ├── ai_providers.html  # ✅ Phase 5: AI Providers tab
│   │   │   └── _ai_provider_card.html  # Provider card partial
│   │   ├── calendar/              # Calendar widgets
│   │   └── pending_contacts/      # Pending contact queue
│   │
│   └── static/                    # Static files
│       ├── manifest.json          # PWA manifest
│       └── icons/                 # PWA icons (14 sizes)
│
├── alembic/                       # Database migrations
│   ├── alembic.ini
│   └── versions/                  # Migration files
│       └── m2i90j1k3l45_add_ai_tables.py  # ✅ Phase 5 migration
│
├── tests/                         # Pytest test suite
│   ├── conftest.py                # Test fixtures
│   ├── test_*.py                  # 20+ test files
│   └── __init__.py
│
├── scripts/                       # Utility scripts
│
├── docs/                          # Documentation
│   ├── DATA_MAPPING.md            # Airtable field mapping
│   ├── GOOGLE_SETUP.md            # OAuth setup guide
│   ├── SYNOLOGY_DEPLOYMENT.md     # NAS deployment guide
│   ├── PHASE_5_AI_ASSISTANT.md    # Phase 5 overview & architecture
│   ├── PHASE_5_TASK_LIST.md       # Phase 5 detailed tasks
│   └── Peruns_BlackBook_Specification_*.md
│
├── docker-compose.yml             # Development Docker
├── docker-compose.prod.yml        # Production Docker (Synology)
├── Dockerfile                     # App container build
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables
├── .env.example                   # Env template
└── Claude_Code_Context.md         # THIS FILE
```

---

## Feature Summary by Phase

### Phase 1: Database & Import (Complete)
- PostgreSQL schema design
- Airtable data migration
- 1,012 persons, 1,259 organizations imported

### Phase 2: Web Application (Complete)
- FastAPI + HTMX architecture
- Person/Organization/Interaction CRUD
- Tag management with color picker
- Saved views system
- Social graph visualization (vis.js)
- A-Z alphabet navigation
- Column resizing with persistence
- Profile pictures and logos
- Mobile-responsive navigation

### Phase 3A: Gmail Integration (Complete)
- Google OAuth authentication
- Multi-account support
- Email history search per person
- Email caching (1-hour TTL)
- "Log as Interaction" feature
- Email ignore patterns (domains/addresses)
- Settings page with 7 tabs

### Phase 3B: Calendar Integration (Complete)
- Calendar event syncing
- Attendee matching to persons
- Pending contacts queue
- Dashboard widgets (Today's Meetings)
- Auto-interaction creation from meetings
- Person merge/deduplication feature

### Phase 4: PWA & Deployment Prep (Complete)
- Progressive Web App manifest
- 14 icon sizes for all devices
- Production Docker configuration
- Synology-optimized compose file
- Backup/restore scripts
- Deployment documentation

### Phase 5: AI Research Assistant (Planning Complete)
- Multi-provider AI chat (Claude, OpenAI, Gemini)
- Contextual research with CRM data awareness
- Web search, YouTube, and podcast discovery
- AI-suggested CRM field updates
- Record snapshots for data safety
- **See:** `docs/PHASE_5_AI_ASSISTANT.md` and `docs/PHASE_5_TASK_LIST.md`

### Phase 6: Synology Production Deployment (Pending)
- Deploy to Synology DS220+ NAS
- Configure Tailscale VPN
- Set up automated backups
- Update OAuth redirect URIs

---

## Settings Page Tabs

The Settings page (`/settings`) has 9 tabs:

1. **Google Accounts** - Connect/disconnect Google accounts
2. **Import Contacts** - LinkedIn CSV upload, Google Contacts sync
3. **Data Management** - Duplicate detection and merge
4. **Email Ignore** - Domains and email patterns to ignore
5. **Tags** - View all tags with usage counts
6. **Pending** - Unknown meeting attendees queue
7. **AI Providers** - AI API keys (Claude, OpenAI, Gemini), search APIs, data access controls
8. **AI Chat** - AI conversation history, usage statistics by model (collapsible sections), pending suggestions
9. **Organization Types** - Manage organization type categories

---

## Key Files Reference

| Purpose | File |
|---------|------|
| App entry point | `app/main.py` |
| Configuration | `app/config.py` |
| Database setup | `app/database.py` |
| Base template | `app/templates/base.html` |
| Dashboard | `app/templates/dashboard.html` |
| PWA manifest | `app/static/manifest.json` |
| Dev Docker | `docker-compose.yml` |
| Prod Docker | `docker-compose.prod.yml` |
| Phase 5 Overview | `docs/PHASE_5_AI_ASSISTANT.md` |
| Phase 5 Tasks | `docs/PHASE_5_TASK_LIST.md` |
| This doc | `Claude_Code_Context.md` |

---

## Environment Variables

Required in `.env`:

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=perunsblackbook
DB_USER=blackbook
DB_PASSWORD=BlackBook2024!

# Application
SECRET_KEY=your-secret-key
DEBUG=true

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Encryption (for OAuth tokens and AI API keys)
ENCRYPTION_KEY=your-fernet-key

# --- Phase 5: AI Research Assistant ---
# AI Providers (keys stored encrypted in DB, these are optional defaults)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_AI_API_KEY=...

# Search APIs
# BRAVE_SEARCH_API_KEY=...
# YOUTUBE_API_KEY=...
# LISTEN_NOTES_API_KEY=...

# AI Settings
# AI_DEFAULT_PROVIDER=anthropic
# AI_MAX_CONTEXT_TOKENS=4000
# AI_STREAMING_ENABLED=true
```

---

## Common Issues & Solutions

### Browser showing old version
**Cause:** Docker `blackbook-app` container running with old image
**Solution:**
```powershell
docker stop blackbook-app
uvicorn app.main:app --reload --port 8000
```

### Database connection refused
**Cause:** Docker Desktop not running or blackbook-db stopped
**Solution:**
```powershell
# Start Docker Desktop first, then:
docker start blackbook-db
```

### Port 8000 already in use
**Cause:** Multiple uvicorn processes running
**Solution:**
```powershell
# Kill all Python processes
Get-Process python* | Stop-Process -Force
# Then restart
uvicorn app.main:app --reload --port 8000
```

---

## Changelog

### 2025-12-16 (Session 2) - OAuth Scopes Verified & Gmail Compose Utility
- **OAuth Scope Configuration Complete**
  - Updated `app/services/google_auth.py` with all 22 OAuth scopes
  - Successfully connected `ossowski.chris@gmail.com` and `chris@blackperun.com`
  - Configured Google Workspace admin settings for custom domain accounts
  - Fixed test user re-authentication issues (remove + re-add trick)
  - Updated `docs/GOOGLE_SETUP.md` to version 2025.12.16.2 with Workspace admin guide

- **Gmail Compose Utility Created**
  - New file: `app/utils/gmail_compose.py`
  - Functions: `build_gmail_compose_url()`, `build_gmail_compose_url_with_chooser()`, `build_bulk_bcc_url()`, `build_christmas_email_url()`
  - Email button on Person detail page now works
  - Unit tests: `tests/test_gmail_compose.py`

- **Connected Google Accounts (with new scopes)**
  - `ossowski.chris@gmail.com` ✅ Active
  - `chris@blackperun.com` ✅ Active (Workspace trust configured)
  - `xris.chosser@gmail.com` ⏳ Pending (test user issue)

### 2025-12-16 (Session 1) - OAuth Scopes Expansion
- **Expanded Google OAuth Scopes in Google Cloud Console**
  - Added 20+ new OAuth scopes for enhanced Google integration
  - **Gmail send/compose**: `gmail.send`, `gmail.compose` for Christmas emails feature
  - **Calendar full access**: `calendar.events`, `calendar.calendarlist`, `calendar.calendars`
  - **People API enrichment**: `user.organization.read` (work history!), `user.phonenumbers.read`, `user.emails.read`, `user.birthday.read`
  - **Contacts full sync**: `contacts`, `contacts.other.readonly` (import "Other contacts")
  - Updated `docs/GOOGLE_SETUP.md` to version 2025.12.16.1 with complete scope reference

### 2025-12-12 (Session 7)
- **Organizations List Page - Multi-Tag Filter with AND/OR Logic**
  - Fixed `tag_ids` parameter not being received by FastAPI endpoint
  - Used FastAPI `Query` alias to map URL parameter `tag_ids` to `selected_tags` variable
  - Multi-tag filter now works correctly with AND (must have all tags) and OR (any tag) logic
  - Tags persist in UI after applying filter
  - Files modified: `app/routers/organizations.py` (lines 61, 209)

- **Organizations List Page - Filter Bar Redesign**
  - Reorganized filter bar into two rows for better navigation
  - **Row 1:** Search box (full width), Per Page selector, Clear Filters, Save View buttons
  - **Row 2:** Category dropdown, Type dropdown, Tags multi-select with AND/OR toggle and Go button
  - Tags filter now has more horizontal space (`flex-1`)
  - File: `app/templates/organizations/list.html`

### 2025-12-12 (Session 6)
- **AI Chat Moved to Settings Page**
  - Removed AI Chat from main navigation bar
  - Added AI Chat as 8th tab in Settings page (`/settings?tab=ai-chat`)
  - Files modified: `app/templates/base.html`, `app/templates/settings/index.html`, `app/routers/settings.py`

- **Model-Specific Usage Statistics**
  - Added "Usage by Model" table to AI Chat settings tab
  - Shows per-provider/per-model token usage breakdown (conversations, messages, tokens in/out)
  - Provider badges with color coding (OpenAI=green, Anthropic=orange, Google=blue)
  - File: `app/routers/settings.py` (model_stats_query)

- **Collapsible Sections in AI Chat Settings**
  - Overview Statistics section (collapsible)
  - Usage by Model table (collapsible)
  - All Conversations list (collapsible)
  - Uses native HTML `<details>` element with animated chevron icons
  - File: `app/templates/settings/index.html`

- **Documentation Updated**
  - Updated `docs/Peruns_BlackBook_Specification_2025.12.07.1.md` to v2025.12.12.1
  - Updated `Claude_Code_Context.md` to v2025.12.12.1
  - Phases 1-5 all marked complete
  - Settings tabs updated to 9 tabs

### 2025-12-10 (Session 5)
- **Google Gemini Provider Fixed and Validated**
  - Updated model names from retired Gemini 1.5 models (retired April 2025) to current 2.x models
  - New models: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.0-flash`
  - Default model: `gemini-2.0-flash`
  - Successfully tested tool/function calling with `add_relationship` tool
  - File: `app/services/ai/google_provider.py`

- **Context Builder Relationship Fix**
  - Fixed `AttributeError: 'PersonRelationship' object has no attribute 'to_person'`
  - Changed `rel.to_person` to `rel.related_person` in context_builder.py line 135
  - File: `app/services/ai/context_builder.py`

- **Model Validation in Chat Service**
  - Added validation to check if stored `conversation.model_name` exists in provider's available models
  - Falls back to `provider.default_model` if stored model is invalid/deprecated
  - Prevents 404 errors from old conversations with retired model names
  - Applied to both `send_message()` and streaming methods
  - File: `app/services/ai/chat_service.py` (lines ~400 and ~587)

- **Documentation Updated**
  - All three documentation files updated to reflect Phase 5 completion
  - `docs/PHASE_5_TASK_LIST.md` - Version 2025.12.10.2, 142/142 tasks complete
  - `docs/PHASE_5_AI_ASSISTANT.md` - Version 2025.12.10.2, all phases marked complete
  - `Claude_Code_Context.md` - Version 2025.12.10.2, Gemini status updated

### 2025-12-09 (Session 4)
- **Tool Support for Streaming Complete**
  - Rewrote `send_message_stream()` in chat_service.py to support tools during streaming
  - Uses non-streaming for tool execution loop, yields status updates ("*Using tools: web_search...*")
  - Streams final response after tools complete
  - All tool calls and token usage properly tracked

- **Record Snapshots for AI Suggestions Complete**
  - Updated `suggestion_service.py` to create snapshots before applying changes
  - Added `_create_snapshot_for_entity()` helper method
  - Uses `RecordSnapshot.create_for_person()` and `create_for_organization()`
  - Change source: `ChangeSource.ai_suggestion`

- **OpenAI Provider Setup Complete**
  - Installed `openai` package (v2.9.0)
  - Connection successfully tested from Settings UI

- **Test Fixes**
  - Fixed `test_ai_providers.py` - updated Anthropic model assertions to use `claude-3-5-sonnet-latest` and `claude-3-5-haiku-latest`
  - Fixed `test_provider_factory.py` - added database cleanup before tests to handle pre-existing providers
  - All 87 AI-related tests passing

- **Listen Notes API Unavailable**
  - API key application was declined
  - Podcast search infrastructure in place but non-functional without API access

### 2025-12-09 (Session 3)
- **Phase 5D - AI Profile Suggestions Complete**
  - Created `suggestion_service.py` for parsing AI responses and managing suggestions
  - Added 6 API endpoints for suggestion management (accept, reject, bulk actions)
  - Updated AI system prompt to output structured JSON suggestions
  - Added suggestions panel to AI sidebar with Accept/Reject buttons
  - Animated card removal and toast notifications for user feedback
  - Suggestable fields: Person (title, linkedin, twitter, website, location, notes), Organization (website, category, description, notes)

- **Key Fixes Applied:**
  - Fixed Anthropic provider to accept both `ChatMessage` objects and plain dicts
  - Changed default model from `claude-3-5-sonnet-20241022` to `claude-3-haiku-20240307` (404 fix)
  - Integrated suggestion parsing into chat service after AI responses

- **Files Created:**
  - `app/services/ai/suggestion_service.py` - Suggestion management service

- **Files Modified:**
  - `app/routers/ai_chat.py` - Added suggestion endpoints
  - `app/services/ai/context_builder.py` - Updated system prompt with suggestion format
  - `app/services/ai/chat_service.py` - Integrated suggestion parsing
  - `app/services/ai/anthropic_provider.py` - Fixed message conversion and model
  - `app/templates/partials/_ai_sidebar.html` - Added suggestions panel
  - `app/models/ai_suggestion.py` - Updated suggestable fields list

### 2025-12-09 (Session 2)
- **Phase 5A-C Implementation Complete**
  - All 7 AI database models created and migrated
  - Provider abstraction layer for OpenAI, Anthropic, Google Gemini
  - Settings UI with "AI Providers" tab (8th tab)
  - API key encryption/decryption working
  - Test connection functionality validated
  - Claude API key successfully validated (`claude-3-haiku-20240307`)

- **Key Fixes Applied:**
  - Fixed `ProviderFactory.validate_api_key()` - changed from static to instance method call
  - Fixed Anthropic model names - added `VALIDATION_MODEL` constant for cheapest model
  - Fixed template null checks for `data_access_settings`
  - Installed `anthropic` Python package

- **Files Modified:**
  - `app/routers/settings.py` - Fixed test_api_key endpoint
  - `app/services/ai/anthropic_provider.py` - Fixed models and validation
  - `app/templates/settings/ai_providers.html` - Fixed null checks
  - `requirements.txt` - Added anthropic package

### 2025-12-09 (Session 1)
- **Phase 5 Planning Complete** - AI Research Assistant
  - Created `docs/PHASE_5_AI_ASSISTANT.md` (overview, architecture, data model)
  - Created `docs/PHASE_5_TASK_LIST.md` (142 detailed tasks)
  - Updated this context document with Phase 5 information
  - Synology deployment moved to Phase 6 (after AI features)
- Fixed Docker container conflict issue (old app image)
- Verified all Phase 3A/3B/4 features working

### 2025-12-08
- Completed Phase 4: PWA support + Synology deployment preparation
- Generated 14 PWA icons from custom logo
- Created production Docker configuration
- Created backup/restore scripts
- Created SYNOLOGY_DEPLOYMENT.md guide
- Added import history tracking
- Added collapsible tag lists
- Added dashboard logo
- Fixed calendar sync button (HTML response)

### 2025-12-07
- Completed Phase 3B: Calendar integration
- Dashboard with Today's Meetings widget
- Pending contacts queue
- Person merge feature
- 320 tests passing

---

## Current Work: Phase 5.5 - Gmail Integration

### Overview
Enhanced Gmail integration to add email composition and full inbox management within BlackBook.

### Documentation
- **Full Specification:** `docs/GMAIL_INTEGRATION_2025.12.13.1.md`
- **Claude Code Prompt:** `docs/CLAUDE_CODE_PROMPT_GMAIL.md`

### Priority 1: Gmail Compose Links (Quick Win)
Add "Email" buttons that open Gmail with pre-filled fields. No API changes needed.

| Task | Description | Status |
|------|-------------|--------|
| 5.5A.1 | Create `app/utils/gmail_compose.py` utility | ⏳ Pending |
| 5.5A.2 | Add Email button to Person profile | ⏳ Pending |
| 5.5A.3 | Handle multiple emails per person | ⏳ Pending |
| 5.5A.4 | Add bulk email selection to People list | ⏳ Pending |
| 5.5A.5 | Add Email button to Organization page | ⏳ Pending |

### Priority 2: Full Gmail Inbox Integration
Dedicated Email page with inbox view, sync, and CRM integration.

| Task | Description | Status |
|------|-------------|--------|
| 5.5B.1 | Add OAuth scopes to Google Cloud Console | ✅ **Done** (2025-12-16) |
| 5.5B.1a | Update `google_auth.py` to request new scopes | ✅ **Done** (2025-12-16) |
| 5.5B.1b | Re-authenticate accounts to grant permissions | ⏳ Pending |
| 5.5B.2 | Create email_messages database schema | ⏳ Pending |
| 5.5B.3 | Create GmailSyncService | ⏳ Pending |
| 5.5B.4 | Add background sync task (15 min) | ⏳ Pending |
| 5.5B.5 | Create /emails inbox page | ⏳ Pending |
| 5.5B.6 | Add email-to-person linking | ⏳ Pending |
| 5.5B.7 | Add "Add to CRM" for unknown senders | ⏳ Pending |

### Future Enhancements (Not in Current Scope)
- In-app email composer with rich text
- Email templates
- AI email summarization
- Proton Mail integration

---

## Next Steps: Phase 6 - Synology Deployment

After Gmail Integration is complete:
- Deploy to Synology DS220+ NAS
- Configure Tailscale VPN access
- Set up automated backups
- Update OAuth redirect URIs for production

---

## Christopher's Development Preferences

1. **Ask detailed questions** before writing code
2. **Draft a task list** before implementation
3. **Documentation versioning:** YYYY.MM.DD.V format
4. **Primary language:** Python 3.11+ on Windows
5. **Terminal:** PowerShell
6. **Start simple:** Build basic functionality first, iterate
7. **Test after every step:** Write tests alongside implementation

---

*End of Claude Code Context Document*
