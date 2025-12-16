"""
PendingContact model for unknown meeting attendees queue.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.calendar_event import CalendarEvent
    from app.models.person import Person


class PendingContactStatus(str, enum.Enum):
    """Status of a pending contact."""
    pending = "pending"
    created = "created"
    ignored = "ignored"


class PendingContact(Base):
    """
    Queue for unknown meeting attendees discovered from calendar events.

    When calendar events are synced, attendees who don't match any existing
    person are added here for review. Users can then:
    - Create a new person from the pending contact
    - Link to an existing person
    - Ignore the contact
    """

    __tablename__ = "pending_contacts"
    __table_args__ = (
        UniqueConstraint("email", name="uq_pending_contacts_email"),
        Index("idx_pending_contacts_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email address of the unknown attendee",
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        comment="Name from calendar event (if available)",
    )
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendar_events.id", ondelete="SET NULL"),
        comment="Calendar event where this contact was first seen",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        comment="When this contact was first discovered",
    )
    occurrence_count: Mapped[int] = mapped_column(
        default=1,
        comment="Number of events this contact appears in",
    )
    status: Mapped[PendingContactStatus] = mapped_column(
        Enum(PendingContactStatus),
        default=PendingContactStatus.pending,
        comment="Processing status: pending, created, ignored",
    )
    created_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        comment="Person record created from this pending contact",
    )
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
    source_event: Mapped["CalendarEvent | None"] = orm_relationship(
        "CalendarEvent",
        foreign_keys=[source_event_id],
    )
    created_person: Mapped["Person | None"] = orm_relationship(
        "Person",
        foreign_keys=[created_person_id],
    )

    def __repr__(self) -> str:
        return f"<PendingContact(email={self.email!r}, status={self.status.value})>"

    @property
    def is_pending(self) -> bool:
        """Check if this contact is still pending review."""
        return self.status == PendingContactStatus.pending

    @property
    def is_created(self) -> bool:
        """Check if a person was created from this contact."""
        return self.status == PendingContactStatus.created

    @property
    def is_ignored(self) -> bool:
        """Check if this contact was ignored."""
        return self.status == PendingContactStatus.ignored

    def mark_created(self, person_id: uuid.UUID) -> None:
        """
        Mark this contact as created and link to the person.

        Args:
            person_id: UUID of the created Person record
        """
        self.status = PendingContactStatus.created
        self.created_person_id = person_id

    def mark_ignored(self) -> None:
        """Mark this contact as ignored."""
        self.status = PendingContactStatus.ignored

    def increment_occurrence(self) -> None:
        """Increment the occurrence count when seen in another event."""
        self.occurrence_count += 1
