# Claude Code Prompt - Perun's BlackBook

**Date:** 2025.12.11
**Project:** `C:\Users\ossow\OneDrive\PerunsBlackBook`

## Quick Context

Self-hosted personal CRM (Python/FastAPI/PostgreSQL/HTMX). All phases complete except AI search tools aren't working.

## Read These First

1. `Claude_Code_Context.md` - Full project context
2. `docs/PHASE_5_AI_ASSISTANT.md` - AI architecture

## Current Issue

AI chat works (Claude, OpenAI, Gemini all respond), but **search tools are not executing**. When asking "search for YouTube videos about Fred Wilson", all providers say "unable to perform search due to technical issue."

API keys for Brave Search and YouTube are configured and validated in Settings.

## Files to Investigate

```
app/services/ai/chat_service.py      # Tool calling loop
app/services/ai/tools/executor.py    # Tool dispatcher
app/services/ai/tools/definitions.py # Tool schemas
app/services/ai/search/brave.py      # Brave API
app/services/ai/search/youtube.py    # YouTube API
```

## Dev Environment

```powershell
docker start blackbook-db
cd C:\Users\ossow\OneDrive\PerunsBlackBook
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Note:** Run locally, not Docker - the container lacks ENCRYPTION_KEY.

## Task

Debug why AI search tools aren't being called. Check logs in terminal when making search requests.
