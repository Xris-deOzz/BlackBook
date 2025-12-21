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

3. **Migrates existing data** from `google_resource_name` and `custom_fields`:
   - If `google_resource_name` exists, use it
   - Else if `custom_fields->>'google_contact_id'` exists, construct `people/{id}`
   - Key by `custom_fields->>'google_account_id'` or 'unknown_account' if missing

4. **Drops old columns** (google_resource_name, google_etag)

5. **Cleans up custom_fields** by removing google_contact_id and google_account_id keys

---

## Task 2: Update Person Model

In `app/models/person.py`:

1. **Remove** these fields:
   - `google_resource_name`
   - `google_etag`

2. **Add** new field:
   ```python
   google_resource_names: Mapped[dict[str, str]] = mapped_column(
       JSONB,
       default=dict,
       comment="Google resource names by account email: {'email@gmail.com': 'people/c123...'}"
   )
   ```

3. **Add helper methods:**
   ```python
   def get_google_resource_name(self, account_email: str) -> str | None:
       """Get the Google resource name for a specific account."""
       if self.google_resource_names is None:
           return None
       return self.google_resource_names.get(account_email)

   def set_google_resource_name(self, account_email: str, resource_name: str) -> None:
       """Set the Google resource name for a specific account."""
       if self.google_resource_names is None:
           self.google_resource_names = {}
       self.google_resource_names[account_email] = resource_name

   def has_google_resource_name(self, resource_name: str) -> bool:
       """Check if this person has a specific Google resource name from any account."""
       if not self.google_resource_names:
           return False
       return resource_name in self.google_resource_names.values()
   ```

4. **Keep** `google_synced_at` field as-is (still useful)

---

## Task 3: Update ContactsService

In `app/services/contacts_service.py`:

### 3.1 Add imports
```python
import re
```

### 3.2 Add phone normalization function (module level)
```python
def normalize_phone(phone: str | None) -> str | None:
    """Normalize phone number by removing all non-digit characters."""
    if not phone:
        return None
    normalized = re.sub(r'\D', '', phone)
    return normalized if normalized else None
```

### 3.3 Add new instance variables in `__init__`
```python
self._resource_name_to_person_cache: dict[str, UUID] | None = None
self._phone_name_to_person_cache: dict[tuple[str, str], UUID] | None = None
```

### 3.4 Add `_build_resource_name_cache()` method
```python
def _build_resource_name_cache(self) -> None:
    """Build cache mapping Google resource names to person IDs."""
    self._resource_name_to_person_cache = {}
    
    persons = self.db.query(Person).filter(
        Person.google_resource_names.isnot(None),
        Person.google_resource_names != {},
    ).all()
    
    for person in persons:
        if person.google_resource_names:
            for account_email, resource_name in person.google_resource_names.items():
                if resource_name:
                    self._resource_name_to_person_cache[resource_name] = person.id
```

### 3.5 Add `_build_phone_name_cache()` method
```python
def _build_phone_name_cache(self) -> None:
    """Build cache mapping (normalized_phone, full_name) to person IDs."""
    self._phone_name_to_person_cache = {}
    
    persons = self.db.query(Person).filter(Person.phone.isnot(None)).all()
    
    for person in persons:
        normalized = normalize_phone(person.phone)
        if normalized and person.full_name:
            key = (normalized, person.full_name.lower())
            self._phone_name_to_person_cache[key] = person.id
```

### 3.6 Update `_match_contact_to_person()` method

Replace the existing method with 3-tier matching:
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
    3. Phone + name combination (with normalized phone)
    """
    # Ensure caches are built
    if self._resource_name_to_person_cache is None:
        self._build_resource_name_cache()
    if self._email_to_person_cache is None:
        self._build_email_cache()
    if self._phone_name_to_person_cache is None:
        self._build_phone_name_cache()
    
    # TIER 1: Match by Google resource name
    if contact.resource_name and contact.resource_name in self._resource_name_to_person_cache:
        person_id = self._resource_name_to_person_cache[contact.resource_name]
        person = self.db.query(Person).filter_by(id=person_id).first()
        if person:
            return person
    
    # TIER 2: Match by email
    for email_data in contact.emails:
        email = email_data.get("value", "").lower()
        if email and email in self._email_to_person_cache:
            person_id = self._email_to_person_cache[email]
            person = self.db.query(Person).filter_by(id=person_id).first()
            if person:
                return person
    
    # TIER 3: Match by phone + name
    if contact.phones and contact.display_name:
        contact_name_lower = contact.display_name.lower()
        for phone_data in contact.phones:
            phone = phone_data.get("value")
            normalized_phone = normalize_phone(phone)
            if normalized_phone:
                key = (normalized_phone, contact_name_lower)
                if key in self._phone_name_to_person_cache:
                    person_id = self._phone_name_to_person_cache[key]
                    person = self.db.query(Person).filter_by(id=person_id).first()
                    if person:
                        return person
    
    return None
```

### 3.7 Update `_create_person_from_contact()` method

Update the method signature and body:
```python
def _create_person_from_contact(
    self,
    contact: GoogleContact,
    account_id: UUID,
    account_email: str,  # NEW PARAMETER
) -> Person:
```

Replace custom_fields creation:
```python
# OLD: 
custom_fields: dict[str, Any] = {
    "google_contact_id": contact.google_contact_id,
    "google_account_id": str(account_id),
    "imported_from": "google_contacts",
}

# NEW:
custom_fields: dict[str, Any] = {
    "imported_from": "google_contacts",
}
```

When creating the Person, add google_resource_names:
```python
person = Person(
    full_name=contact.display_name or "Unknown",
    first_name=contact.given_name,
    last_name=contact.family_name,
    title=contact.organization_title,
    profile_picture=contact.photo_url,
    birthday=contact.birthday,
    notes=contact.notes,
    location=contact.formatted_address,
    custom_fields=custom_fields,
    google_resource_names={account_email: contact.resource_name},  # NEW
)
```

After creating the person, update caches:
```python
# Update resource name cache
if self._resource_name_to_person_cache is not None:
    self._resource_name_to_person_cache[contact.resource_name] = person.id

# Update phone+name cache
if person.phone:
    normalized = normalize_phone(person.phone)
    if normalized and person.full_name and self._phone_name_to_person_cache is not None:
        key = (normalized, person.full_name.lower())
        self._phone_name_to_person_cache[key] = person.id
```

### 3.8 Update `_update_person_from_contact()` method

Update the method signature:
```python
def _update_person_from_contact(
    self,
    person: Person,
    contact: GoogleContact,
    account_email: str,  # NEW PARAMETER
) -> bool:
```

Remove the old google_contact_id storage in custom_fields and add:
```python
# Ensure Google resource name is stored for this account
if not person.has_google_resource_name(contact.resource_name):
    person.set_google_resource_name(account_email, contact.resource_name)
    updated = True
    
    # Update cache
    if self._resource_name_to_person_cache is not None:
        self._resource_name_to_person_cache[contact.resource_name] = person.id
```

### 3.9 Update `sync_contacts()` method

Update the sync loop to pass account.email:
```python
for contact in contacts:
    if not contact.display_name:
        result.contacts_skipped += 1
        continue

    # Try to match by resource name, email, or phone+name
    person = self._match_contact_to_person(contact, account.email)  # Pass email

    if person:
        updated = self._update_person_from_contact(person, contact, account.email)  # Pass email
        if updated:
            result.contacts_updated += 1
        result.contacts_matched += 1
    else:
        self._create_person_from_contact(contact, account.id, account.email)  # Pass email
        result.contacts_created += 1
```

---

## Task 4: Create Auto-Merge Script

Create `app/services/duplicate_auto_merge.py`:

```python
"""
Auto-merge duplicate persons based on completeness score.
Used during migration to clean up existing duplicates.
"""

from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Person
from app.services.person_merge import PersonMergeService


def calculate_completeness_score(person: Person) -> int:
    """
    Calculate how complete a person record is.
    Higher score = more data = better candidate for canonical record.
    """
    score = 0
    
    # Core identity fields (high value)
    if person.first_name: score += 10
    if person.last_name: score += 10
    if person.full_name and person.full_name.lower() != "unknown": score += 5
    if person.title: score += 8
    if person.phone: score += 8
    if person.email: score += 8
    if person.linkedin: score += 7
    if person.notes: score += 5
    if person.profile_picture: score += 3
    if person.birthday: score += 5
    if person.location: score += 4
    
    # Related records (medium value)
    if hasattr(person, 'emails'):
        score += len(person.emails) * 3
    if hasattr(person, 'phones'):
        score += len(person.phones) * 3
    if hasattr(person, 'organizations'):
        score += len(person.organizations) * 5
    if hasattr(person, 'interactions'):
        score += len(person.interactions) * 2
    if hasattr(person, 'tags'):
        score += len(person.tags) * 1
    
    # Google sync data (important for preventing future duplicates)
    if person.google_resource_names:
        score += 15
    if person.custom_fields and person.custom_fields.get("google_contact_id"):
        score += 10
    
    return score


def auto_merge_duplicates(db: Session, dry_run: bool = False) -> dict:
    """
    Auto-merge all duplicate groups (same full_name).
    
    Args:
        db: Database session
        dry_run: If True, only report what would be merged without actually merging
    
    Returns:
        Dict with merge statistics and details
    """
    merge_service = PersonMergeService(db)
    
    stats = {
        "groups_found": 0,
        "groups_processed": 0,
        "persons_merged": 0,
        "persons_remaining": 0,
        "errors": [],
        "merge_log": [],
    }
    
    # Find all duplicate groups (2+ persons with same full_name)
    duplicate_names = db.query(
        Person.full_name,
        func.count(Person.id).label('count')
    ).group_by(
        Person.full_name
    ).having(
        func.count(Person.id) > 1
    ).all()
    
    stats["groups_found"] = len(duplicate_names)
    
    for name, count in duplicate_names:
        # Get all persons with this name
        persons = db.query(Person).filter(
            Person.full_name == name
        ).all()
        
        if len(persons) < 2:
            continue
        
        stats["groups_processed"] += 1
        
        # Score each person by completeness
        scored = [(p, calculate_completeness_score(p)) for p in persons]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        canonical = scored[0][0]
        canonical_score = scored[0][1]
        duplicates = [p for p, _ in scored[1:]]
        
        # Log the merge plan
        merge_entry = {
            "name": name,
            "canonical_id": str(canonical.id),
            "canonical_score": canonical_score,
            "duplicates": [
                {"id": str(dup.id), "score": s}
                for dup, s in scored[1:]
            ],
        }
        stats["merge_log"].append(merge_entry)
        
        if dry_run:
            stats["persons_merged"] += len(duplicates)
            continue
        
        # Perform merges
        for dup in duplicates:
            try:
                merge_service.merge_persons(
                    target_id=canonical.id,
                    source_id=dup.id,
                )
                stats["persons_merged"] += 1
            except Exception as e:
                stats["errors"].append({
                    "name": name,
                    "target_id": str(canonical.id),
                    "source_id": str(dup.id),
                    "error": str(e),
                })
    
    # Count remaining persons
    stats["persons_remaining"] = db.query(func.count(Person.id)).scalar()
    
    return stats


def run_auto_merge_with_report(db: Session) -> str:
    """
    Run auto-merge and generate a human-readable report.
    """
    # First do a dry run
    dry_stats = auto_merge_duplicates(db, dry_run=True)
    
    report_lines = [
        "=" * 60,
        "DUPLICATE AUTO-MERGE REPORT",
        "=" * 60,
        f"Duplicate groups found: {dry_stats['groups_found']}",
        f"Persons to be merged: {dry_stats['persons_merged']}",
        "",
        "Proceeding with merge...",
        "",
    ]
    
    # Now do the actual merge
    actual_stats = auto_merge_duplicates(db, dry_run=False)
    
    report_lines.extend([
        f"Groups processed: {actual_stats['groups_processed']}",
        f"Persons merged: {actual_stats['persons_merged']}",
        f"Errors: {len(actual_stats['errors'])}",
        f"Persons remaining: {actual_stats['persons_remaining']}",
    ])
    
    if actual_stats['errors']:
        report_lines.append("")
        report_lines.append("ERRORS:")
        for err in actual_stats['errors']:
            report_lines.append(f"  - {err['name']}: {err['error']}")
    
    report_lines.append("=" * 60)
    
    return "\n".join(report_lines)
```

---

## Task 5: Integrate Auto-Merge into Migration

In the Alembic migration file, after the schema changes, add a data migration step that calls the auto-merge function. You can either:

**Option A:** Add to migration upgrade():
```python
from app.services.duplicate_auto_merge import run_auto_merge_with_report

def upgrade():
    # ... schema changes ...
    
    # Run auto-merge
    from sqlalchemy.orm import Session
    bind = op.get_bind()
    session = Session(bind=bind)
    
    try:
        report = run_auto_merge_with_report(session)
        print(report)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Auto-merge failed: {e}")
        raise
```

**Option B:** Create separate script `scripts/run_dedup_migration.py` that runs after migration.

Choose Option A for simplicity unless the merge is too slow.

---

## Task 6: Update push_to_google Method

In `contacts_service.py`, update the `push_to_google()` method to use `google_resource_names` instead of `google_resource_name`:

```python
def push_to_google(self, person_id: UUID, account_id: UUID) -> dict[str, Any]:
    # ... existing code ...
    
    # Check if already linked (updated check)
    if person.google_resource_names and account.email in person.google_resource_names:
        raise ContactsServiceError(
            f"Person is already linked to Google Contacts for account {account.email}"
        )
    
    # ... API call code ...
    
    # Update person with new resource name (updated)
    person.set_google_resource_name(account.email, result.get("resourceName"))
    person.google_synced_at = datetime.now(timezone.utc)
    self.db.commit()
```

---

## Testing Checklist

After implementation:

1. [ ] Run Alembic migration: `alembic upgrade head`
2. [ ] Verify `google_resource_names` column exists with data migrated
3. [ ] Verify auto-merge report shows duplicates merged
4. [ ] Check Duplicate Management page - should show significantly fewer duplicates
5. [ ] Trigger a Google Contacts sync
6. [ ] Verify no new duplicates created
7. [ ] Trigger sync again - still no duplicates
8. [ ] Test creating a new person and pushing to Google
9. [ ] Test syncing from a second Google account (if available)

---

## Files to Modify

1. `alembic/versions/xxx_add_google_resource_names.py` (new)
2. `app/models/person.py`
3. `app/services/contacts_service.py`
4. `app/services/duplicate_auto_merge.py` (new)

---

## Important Notes

- Take a database backup before running migration
- The auto-merge uses existing `PersonMergeService` - verify it handles all related tables
- Phone normalization strips ALL non-digits (international prefixes like +1 become 1)
- The GIN index on JSONB enables efficient lookups into `google_resource_names`
