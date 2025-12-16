"""
Interaction model for tracking communications with persons.
"""

import uuid
from datetime import datetime, date
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, Date, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person


class InteractionMedium(str, PyEnum):
    """Interaction medium enum (matches PostgreSQL interaction_medium)."""

    email = "email"
    meeting = "meeting"
    call = "call"
    linkedin = "linkedin"
    lunch = "lunch"
    coffee = "coffee"
    event = "event"
    video_call = "video_call"
    text = "text"
    other = "other"


class InteractionSource(str, PyEnum):
    """Source of interaction creation."""

    manual = "manual"
    email = "email"
    calendar = "calendar"


class Interaction(Base):
    """Interaction/communication record with a person."""

    __tablename__ = "interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    person_name: Mapped[str | None] = mapped_column(String(300))
    medium: Mapped[InteractionMedium] = mapped_column(
        Enum(InteractionMedium, name="interaction_medium", create_type=False),
        nullable=False,
        default=InteractionMedium.other,
    )
    interaction_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    files_sent: Mapped[str | None] = mapped_column(Text)
    airtable_name: Mapped[str | None] = mapped_column(String(500))

    # Gmail integration fields
    gmail_thread_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="Gmail thread ID for viewing in Gmail",
    )
    gmail_message_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="Gmail message ID for direct message link",
    )

    # Calendar integration fields
    calendar_event_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="Google Calendar event ID for linking to calendar",
    )

    source: Mapped[InteractionSource] = mapped_column(
        Enum(InteractionSource, name="interaction_source", create_type=False),
        nullable=False,
        default=InteractionSource.manual,
        comment="Source of interaction: manual entry, email import, or calendar sync",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    person: Mapped["Person | None"] = relationship(
        "Person",
        back_populates="interactions",
    )

    def __repr__(self) -> str:
        return f"<Interaction(person={self.person_name!r}, medium={self.medium.value})>"

    @property
    def gmail_link(self) -> str | None:
        """Generate Gmail web link for this interaction's thread.

        Returns:
            Gmail URL to view the thread, or None if no thread ID.
        """
        if self.gmail_thread_id:
            return f"https://mail.google.com/mail/u/0/#all/{self.gmail_thread_id}"
        return None

    @property
    def is_from_gmail(self) -> bool:
        """Check if this interaction was created from Gmail."""
        return self.source == InteractionSource.email
