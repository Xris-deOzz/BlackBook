# Perun's BlackBook

A self-hosted personal CRM for managing professional relationships, contacts, organizations, and interactions - with AI-powered research assistant.

## Features

### Core CRM
- **People Management**: Track contacts with detailed profiles, multiple emails, tags, and organization affiliations
- **Organization Management**: Manage companies, investment firms, and other entities with type/category classification
- **Interaction Logging**: Record meetings, calls, emails, and other touchpoints
- **Tag System**: Organize contacts with customizable, color-coded tags grouped by subcategory
- **Saved Views**: Create and save filtered views for quick access
- **Social Graph**: Visualize relationships between people and organizations

### Google Integration
- **Gmail Sync**: Full email inbox with search, filtering by folder/label, and contact linking
- **Gmail Compose**: One-click email buttons to compose emails to contacts (single or bulk BCC)
- **Gmail Send**: Send emails directly from BlackBook (OAuth scopes ready)
- **Calendar Integration**: Sync Google Calendar, view today's meetings, match attendees to contacts
- **Calendar Events**: Create calendar events with contacts (OAuth scopes ready)
- **Google Tasks**: Sync and manage tasks from Google Tasks, with dashboard widget
- **People API**: Enrich contact profiles with work history, phone numbers, birthdays (OAuth scopes ready)
- **Contacts Sync**: Import contacts from Google with smart deduplication (matches by Google ID, email, name)
- **Bidirectional Delete**: Delete contacts from BlackBook only, Google only, or both (single & bulk)

### Dashboard Widgets
- **Today's Calendar**: View upcoming meetings with attendee matching
- **Today's Tasks**: Google Tasks integration with sync, completion, and inline editing
- **Birthday Reminders**: Track upcoming birthdays with calendar view and age calculation
- **Customizable Layout**: Drag-and-drop widget ordering, collapsible sections

### Communication Tools
- **Email Inbox**: Browse synced emails with folder/label filtering and full-text search
- **Email Ignore Patterns**: Filter out automated/marketing emails from search results
- **Bulk Email**: Select multiple contacts and open Gmail compose with BCC

### Seasonal Features
- **Christmas Email Lists**: Manage Polish and English Christmas card recipient lists
  - AI-powered suggestions based on location and name patterns
  - Confidence levels (high/medium/low) for suggestions
  - Bulk assignment and CSV export

### AI Features
- **AI Research Assistant**: Chat with AI about your contacts, get profile suggestions
- **Auto-populate Fields**: AI can suggest and fill in contact details from research
- **Multiple Providers**: OpenAI (GPT-4o), Anthropic (Claude), Google (Gemini)

### Other
- **Progressive Web App**: Install on mobile/desktop, works offline-capable
- **Dark Mode**: Full dark mode support across all pages
- **LinkedIn Import**: Import contacts from LinkedIn CSV exports

## Quick Start

### Prerequisites

- Python 3.11+ (tested with 3.12)
- Docker Desktop
- Git

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd PerunsBlackBook
   ```

2. **Start the database**
   ```bash
   docker-compose up -d db
   ```

3. **Create Python virtual environment**
   ```bash
   python -m venv venv

   # Windows
   .\venv\Scripts\Activate.ps1

   # macOS/Linux
   source venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment**
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env with your settings (defaults work for local development)
   ```

6. **Run the development server**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

7. **Open in browser**
   ```
   http://localhost:8000
   ```

### Docker Deployment (Local)

For local production deployment, use Docker Compose:

```bash
# Start all services (database + app)
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

### Synology NAS Deployment

BlackBook is deployed to a Synology DS220+ NAS with Tailscale for secure remote access.

**Access URL:** `https://bearcave.tail1d5888.ts.net/`

**Quick deploy after code changes:**
```bash
# On Windows: commit and push
git add . && git commit -m "Update" && git push

# On Synology: pull and rebuild
ssh admin@bearcave
cd /volume1/docker/blackbook
git pull && sudo docker-compose -f docker-compose.prod.yml up -d --build
```

See [docs/SYNOLOGY_DEPLOYMENT.md](docs/SYNOLOGY_DEPLOYMENT.md) for full setup guide.

## Project Structure

```
PerunsBlackBook/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings via pydantic-settings
│   ├── database.py          # SQLAlchemy engine & session
│   ├── models/              # SQLAlchemy ORM models
│   ├── routers/             # API route handlers
│   │   ├── persons.py       # People CRUD & list
│   │   ├── person_details.py    # Person detail page
│   │   ├── person_sections.py   # Person page sections (HTMX)
│   │   ├── organizations.py     # Organizations CRUD & list
│   │   ├── organization_details.py  # Organization detail page
│   │   ├── organization_sections.py # Organization sections (HTMX)
│   │   ├── interactions.py  # Interactions CRUD
│   │   ├── tags.py          # Tag management
│   │   ├── views.py         # Saved views
│   │   ├── graph.py         # Social graph visualization
│   │   ├── emails.py        # Email history per person
│   │   ├── emails_inbox.py  # Full email inbox
│   │   ├── calendar.py      # Google Calendar integration
│   │   ├── tasks.py         # Google Tasks integration
│   │   ├── dashboard.py     # Dashboard widgets
│   │   ├── christmas_lists.py   # Christmas email lists
│   │   ├── ai_chat.py       # AI chat interface
│   │   ├── ai_research.py   # AI research assistant
│   │   ├── auth.py          # Google OAuth
│   │   └── settings.py      # Application settings
│   ├── services/            # Business logic services
│   │   ├── gmail_service.py     # Gmail API wrapper
│   │   ├── gmail_sync_service.py    # Email sync logic
│   │   ├── calendar_service.py  # Calendar API wrapper
│   │   ├── tasks_service.py     # Google Tasks service
│   │   ├── christmas_service.py # Christmas list suggestions
│   │   └── google_auth.py       # OAuth token management
│   ├── utils/               # Utility functions
│   │   └── gmail_compose.py     # Gmail compose URL builder
│   └── templates/           # Jinja2 HTML templates
├── scripts/                 # Utility scripts
├── docs/                    # Documentation
├── alembic/                 # Database migrations
├── docker-compose.yml       # Docker services configuration
├── Dockerfile              # App container definition
├── requirements.txt        # Python dependencies
├── start_blackbook.bat     # Windows startup script
└── .env                    # Environment variables (not in repo)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `perunsblackbook` | Database name |
| `DB_USER` | `blackbook` | Database user |
| `DB_PASSWORD` | `changeme` | Database password |
| `SECRET_KEY` | (random) | Application secret key |
| `DEBUG` | `false` | Enable debug mode |
| `ENCRYPTION_KEY` | (required) | Fernet key for encrypting OAuth tokens and API keys |
| `GOOGLE_CLIENT_ID` | (optional) | Google OAuth client ID for Gmail integration |
| `GOOGLE_CLIENT_SECRET` | (optional) | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8000/auth/google/callback` | OAuth callback URL |

### AI Features (Optional)

AI API keys are stored encrypted in the database. Configure them in Settings > AI Providers:

| Provider | Description |
|----------|-------------|
| OpenAI | GPT-4o, GPT-4-turbo, GPT-3.5-turbo |
| Anthropic | Claude 3 Opus, Sonnet, Haiku |
| Google | Gemini 1.5 Pro, Flash |

Search APIs (also configured in Settings):
- Brave Search - web search
- YouTube Data API - video search

### Gmail Integration Setup

To enable Gmail integration:

1. Create a Google Cloud project and enable the Gmail API, Calendar API, People API, and Contacts API (see `docs/GOOGLE_SETUP.md`)
2. Configure OAuth scopes in Google Cloud Console (see `docs/GOOGLE_SETUP.md` for complete scope list)
3. Generate an encryption key:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
4. Add the credentials to your `.env` file
5. Go to Settings > Google Accounts to connect your Gmail accounts

**Note:** After adding new scopes, existing connected accounts must re-authenticate to grant the new permissions.

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0
- **Frontend**: Jinja2 templates, TailwindCSS (CDN), HTMX
- **Visualization**: vis.js for social graph

## API Endpoints

### People
- `GET /people` - List people with filters
- `GET /people/{id}` - Person detail
- `POST /people` - Create person
- `PUT /people/{id}` - Update person
- `DELETE /people/{id}?scope=both|blackbook_only|google_only` - Delete person with scope
- `POST /people/batch/delete` - Bulk delete with scope selection

### Organizations
- `GET /organizations` - List organizations with filters
- `GET /organizations/{id}` - Organization detail
- `POST /organizations` - Create organization
- `PUT /organizations/{id}` - Update organization
- `DELETE /organizations/{id}` - Delete organization

### Interactions
- `GET /interactions` - List interactions
- `GET /interactions/{id}` - Interaction detail
- `POST /interactions` - Log interaction
- `PUT /interactions/{id}` - Update interaction
- `DELETE /interactions/{id}` - Delete interaction

### Tags
- `GET /tags` - Tag management page
- `POST /tags` - Create tag
- `PUT /tags/{id}` - Update tag
- `DELETE /tags/{id}` - Delete tag

### Views
- `GET /views` - Saved views list
- `POST /views` - Save current view
- `GET /views/{id}` - Apply saved view

### Graph
- `GET /graph` - Social graph visualization
- `GET /graph/data` - Graph data API (JSON)

### Email Inbox
- `GET /emails` - Full email inbox with search and filtering
- `GET /emails/{message_id}` - Email detail view
- `GET /emails/person/{id}` - Email history for a person
- `GET /emails/person/{id}/refresh` - Force refresh email cache
- `POST /emails/thread/{account_id}/{thread_id}/log` - Log email as interaction
- `POST /emails/sync` - Trigger email sync

### Calendar
- `GET /calendar` - Calendar overview page
- `GET /calendar/today` - Today's calendar widget
- `GET /calendar/sync` - Sync calendar events
- `POST /calendar/events/{id}/create-interaction` - Create interaction from meeting

### Tasks
- `GET /tasks` - Tasks page (if standalone)
- `POST /tasks/sync` - Sync tasks from Google Tasks
- `POST /tasks/{task_id}/complete` - Mark task complete
- `POST /tasks/{task_id}/uncomplete` - Mark task incomplete
- `PUT /tasks/{task_id}` - Update task details
- `POST /tasks/create` - Create new task
- `DELETE /tasks/{task_id}` - Delete task

### Dashboard
- `GET /` - Main dashboard with widgets
- `GET /dashboard/calendar` - Calendar widget data
- `GET /dashboard/tasks` - Tasks widget data
- `GET /dashboard/birthdays` - Birthday reminders widget
- `GET /dashboard/birthdays/calendar` - Birthday calendar view
- `POST /dashboard/layout` - Save widget layout preferences

### Christmas Lists
- `GET /christmas-lists` - Overview of Polish/English lists
- `GET /christmas-lists/polish` - View Polish list members
- `GET /christmas-lists/english` - View English list members
- `GET /christmas-lists/suggestions` - Review unassigned contacts with AI suggestions
- `POST /christmas-lists/assign` - Assign person to a list
- `POST /christmas-lists/remove` - Remove person from a list
- `POST /christmas-lists/bulk-assign` - Bulk assign by confidence level
- `GET /christmas-lists/export/{list}` - Export list to CSV

### Settings
- `GET /settings` - Settings page (accounts & email patterns)
- `POST /settings/patterns` - Add email ignore pattern
- `DELETE /settings/patterns/{id}` - Remove ignore pattern

### Authentication
- `GET /auth/google/connect` - Start Google OAuth flow
- `GET /auth/google/callback` - OAuth callback handler
- `GET /auth/google/disconnect/{id}` - Disconnect Google account

### AI Chat
- `GET /ai-chat` - Standalone AI chat page
- `POST /ai-chat/send` - Send message to AI
- `GET /ai-chat/stream/{conversation_id}` - Stream AI response (SSE)
- `GET /ai-chat/suggestions/{entity_type}/{entity_id}` - Get pending suggestions
- `POST /ai-chat/suggestions/{id}/accept` - Accept a suggestion
- `POST /ai-chat/suggestions/{id}/reject` - Reject a suggestion

### Utility
- `GET /health` - Health check
- `GET /api/stats` - Database statistics

## Data Import

To import data from Airtable CSVs:

1. Export your Airtable bases as CSV files to the `data/` directory
2. Run the import script:
   ```bash
   docker-compose --profile import up import
   ```

## Development

### Running Tests
```bash
pytest
```

### Database Access
```bash
docker exec -it blackbook-db psql -U blackbook -d perunsblackbook
```

### Useful SQL Queries
```sql
-- Count all records
SELECT
  (SELECT COUNT(*) FROM persons) as people,
  (SELECT COUNT(*) FROM organizations) as orgs,
  (SELECT COUNT(*) FROM tags) as tags,
  (SELECT COUNT(*) FROM interactions) as interactions;

-- Most used tags
SELECT t.name, COUNT(*)
FROM tags t
JOIN person_tags pt ON t.id = pt.tag_id
GROUP BY t.name
ORDER BY COUNT(*) DESC
LIMIT 10;
```

## License

Private project - All rights reserved
