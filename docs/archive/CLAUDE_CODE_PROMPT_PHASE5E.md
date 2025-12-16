# Claude Code Prompt: Phase 5E - Polish & Integration

Copy and paste the content below into Claude Code to continue implementation.

---

## PROMPT START

I'm continuing Phase 5 implementation for Perun's BlackBook. Phases 5A-5D are complete. Today we're finishing **Phase 5E: Polish & Integration**.

### Project Context

Please read these files to understand current state:

1. **Project Context:** `Claude_Code_Context.md` (root directory) - Version 2025.12.09.6
2. **Phase 5 Task List:** `docs/PHASE_5_TASK_LIST.md` (Tasks 126-142)

### Current State

| Component | Status |
|-----------|--------|
| Phase 5A: AI Infrastructure | ✅ Complete |
| Phase 5B: Chat UI & Context | ✅ Complete |
| Phase 5C: Research Tools | ✅ Complete |
| Phase 5D: Suggestions & Snapshots | ✅ Complete |
| **Phase 5E: Polish & Integration** | ⏳ **Today's Focus** |

**What's already working:**
- AI Chat with Claude/OpenAI/Gemini from person/org detail pages
- Tool/function calling during conversations
- Streaming responses with tool status updates
- Profile suggestions with Accept/Reject workflow
- Record snapshots before AI applies changes
- Privacy filter for emails/phones
- 570+ tests passing

### Phase 5E Tasks (17 total)

#### Priority 1: Dashboard Integration (Tasks 126-129)

**Task 126: Add "Recent AI Conversations" widget to dashboard**
- File: `app/templates/dashboard.html`
- Show last 5 AI conversations with title, entity name, and timestamp
- Link each to continue the conversation
- Add route in `app/routers/ai_chat.py` if needed: `GET /ai-chat/recent`

**Task 127: Add "Pending Suggestions" counter badge**
- Show badge in navigation showing count of pending suggestions
- File: `app/templates/base.html` (navigation)
- Add endpoint: `GET /ai-chat/suggestions/count` → returns `{"count": N}`
- Badge should update on page load

**Task 128: Add quick-start buttons to dashboard**
- "Research a Person" button → opens AI chat with prompt template
- "Research a Company" button → opens AI chat with prompt template  
- Could open a modal to select person/org, then redirect to their page with sidebar open

**Task 129: Add AI Chat link to main navigation**
- File: `app/templates/base.html`
- Add "AI Chat" or "Research" link in main nav
- Include the pending suggestions badge from Task 127
- Icon suggestion: 🤖 or similar

#### Priority 2: UX Improvements (Tasks 130-135)

**Task 130: Implement conversation search**
- Add search input to AI chat page (if standalone page exists)
- Search across conversation titles and messages
- HTMX search with debounce

**Task 131: Add keyboard shortcuts**
- `Escape` - Close AI sidebar
- `Enter` or `Ctrl+Enter` - Send message (make configurable or pick one)
- Document shortcuts somewhere visible (tooltip or help text)

**Task 132: Add loading states**
- Spinner/skeleton during API calls
- Disable send button while processing
- Show "Thinking..." or typing indicator during AI response

**Task 133: Implement retry logic**
- Auto-retry on transient failures (network errors, 5xx)
- Max 3 retries with exponential backoff
- Show error message after all retries fail

**Task 134: Improve error handling**
- User-friendly error messages (not stack traces)
- Handle: invalid API key, rate limits, network errors, model errors
- Toast notifications for errors

**Task 135: Add usage statistics view**
- In Settings > AI Providers tab
- Show tokens used per provider (from ai_messages table)
- Show estimated cost if possible
- Show conversation count

#### Priority 3: Snapshot Viewer (Optional but useful)

**Task: Snapshot viewer UI**
- On person/org detail page, add "History" section or tab
- List snapshots by date with change source indicator
- Show diff view between current and snapshot
- "Restore" button to revert to snapshot
- Files: Create `app/templates/partials/_snapshot_history.html`
- Route: `GET /snapshots/{entity_type}/{entity_id}`

#### Priority 4: Documentation (Tasks 139-142)

**Task 139: Update Claude_Code_Context.md**
- Mark Phase 5E as complete
- Update version to 2025.12.10.1
- Add any new files created today
- Update test count

**Task 140: Create AI_SETUP.md**
- File: `docs/AI_SETUP.md`
- Step-by-step guide to configure AI providers
- How to get API keys (links to provider dashboards)
- How to add keys in Settings
- Troubleshooting common issues

**Task 141: Document privacy model**
- In AI_SETUP.md or separate section
- What data is sent to AI providers
- What is never sent (emails, phones)
- How to control via Data Access settings

**Task 142: Add troubleshooting section**
- Common errors and solutions
- API key validation failures
- Rate limiting issues
- Streaming problems

### Implementation Order

Suggested order for today:

1. **Start with navigation/dashboard** (Tasks 127, 129, 126, 128)
   - These are most visible and provide immediate value
   
2. **Then UX improvements** (Tasks 131, 132, 134)
   - Keyboard shortcuts, loading states, error handling
   
3. **Usage statistics** (Task 135)
   - Nice to have for tracking API costs
   
4. **Documentation** (Tasks 139-142)
   - Wrap up with docs

5. **Snapshot viewer** (Optional)
   - If time permits

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

### Existing Patterns to Follow

- **Dashboard widgets:** See existing "Today's Meetings" widget in `dashboard.html`
- **Navigation badges:** Check how pending contacts count is shown (if applicable)
- **HTMX patterns:** Follow existing HTMX usage throughout templates
- **Toast notifications:** Already implemented in AI sidebar for suggestions

### Files You'll Likely Modify

| File | Purpose |
|------|---------|
| `app/templates/base.html` | Add AI nav link + badge |
| `app/templates/dashboard.html` | Add AI conversations widget, quick-start buttons |
| `app/routers/ai_chat.py` | Add endpoints for recent conversations, suggestion count |
| `app/templates/partials/_ai_sidebar.html` | Add keyboard shortcuts |
| `app/templates/settings/ai_providers.html` | Add usage statistics |
| `docs/AI_SETUP.md` | Create new documentation |
| `Claude_Code_Context.md` | Update with Phase 5E completion |

### First Steps

Please begin by:

1. Reviewing `Claude_Code_Context.md` to confirm current state
2. Looking at `app/templates/dashboard.html` to understand existing widget patterns
3. Starting with **Task 129: Add AI Chat link to main navigation** (quick win)

Before writing code, briefly confirm:
- You understand the current Phase 5 state
- The approach for adding nav link and badge
- Any questions about the tasks

Let's finish Phase 5! 🚀

---

## PROMPT END

