# Changelog 2025.12.19

**Document Version:** 2025.12.19.3
**Date:** 2025-12-19

---

## Summary

1. **Google Contacts Sync Deduplication** - Fixed critical sync issue that created 1,394+ duplicates
2. **Bidirectional Delete** - Users can now choose to delete from BlackBook only, Google only, or both
3. **Tag Subcategories Data** - Populated subcategory values for all tags on both localhost and Synology

---

## Changes

### Google Contacts Sync - Deduplication Fix

**Problem:** Syncing contacts from multiple Google accounts created 1,394+ duplicate entries because matching was only done by email address.

**Solution:** Implemented 3-tier matching strategy:
1. **Tier 1:** Match by `google_resource_name` (unique Google ID) - Most reliable
2. **Tier 2:** Match by email address
3. **Tier 3:** (Future) Match by phone + similar name

**New Fields Stored:**
- `google_resource_name` - e.g., "people/c12345678901234567"
- `google_etag` - For change detection
- `google_synced_at` - Last sync timestamp

### New Field Imports

**URLs from Google Contacts:**
- LinkedIn URLs ? `person.linkedin`
- Twitter/X URLs ? `person.twitter`
- Homepage URLs ? `person.website`
- Other URLs ? `custom_fields["other_urls"]`

**Nicknames:**
- Google nicknames ? `person.nickname`

**Updated API Request:**
- Added `urls` and `nicknames` to personFields parameter

### Tag Assignment Fix

**Problem:** Duplicate tag assignment errors during sync when same label appeared multiple times.

**Solution:**
- Deduplicate labels case-insensitively before processing
- Track tag IDs added in current batch
- Query existing tags from DB directly (not via relationship)
- Flush tag creation to get ID before comparison
- Use try/except with individual flush per tag

### Docker Compose Update

- Added `env_file: .env` to app service for proper environment variable loading

---

## Results

**Before Fix (Synology):**
- 5,209 persons with 1,394 duplicates
- No google_resource_name tracking
- No URL/nickname imports

**After Fix (Local Test):**
- 4,504 persons with 0 duplicates  
- 100% have google_resource_name
- 41 with LinkedIn URLs
- 5 with Twitter URLs
- 33 with nicknames

**Matching Statistics:**
- 161 contacts matched between accounts (not duplicated)
- 3,931 new contacts created
- 161 existing contacts updated with new data

---

## Files Modified

- `app/services/contacts_service.py` - Major updates
- `docker-compose.yml` - Added env_file

---

## Deployment

1. Changes committed to GitHub (commit 78d4787)
2. Files copied to Synology
3. Synology needs Docker rebuild:
   `bash
   cd /volume1/docker/blackbook
   sudo docker-compose down
   sudo docker-compose build --no-cache app
   sudo docker-compose up -d
   `

---

## Bidirectional Google Contacts Delete (Session 2)

### Feature Implemented

When deleting a contact, users can now choose the deletion scope:
- **Both (default):** Delete from BlackBook and Google Contacts
- **BlackBook Only:** Remove from BlackBook, keep in Google
- **Google Only:** Remove from Google, keep in BlackBook (unlinks)

Works for both single delete and bulk delete operations.

### Files Created

| File | Purpose |
|------|---------|
| `app/schemas/person.py` | `DeleteScope` enum and Pydantic models |
| `app/templates/persons/_delete_modal.html` | Single delete modal with 3 radio options |
| `app/templates/persons/_bulk_delete_modal.html` | Bulk delete modal with 3 radio options |

### Files Modified

| File | Changes |
|------|---------|
| `app/schemas/__init__.py` | Export new schema classes |
| `app/services/contacts_service.py` | Added `delete_contact_from_google()`, `delete_person_with_scope()`, `delete_persons_bulk_with_scope()` |
| `app/routers/persons.py` | Updated `DELETE /people/{id}` with `?scope=`, updated `POST /people/batch/delete` with scope, added modal endpoints |
| `app/templates/persons/list.html` | `deleteSelected()` now opens modal |
| `app/templates/persons/detail.html` | Delete button now opens modal via HTMX |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/people/{id}` | DELETE | Delete single contact with `?scope=both\|blackbook_only\|google_only` |
| `/people/{id}/delete/modal` | GET | Fetch delete modal HTML |
| `/people/batch/delete` | POST | Bulk delete with `{ids: [], scope: "both"}` |
| `/people/batch/delete/modal` | GET | Fetch bulk delete modal HTML |

### Google API Used

```
DELETE https://people.googleapis.com/v1/{resourceName}:deleteContact
```

### Error Handling

- Google deletion happens first; if it fails, BlackBook deletion is skipped
- 404 from Google treated as success (already deleted)
- Failed deletions show error messages in UI

---

## Tag Subcategories Data Population (Session 3)

### Background

The tag subcategory feature code was already implemented (grouping tags by subcategory in dropdown). However, the tags in both databases had `subcategory = NULL`, causing all tags to appear under "Other".

### Solution

Populated subcategory values directly in both databases via SQL updates.

### Localhost Database (35 tags)

| Subcategory | Tags |
|-------------|------|
| Education | Georgetown, Karski, LSE, Maine East |
| Holidays | Hanukah, Happy Easter, Salute, Xmas - Holidays, Xmas ENG, Xmas POL |
| Location | Bialystok, Chicago, DC, Georgia, London, Moscow |
| Personal | Hentz, Matt, Medical Contacts, PL, Personal |
| Professional | Admin, Bankers, Credit Suisse, FinTech, GAFG, Headhunters, Lehman, State Department |
| Social | Goodenough, LFC, Nudists, StartOut, X-Guys, arts |

### Synology Database (113 tags)

| Subcategory | Count | Examples |
|-------------|-------|----------|
| Data | 4 | Accounting Data, Banking Data, Credit Data, Payroll Data |
| Education | 4 | Georgetown, Karski, LSE, Maine East |
| FinTech | 19 | API tools, Blockchain, Card Issuing, Payments, PropTech |
| Holidays | 6 | Hanukah, Happy Easter, Salute, Xmas variants |
| Industry | 8 | AM, Banking, Competition, Compliance, Corp, HR & Benefits |
| Insurance | 12 | Annuities, Cyber Insurance, Life Insurance, P&C |
| Investment | 18 | Angel(s), Family Office, Hedge Fund, PE, VC, SWF |
| Location | 6 | Bialystok, Chicago, DC, Georgia, London, Moscow |
| Personal | 13 | Admin, Arts, Goodenough, Hentz, LFC, LGBTQ, Matt |
| Professional | 14 | Advisor, Bankers, Enterpreneur, Headhunters, Lehman |
| Resources | 9 | Freelancers, Resource: Lawyer, Resource: Tech |

### Scripts Created

| File | Purpose |
|------|---------|
| `scripts/sync_tag_subcategories.py` | Sync subcategories from Synology to localhost (for future use) |

---

## Next Steps

1. **Deploy to Synology** - Rebuild Docker container with bidirectional delete feature
2. **Clean up Synology duplicates** - Run dedup script on existing 1,394 duplicates
3. **Add phone+name matching** - Tier 3 of matching strategy
