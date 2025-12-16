"""
EmailPersonLink model for linking emails to CRM contacts.

This junction table connects EmailMessage records to Person records,
enabling email history on person profiles and CRM-aware inbox views.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.email_message import EmailMessage
    from app.models.person import Person


class EmailLinkType(str, Enum):
    """How the person is connected to the email."""

    FROM = "from"  # Person sent the email
    TO = "to"  # Person is a recipient
    CC = "cc"  # Person is CC'd
    BCC = "bcc"  # Person is BCC'd (rarely known)
    MENTIONED = "mentioned"  # Person's name appears in email body


class EmailLinkSource(str, Enum):
    """How the link was created."""

    AUTO = "auto"  # Auto-linked by email address match
    MANUAL = "manual"  # Manually linked by user


class EmailPersonLink(Base):
    """
    Links an email message to a CRM Person record.

    Emails are automatically linked to contacts when email addresses match.
    Users can also manually link emails to contacts.

    This enables:
    - Showing email history on person profiles
    - Filtering inbox by CRM contact
    - "Add to CRM" workflow for unknown senders
    """

    __tablename__ = "email_person_links"
    __table_args__ = (
        UniqueConstraint(
            "email_message_id",
            "person_id",
            "link_type",
            name="uq_email_person_link_unique",
        ),
        Index("idx_email_person_links_email", "email_message_id"),
        Index("idx_email_person_links_person", "person_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    link_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="How person is connected: from, to, cc, mentioned",
    )
    linked_by: Mapped[str] = mapped_column(
        String(50),
        default=EmailLinkSource.AUTO.value,
        comment="How link was created: auto or manual",
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    email_message: Mapped["EmailMessage"] = orm_relationship(
        "EmailMessage",
        back_populates="person_links",
    )
    person: Mapped["Person"] = orm_relationship(
        "Person",
        back_populates="email_links",
    )

    def __repr__(self) -> str:
        return f"<EmailPersonLink(email={self.email_message_id}, person={self.person_id}, type={self.link_type})>"

    @property
    def is_sender(self) -> bool:
        """Check if this person sent the email."""
        return self.link_type == EmailLinkType.FROM.value

    @property
    def is_recipient(self) -> bool:
        """Check if this person received the email (to, cc, or bcc)."""
        return self.link_type in [
            EmailLinkType.TO.value,
            EmailLinkType.CC.value,
            EmailLinkType.BCC.value,
        ]
