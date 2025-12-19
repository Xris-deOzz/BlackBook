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

## Database Schema Changes

### Migration: Add google_resource_names Column

```sql
-- Step 1: Add new JSONB column
ALTER TABLE persons ADD COLUMN google_resource_names JSONB DEFAULT '{}';

-- Step 2: Create GIN index for fast lookups
CREATE INDEX idx_persons_google_resource_names ON persons USING GIN (google_resource_names);

-- Step 3: Migrate existing data from google_resource_name and custom_fields
UPDATE persons
SET google_resource_names = jsonb_build_object(
    COALESCE(
        custom_fields->>'google_account_id',
        'unknown_account'
    )::text,
    COALESCE(
        google_resource_name,
        'people/' || (custom_fields->>'google_contact_id')
    )
)
WHERE google_resource_name IS NOT NULL 
   OR custom_fields->>'google_contact_id' IS NOT NULL;

-- Step 4: Drop old columns (after verifying migration)
ALTER TABLE persons DROP COLUMN IF EXISTS google_resource_name;
ALTER TABLE persons DROP COLUMN IF EXISTS google_etag;
```

### Person Model Changes

```python
# Remove:
google_resource_name: Mapped[str | None]
google_etag: Mapped[str | None]

# Add:
google_resource_names: Mapped[dict[str, str]] = mapped_column(
    JSONB,
    default=dict,
    comment="Google resource names by account email: {'email@gmail.com': 'people/c123...'}"
)

# Helper methods:
def get_google_resource_name(self, account_email: str) -> str | None:
    """Get the Google resource name for a specific account."""
    return self.google_resource_names.get(account_email)

def set_google_resource_name(self, account_email: str, resource_name: str) -> None:
    """Set the Google resource name for a specific account."""
    if self.google_resource_names is None:
        self.google_resource_names = {}
    self.google_resource_names[account_email] = resource_name

def has_google_resource_name(self, resource_name: str) -> bool:
    """Check if this person has a specific Google resource name from any account."""
    return resource_name in self.google_resource_names.values()
```

---

## Updated contacts_service.py

### New Cache Structures

```python
class ContactsService:
    def __init__(self, db: Session):
        self.db = db
        self._email_to_person_cache: dict[str, UUID] | None = None
        self._contact_groups_cache: dict[str, str] | None = None
        # NEW:
        self._resource_name_to_person_cache: dict[str, UUID] | None = None
        self._phone_name_to_person_cache: dict[tuple[str, str], UUID] | None = None
```

### New: Phone Normalization Utility

```python
import re

def normalize_phone(phone: str | None) -> str | None:
    """Normalize phone number by removing all non-digit characters."""
    if not phone:
        return None
    normalized = re.sub(r'\D', '', phone)
    return normalized if normalized else None
```

### New: Build Resource Name Cache

```python
def _build_resource_name_cache(self) -> None:
    """Build cache mapping Google resource names to person IDs."""
    self._resource_name_to_person_cache = {}
    
    # Query all persons with google_resource_names
    persons = self.db.query(Person).filter(
        Person.google_resource_names != {}
    ).all()
    
    for person in persons:
        if person.google_resource_names:
            for account_email, resource_name in person.google_resource_names.items():
                self._resource_name_to_person_cache[resource_name] = person.id
```

### New: Build Phone+Name Cache

```python
def _build_phone_name_cache(self) -> None:
    """Build cache mapping (normalized_phone, full_name) to person IDs."""
    self._phone_name_to_person_cache = {}
    
    # Get persons with phone numbers
    persons = self.db.query(Person).filter(Person.phone.isnot(None)).all()
    
    for person in persons:
        normalized = normalize_phone(person.phone)
        if normalized and person.full_name:
            key = (normalized, person.full_name.lower())
            self._phone_name_to_person_cache[key] = person.id
```

### Updated: Match Contact to Person (3-Tier)

```python
def _match_contact_to_person(
    self, 
    contact: GoogleContact,
    account_email: str,
) -> Person | None:
    """
    Try to find an existing person using 3-tier matching:
    1. Google resource name (most reliable)
    2. Email address
    3. Phone + name combination
    """
    # Ensure caches are built
    if self._resource_name_to_person_cache is None:
        self._build_resource_name_cache()
    if self._email_to_person_cache is None:
        self._build_email_cache()
    if self._phone_name_to_person_cache is None:
        self._build_phone_name_cache()
    
    # TIER 1: Match by Google resource name
    if contact.resource_name in self._resource_name_to_person_cache:
        person_id = self._resource_name_to_person_cache[contact.resource_name]
        return self.db.query(Person).filter_by(id=person_id).first()
    
    # TIER 2: Match by email
    for email_data in contact.emails:
        email = email_data.get("value", "").lower()
        if email and email in self._email_to_person_cache:
            person_id = self._email_to_person_cache[email]
            return self.db.query(Person).filter_by(id=person_id).first()
    
    # TIER 3: Match by phone + name
    if contact.phones and contact.display_name:
        for phone_data in contact.phones:
            phone = phone_data.get("value")
            normalized_phone = normalize_phone(phone)
            if normalized_phone:
                key = (normalized_phone, contact.display_name.lower())
                if key in self._phone_name_to_person_cache:
                    person_id = self._phone_name_to_person_cache[key]
                    return self.db.query(Person).filter_by(id=person_id).first()
    
    # No match found
    return None
```

### Updated: Create Person from Contact

```python
def _create_person_from_contact(
    self,
    contact: GoogleContact,
    account_id: UUID,
    account_email: str,  # NEW PARAMETER
) -> Person:
    """Create a new Person record from a Google Contact."""
    # ... existing field mapping code ...
    
    person = Person(
        full_name=contact.display_name or "Unknown",
        first_name=contact.given_name,
        last_name=contact.family_name,
        # ... other fields ...
        
        # NEW: Store Google resource name properly
        google_resource_names={account_email: contact.resource_name},
    )
    
    # ... rest of method (emails, tags, etc.) ...
    
    # Update caches
    if self._resource_name_to_person_cache is not None:
        self._resource_name_to_person_cache[contact.resource_name] = person.id
    
    if person.phone:
        normalized = normalize_phone(person.phone)
        if normalized and self._phone_name_to_person_cache is not None:
            key = (normalized, person.full_name.lower())
            self._phone_name_to_person_cache[key] = person.id
    
    return person
```

### Updated: Update Person from Contact

```python
def _update_person_from_contact(
    self,
    person: Person,
    contact: GoogleContact,
    account_email: str,  # NEW PARAMETER
) -> bool:
    """Update existing person with Google Contact data."""
    updated = False
    
    # ... existing field update code ...
    
    # NEW: Ensure Google resource name is stored
    if not person.has_google_resource_name(contact.resource_name):
        person.set_google_resource_name(account_email, contact.resource_name)
        updated = True
        
        # Update cache
        if self._resource_name_to_person_cache is not None:
            self._resource_name_to_person_cache[contact.resource_name] = person.id
    
    return updated
```

---

## Auto-Merge Script (Run During Migration)

### Logic for Canonical Record Selection

```python
def calculate_completeness_score(person: Person) -> int:
    """Calculate how complete a person record is."""
    score = 0
    
    # Core fields (high value)
    if person.first_name: score += 10
    if person.last_name: score += 10
    if person.full_name and person.full_name != "Unknown": score += 5
    if person.title: score += 8
    if person.phone: score += 8
    if person.email: score += 8
    if person.linkedin: score += 7
    if person.notes: score += 5
    if person.profile_picture: score += 3
    if person.birthday: score += 5
    if person.location: score += 4
    
    # Related records (medium value)
    score += len(person.emails) * 3
    score += len(person.phones) * 3
    score += len(person.organizations) * 5
    score += len(person.interactions) * 2
    score += len(person.tags) * 1
    
    # Google sync (important for dedup)
    if person.google_resource_names: score += 15
    if person.custom_fields and person.custom_fields.get("google_contact_id"): score += 10
    
    return score


def auto_merge_duplicates(db: Session) -> dict:
    """
    Auto-merge all duplicate groups.
    
    Returns:
        Dict with merge statistics
    """
    from app.services.duplicate_service import DuplicateService
    from app.services.person_merge import PersonMergeService
    
    dup_service = DuplicateService(db)
    merge_service = PersonMergeService(db)
    
    stats = {
        "groups_processed": 0,
        "persons_merged": 0,
        "errors": [],
    }
    
    # Get all duplicate groups (exact name match)
    duplicate_groups = dup_service.find_exact_duplicates()
    
    for group in duplicate_groups:
        if len(group) < 2:
            continue
        
        stats["groups_processed"] += 1
        
        # Find canonical record (most complete)
        scored = [(p, calculate_completeness_score(p)) for p in group]
        scored.sort(key=lambda x: x[1], reverse=True)
        canonical = scored[0][0]
        duplicates = [p for p, _ in scored[1:]]
        
        # Merge all duplicates into canonical
        for dup in duplicates:
            try:
                merge_service.merge_persons(
                    target_id=canonical.id,
                    source_id=dup.id,
                )
                stats["persons_merged"] += 1
            except Exception as e:
                stats["errors"].append({
                    "target": str(canonical.id),
                    "source": str(dup.id),
                    "error": str(e),
                })
    
    return stats
```

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
