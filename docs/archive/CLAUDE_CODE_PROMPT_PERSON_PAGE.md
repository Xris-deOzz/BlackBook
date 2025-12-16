# Claude Code Prompt - Person Page Redesign
**Version: 2025.12.09.1**

## Quick Context

Perun's BlackBook CRM - Python 3.11, FastAPI, PostgreSQL, HTMX, TailwindCSS

## Task

Implement the Person Page Redesign as specified in `docs/PERSON_PAGE_REDESIGN_2025.12.09.1.md`

## Priority Order

Start with **Phase A** (Database), then proceed through B, C, D, E sequentially.

## Critical Requirements

1. **Remove Status & Priority** - Delete section from Edit page, drop columns, remove tags
2. **Profile picture = file upload** - JPEG/PNG, max 3MB, store in `/uploads/profile_pictures/`
3. **All sections collapsible** - Both View and Edit pages
4. **Edit page = View page layout** - Identical structure
5. **Sidebar "Add" fix** - Opens org selector modal, not new page
6. **Bidirectional relationships** - Auto-create inverse when adding A→B

## New Database Tables

- `person_emails` (max 5 per person)
- `person_phones` (max 5)
- `person_websites` (max 3)
- `person_addresses` (max 2: home/work)
- `person_education` (max 6)
- `person_employment` (max 10)
- `person_relationships` (bidirectional)
- `affiliation_types` (lookup)
- `relationship_types` (lookup with inverse_name)

## Section Order (View & Edit)

1. Header (photo + name)
2. Tags
3. Contact Information
4. Current Company
5. Previous Employers/Affiliations
6. Social Profiles
7. Education
8. Relationships
9. Investment Details
10. Notes

Sidebar: Organizations, Interactions, Email History, Record Info

## Commands to Start

```bash
# Activate virtual environment
cd C:\Users\ossow\OneDrive\PerunsBlackBook
.\venv\Scripts\activate

# Create migration
alembic revision --autogenerate -m "person_page_redesign"

# Run migration
alembic upgrade head
```

## Reference

Full specification: `docs/PERSON_PAGE_REDESIGN_2025.12.09.1.md`
