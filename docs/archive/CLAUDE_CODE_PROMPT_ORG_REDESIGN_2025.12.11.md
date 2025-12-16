# Claude Code Prompt - Organization Page Redesign

**Date:** 2025.12.11
**Project:** `C:\Users\ossow\OneDrive\PerunsBlackBook`

## Quick Context

Self-hosted personal CRM (Python/FastAPI/PostgreSQL/HTMX). Redesigning the Organization page to better track VC/PE firms, portfolio companies, and professional relationships.

## Read These First

1. `Claude_Code_Context.md` - Full project context
2. `docs/ORGANIZATION_PAGE_REDESIGN_2025.12.11.1.md` - **Full specification for this task**
3. `docs/PERSON_PAGE_REDESIGN_2025.12.09.1.md` - Reference for similar patterns used on Person page

## Task Overview

Enhance the Organization detail/edit pages with:

1. **Investment Profile** (for VC/PE firms only) - stages, check size, sectors, fund info
2. **Office Locations** - HQ and regional offices
3. **Enhanced Links** - LinkedIn, Twitter, Crunchbase, PitchBook, AngelList
4. **My Relationship Status** - primary contact, warmth (🔥🟢🟡🔴), intro via, follow-up date
5. **Enhanced Affiliated People** - show titles/roles next to names
6. **Enhanced Related Organizations** - portfolio companies, co-investors, parent/subsidiary with types
7. **Interaction History** - aggregated interactions with anyone at the org
8. **Logo Upload** - like person profile pictures

## Implementation Phases

### Phase A: Database & Models
- Create migration for new tables: `organization_offices`, `organization_relationships`, `organization_relationship_status`, `organization_relationship_types`
- Add columns to `organizations`: social links, investment profile fields
- Create SQLAlchemy models

### Phase B: API Endpoints
- CRUD for offices, relationships, relationship status
- Aggregated interactions endpoint
- Logo upload/delete
- Lookup endpoints

### Phase C: Frontend - View Page
- Add collapsible sections matching Person page style
- Investment Profile (conditional - only for VC/PE types)
- Relationship Status card in sidebar
- Show titles in Affiliated People
- Interaction History section

### Phase D: Frontend - Edit Page
- Forms for all new sections
- Related Organizations modal with relationship type selection

## Key Patterns to Follow

- Use same collapsible section pattern as Person page (`docs/PERSON_PAGE_REDESIGN_2025.12.09.1.md`)
- Bidirectional relationships (Portfolio Company ↔ Investor)
- HTMX for inline editing
- Existing templates: `app/templates/organizations/detail.html`, `_form.html`

## Dev Environment

```powershell
docker start blackbook-db
cd C:\Users\ossow\OneDrive\PerunsBlackBook
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

## Estimated Effort

~32 hours total across all phases. Start with Phase A (database) then proceed sequentially.
