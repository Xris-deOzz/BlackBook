"""
EmailCache model for temporary storage of fetched Gmail threads.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.google_account import GoogleAccount


# Default cache TTL in hours
DEFAULT_CACHE_TTL_HOURS = 1


class EmailCache(Base):
    """
    Cached email thread data from Gmail API.

    Stores fetched email threads temporarily to reduce API calls.
    Cache entries expire after a configurable TTL (default 1 hour).
    """

    __tablename__ = "email_cache"
    __table_args__ = (
        UniqueConstraint("person_id", "gmail_thread_id", name="uq_email_cache_person_thread"),
        Index("idx_email_cache_person_id", "person_id"),
        Index("idx_email_cache_cached_at", "cached_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    google_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("google_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    gmail_thread_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(
        String(500),
    )
    snippet: Mapped[str | None] = mapped_column(
        Text,
    )
    participants: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        comment="Email addresses involved in the thread",
    )
    last_message_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    message_count: Mapped[int | None] = mapped_column(
        Integer,
    )
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    person: Mapped["Person"] = orm_relationship(
        "Person",
    )
    google_account: Mapped["GoogleAccount"] = orm_relationship(
        "GoogleAccount",
    )

    def __repr__(self) -> str:
        return f"<EmailCache(thread={self.gmail_thread_id!r}, subject={self.subject!r})>"

    def is_expired(self, ttl_hours: int = DEFAULT_CACHE_TTL_HOURS) -> bool:
        """
        Check if this cache entry has expired.

        Args:
            ttl_hours: Time-to-live in hours (default: 1 hour)

        Returns:
            True if the cache entry is older than the TTL
        """
        if self.cached_at is None:
            return True

        # Ensure cached_at is timezone-aware
        cached_at = self.cached_at
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)

        expiry_time = cached_at + timedelta(hours=ttl_hours)
        return datetime.now(timezone.utc) > expiry_time

    def is_fresh(self, ttl_hours: int = DEFAULT_CACHE_TTL_HOURS) -> bool:
        """
        Check if this cache entry is still fresh (not expired).

        Args:
            ttl_hours: Time-to-live in hours (default: 1 hour)

        Returns:
            True if the cache entry is still valid
        """
        return not self.is_expired(ttl_hours)

    @property
    def age_seconds(self) -> float:
        """
        Get the age of this cache entry in seconds.

        Returns:
            Number of seconds since the entry was cached
        """
        if self.cached_at is None:
            return float('inf')

        cached_at = self.cached_at
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)

        delta = datetime.now(timezone.utc) - cached_at
        return delta.total_seconds()

    @property
    def age_minutes(self) -> float:
        """Get the age of this cache entry in minutes."""
        return self.age_seconds / 60

    @property
    def gmail_web_url(self) -> str:
        """
        Generate a URL to view this thread in Gmail web interface.

        Returns:
            Gmail web URL for this thread
        """
        return f"https://mail.google.com/mail/u/0/#inbox/{self.gmail_thread_id}"
