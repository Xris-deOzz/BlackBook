# Bidirectional Google Contacts Sync Specification

**Document Version:** 2025.12.18.1  
**Created:** 2025-12-18  
**Status:** Draft - Ready for Implementation  
**Phase:** 7 (Post-Deployment Enhancement)

---

## Executive Summary

Enhance BlackBook's Google Contacts integration from one-way import to full bidirectional synchronization. BlackBook becomes the master database, syncing changes to all connected Google accounts while preserving data from both sources.

### Key Principles

1. **BlackBook is Master** - Source of truth for all contact data
2. **Sync to ALL Accounts** - Every contact syncs to all connected Google accounts
3. **Merge, Don't Overwrite** - Conflicts resolved by keeping both values
4. **Archive Before Delete** - Deleted contacts preserved for recovery
5. **Full Audit Trail** - Every sync operation logged for debugging/recovery

---

## Current State

| Capability | Status |
|------------|--------|
| Google → BlackBook import | ✅ Working |
| BlackBook → Google push | ❌ Not implemented |
| Automatic sync | ❌ Manual only |
| Deletion sync | ❌ Not implemented |
| Conflict resolution | ❌ Not implemented |
| Audit trail | ❌ Not implemented |

---

## Target State

| Capability | Target |
|------------|--------|
| Google → BlackBook sync | ✅ Automatic |
| BlackBook → Google sync | ✅ Automatic |
| Sync frequency | 07:00 & 21:00 ET + manual |
| Deletion sync | ✅ Both directions with archive |
| Conflict resolution | ✅ Merge + manual review queue |
| Audit trail | ✅ Full sync_log table |

---

## Sync Behavior

### Direction: Google → BlackBook

| Scenario | Behavior |
|----------|----------|
| New contact in Google | Create in BlackBook |
| Updated field in Google | Merge (see conflict rules) |
| Deleted contact in Google | Archive in BlackBook, then delete |
| New email/phone in Google | Add to BlackBook (dedupe exact matches) |

### Direction: BlackBook → Google

| Scenario | Behavior |
|----------|----------|
| New contact in BlackBook | Create in ALL connected Google accounts |
| Updated field in BlackBook | Push to ALL Google accounts |
| Deleted contact in BlackBook | Archive in BlackBook, delete from ALL Google accounts |
| New email/phone in BlackBook | Add to ALL Google accounts |

### Sync Scope

- **Accounts:** All connected Google accounts
- **Contacts:** All contacts (no filtering)
- **Tags → Labels:** NOT synced (BlackBook is master for tags)
- **Labels → Tags:** Import on initial sync only, no ongoing sync

---

## Field Mapping

### Fields Synced Bidirectionally

| BlackBook Field | Google Field | Notes |
|-----------------|--------------|-------|
| `full_name` | `names[0].displayName` | |
| `first_name` | `names[0].givenName` | |
| `last_name` | `names[0].familyName` | |
| `title` | `organizations[0].title` | |
| `phone` | `phoneNumbers[]` | Multi-value |
| `emails[]` | `emailAddresses[]` | Multi-value |
| `birthday` | `birthdays[0].date` | |
| `location` | `addresses[0].formattedValue` | |
| `notes` | `biographies[0].value` | 2048 char limit in Google |
| `profile_picture` | `photos[0].url` | Read-only from Google |

### Fields NOT Synced to Google

| BlackBook Field | Reason |
|-----------------|--------|
| `tags` | BlackBook-only (labels not synced) |
| `priority` | BlackBook-only |
| `status` | BlackBook-only |
| `custom_fields` | BlackBook-only |
| `interactions` | BlackBook-only |
| `organizations` (relationships) | BlackBook-only |

---

## Conflict Resolution Rules

### Rule 1: Multi-Value Fields (Phones, Emails)

**Strategy:** Keep all values from both systems

```
Google phones: [(555) 123-4567]
BlackBook phones: [(555) 987-6543]
Result: [(555) 123-4567, (555) 987-6543] in BOTH systems
```

- Deduplicate exact matches (case-insensitive for emails)
- Different formats of same number treated as different (no phone normalization)

### Rule 2: Notes

**Strategy:** Merge with source labels

```
Google note: "Met at conference 2024"
BlackBook note: "Investor contact - interested in Series B"

Result (in BlackBook):
---
Investor contact - interested in Series B
---
[Imported from Google - ossowski.chris@gmail.com] Met at conference 2024
---

Result (in Google) - truncated if needed:
---
Investor contact - interested in Series B
---
[From BlackBook] Met at conference 2024
... [See BlackBook for full note]
```

**Note Length Handling:**
- Google limit: 2048 characters
- If BlackBook note > 2048 chars, truncate with: `\n... [See BlackBook for full note]`

### Rule 3: Names (Nickname Matching)

**Strategy:** Flag for manual review, but recognize common nicknames

**Recognized as SAME person (no conflict):**
- Christopher ↔ Chris
- William ↔ Bill ↔ Will
- Robert ↔ Rob ↔ Bob
- Michael ↔ Mike
- (Full list in `duplicate_service.py` NICKNAMES dict)

**When nicknames match:**
- Flag for manual review
- Show both forms to user
- User decides which to keep or keep both

**When names truly conflict:**
- Example: "John Smith" vs "Jonathan Smith"
- Add to manual review queue
- User resolves

### Rule 4: Single-Value Fields (Title, Location, Birthday)

**Strategy:** BlackBook wins (it's the master)

- If BlackBook has value → use BlackBook value
- If BlackBook empty, Google has value → use Google value
- If both have different values → use BlackBook, log the Google value in sync_log

---

## Deletion Handling

### Deleted in Google

1. Detect deletion during sync (contact no longer in Google API response)
2. Create archive record with full person snapshot
3. Delete person from BlackBook
4. Log in sync_log with `action = 'delete'`, `deleted_from = 'google'`

### Deleted in BlackBook

1. User deletes person in BlackBook UI
2. Create archive record with full person snapshot
3. Delete from ALL connected Google accounts via API
4. Log in sync_log with `action = 'delete'`, `deleted_from = 'blackbook'`

### Archive Recovery

- Archived contacts viewable in Archive Browser UI
- User can restore archived contact (re-creates in BlackBook + all Google accounts)
- Archive retained for 90 days (configurable), then permanently deleted

---

## Database Schema Changes

### New Table: `sync_log`

```sql
CREATE TABLE sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
    google_account_id UUID REFERENCES google_accounts(id) ON DELETE SET NULL,
    direction VARCHAR(25) NOT NULL,  -- 'google_to_blackbook', 'blackbook_to_google'
    action VARCHAR(20) NOT NULL,     -- 'create', 'update', 'delete', 'archive', 'restore'
    status VARCHAR(20) NOT NULL,     -- 'success', 'failed', 'pending_review'
    fields_changed JSONB,            -- {"phone": {"old": "...", "new": "..."}, ...}
    error_message TEXT,              -- If status = 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sync_log_person ON sync_log(person_id);
CREATE INDEX idx_sync_log_created ON sync_log(created_at DESC);
CREATE INDEX idx_sync_log_status ON sync_log(status);
```

### New Table: `archived_persons`

```sql
CREATE TABLE archived_persons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_person_id UUID NOT NULL,
    person_data JSONB NOT NULL,           -- Full snapshot of person + emails + phones
    deleted_from VARCHAR(20) NOT NULL,    -- 'google' or 'blackbook'
    deleted_by_account_id UUID,           -- Google account that triggered deletion (if from Google)
    google_contact_ids JSONB,             -- {"account_email": "people/c123...", ...}
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,  -- 90 days from archived_at
    restored_at TIMESTAMP WITH TIME ZONE, -- NULL until restored
    restored_person_id UUID               -- New person ID if restored
);

CREATE INDEX idx_archived_persons_original ON archived_persons(original_person_id);
CREATE INDEX idx_archived_persons_archived ON archived_persons(archived_at DESC);
```

### New Table: `sync_review_queue`

```sql
CREATE TABLE sync_review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id UUID REFERENCES persons(id) ON DELETE CASCADE,
    review_type VARCHAR(30) NOT NULL,    -- 'name_conflict', 'data_conflict', 'duplicate_suspect'
    google_account_id UUID REFERENCES google_accounts(id),
    google_data JSONB NOT NULL,          -- Data from Google for comparison
    blackbook_data JSONB NOT NULL,       -- Data from BlackBook for comparison
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'resolved', 'dismissed'
    resolution JSONB,                     -- User's decision
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_sync_review_status ON sync_review_queue(status);
```

### Modified Table: `persons`

Add columns:

```sql
ALTER TABLE persons ADD COLUMN sync_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE persons ADD COLUMN last_synced_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE persons ADD COLUMN sync_status VARCHAR(20) DEFAULT 'pending'; -- 'synced', 'pending', 'error'
ALTER TABLE persons ADD COLUMN google_contact_ids JSONB DEFAULT '{}';  
-- Format: {"ossowski.chris@gmail.com": "people/c123...", "chris@blackperun.com": "people/c456..."}
```

### Modified Table: `google_accounts`

Add columns:

```sql
ALTER TABLE google_accounts ADD COLUMN sync_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE google_accounts ADD COLUMN last_full_sync_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE google_accounts ADD COLUMN next_sync_at TIMESTAMP WITH TIME ZONE;
```

---

## Sync Schedule Configuration

### Default Schedule

| Sync Time | Timezone |
|-----------|----------|
| 07:00 | America/New_York (ET) |
| 21:00 | America/New_York (ET) |

### Settings Storage

Add to `app_settings` table or create new `sync_settings` table:

```sql
CREATE TABLE sync_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auto_sync_enabled BOOLEAN DEFAULT TRUE,
    sync_time_1 TIME DEFAULT '07:00',
    sync_time_2 TIME DEFAULT '21:00',
    sync_timezone VARCHAR(50) DEFAULT 'America/New_York',
    archive_retention_days INTEGER DEFAULT 90,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Single row table (singleton pattern)
INSERT INTO sync_settings DEFAULT VALUES;
```

### Scheduler Implementation

Use **APScheduler** with persistent job store:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = AsyncIOScheduler(
    jobstores={'default': SQLAlchemyJobStore(url=DATABASE_URL)},
    timezone='America/New_York'
)

# Jobs added dynamically based on sync_settings
scheduler.add_job(
    run_bidirectional_sync,
    'cron',
    hour=7,
    minute=0,
    id='sync_morning',
    replace_existing=True
)
```

---

## API Endpoints

### Sync Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sync/now` | Trigger immediate full sync |
| POST | `/api/sync/person/{id}` | Sync single person to Google |
| GET | `/api/sync/status` | Get sync status (last run, next run, errors) |
| GET | `/api/sync/log` | Get sync log with pagination |
| GET | `/api/sync/log/{person_id}` | Get sync log for specific person |

### Review Queue

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sync/review` | Get pending review items |
| POST | `/api/sync/review/{id}/resolve` | Resolve a review item |
| POST | `/api/sync/review/{id}/dismiss` | Dismiss without action |

### Archive

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/archive/persons` | List archived persons |
| GET | `/api/archive/persons/{id}` | Get archived person details |
| POST | `/api/archive/persons/{id}/restore` | Restore archived person |
| DELETE | `/api/archive/persons/{id}` | Permanently delete |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sync/settings` | Get sync settings |
| PUT | `/api/sync/settings` | Update sync settings |

---

## UI Components

### 1. Person Card - Sync Status Badge

Location: Person list view, each card

```
┌─────────────────────────────────────┐
│ John Smith              ✅ Synced   │
│ VP of Engineering                   │
│ Acme Corp                          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Jane Doe                ⏳ Pending  │
│ CEO                                 │
│ StartupXYZ                         │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Bob Wilson              ⚠️ Error    │
│ Consultant                          │
│                                     │
└─────────────────────────────────────┘
```

### 2. Person Detail Page - Sync Info

Location: Person detail page, sidebar or info section

```
┌─────────────────────────────────────┐
│ Sync Status                         │
├─────────────────────────────────────┤
│ Status: ✅ Synced                   │
│ Last synced: 2 hours ago            │
│                                     │
│ Google Accounts:                    │
│   • ossowski.chris@gmail.com ✅     │
│   • chris@blackperun.com ✅         │
│                                     │
│ [🔄 Push to Google]                 │
└─────────────────────────────────────┘
```

### 3. Settings Page - Sync Tab (New Tab #10)

```
┌─────────────────────────────────────────────────────────────┐
│ Sync Settings                                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Auto-Sync                                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [✓] Enable automatic sync                               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Sync Schedule                                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Morning sync:  [07:00 ▼]                                │ │
│ │ Evening sync:  [21:00 ▼]                                │ │
│ │ Timezone:      [America/New_York ▼]                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Manual Sync                                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Last sync: Dec 18, 2025 at 07:00 ET                     │ │
│ │ Next sync: Dec 18, 2025 at 21:00 ET                     │ │
│ │                                                         │ │
│ │ [🔄 Sync Now]                                           │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Archive Settings                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Retain archived contacts for: [90 ▼] days               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4. Sync Log Page

Location: Settings → Sync → "View Sync Log" link

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Sync Log                                                    [Filter ▼]  │
├─────────────────────────────────────────────────────────────────────────┤
│ Time                │ Person        │ Action  │ Direction │ Status     │
├─────────────────────────────────────────────────────────────────────────┤
│ 2025-12-18 07:00:05 │ John Smith    │ update  │ G → BB    │ ✅ Success │
│ 2025-12-18 07:00:04 │ Jane Doe      │ create  │ BB → G    │ ✅ Success │
│ 2025-12-18 07:00:03 │ Bob Wilson    │ update  │ G → BB    │ ⚠️ Review  │
│ 2025-12-18 07:00:02 │ Alice Chen    │ delete  │ G → BB    │ ✅ Archived│
│ 2025-12-17 21:00:15 │ Tom Brown     │ update  │ BB → G    │ ❌ Failed  │
├─────────────────────────────────────────────────────────────────────────┤
│                              [< Prev] Page 1 of 5 [Next >]              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5. Review Queue Page

Location: Settings → Sync → "Review Queue (3)" badge

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Sync Review Queue                                          3 pending    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ⚠️ Name Conflict                                                    │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ BlackBook:  Christopher Ossowski                                    │ │
│ │ Google:     Chris Ossowski                                          │ │
│ │                                                                     │ │
│ │ [Use BlackBook] [Use Google] [Keep Both] [Dismiss]                  │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ⚠️ Name Conflict                                                    │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ BlackBook:  William Johnson                                         │ │
│ │ Google:     Bill Johnson                                            │ │
│ │                                                                     │ │
│ │ [Use BlackBook] [Use Google] [Keep Both] [Dismiss]                  │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6. Archive Browser Page

Location: Settings → Sync → "Archive Browser" link

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Archived Contacts                                          [Search 🔍] │
├─────────────────────────────────────────────────────────────────────────┤
│ Archived        │ Name           │ Deleted From │ Actions              │
├─────────────────────────────────────────────────────────────────────────┤
│ Dec 18, 2025    │ Alice Chen     │ Google       │ [View] [Restore] [🗑]│
│ Dec 15, 2025    │ Old Contact    │ BlackBook    │ [View] [Restore] [🗑]│
│ Dec 10, 2025    │ Test Person    │ BlackBook    │ [View] [Restore] [🗑]│
├─────────────────────────────────────────────────────────────────────────┤
│ Showing 3 archived contacts │ Expires after 90 days                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7. Person Create/Edit Form - Sync Checkbox

Location: Person create/edit modal or page

```
┌─────────────────────────────────────────────────────────────┐
│ Create New Person                                           │
├─────────────────────────────────────────────────────────────┤
│ First Name: [_______________]                               │
│ Last Name:  [_______________]                               │
│ Email:      [_______________]                               │
│ Phone:      [_______________]                               │
│ ...                                                         │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [✓] Sync to Google Contacts                             │ │
│ │     (Will sync to all connected accounts)               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│                              [Cancel] [Save]                │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Tasks

### Phase 7A: Database & Models (8 tasks)

| # | Task | Estimate |
|---|------|----------|
| 7A.1 | Create Alembic migration for new tables | 1 hr |
| 7A.2 | Create `SyncLog` SQLAlchemy model | 0.5 hr |
| 7A.3 | Create `ArchivedPerson` SQLAlchemy model | 0.5 hr |
| 7A.4 | Create `SyncReviewQueue` SQLAlchemy model | 0.5 hr |
| 7A.5 | Create `SyncSettings` SQLAlchemy model | 0.5 hr |
| 7A.6 | Add sync columns to `Person` model | 0.5 hr |
| 7A.7 | Add sync columns to `GoogleAccount` model | 0.5 hr |
| 7A.8 | Write model unit tests | 1 hr |

### Phase 7B: Sync Service Core (12 tasks)

| # | Task | Estimate |
|---|------|----------|
| 7B.1 | Create `BidirectionalSyncService` class | 1 hr |
| 7B.2 | Implement `sync_google_to_blackbook()` | 3 hr |
| 7B.3 | Implement `sync_blackbook_to_google()` | 3 hr |
| 7B.4 | Implement `create_google_contact()` API call | 1 hr |
| 7B.5 | Implement `update_google_contact()` API call | 1 hr |
| 7B.6 | Implement `delete_google_contact()` API call | 1 hr |
| 7B.7 | Implement conflict detection logic | 2 hr |
| 7B.8 | Implement notes merge logic | 1 hr |
| 7B.9 | Implement phone/email deduplication | 1 hr |
| 7B.10 | Implement archive service | 1.5 hr |
| 7B.11 | Implement restore from archive | 1 hr |
| 7B.12 | Write sync service unit tests | 3 hr |

### Phase 7C: Scheduler (5 tasks)

| # | Task | Estimate |
|---|------|----------|
| 7C.1 | Add APScheduler to requirements | 0.25 hr |
| 7C.2 | Create scheduler initialization in `main.py` | 1 hr |
| 7C.3 | Implement dynamic schedule from settings | 1 hr |
| 7C.4 | Add scheduler health check endpoint | 0.5 hr |
| 7C.5 | Test scheduler with timezone handling | 1 hr |

### Phase 7D: API Endpoints (8 tasks)

| # | Task | Estimate |
|---|------|----------|
| 7D.1 | Create `app/routers/sync.py` | 0.5 hr |
| 7D.2 | Implement `POST /api/sync/now` | 1 hr |
| 7D.3 | Implement `POST /api/sync/person/{id}` | 0.5 hr |
| 7D.4 | Implement `GET /api/sync/status` | 0.5 hr |
| 7D.5 | Implement `GET /api/sync/log` | 1 hr |
| 7D.6 | Implement review queue endpoints | 1.5 hr |
| 7D.7 | Implement archive endpoints | 1.5 hr |
| 7D.8 | Implement settings endpoints | 1 hr |

### Phase 7E: UI Components (10 tasks)

| # | Task | Estimate |
|---|------|----------|
| 7E.1 | Add sync status badge to person cards | 1 hr |
| 7E.2 | Add sync info section to person detail | 1 hr |
| 7E.3 | Add "Push to Google" button | 0.5 hr |
| 7E.4 | Create Sync Settings tab in Settings | 2 hr |
| 7E.5 | Create Sync Log page | 2 hr |
| 7E.6 | Create Review Queue page | 2.5 hr |
| 7E.7 | Create Archive Browser page | 2 hr |
| 7E.8 | Add sync checkbox to person forms | 0.5 hr |
| 7E.9 | Add "Sync Now" button to Settings | 0.5 hr |
| 7E.10 | Add review queue badge to nav | 0.5 hr |

### Phase 7F: Testing & Documentation (5 tasks)

| # | Task | Estimate |
|---|------|----------|
| 7F.1 | Integration tests for full sync cycle | 3 hr |
| 7F.2 | Test deletion sync both directions | 1 hr |
| 7F.3 | Test conflict resolution scenarios | 2 hr |
| 7F.4 | Update `GOOGLE_SETUP.md` with sync info | 1 hr |
| 7F.5 | Update `Claude_Code_Context.md` | 0.5 hr |

---

## Estimated Total Effort

| Phase | Tasks | Hours |
|-------|-------|-------|
| 7A: Database & Models | 8 | 5 |
| 7B: Sync Service Core | 12 | 19.5 |
| 7C: Scheduler | 5 | 3.75 |
| 7D: API Endpoints | 8 | 7.5 |
| 7E: UI Components | 10 | 12.5 |
| 7F: Testing & Docs | 5 | 7.5 |
| **Total** | **48** | **~56 hours** |

---

## Dependencies

### Python Packages to Add

```
APScheduler>=3.10.0      # Background scheduler
pytz>=2023.3             # Timezone handling (may already have)
```

### Google API Scopes Required

Already configured ✅:
- `https://www.googleapis.com/auth/contacts` (full read/write)
- `https://www.googleapis.com/auth/contacts.other.readonly` (other contacts)

---

## Risk Mitigation

### Risk 1: Accidental Mass Deletion

**Mitigation:**
- Archive before any deletion
- 90-day retention on archives
- Sync log for full audit trail
- Confirmation dialog for bulk operations

### Risk 2: Google API Rate Limits

**Mitigation:**
- Batch operations where possible
- Exponential backoff on rate limit errors
- Track API quota usage in sync_log
- Alert if approaching limits

### Risk 3: Sync Conflicts Causing Data Loss

**Mitigation:**
- Never overwrite, always merge
- Flag ambiguous cases for review
- Full field change history in sync_log
- Archive contains complete person snapshot

### Risk 4: Scheduler Fails Silently

**Mitigation:**
- Health check endpoint for scheduler
- Log all scheduler runs (success or failure)
- Dashboard widget showing last sync status
- Email notification on sync failure (future)

---

## Future Enhancements (Not in Scope)

- Email notifications for sync failures
- Selective sync (choose which contacts to sync)
- Sync frequency per account
- Google Workspace admin sync (organization-wide)
- Proton Mail / other providers
- Webhook-based real-time sync

---

## Acceptance Criteria

1. ✅ New contact in BlackBook appears in all Google accounts within scheduled sync
2. ✅ New contact in Google appears in BlackBook within scheduled sync
3. ✅ Edited fields sync both directions
4. ✅ Deleted contact archived and removed from both systems
5. ✅ Name conflicts flagged for manual review
6. ✅ Notes merged with source labels
7. ✅ Multiple phones/emails kept from both systems
8. ✅ Sync runs automatically at configured times
9. ✅ Manual "Sync Now" works immediately
10. ✅ Archived contacts can be restored
11. ✅ Full audit trail in sync log
12. ✅ UI shows sync status on person cards

---

*End of Specification*
