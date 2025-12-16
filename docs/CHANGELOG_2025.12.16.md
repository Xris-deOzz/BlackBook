# Changelog - December 16, 2025

## Session Summary
This session focused on duplicate management enhancements, Google Contacts full sync, bug fixes, and **Synology NAS deployment**.

---

## Synology NAS Deployment

### Successfully Deployed to BearCave (Synology DS220+)

| Item | Value |
|------|-------|
| **Access URL** | `https://bearcave.tail1d5888.ts.net/` |
| **People Migrated** | 5,215 |
| **Organizations Migrated** | 1,867 |
| **Google Accounts** | 2 connected |

### Key Steps Completed

1. **Database Migration**
   - Created `scripts/export_database.py` for SQLAlchemy-based export
   - Used `Base.metadata.create_all()` for schema creation (Alembic migrations were incremental)
   - Exported data with proper JSON/UUID/array handling

2. **Docker Deployment**
   - Built and deployed using `docker-compose.prod.yml`
   - Containers: `blackbook-app` (FastAPI) + `blackbook-db` (PostgreSQL)

3. **Tailscale Setup**
   - Installed Tailscale on Synology NAS
   - Enabled MagicDNS for domain `bearcave.tail1d5888.ts.net`
   - Configured Tailscale Serve for HTTPS: `sudo tailscale serve --bg http://localhost:8000`

4. **Google OAuth Fix**
   - **Issue:** redirect_uri_mismatch error
   - **Root Cause:** App was using Client ID `154555900230-...` but redirect URI was on `948691232998-...`
   - **Fix:** Updated `.env` with correct Client ID and new Client Secret

5. **PWA Icons Generated**
   - Created custom lightning bolt icons using `scripts/generate_icons.py`
   - Sizes: 16, 32, 48, 72, 96, 128, 144, 152, 192, 384, 512px
   - Plus favicon.ico and apple-touch-icon.png

6. **Git Repository Initialized**
   - Initialized git repo with 421 files
   - Created `.gitignore` with proper exclusions
   - Ready for GitHub push

### Files Added/Modified for Deployment

- `scripts/export_database.py` - Enhanced with JSON/array handling
- `scripts/init_schema.py` - Schema creation from SQLAlchemy models
- `docs/SYNOLOGY_DEPLOYMENT.md` - Comprehensive deployment guide
- `README.md` - Added Synology deployment section
- `.gitignore` - Added backups/ and assets/blackbook-icons/

---

## Features Implemented

### 1. Duplicate Exclusion Management ✅
**Location:** `/settings/duplicates/exclusions`

Added ability to view and manage pairs marked as "not duplicates":
- New "Excluded Pairs" tab on Duplicate Management page with count badge
- Table showing Person 1, Person 2, Date Excluded, and Undo button
- HTMX-powered undo functionality to restore pairs to duplicate detection
- Links to person profiles for quick verification

**Files Modified:**
- `app/routers/settings.py` - Added `exclusions_page`, `get_exclusions_list`, `remove_exclusion` endpoints
- `app/services/duplicate_service.py` - Added `get_exclusions_with_details()`, `remove_exclusion_by_id()` methods
- `app/templates/settings/exclusions.html` - New full page template
- `app/templates/settings/_exclusions_list.html` - Partial template for HTMX updates

### 2. "Not Duplicates" Button on Fuzzy Merge Page ✅
**Location:** `/settings/duplicates/fuzzy/merge`

Added red "Not Duplicates" button with confirmation dialog to mark an entire fuzzy duplicate group as not duplicates.

**Files Modified:**
- `app/templates/settings/fuzzy_merge.html` - Added button and hidden input for person IDs
- `app/routers/settings.py` - Added `mark_not_duplicates` POST endpoint

### 3. Google Contacts Full Sync ✅
**Behavior:** Sync from both accounts, merge (fill blanks only)

Enhanced contacts sync to fetch BOTH saved contacts AND "other contacts" (people you've emailed):
- Fetches saved contacts via `connections().list()` API
- Also fetches "other contacts" via `otherContacts().list()` API
- Deduplicates by email address (saved contacts take priority)
- Merge behavior: Only fills empty fields, never overwrites existing data
- Sync result now shows breakdown: "X saved + Y other contacts"

**Files Modified:**
- `app/services/contacts_service.py`:
  - Updated `fetch_contacts()` to fetch both saved and other contacts
  - Added `include_other_contacts` parameter
  - Returns tuple with counts: `(contacts_list, saved_count, other_count)`
  - Updated `SyncResult` dataclass with `saved_contacts_fetched` and `other_contacts_fetched` fields
- `app/routers/import_contacts.py` - Updated sync result messages to show source breakdown

### 4. HTML Cleanup in Interaction Notes ✅
**Migration:** `z5v23w4x6y78_strip_html_from_interaction_notes.py`

Created migration to strip HTML tags from interaction notes:
- Converts `<p>` tags to newlines
- Converts `<br>` tags to newlines
- Decodes HTML entities (`&nbsp;`, `&amp;`, etc.)
- Strips remaining HTML tags
- Collapses multiple newlines

**Run with:**
```bash
alembic upgrade head
```

---

## Bug Fixes

### 1. Mike/Michaela False Match Fix ✅
**Issue:** "Mike" and "Michaela" were incorrectly flagged as potential duplicates.

**Root Cause:** "mickey" was in both Michael's nicknames (`["mike", "mikey", "mick", "mickey"]`) and Michaela's nicknames (`["micki", "mickey", "kayla"]`).

**Fix:** Removed "mickey" from Michaela's nicknames (changed to `["micki", "kayla", "miki"]`).

**File Modified:** `app/services/duplicate_service.py` line 153

### 2. Graceful Redirects for Missing Duplicate Groups ✅
**Issue:** 404 error when fuzzy duplicate group no longer exists (already merged or excluded).

**Fix:** Redirect to list page instead of showing error.

**File Modified:** `app/routers/settings.py` - `fuzzy_merge_page()` and `merge_page()`

### 3. Tasks Scope Restored ✅
**Issue:** Google Tasks scope was accidentally disabled.

**Fix:** Re-enabled `https://www.googleapis.com/auth/tasks` in `ALL_SCOPES`.

**File Modified:** `app/services/google_auth.py`

**Note:** User must re-connect Google account to grant new permissions.

---

## Navigation Styling ✅
**Status:** Already fixed in previous session

The "Communication" and "Lists & Views" dropdown buttons already have:
- Inline styles: `style="color: #cbd5e1;"`
- CSS class: `nav-dropdown-btn`
- CSS rules in base.html forcing correct colors

---

## Database Migrations

| Migration ID | Description | Status |
|--------------|-------------|--------|
| `y4u12v3w5x67` | Add duplicate_exclusions table | ✅ Applied |
| `z5v23w4x6y78` | Strip HTML from interaction notes | ⏳ Pending (run `alembic upgrade head`) |

---

## Files Changed Summary

### New Files
- `alembic/versions/z5v23w4x6y78_strip_html_from_interaction_notes.py`
- `app/templates/settings/exclusions.html`
- `app/templates/settings/_exclusions_list.html`

### Modified Files
- `app/routers/settings.py`
- `app/routers/import_contacts.py`
- `app/services/duplicate_service.py`
- `app/services/contacts_service.py`
- `app/services/google_auth.py`
- `app/templates/settings/duplicates.html`
- `app/templates/settings/fuzzy_duplicates.html`
- `app/templates/settings/fuzzy_merge.html`
