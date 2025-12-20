# BlackBook - Bidirectional Google Contacts Delete Feature

**Document Version:** 2025.12.19.3
**Status:** IMPLEMENTED

## Project Context

BlackBook is a self-hosted personal CRM built with:
- **Backend:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL
- **Frontend:** HTMX, TailwindCSS, Jinja2 templates
- **Deployment:** Docker containers

**Working Directory:** `C:\BlackBook`
**Test URL:** `http://localhost:8000`

## Feature Overview

Bidirectional delete for contacts synced with Google Contacts. Users can:
1. Delete from BlackBook only
2. Delete from Google only (unlink)
3. Delete from both (default)

Works for single contact delete and bulk delete.

## Requirements

| Requirement | Decision | Status |
|-------------|----------|--------|
| Delete Options | 3 choices: Both (default), BlackBook only, Google only | Done |
| Bulk Delete | Yes - multi-select + individual profile page | Done |
| Error Handling | Delete Google first, then BlackBook (avoid orphans) | Done |
| Multi-Account | Try all connected Google accounts | Done |

## Implementation

### Files Created

| File | Purpose |
|------|---------|
| `app/schemas/person.py` | `DeleteScope` enum, `PersonDeleteRequest`, `PersonBulkDeleteRequest`, `DeleteResult`, `BulkDeleteResult` |
| `app/templates/persons/_delete_modal.html` | Single delete confirmation modal with 3 scope radio options |
| `app/templates/persons/_bulk_delete_modal.html` | Bulk delete confirmation modal with 3 scope radio options |

### Files Modified

| File | Changes |
|------|---------|
| `app/schemas/__init__.py` | Export new schema classes |
| `app/services/contacts_service.py` | Added `delete_contact_from_google()`, `delete_person_with_scope()`, `delete_persons_bulk_with_scope()` methods |
| `app/routers/persons.py` | Updated endpoints, added modal endpoints |
| `app/templates/persons/list.html` | `deleteSelected()` opens modal instead of confirm() |
| `app/templates/persons/detail.html` | Delete button fetches modal via HTMX |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/people/{id}` | DELETE | Single delete with `?scope=both\|blackbook_only\|google_only` |
| `/people/{id}/delete/modal` | GET | Fetch single delete modal HTML |
| `/people/batch/delete` | POST | Bulk delete with `{ids: [], scope: "both"}` |
| `/people/batch/delete/modal` | GET | Fetch bulk delete modal HTML |

### Service Methods

```python
# app/services/contacts_service.py

def delete_contact_from_google(self, resource_name: str, account_id: UUID | None = None) -> bool:
    """Delete contact from Google using People API."""

def delete_person_with_scope(self, person_id: UUID, scope: str = "both") -> dict:
    """Delete person with scope control (blackbook_only, google_only, both)."""

def delete_persons_bulk_with_scope(self, person_ids: list[UUID], scope: str = "both") -> dict:
    """Bulk delete with scope control."""
```

## Google API

```
DELETE https://people.googleapis.com/v1/{resourceName}:deleteContact
```

## Error Handling

- Google deletion happens FIRST
- If Google fails, BlackBook deletion is skipped (for scope="both")
- 404 from Google treated as success (already deleted)
- Failed deletions show error messages in modal

## UI Screenshots

### Single Delete Modal
- Shows person name
- Google icon if linked to Google
- 3 radio options with descriptions
- Cancel/Delete buttons

### Bulk Delete Modal
- Shows count of selected contacts
- Note about Google-linked contacts
- 3 radio options with descriptions
- Cancel/Delete buttons
