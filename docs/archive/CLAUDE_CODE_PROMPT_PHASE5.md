# Claude Code Prompt: Phase 5 - AI Research Assistant

Copy and paste the content below into Claude Code to begin implementation.

---

## PROMPT START

I'm ready to begin implementing Phase 5: AI Research Assistant for Perun's BlackBook.

### Project Context

Please read these files first to understand the project and Phase 5 requirements:

1. **Project Context:** `Claude_Code_Context.md` (root directory)
2. **Phase 5 Overview:** `docs/PHASE_5_AI_ASSISTANT.md`
3. **Phase 5 Task List:** `docs/PHASE_5_TASK_LIST.md`

### What Phase 5 Does

This phase adds an AI-powered research assistant to help users:
- Research people and companies using multiple AI providers (Claude, OpenAI GPT-4, Google Gemini)
- Search the web in real-time (Brave Search API)
- Find YouTube videos and podcast interviews about people (YouTube Data API, Listen Notes API)
- Populate CRM fields with AI-discovered information (with approval workflow)
- Protect sensitive data (emails/phones never sent to external APIs)

### Implementation Approach

1. **Start with Phase 5A (Infrastructure)** - Tasks 1-32
   - Database schema and migrations first (Tasks 1-8)
   - Then provider abstraction layer (Tasks 9-18)
   - Then API key management UI (Tasks 19-24)
   - Finally configuration and tests (Tasks 25-32)

2. **Follow the task list sequentially** within each sub-phase
   - Each task in `docs/PHASE_5_TASK_LIST.md` has specific file paths and requirements
   - Write tests alongside implementation (don't leave all tests for the end)
   - Commit after completing logical chunks of work

3. **Use existing patterns** from the codebase:
   - Encryption: Follow `app/services/encryption.py` pattern for API key storage
   - Models: Follow existing SQLAlchemy model patterns in `app/models/`
   - Routers: Follow existing FastAPI router patterns in `app/routers/`
   - Templates: Follow existing Jinja2/HTMX patterns in `app/templates/`
   - Tests: Follow existing pytest patterns in `tests/`

### Development Environment

```powershell
# Start database
docker start blackbook-db

# Activate virtual environment
cd C:\Users\ossow\OneDrive\PerunsBlackBook
.\venv\Scripts\Activate.ps1

# Run dev server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v
```

### First Steps

Please begin by:

1. Reading the three documentation files mentioned above
2. Confirming you understand the Phase 5 architecture and task breakdown
3. Starting with **Task 1: Create `ai_providers` model** from Phase 5A

Before writing any code, briefly summarize:
- What Phase 5A accomplishes
- The database tables you'll create
- Any questions or clarifications needed

Let's begin!

---

## PROMPT END

