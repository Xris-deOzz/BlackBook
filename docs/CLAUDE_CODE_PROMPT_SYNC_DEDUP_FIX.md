# Claude Code Prompt: Google Contacts Sync Deduplication Fix

**Date:** 2025-12-18  
**Specification:** `docs/GOOGLE_SYNC_DEDUPLICATION_FIX_2025.12.18.2.md`

---

## Context

BlackBook's Google Contacts sync creates duplicate person records on every sync. The current implementation only matches contacts by email, ignoring Google's unique resource identifiers. This results in 1394 duplicate groups requiring manual cleanup.

## Objective

Fix the sync to prevent duplicates by:
1. Matching on Google resource name first (most reliable)
2. Falling back to email matching
3. Falling back to phone + name matching (with phone normalization)
4. Auto-merging existing duplicates during migration

---

## Task 1: Create Alembic Migration

Create a new migration file in `alembic/versions/` that:

1. **Adds new column:**
   ```sql
   ALTER TABLE persons ADD COLUMN google_resource_names JSONB DEFAULT '{}';
   ```

2. **Creates GIN index:**
   ```sql
   CREATE INDEX idx_persons_google_resource_names ON persons USING GIN (google_resource_names);
   ```

3. **Migrates existing data** from `google_resource_name` and `custom_fields`

4. **Drops old columns** (google_resource_name, google_etag)

---

## Task 2: Update Person Model

In `app/models/person.py`:

1. **Remove** `google_resource_name` and `google_etag` fields
2. **Add** `google_resource_names` JSONB field
3. **Add helper methods:** `get_google_resource_name()`, `set_google_resource_name()`, `has_google_resource_name()`

---

## Task 3: Update ContactsService

In `app/services/contacts_service.py`:

1. Add `normalize_phone()` function
2. Add resource name and phone+name caches
3. Update `_match_contact_to_person()` with 3-tier matching
4. Update `_create_person_from_contact()` to store google_resource_names
5. Update `_update_person_from_contact()` to add missing resource names
6. Update `sync_contacts()` to pass account.email

---

## Task 4: Create Auto-Merge Script

Create `app/services/duplicate_auto_merge.py` with:
- `calculate_completeness_score()` function
- `auto_merge_duplicates()` function
- Integration with existing `PersonMergeService`

---

## Testing Checklist

1. [ ] Run Alembic migration
2. [ ] Verify auto-merge report
3. [ ] Check Duplicate Management page
4. [ ] Trigger Google Contacts sync - no new duplicates
5. [ ] Sync again - still no duplicates

---

## Files to Modify

1. `alembic/versions/xxx_add_google_resource_names.py` (new)
2. `app/models/person.py`
3. `app/services/contacts_service.py`
4. `app/services/duplicate_auto_merge.py` (new)
