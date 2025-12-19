# Google Contacts Sync Deduplication Fix

**Document Version:** 2025.12.18.2  
**Created:** 2025-12-18  
**Status:** Ready for Implementation  
**Priority:** High (blocking normal sync usage)

---

## Problem Statement

Every Google Contacts sync creates duplicate person records instead of updating existing ones. The Duplicate Management page shows 1394 duplicate groups requiring manual review.

### Root Cause

The current sync logic in `contacts_service.py` only matches contacts by email address. It ignores the `google_resource_name` field (Google's unique contact identifier) that already exists in the Person model but is never:
1. Used for matching during sync
2. Populated when creating new persons from Google contacts

### Evidence

- "Jake Grindr" has 9 duplicates: 1 from Dec 08, 8 from Dec 18 syncs
- Each sync fetches the same Google contact but fails to match it to existing records
- `google_resource_name` column exists but is always NULL
- `custom_fields.google_contact_id` stores the ID but is never used for matching

---

## Solution Overview

### 1. Enhanced Matching Logic (3-Tier Priority)

```
Priority 1: GOOGLE RESOURCE NAME
├─ Check contact.resource_name against persons.google_resource_names JSONB
├─ Supports multiple Google accounts (personal + work)
└─ Most reliable match - Google's unique identifier

Priority 2: EMAIL ADDRESS
├─ Check all contact emails against PersonEmail table + legacy email field
├─ Case-insensitive matching
└─ Reliable for contacts with email addresses

Priority 3: PHONE + NAME (New!)
├─ Normalize phone numbers (strip formatting)
├─ Match if: normalized_phone matches AND (full_name matches OR first+last match)
├─ Prevents false positives like two different "John Smith" contacts
└─ Fallback for contacts without email

Priority 4: NO MATCH → Create new person
```

### 2. Schema Changes

**Replace single-value field with multi-account JSONB:**

```sql
-- Old (single account):
google_resource_name VARCHAR(255)  -- e.g., "people/c1234567890"

-- New (multi-account):
google_resource_names JSONB DEFAULT '{}'
-- Format: {
--   "ossowski.chris@gmail.com": "people/c1234567890",
--   "chris@blackperun.com": "people/c9876543210"
-- }
```

### 3. Phone Number Normalization

```python
def normalize_phone(phone: str) -> str:
    """Strip all non-digit characters for comparison."""
    # (555) 123-4567 → 5551234567
    # +1-555-123-4567 → 15551234567
    # 555.123.4567 → 5551234567
    return re.sub(r'\D', '', phone)
```

### 4. Auto-Merge Existing Duplicates

Run as part of migration to clean up 1394 duplicate groups:
- Use existing `person_merge.py` service
- Canonical record = most complete (most non-null fields)
- Merge all duplicates in each group into canonical
- Log all merges for audit trail

---

## Implementation Tasks

### Phase A: Database Migration (2 tasks)

| # | Task | Description |
|---|------|-------------|
| A1 | Create Alembic migration | Add `google_resource_names` JSONB column, migrate existing data, drop old columns |
| A2 | Update Person model | Replace `google_resource_name` with `google_resource_names` JSONB, add helper methods |

### Phase B: Phone Normalization (1 task)

| # | Task | Description |
|---|------|-------------|
| B1 | Add phone normalization utility | Create `normalize_phone()` function in contacts_service.py |

### Phase C: Matching Logic Updates (5 tasks)

| # | Task | Description |
|---|------|-------------|
| C1 | Add `_build_resource_name_cache()` method | Cache mapping resource_name → person_id |
| C2 | Add `_build_phone_name_cache()` method | Cache mapping (normalized_phone, full_name) → person_id |
| C3 | Update `_match_contact_to_person()` | Implement 3-tier matching with account_email parameter |
| C4 | Update `_create_person_from_contact()` | Store google_resource_names, update caches |
| C5 | Update `_update_person_from_contact()` | Add resource_name if missing, update caches |

### Phase D: Sync Method Updates (2 tasks)

| # | Task | Description |
|---|------|-------------|
| D1 | Update `sync_contacts()` | Pass account.email to matching/create/update methods |
| D2 | Update `sync_all_accounts()` | Ensure account email is passed through |

### Phase E: Auto-Merge Integration (2 tasks)

| # | Task | Description |
|---|------|-------------|
| E1 | Add `calculate_completeness_score()` function | Score persons by data completeness |
| E2 | Add `auto_merge_duplicates()` function | Merge all duplicate groups using most complete as canonical |

### Phase F: Migration Execution (1 task)

| # | Task | Description |
|---|------|-------------|
| F1 | Run migration with auto-merge | Execute Alembic migration, then run auto_merge_duplicates() |

### Phase G: Testing & Documentation (2 tasks)

| # | Task | Description |
|---|------|-------------|
| G1 | Test sync creates no duplicates | Sync same account twice, verify no new duplicates |
| G2 | Update CHANGELOG | Document the fix |

---

## Acceptance Criteria

1. ✅ Syncing Google Contacts does NOT create duplicates for existing contacts
2. ✅ Multi-account support: same contact from 2 Google accounts creates 1 BlackBook person
3. ✅ Phone+name matching catches contacts without email
4. ✅ Existing 1394 duplicate groups auto-merged
5. ✅ `google_resource_names` properly populated for all synced contacts
6. ✅ Audit log of all auto-merged records

---

## Rollback Plan

If issues arise:
1. The Alembic migration can be reversed (down revision)
2. Auto-merged records are logged but not easily un-merged
3. Database backup should be taken before running migration

---

*End of Specification*
