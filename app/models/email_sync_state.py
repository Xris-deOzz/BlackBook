"""
EmailSyncState model for tracking Gmail sync progress per account.

Each connected Google account has its own sync state, allowing for:
- Incremental sync using Gmail history API
- Tracking last sync time and status
- Error reporting and recovery
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Text,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.google_account import GoogleAccount


class SyncStatus(str, Enum):
    """Current state of the sync process."""

    IDLE = "idle"  # Not currently syncing
    SYNCING = "syncing"  # Sync in progress
    ERROR = "error"  # Last sync failed
    NEVER_SYNCED = "never_synced"  # Initial state, needs full sync


class EmailSyncState(Base):
    """
    Tracks email sync state for each connected Google account.

    Gmail supports incremental sync using history IDs. After an initial
    full sync, we only need to fetch changes since the last history ID,
    making subsequent syncs much faster.

    This model stores:
    - Last history ID for incremental sync
    - Sync timestamps and status
    - Error information for debugging
    - Statistics (messages synced, etc.)
    """

    __tablename__ = "email_sync_state"
    __table_args__ = (
        UniqueConstraint("google_account_id", name="uq_email_sync_state_account"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    google_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("google_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Gmail history tracking
    last_history_id: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="Gmail history ID for incremental sync",
    )

    # Sync timestamps
    last_full_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="When the last full sync completed",
    )
    last_incremental_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="When the last incremental sync completed",
    )

    # Current status
    sync_status: Mapped[str] = mapped_column(
        String(50),
        default=SyncStatus.NEVER_SYNCED.value,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        comment="Error details if last sync failed",
    )

    # Statistics
    messages_synced: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Total messages synced from this account",
    )
    last_sync_message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Messages synced in last sync operation",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    google_account: Mapped["GoogleAccount"] = orm_relationship(
        "GoogleAccount",
        back_populates="email_sync_state",
    )

    def __repr__(self) -> str:
        return f"<EmailSyncState(account={self.google_account_id}, status={self.sync_status})>"

    @property
    def needs_full_sync(self) -> bool:
        """Check if this account needs a full sync (never synced or no history ID)."""
        return (
            self.sync_status == SyncStatus.NEVER_SYNCED.value
            or self.last_history_id is None
        )

    @property
    def is_syncing(self) -> bool:
        """Check if sync is currently in progress."""
        return self.sync_status == SyncStatus.SYNCING.value

    @property
    def has_error(self) -> bool:
        """Check if last sync failed."""
        return self.sync_status == SyncStatus.ERROR.value

    @property
    def last_sync_at(self) -> datetime | None:
        """Get the most recent sync time (full or incremental)."""
        if self.last_incremental_sync_at and self.last_full_sync_at:
            return max(self.last_incremental_sync_at, self.last_full_sync_at)
        return self.last_incremental_sync_at or self.last_full_sync_at

    def start_sync(self) -> None:
        """Mark sync as started."""
        self.sync_status = SyncStatus.SYNCING.value
        self.error_message = None

    def complete_sync(
        self,
        history_id: int | None = None,
        messages_synced: int = 0,
        is_full_sync: bool = False,
    ) -> None:
        """Mark sync as completed successfully."""
        self.sync_status = SyncStatus.IDLE.value
        self.error_message = None
        self.last_sync_message_count = messages_synced
        self.messages_synced += messages_synced

        if history_id:
            self.last_history_id = history_id

        now = datetime.now(timezone.utc)
        if is_full_sync:
            self.last_full_sync_at = now
        else:
            self.last_incremental_sync_at = now

    def fail_sync(self, error: str) -> None:
        """Mark sync as failed with error message."""
        self.sync_status = SyncStatus.ERROR.value
        self.error_message = error
