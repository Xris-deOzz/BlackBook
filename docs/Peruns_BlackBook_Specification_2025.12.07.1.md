# Perun's BlackBook - Design Specification

**Document Version:** 2025.12.12.1
**Project Name:** Perun's BlackBook
**Author:** Christopher
**Status:** Phase 5 Complete (All Phases 1-5 Done)

---

## 1. Project Overview

### Purpose
A self-hosted personal CRM system to manage relationships with investors, advisors, lawyers, bankers, and other professional contacts. Replaces the current Airtable-based system with a more powerful, private, and customizable solution.

### Goals
- Track people and organizations with flexible tagging
- Log interactions (emails, meetings, calls, notes)
- Provide Airtable-like filtering and saved views
- Enable quick search and keyboard navigation
- Self-hosted on Synology DS220+ for data privacy
- Import existing data from Airtable

### Current Features
- Mobile-responsive Progressive Web App (PWA)
- Multi-provider AI Research Assistant (Claude, OpenAI, Gemini)
- Gmail integration with email history search
- Google Calendar integration with attendee matching
- Social graph visualization
- AI-suggested profile updates with approval workflow

### Non-Goals
- Multi-user/team features
- Automated call logging

---

## 2. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.12.8+ | Developer preference, rich ecosystem |
| Web Framework | FastAPI | Modern, fast, async support, great docs |
| Database | PostgreSQL 15 | JSONB support, full-text search, reliable |
| ORM | SQLAlchemy 2.0 | Industry standard, async support |
| Migrations | Alembic | Native SQLAlchemy integration |
| Frontend | Jinja2 + HTMX | Server-rendered, minimal JS, fast development |
| CSS | TailwindCSS | Utility-first, rapid prototyping |
| Containerization | Docker + Docker Compose | Easy deployment on Synology |
| Hosting | Synology DS220+ | Existing NAS, always-on, local network |

---

## 3. Architecture

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Synology DS220+                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 Docker Engine                        │   │
│  │  ┌─────────────────┐    ┌─────────────────────────┐ │   │
│  │  │  PostgreSQL 15  │◄───│  Perun's BlackBook App  │ │   │
│  │  │   (Container)   │    │      (Container)        │ │   │
│  │  │   Port: 5432    │    │      Port: 8000         │ │   │
│  │  └─────────────────┘    └─────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP :8000
                              ▼
                    ┌─────────────────┐
                    │  Web Browser    │
                    │  (Any Device)   │
                    └─────────────────┘
```

### Directory Structure

```
peruns-blackbook/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── alembic/
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings and configuration
│   ├── database.py          # Database connection
│   ├── models/
│   │   ├── __init__.py
│   │   ├── person.py
│   │   ├── organization.py
│   │   ├── interaction.py
│   │   └── tag.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── ...              # Pydantic models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── people.py
│   │   ├── organizations.py
│   │   ├── interactions.py
│   │   └── search.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gmail.py         # Gmail API integration
│   │   └── calendar.py      # Calendar API integration
│   ├── templates/
│   │   ├── base.html
│   │   ├── components/
│   │   └── pages/
│   └── static/
│       ├── css/
│       └── js/
├── scripts/
│   └── import_airtable.py   # Data migration script
└── tests/
    └── ...
```

---

## 4. Data Model

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     Person      │       │  PersonOrg      │       │  Organization   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id              │──┐    │ id              │    ┌──│ id              │
│ first_name      │  │    │ person_id    ───┼────┘  │ name            │
│ last_name       │  └────┼─ org_id         │       │ type            │
│ email           │       │ role            │       │ website         │
│ phone           │       │ is_primary      │       │ industry        │
│ linkedin_url    │       │ start_date      │       │ description     │
│ title           │       │ end_date        │       │ priority        │
│ status          │       │ notes           │       │ notes           │
│ priority        │       └─────────────────┘       │ custom_fields   │
│ notes           │                                 │ created_at      │
│ source          │                                 │ updated_at      │
│ custom_fields   │                                 └─────────────────┘
│ last_contacted  │
│ created_at      │
│ updated_at      │
└─────────────────┘

┌─────────────────┐       ┌─────────────────────┐       ┌─────────────────┐
│      Tag        │       │     EntityTag       │       │   Interaction   │
├─────────────────┤       ├─────────────────────┤       ├─────────────────┤
│ id              │──┐    │ id                  │       │ id              │
│ name            │  │    │ tag_id           ───┼───┐   │ person_id       │
│ category        │  └────┼─ entity_id          │   │   │ type            │
│ color           │       │ entity_type         │   │   │ direction       │
└─────────────────┘       └─────────────────────┘   │   │ subject         │
                          (polymorphic: person/org) │   │ body            │
                                                    │   │ occurred_at     │
                                                    │   │ gmail_id        │
                                                    │   │ calendar_id     │
                                                    │   │ created_at      │
                                                    │   └─────────────────┘
```

### Table Definitions

#### Person

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| first_name | VARCHAR(100) | NOT NULL | First name |
| last_name | VARCHAR(100) | NOT NULL | Last name |
| email | VARCHAR(255) | UNIQUE | Primary email |
| phone | VARCHAR(50) | | Phone number |
| linkedin_url | VARCHAR(500) | | LinkedIn profile URL |
| title | VARCHAR(200) | | Current job title |
| status | VARCHAR(50) | DEFAULT 'active' | active, inactive, archived |
| priority | INTEGER | DEFAULT 0 | 0=normal, 1=important, 2=VIP |
| notes | TEXT | | Free-form notes |
| source | VARCHAR(100) | | How you met/found them |
| custom_fields | JSONB | DEFAULT '{}' | Flexible custom fields |
| last_contacted_at | TIMESTAMP | | Last interaction date |
| created_at | TIMESTAMP | DEFAULT now() | Record creation |
| updated_at | TIMESTAMP | DEFAULT now() | Last update |

#### Organization

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(200) | NOT NULL | Organization name |
| type | VARCHAR(50) | NOT NULL | vc_firm, pe_firm, startup, law_firm, bank, other |
| website | VARCHAR(500) | | Company website |
| industry | VARCHAR(100) | | Industry/sector |
| description | TEXT | | About the organization |
| notes | TEXT | | Free-form notes |
| custom_fields | JSONB | DEFAULT '{}' | Flexible custom fields |
| priority | INTEGER | DEFAULT 0 | Priority level |
| created_at | TIMESTAMP | DEFAULT now() | Record creation |
| updated_at | TIMESTAMP | DEFAULT now() | Last update |

#### PersonOrganization (Junction Table)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| person_id | UUID | FK → Person.id | Person reference |
| organization_id | UUID | FK → Organization.id | Organization reference |
| role | VARCHAR(200) | | Role/title at this org |
| is_primary | BOOLEAN | DEFAULT false | Primary affiliation |
| start_date | DATE | | When they joined |
| end_date | DATE | | When they left (null if current) |
| notes | TEXT | | Notes about relationship |
| created_at | TIMESTAMP | DEFAULT now() | Record creation |

#### Tag

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(100) | NOT NULL, UNIQUE | Tag name |
| category | VARCHAR(50) | | role, industry, relationship, etc. |
| color | VARCHAR(20) | | Hex color for UI |
| created_at | TIMESTAMP | DEFAULT now() | Record creation |

**Predefined Tags:**
- **Role:** investor-vc, investor-pe, investor-angel, lawyer, banker, advisor, founder, executive
- **Relationship:** warm, cold, introduced, met-at-event
- **Priority:** follow-up, high-priority, dormant

#### EntityTag (Polymorphic Junction)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| tag_id | UUID | FK → Tag.id | Tag reference |
| entity_id | UUID | NOT NULL | Person or Organization ID |
| entity_type | VARCHAR(20) | NOT NULL | 'person' or 'organization' |
| created_at | TIMESTAMP | DEFAULT now() | Record creation |

#### Interaction

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| person_id | UUID | FK → Person.id | Who the interaction was with |
| type | VARCHAR(50) | NOT NULL | email, meeting, call, note |
| direction | VARCHAR(20) | | inbound, outbound |
| subject | VARCHAR(500) | | Email subject or meeting title |
| body | TEXT | | Content or notes |
| occurred_at | TIMESTAMP | NOT NULL | When it happened |
| gmail_message_id | VARCHAR(100) | | Gmail message ID |
| gmail_thread_id | VARCHAR(100) | | Gmail thread ID |
| calendar_event_id | VARCHAR(100) | | Google Calendar event ID |
| created_at | TIMESTAMP | DEFAULT now() | Record creation |

#### SavedView

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(100) | NOT NULL | View name |
| entity_type | VARCHAR(20) | NOT NULL | 'person' or 'organization' |
| filters | JSONB | | Filter criteria |
| sort_by | VARCHAR(100) | | Sort field |
| sort_order | VARCHAR(10) | DEFAULT 'asc' | asc or desc |
| columns | JSONB | | Which columns to display |
| is_default | BOOLEAN | DEFAULT false | Show on sidebar |
| created_at | TIMESTAMP | DEFAULT now() | Record creation |

---

## 5. Development Phases

### Phase 1: Data Foundation ✅ COMPLETE (2025.12.07)
- [x] Design specification
- [x] Project folder structure
- [x] Docker + PostgreSQL setup
- [x] Database schema (001_initial_schema.sql)
- [x] Airtable data import script
- [x] Full data import validated
  - 1,012 persons
  - 1,259 organizations
  - 77 tags
  - 130 interactions
  - 7,299 total records

### Phase 2: Web Application ✅ COMPLETE (2025.12.07)
- [x] FastAPI application skeleton
- [x] SQLAlchemy models
- [x] Basic CRUD APIs for People and Organizations
- [x] List views with HTMX
- [x] Detail views with tabs (Overview, Interactions, Notes)
- [x] Global search functionality
- [x] Tag management UI with color picker
- [x] Interaction logging (manual entry)
- [x] Saved views (Airtable-style filters)
- [x] Keyboard navigation
- [x] Social graph visualization (vis.js)
- [x] A-Z alphabet navigation
- [x] Column resizing with persistence
- [x] Profile pictures and logos

### Phase 3A: Gmail Integration ✅ COMPLETE (2025.12.07)
- [x] Google OAuth2 setup with multi-account support
- [x] Gmail API integration
- [x] Email history search per person
- [x] Email caching (1-hour TTL)
- [x] "Log as Interaction" feature
- [x] Email ignore patterns (domains/addresses)

### Phase 3B: Calendar Integration ✅ COMPLETE (2025.12.07)
- [x] Google Calendar API integration
- [x] Calendar event syncing
- [x] Attendee matching to persons
- [x] Pending contacts queue for unknown attendees
- [x] Dashboard widget (Today's Meetings)
- [x] Auto-interaction creation from meetings
- [x] Person merge/deduplication feature

### Phase 4: PWA & Deployment Prep ✅ COMPLETE (2025.12.08)
- [x] Progressive Web App manifest
- [x] 14 icon sizes for all devices
- [x] Production Docker configuration
- [x] Synology-optimized compose file
- [x] Backup/restore scripts
- [x] Deployment documentation
- [x] Mobile-responsive navigation

### Phase 5: AI Research Assistant ✅ COMPLETE (2025.12.10)
- [x] Multi-provider AI chat (Claude, OpenAI, Gemini)
- [x] AI sidebar on person/organization detail pages
- [x] CRM context builder with privacy filtering
- [x] Web search integration (Brave Search API ready)
- [x] YouTube search integration (API ready)
- [x] AI-suggested profile updates with approval workflow
- [x] Record snapshots for undo/restore
- [x] Dashboard integration (AI conversations widget, suggestions widget)
- [x] Usage statistics tracking (tokens, conversations, suggestions)
- [x] Settings page with AI Providers tab

**Documentation:**
- `docs/PHASE_5_AI_ASSISTANT.md` - Architecture overview
- `docs/PHASE_5_TASK_LIST.md` - 142 detailed tasks (all complete)
- `docs/AI_SETUP.md` - API key setup guide

### Phase 6: Synology Production Deployment (Pending)
- [ ] Deploy to Synology DS220+ NAS
- [ ] Configure Tailscale VPN access
- [ ] Set up automated backups
- [ ] Update OAuth redirect URIs for production
- [ ] Performance monitoring

---

## 6. Airtable Data Import - Implementation Steps

### Data Files Received (2025.12.06)

| File | Size | Records |
|------|------|--------|
| Individuals-All Contacts.csv | 609 KB | Contacts |
| Firms-All Funds.csv | 232 KB | Investment firms |
| Company-List.csv | 271 KB | Companies |
| Interactions-All Interactions.csv | 14 KB | Interaction log |

### Field Mapping Decisions

| Source | Field | Maps To | Notes |
|--------|-------|---------|-------|
| Individuals | `First & Last Name` | `first_name`, `last_name` | Split on last space |
| Individuals | `Category` | Tags (many-to-many) | Comma-separated values |
| Individuals | `Invest Firm` | person_organizations | Link to org |
| Individuals | `Peers`, `Peers 2` | person_organizations | "peer_history" type |
| Firms | * | organizations | org_type="Investment Firm" |
| Companies | * | organizations | org_type="Company" |
| Companies | `Key People` | organization_persons | "key_person" type |
| Companies | `Connections` | organization_persons | "connection" type |
| Companies | `Individuals` | organization_persons | "contact_at" type |
| Interactions | `Indiv Partner` | interactions.person_id | Match by name |

### Fields to Skip
- `No. of Days Since Last Interaction` (calculated)
- `Most Recent Interaction` (calculated)
- All job fields (`Jobs`, `Job Open 1`, `Job Open 2`, `Applied?`, `Applied J2?`)

### Import Validation Rules
- Skip rows with empty names
- Log unmatched organization references
- Log name-splitting edge cases for manual review

---

### Step 1: Database Schema & Documentation
**Status:** ✅ Complete (2025.12.06)

- [x] Create `scripts/001_initial_schema.sql`
  - [x] `persons` table
  - [x] `organizations` table
  - [x] `tags` table
  - [x] `person_tags` junction table
  - [x] `organization_tags` junction table
  - [x] `person_organizations` junction table (person→org links)
  - [x] `organization_persons` junction table (org→person links like Key People)
  - [x] `interactions` table
  - [x] `saved_views` table
  - [x] `import_logs` table (for tracking import runs)
  - [x] Indexes and triggers
- [x] Create `scripts/requirements.txt`
- [x] Create `scripts/.env.example`
- [x] Create `docs/DATA_MAPPING.md`

---

### Step 2: Import Script Core
**Status:** ✅ Complete (2025.12.06)

- [x] Create `scripts/import_airtable.py` skeleton
- [x] CSV loading utilities (handle BOM, encoding)
- [x] Name splitting function
- [x] Tag extraction and normalization
- [x] Organizations import (Firms + Companies merged)
- [x] Build org name→id lookup dictionary
- [x] Dry-run mode for testing
- [x] Progress bars and logging
- [x] Import statistics tracking

---

### Step 3: Persons Import & Linking
**Status:** ✅ Complete (2025.12.06)

- [x] Persons import with name splitting
- [x] Parse and link tags from Category field
- [x] Link person→org via `Invest Firm` field (relationship='affiliated_with')
- [x] Link person→org via `Peers`, `Peers 2` fields (relationship='peer_history')
- [x] Skip rows with empty names
- [x] Store unmapped fields in custom_fields JSONB
- [x] Report name-splitting edge cases (single names, 3+ parts)
- [x] Report unmatched organization references

---

### Step 4: Organization→Person Links & Interactions
**Status:** ✅ Complete (2025.12.06)

- [x] Parse `Key People` field → organization_persons (relationship='key_person')
- [x] Parse `Connections` field → organization_persons (relationship='connection')
- [x] Parse `Individuals` field → organization_persons (relationship='contact_at')
- [x] Import Interactions table
- [x] Match `Indiv Partner` to persons
- [x] Parse date formats (M/D/YYYY, MM/DD/YYYY)
- [x] Map interaction medium to enum
- [x] Report unmatched person references

---

### Step 5: Testing & Validation
**Status:** ✅ Complete (2025.12.07)

- [x] Run import against test database
- [x] Verify record counts match source
- [x] Review edge case report
- [x] Manual spot-checks on relationships
- [x] Fix data issues (field length, priority text→number)

**Final Import Results:**
| Table | Imported |
|-------|----------|
| tags | 77 |
| organizations | 1,259 |
| persons | 1,012 |
| person_tags | 992 |
| organization_tags | 1,448 |
| person_organizations | 1,086 |
| organization_persons | 1,295 |
| interactions | 130 |

---

## 7. Docker Configuration

### docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: blackbook-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: blackbook
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: perunsblackbook
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U blackbook -d perunsblackbook"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    container_name: blackbook-app
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://blackbook:${DB_PASSWORD}@db:5432/perunsblackbook
      SECRET_KEY: ${SECRET_KEY}
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app/app
      - ./data/uploads:/app/uploads
```

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

---

## 8. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Focus global search |
| `Esc` | Close modal / Clear search / Close AI sidebar |
| `n` | New person (from People page) |
| `N` (Shift+n) | New organization |
| `i` | New interaction |
| `e` | Edit current record |
| `j` / `k` | Navigate list down/up |
| `Enter` | Open selected record / Send AI message |
| `Shift+Enter` | New line in AI chat input |
| `g p` | Go to People |
| `g o` | Go to Organizations |
| `g d` | Go to Dashboard |
| `?` | Show keyboard shortcuts |

---

## 8.1 Settings Page Tabs

The Settings page (`/settings`) has 9 tabs:

| Tab | Description |
|-----|-------------|
| **Google Accounts** | Connect/disconnect Google accounts for Gmail & Calendar |
| **Import Contacts** | LinkedIn CSV upload, Google Contacts sync |
| **Data Management** | Duplicate detection and person merge |
| **Email Ignore** | Domains and email patterns to ignore |
| **Tags** | View all tags with usage counts |
| **Pending** | Unknown meeting attendees queue |
| **AI Providers** | AI API keys (Claude, OpenAI, Gemini), search APIs, data access controls |
| **AI Chat** | AI conversation history, usage statistics by model, pending suggestions |
| **Organization Types** | Manage organization type categories |

---

## 9. Resolved Decisions

1. **Call logging:** Manual entry for Phase 1, automation later. ✓
2. **Quick interaction entry:** Both floating "+" button AND keyboard shortcut (`i`). ✓
3. **Email sync depth:** All time - full Gmail history sync. ✓
4. **Export format:** Both CSV and JSON for maximum flexibility. ✓
5. **Custom fields:** Added `custom_fields JSONB` column to Person and Organization. ✓
6. **Project name:** Perun's BlackBook ✓
7. **Python version:** 3.12.8+ ✓

---

## Appendix A: Airtable Migration

Export the following from Airtable as CSV:
- Individuals table → `data/Individuals.csv`
- Firms table → `data/Firms.csv`
- Company table → `data/Companies.csv`
- Interactions table (if exists) → `data/Interactions.csv`

The import script will:
1. Parse CSV files
2. Create Organization records from Firms/Companies
3. Create Person records from Individuals
4. Link People to Organizations
5. Create Tags based on existing categories
6. Import Interactions with person linkage

---

*End of Specification Document*
