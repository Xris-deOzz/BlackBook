# Claude Code Prompt: Phase 7 - Bidirectional Google Contacts Sync

**Document Version:** 2025.12.18.1  
**Created:** 2025-12-18  
**Specification:** `docs/GOOGLE_CONTACTS_BIDIRECTIONAL_SYNC_2025.12.18.1.md`

---

## Overview

Implement bidirectional synchronization between BlackBook and Google Contacts. BlackBook is the master database. All contacts sync to ALL connected Google accounts.

## Key Requirements

1. **Sync Direction:** Bidirectional (BlackBook ↔ All Google Accounts)
2. **Schedule:** 07:00 & 21:00 ET daily + manual "Sync Now" button
3. **Conflicts:** Merge values (keep both), flag name conflicts for manual review
4. **Deletions:** Archive before delete, 90-day retention
5. **Audit:** Full sync_log table tracking every operation

---

## Project Context

- **Tech Stack:** Python 3.11, FastAPI, PostgreSQL, SQLAlchemy, HTMX, TailwindCSS
- **Location:** `Synology via SSH` (Synology NAS via MCP) or `C:\BlackBook` (local dev)
- **Existing Contacts Service:** `app/services/contacts_service.py` (one-way import only)
- **Google Auth:** `app/services/google_auth.py` (OAuth with `contacts` scope already configured)
- **Settings Router:** `app/routers/settings.py` (9 tabs currently)

---

## Implementation Order

Complete these phases in order. Test each phase before moving to the next.

---

## Phase 7A: Database & Models

### Task 7A.1: Create Alembic Migration

Create migration file: `alembic/versions/[timestamp]_add_bidirectional_sync_tables.py`

```python
"""Add bidirectional sync tables

Revision ID: a7b8c9d0e1f2
Revises: [previous_revision]
Create Date: 2025-12-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = 'a7b8c9d0e1f2'
down_revision = '[GET_CURRENT_HEAD]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sync_log table
    op.create_table(
        'sync_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', UUID(as_uuid=True), sa.ForeignKey('persons.id', ondelete='SET NULL'), nullable=True),
        sa.Column('google_account_id', UUID(as_uuid=True), sa.ForeignKey('google_accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('direction', sa.String(25), nullable=False),  # 'google_to_blackbook', 'blackbook_to_google'
        sa.Column('action', sa.String(20), nullable=False),  # 'create', 'update', 'delete', 'archive', 'restore'
        sa.Column('status', sa.String(20), nullable=False),  # 'success', 'failed', 'pending_review'
        sa.Column('fields_changed', JSONB, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_sync_log_person', 'sync_log', ['person_id'])
    op.create_index('idx_sync_log_created', 'sync_log', ['created_at'])
    op.create_index('idx_sync_log_status', 'sync_log', ['status'])

    # archived_persons table
    op.create_table(
        'archived_persons',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('original_person_id', UUID(as_uuid=True), nullable=False),
        sa.Column('person_data', JSONB, nullable=False),
        sa.Column('deleted_from', sa.String(20), nullable=False),  # 'google', 'blackbook'
        sa.Column('deleted_by_account_id', UUID(as_uuid=True), nullable=True),
        sa.Column('google_contact_ids', JSONB, nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('restored_person_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_index('idx_archived_persons_original', 'archived_persons', ['original_person_id'])
    op.create_index('idx_archived_persons_archived', 'archived_persons', ['archived_at'])

    # sync_review_queue table
    op.create_table(
        'sync_review_queue',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', UUID(as_uuid=True), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=True),
        sa.Column('review_type', sa.String(30), nullable=False),  # 'name_conflict', 'data_conflict'
        sa.Column('google_account_id', UUID(as_uuid=True), sa.ForeignKey('google_accounts.id'), nullable=True),
        sa.Column('google_data', JSONB, nullable=False),
        sa.Column('blackbook_data', JSONB, nullable=False),
        sa.Column('status', sa.String(20), server_default='pending'),  # 'pending', 'resolved', 'dismissed'
        sa.Column('resolution', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_sync_review_status', 'sync_review_queue', ['status'])

    # sync_settings table (singleton)
    op.create_table(
        'sync_settings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('auto_sync_enabled', sa.Boolean, server_default='true'),
        sa.Column('sync_time_1', sa.Time, server_default=sa.text("'07:00'")),
        sa.Column('sync_time_2', sa.Time, server_default=sa.text("'21:00'")),
        sa.Column('sync_timezone', sa.String(50), server_default="'America/New_York'"),
        sa.Column('archive_retention_days', sa.Integer, server_default='90'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    # Insert default row
    op.execute("INSERT INTO sync_settings (id) VALUES (gen_random_uuid())")

    # Add columns to persons table
    op.add_column('persons', sa.Column('sync_enabled', sa.Boolean, server_default='true'))
    op.add_column('persons', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('persons', sa.Column('sync_status', sa.String(20), server_default="'pending'"))
    op.add_column('persons', sa.Column('google_contact_ids', JSONB, server_default="'{}'"))

    # Add columns to google_accounts table
    op.add_column('google_accounts', sa.Column('sync_enabled', sa.Boolean, server_default='true'))
    op.add_column('google_accounts', sa.Column('last_full_sync_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('google_accounts', sa.Column('next_sync_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove columns from google_accounts
    op.drop_column('google_accounts', 'next_sync_at')
    op.drop_column('google_accounts', 'last_full_sync_at')
    op.drop_column('google_accounts', 'sync_enabled')
    
    # Remove columns from persons
    op.drop_column('persons', 'google_contact_ids')
    op.drop_column('persons', 'sync_status')
    op.drop_column('persons', 'last_synced_at')
    op.drop_column('persons', 'sync_enabled')
    
    # Drop tables
    op.drop_table('sync_settings')
    op.drop_table('sync_review_queue')
    op.drop_table('archived_persons')
    op.drop_table('sync_log')
```

### Task 7A.2-7A.7: Create SQLAlchemy Models

Create file: `app/models/sync_log.py`

```python
"""Sync log model for tracking bidirectional sync operations."""
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SyncLog(Base):
    """Log entry for a sync operation."""
    
    __tablename__ = "sync_log"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    person_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"))
    google_account_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("google_accounts.id", ondelete="SET NULL"))
    direction: Mapped[str] = mapped_column(String(25))  # 'google_to_blackbook', 'blackbook_to_google'
    action: Mapped[str] = mapped_column(String(20))  # 'create', 'update', 'delete', 'archive', 'restore'
    status: Mapped[str] = mapped_column(String(20))  # 'success', 'failed', 'pending_review'
    fields_changed: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="NOW()")

    # Relationships
    person = relationship("Person", back_populates="sync_logs")
    google_account = relationship("GoogleAccount")
```

Create similar models for:
- `app/models/archived_person.py` - ArchivedPerson model
- `app/models/sync_review.py` - SyncReviewQueue model  
- `app/models/sync_settings.py` - SyncSettings model (singleton pattern)

Update `app/models/__init__.py` to export new models.

Update `app/models/person.py` to add:
- `sync_enabled`, `last_synced_at`, `sync_status`, `google_contact_ids` columns
- `sync_logs` relationship

Update `app/models/google_account.py` to add:
- `sync_enabled`, `last_full_sync_at`, `next_sync_at` columns

### Task 7A.8: Write Model Tests

Create `tests/test_sync_models.py` with tests for all new models.

---

## Phase 7B: Sync Service Core

### Task 7B.1: Create BidirectionalSyncService

Create file: `app/services/sync_service.py`

```python
"""
Bidirectional sync service for Google Contacts.

Handles two-way synchronization between BlackBook and all connected Google accounts.
BlackBook is the master database.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.models import GoogleAccount, Person, PersonEmail, SyncLog, ArchivedPerson, SyncReviewQueue, SyncSettings
from app.services.duplicate_service import NICKNAMES


@dataclass
class SyncResult:
    """Result of a sync operation."""
    persons_created: int = 0
    persons_updated: int = 0
    persons_deleted: int = 0
    persons_archived: int = 0
    conflicts_flagged: int = 0
    errors: list[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class BidirectionalSyncService:
    """
    Service for bidirectional sync between BlackBook and Google Contacts.
    
    BlackBook is the master database. All contacts sync to ALL connected accounts.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._nickname_map: dict[str, set[str]] | None = None
    
    def run_full_sync(self) -> dict[str, SyncResult]:
        """
        Run full bidirectional sync for all accounts.
        
        1. Sync Google → BlackBook (import new/updated contacts)
        2. Sync BlackBook → Google (push changes to all accounts)
        
        Returns:
            Dict mapping account email to SyncResult
        """
        results = {}
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True, sync_enabled=True).all()
        
        # Phase 1: Google → BlackBook
        for account in accounts:
            try:
                result = self._sync_google_to_blackbook(account)
                results[f"{account.email}_import"] = result
            except Exception as e:
                results[f"{account.email}_import"] = SyncResult(errors=[str(e)])
        
        # Phase 2: BlackBook → Google (all accounts)
        try:
            result = self._sync_blackbook_to_google(accounts)
            results["blackbook_export"] = result
        except Exception as e:
            results["blackbook_export"] = SyncResult(errors=[str(e)])
        
        return results
    
    def sync_single_person(self, person_id: UUID) -> SyncResult:
        """Push a single person to all Google accounts."""
        person = self.db.query(Person).filter_by(id=person_id).first()
        if not person:
            return SyncResult(errors=["Person not found"])
        
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True, sync_enabled=True).all()
        return self._push_person_to_google(person, accounts)
    
    def _sync_google_to_blackbook(self, account: GoogleAccount) -> SyncResult:
        """Import contacts from Google to BlackBook."""
        # TODO: Implement - fetch from Google, match/create/update in BlackBook
        # Use existing contacts_service.py as reference
        pass
    
    def _sync_blackbook_to_google(self, accounts: list[GoogleAccount]) -> SyncResult:
        """Push BlackBook contacts to all Google accounts."""
        # TODO: Implement - iterate persons, push to each account
        pass
    
    def _push_person_to_google(self, person: Person, accounts: list[GoogleAccount]) -> SyncResult:
        """Push a single person to all Google accounts."""
        # TODO: Implement
        pass
    
    def _create_google_contact(self, person: Person, account: GoogleAccount) -> str | None:
        """Create a new contact in Google. Returns resource_name or None."""
        # TODO: Implement using People API people().createContact()
        pass
    
    def _update_google_contact(self, person: Person, account: GoogleAccount, resource_name: str) -> bool:
        """Update existing contact in Google. Returns success."""
        # TODO: Implement using People API people().updateContact()
        pass
    
    def _delete_google_contact(self, account: GoogleAccount, resource_name: str) -> bool:
        """Delete contact from Google. Returns success."""
        # TODO: Implement using People API people().deleteContact()
        pass
    
    def _detect_conflicts(self, person: Person, google_data: dict) -> list[dict]:
        """Detect conflicts between BlackBook and Google data."""
        # TODO: Implement conflict detection
        pass
    
    def _is_nickname_match(self, name1: str, name2: str) -> bool:
        """Check if two names are nickname variants."""
        if self._nickname_map is None:
            self._build_nickname_map()
        
        name1_lower = name1.lower().strip()
        name2_lower = name2.lower().strip()
        
        if name1_lower == name2_lower:
            return True
        
        # Check if they share a nickname group
        name1_groups = self._nickname_map.get(name1_lower, set())
        name2_groups = self._nickname_map.get(name2_lower, set())
        
        return bool(name1_groups & name2_groups)
    
    def _build_nickname_map(self):
        """Build reverse lookup for nicknames."""
        self._nickname_map = {}
        for canonical, nicknames in NICKNAMES.items():
            all_names = {canonical} | set(nicknames)
            for name in all_names:
                if name not in self._nickname_map:
                    self._nickname_map[name] = set()
                self._nickname_map[name].update(all_names)
    
    def _merge_notes(self, blackbook_note: str | None, google_note: str | None, account_email: str) -> str:
        """Merge notes from both sources."""
        if not google_note:
            return blackbook_note or ""
        if not blackbook_note:
            return f"[Imported from Google - {account_email}] {google_note}"
        
        # Check if Google note already merged
        if f"[Imported from Google" in blackbook_note and google_note in blackbook_note:
            return blackbook_note
        
        return f"{blackbook_note}\n---\n[Imported from Google - {account_email}] {google_note}"
    
    def _truncate_note_for_google(self, note: str) -> str:
        """Truncate note to Google's 2048 char limit."""
        if not note or len(note) <= 2048:
            return note or ""
        
        suffix = "\n... [See BlackBook for full note]"
        max_content = 2048 - len(suffix)
        return note[:max_content] + suffix
    
    def _log_sync(
        self,
        person_id: UUID | None,
        account_id: UUID | None,
        direction: str,
        action: str,
        status: str,
        fields_changed: dict | None = None,
        error_message: str | None = None,
    ) -> SyncLog:
        """Create a sync log entry."""
        log = SyncLog(
            person_id=person_id,
            google_account_id=account_id,
            direction=direction,
            action=action,
            status=status,
            fields_changed=fields_changed,
            error_message=error_message,
        )
        self.db.add(log)
        return log
    
    def _archive_person(self, person: Person, deleted_from: str, account_id: UUID | None = None) -> ArchivedPerson:
        """Archive a person before deletion."""
        # Build full snapshot
        person_data = {
            "full_name": person.full_name,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "title": person.title,
            "phone": person.phone,
            "birthday": person.birthday.isoformat() if person.birthday else None,
            "notes": person.notes,
            "location": person.location,
            "emails": [{"email": e.email, "label": e.label.value, "is_primary": e.is_primary} for e in person.emails],
            # Add other fields as needed
        }
        
        archive = ArchivedPerson(
            original_person_id=person.id,
            person_data=person_data,
            deleted_from=deleted_from,
            deleted_by_account_id=account_id,
            google_contact_ids=person.google_contact_ids,
            expires_at=datetime.now(timezone.utc) + timedelta(days=self._get_retention_days()),
        )
        self.db.add(archive)
        return archive
    
    def _get_retention_days(self) -> int:
        """Get archive retention days from settings."""
        settings = self.db.query(SyncSettings).first()
        return settings.archive_retention_days if settings else 90


def get_sync_service(db: Session) -> BidirectionalSyncService:
    """Get a sync service instance."""
    return BidirectionalSyncService(db)
```

### Tasks 7B.2-7B.12: Implement Service Methods

Implement each method marked with `# TODO`. Reference:
- `app/services/contacts_service.py` for Google API patterns
- `app/services/duplicate_service.py` for NICKNAMES dict
- Google People API docs: https://developers.google.com/people/api/rest/v1/people

Key Google API calls needed:
```python
# Create contact
service.people().createContact(body={...}).execute()

# Update contact  
service.people().updateContact(
    resourceName="people/c123...",
    updatePersonFields="names,emailAddresses,phoneNumbers,biographies",
    body={...}
).execute()

# Delete contact
service.people().deleteContact(resourceName="people/c123...").execute()
```

---

## Phase 7C: Scheduler

### Task 7C.1: Add APScheduler

Add to `requirements.txt`:
```
APScheduler>=3.10.0
pytz>=2023.3
```

### Tasks 7C.2-7C.5: Implement Scheduler

Create file: `app/services/scheduler.py`

```python
"""Background scheduler for sync jobs."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
import pytz

from app.database import SessionLocal
from app.models import SyncSettings
from app.services.sync_service import get_sync_service


scheduler = AsyncIOScheduler()


def run_scheduled_sync():
    """Execute scheduled sync job."""
    db = SessionLocal()
    try:
        service = get_sync_service(db)
        results = service.run_full_sync()
        # Log results
        print(f"Scheduled sync completed: {results}")
    finally:
        db.close()


def init_scheduler(db: Session):
    """Initialize scheduler with current settings."""
    settings = db.query(SyncSettings).first()
    if not settings or not settings.auto_sync_enabled:
        return
    
    tz = pytz.timezone(settings.sync_timezone)
    
    # Morning sync
    scheduler.add_job(
        run_scheduled_sync,
        CronTrigger(
            hour=settings.sync_time_1.hour,
            minute=settings.sync_time_1.minute,
            timezone=tz
        ),
        id='sync_morning',
        replace_existing=True
    )
    
    # Evening sync
    scheduler.add_job(
        run_scheduled_sync,
        CronTrigger(
            hour=settings.sync_time_2.hour,
            minute=settings.sync_time_2.minute,
            timezone=tz
        ),
        id='sync_evening',
        replace_existing=True
    )
    
    scheduler.start()


def update_schedule(db: Session):
    """Update scheduler when settings change."""
    # Remove existing jobs
    if scheduler.get_job('sync_morning'):
        scheduler.remove_job('sync_morning')
    if scheduler.get_job('sync_evening'):
        scheduler.remove_job('sync_evening')
    
    # Re-initialize
    init_scheduler(db)
```

Update `app/main.py` to initialize scheduler on startup:
```python
from app.services.scheduler import init_scheduler

@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    try:
        init_scheduler(db)
    finally:
        db.close()
```

---

## Phase 7D: API Endpoints

### Task 7D.1: Create Sync Router

Create file: `app/routers/sync.py`

```python
"""Sync management endpoints."""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SyncLog, ArchivedPerson, SyncReviewQueue, SyncSettings, Person
from app.services.sync_service import get_sync_service
from app.services.scheduler import update_schedule

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/now")
async def trigger_sync(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Trigger immediate full sync."""
    service = get_sync_service(db)
    results = service.run_full_sync()
    db.commit()
    return {"status": "completed", "results": results}


@router.post("/person/{person_id}")
async def sync_single_person(person_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Sync a single person to Google."""
    service = get_sync_service(db)
    result = service.sync_single_person(person_id)
    db.commit()
    return {"status": "completed", "result": result}


@router.get("/status")
async def get_sync_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get current sync status."""
    settings = db.query(SyncSettings).first()
    last_log = db.query(SyncLog).order_by(SyncLog.created_at.desc()).first()
    pending_reviews = db.query(SyncReviewQueue).filter_by(status="pending").count()
    
    return {
        "auto_sync_enabled": settings.auto_sync_enabled if settings else False,
        "last_sync": last_log.created_at.isoformat() if last_log else None,
        "last_sync_status": last_log.status if last_log else None,
        "pending_reviews": pending_reviews,
        "next_sync_time_1": f"{settings.sync_time_1} {settings.sync_timezone}" if settings else None,
        "next_sync_time_2": f"{settings.sync_time_2} {settings.sync_timezone}" if settings else None,
    }


@router.get("/log")
async def get_sync_log(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str | None = None,
    person_id: UUID | None = None,
) -> dict[str, Any]:
    """Get sync log with pagination."""
    query = db.query(SyncLog).order_by(SyncLog.created_at.desc())
    
    if status:
        query = query.filter(SyncLog.status == status)
    if person_id:
        query = query.filter(SyncLog.person_id == person_id)
    
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "logs": [
            {
                "id": str(log.id),
                "person_id": str(log.person_id) if log.person_id else None,
                "person_name": log.person.full_name if log.person else None,
                "direction": log.direction,
                "action": log.action,
                "status": log.status,
                "fields_changed": log.fields_changed,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


# Review queue endpoints
@router.get("/review")
async def get_review_queue(db: Session = Depends(get_db)) -> list[dict]:
    """Get pending review items."""
    items = db.query(SyncReviewQueue).filter_by(status="pending").order_by(SyncReviewQueue.created_at.desc()).all()
    return [
        {
            "id": str(item.id),
            "person_id": str(item.person_id) if item.person_id else None,
            "review_type": item.review_type,
            "google_data": item.google_data,
            "blackbook_data": item.blackbook_data,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


@router.post("/review/{review_id}/resolve")
async def resolve_review(
    review_id: UUID,
    resolution: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Resolve a review item."""
    item = db.query(SyncReviewQueue).filter_by(id=review_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    
    item.status = "resolved"
    item.resolution = resolution
    item.resolved_at = datetime.now()
    
    # Apply resolution to person
    # TODO: Implement based on resolution type
    
    db.commit()
    return {"status": "resolved"}


@router.post("/review/{review_id}/dismiss")
async def dismiss_review(review_id: UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    """Dismiss a review item without action."""
    item = db.query(SyncReviewQueue).filter_by(id=review_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    
    item.status = "dismissed"
    item.resolved_at = datetime.now()
    db.commit()
    return {"status": "dismissed"}


# Archive endpoints
@router.get("/archive")
async def get_archived_persons(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """Get archived persons."""
    query = db.query(ArchivedPerson).filter(ArchivedPerson.restored_at.is_(None)).order_by(ArchivedPerson.archived_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "archived": [
            {
                "id": str(item.id),
                "original_person_id": str(item.original_person_id),
                "person_data": item.person_data,
                "deleted_from": item.deleted_from,
                "archived_at": item.archived_at.isoformat(),
                "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/archive/{archive_id}/restore")
async def restore_archived_person(archive_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Restore an archived person."""
    archive = db.query(ArchivedPerson).filter_by(id=archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="Archived person not found")
    if archive.restored_at:
        raise HTTPException(status_code=400, detail="Person already restored")
    
    # TODO: Implement restore logic - create new Person from person_data
    # Then push to all Google accounts
    
    return {"status": "restored", "new_person_id": str(new_person.id)}


# Settings endpoints
@router.get("/settings")
async def get_sync_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get sync settings."""
    settings = db.query(SyncSettings).first()
    if not settings:
        return {"error": "Settings not found"}
    
    return {
        "auto_sync_enabled": settings.auto_sync_enabled,
        "sync_time_1": settings.sync_time_1.strftime("%H:%M"),
        "sync_time_2": settings.sync_time_2.strftime("%H:%M"),
        "sync_timezone": settings.sync_timezone,
        "archive_retention_days": settings.archive_retention_days,
    }


@router.put("/settings")
async def update_sync_settings(
    auto_sync_enabled: bool | None = None,
    sync_time_1: str | None = None,  # "HH:MM" format
    sync_time_2: str | None = None,
    sync_timezone: str | None = None,
    archive_retention_days: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Update sync settings."""
    settings = db.query(SyncSettings).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    
    if auto_sync_enabled is not None:
        settings.auto_sync_enabled = auto_sync_enabled
    if sync_time_1:
        settings.sync_time_1 = datetime.strptime(sync_time_1, "%H:%M").time()
    if sync_time_2:
        settings.sync_time_2 = datetime.strptime(sync_time_2, "%H:%M").time()
    if sync_timezone:
        settings.sync_timezone = sync_timezone
    if archive_retention_days is not None:
        settings.archive_retention_days = archive_retention_days
    
    settings.updated_at = datetime.now()
    db.commit()
    
    # Update scheduler
    update_schedule(db)
    
    return {"status": "updated"}
```

Register router in `app/main.py`:
```python
from app.routers import sync
app.include_router(sync.router)
```

---

## Phase 7E: UI Components

### Task 7E.1: Sync Status Badge on Person Cards

Update `app/templates/persons/_card.html` or list template to include:

```html
<span class="sync-badge">
    {% if person.sync_status == 'synced' %}
        <span class="text-green-500" title="Synced">✅</span>
    {% elif person.sync_status == 'pending' %}
        <span class="text-yellow-500" title="Pending sync">⏳</span>
    {% elif person.sync_status == 'error' %}
        <span class="text-red-500" title="Sync error">⚠️</span>
    {% endif %}
</span>
```

### Task 7E.2: Sync Info on Person Detail Page

Add to person detail template:

```html
<div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 mt-4">
    <h3 class="font-semibold mb-2">Sync Status</h3>
    <div class="text-sm space-y-1">
        <p>Status: 
            {% if person.sync_status == 'synced' %}
                <span class="text-green-600">✅ Synced</span>
            {% elif person.sync_status == 'pending' %}
                <span class="text-yellow-600">⏳ Pending</span>
            {% else %}
                <span class="text-red-600">⚠️ Error</span>
            {% endif %}
        </p>
        {% if person.last_synced_at %}
        <p>Last synced: {{ person.last_synced_at | timeago }}</p>
        {% endif %}
        <p class="text-gray-500">Syncs to {{ google_accounts|length }} account(s)</p>
    </div>
    <button 
        hx-post="/api/sync/person/{{ person.id }}"
        hx-swap="none"
        class="mt-3 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
    >
        🔄 Push to Google
    </button>
</div>
```

### Task 7E.4: Create Sync Settings Tab

Add 10th tab to Settings page. Create `app/templates/settings/sync.html`:

```html
<div class="space-y-6">
    <h2 class="text-xl font-semibold">Sync Settings</h2>
    
    <!-- Auto-sync toggle -->
    <div class="bg-white dark:bg-gray-800 rounded-lg p-4">
        <label class="flex items-center gap-3">
            <input type="checkbox" 
                   id="auto-sync-enabled"
                   {% if settings.auto_sync_enabled %}checked{% endif %}
                   hx-put="/api/sync/settings"
                   hx-vals='{"auto_sync_enabled": this.checked}'
                   class="w-5 h-5">
            <span class="font-medium">Enable automatic sync</span>
        </label>
    </div>
    
    <!-- Schedule -->
    <div class="bg-white dark:bg-gray-800 rounded-lg p-4">
        <h3 class="font-medium mb-3">Sync Schedule</h3>
        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm mb-1">Morning sync</label>
                <input type="time" value="{{ settings.sync_time_1 }}" 
                       id="sync-time-1"
                       class="border rounded px-3 py-2 w-full">
            </div>
            <div>
                <label class="block text-sm mb-1">Evening sync</label>
                <input type="time" value="{{ settings.sync_time_2 }}"
                       id="sync-time-2" 
                       class="border rounded px-3 py-2 w-full">
            </div>
        </div>
        <div class="mt-3">
            <label class="block text-sm mb-1">Timezone</label>
            <select id="sync-timezone" class="border rounded px-3 py-2 w-full">
                <option value="America/New_York" {% if settings.sync_timezone == 'America/New_York' %}selected{% endif %}>
                    America/New_York (ET)
                </option>
                <option value="America/Chicago" {% if settings.sync_timezone == 'America/Chicago' %}selected{% endif %}>
                    America/Chicago (CT)
                </option>
                <option value="America/Los_Angeles" {% if settings.sync_timezone == 'America/Los_Angeles' %}selected{% endif %}>
                    America/Los_Angeles (PT)
                </option>
                <option value="UTC" {% if settings.sync_timezone == 'UTC' %}selected{% endif %}>
                    UTC
                </option>
            </select>
        </div>
        <button onclick="saveSchedule()" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded">
            Save Schedule
        </button>
    </div>
    
    <!-- Manual sync -->
    <div class="bg-white dark:bg-gray-800 rounded-lg p-4">
        <h3 class="font-medium mb-3">Manual Sync</h3>
        <p class="text-sm text-gray-600 mb-2">
            Last sync: {{ last_sync_time or 'Never' }}
        </p>
        <button hx-post="/api/sync/now" 
                hx-indicator="#sync-spinner"
                class="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
            🔄 Sync Now
        </button>
        <span id="sync-spinner" class="htmx-indicator ml-2">Syncing...</span>
    </div>
    
    <!-- Archive retention -->
    <div class="bg-white dark:bg-gray-800 rounded-lg p-4">
        <h3 class="font-medium mb-3">Archive Settings</h3>
        <label class="block text-sm mb-1">Retain archived contacts for</label>
        <div class="flex items-center gap-2">
            <input type="number" value="{{ settings.archive_retention_days }}" 
                   id="retention-days"
                   class="border rounded px-3 py-2 w-24">
            <span>days</span>
        </div>
    </div>
    
    <!-- Links -->
    <div class="flex gap-4">
        <a href="/settings/sync/log" class="text-blue-600 hover:underline">View Sync Log →</a>
        <a href="/settings/sync/review" class="text-blue-600 hover:underline">
            Review Queue {% if pending_reviews > 0 %}({{ pending_reviews }}){% endif %} →
        </a>
        <a href="/settings/sync/archive" class="text-blue-600 hover:underline">Archive Browser →</a>
    </div>
</div>
```

### Tasks 7E.5-7E.7: Create Sub-Pages

Create templates for:
- `app/templates/settings/sync_log.html` - Paginated log table
- `app/templates/settings/sync_review.html` - Review queue with resolve buttons
- `app/templates/settings/sync_archive.html` - Archive browser with restore

### Task 7E.8: Add Sync Checkbox to Person Forms

Update person create/edit forms to include:

```html
<div class="mt-4">
    <label class="flex items-center gap-2">
        <input type="checkbox" name="sync_enabled" value="true" checked>
        <span>Sync to Google Contacts</span>
    </label>
    <p class="text-xs text-gray-500 ml-6">Will sync to all connected accounts</p>
</div>
```

---

## Phase 7F: Testing & Documentation

### Task 7F.1: Integration Tests

Create `tests/test_bidirectional_sync.py`:
- Test full sync cycle
- Test conflict detection
- Test archive and restore
- Test scheduler configuration

### Task 7F.4-7F.5: Update Documentation

Update:
- `docs/GOOGLE_SETUP.md` - Add sync configuration section
- `Claude_Code_Context.md` - Update phase status and add Phase 7 details

---

## Verification Checklist

After implementation, verify:

- [ ] New contact in BlackBook appears in all Google accounts after sync
- [ ] New contact in Google appears in BlackBook after sync
- [ ] Edited fields sync both directions
- [ ] Deleted contact archived and removed from both systems
- [ ] Name conflicts flagged for manual review (but nicknames recognized)
- [ ] Notes merged with source labels
- [ ] Phones/emails deduplicated but both kept
- [ ] Scheduled sync runs at configured times
- [ ] Manual "Sync Now" works
- [ ] Archive browser shows deleted contacts
- [ ] Archived contacts can be restored
- [ ] Sync log shows all operations
- [ ] Review queue allows resolving conflicts
- [ ] Settings tab allows configuration changes

---

## Important Notes

1. **Test locally first** - Use Windows dev environment before deploying to Synology
2. **Backup database** before running first sync on production data
3. **Google API rate limits** - Be careful with batch operations
4. **Run migration** with `alembic upgrade head` before starting app

---

## Reference Files

| File | Purpose |
|------|---------|
| `app/services/contacts_service.py` | Existing one-way import (reference) |
| `app/services/google_auth.py` | OAuth handling |
| `app/services/duplicate_service.py` | NICKNAMES dict |
| `app/routers/settings.py` | Existing settings (add sync tab) |
| `docs/GOOGLE_CONTACTS_BIDIRECTIONAL_SYNC_2025.12.18.1.md` | Full specification |

---

*End of Claude Code Prompt*
