"""
PersonEmail model for storing multiple email addresses per person.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person


class EmailLabel(str, PyEnum):
    """Email label/type enum."""

    work = "work"
    personal = "personal"
    other = "other"


class PersonEmail(Base):
    """
    Email address associated with a Person.

    A person can have multiple email addresses (work, personal, etc.).
    One email can be marked as primary for display purposes.
    """

    __tablename__ = "person_emails"
    __table_args__ = (
        UniqueConstraint("person_id", "email", name="uq_person_emails_person_email"),
        Index("idx_person_emails_email", "email"),
        Index("idx_person_emails_person_id", "person_id"),
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
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    label: Mapped[EmailLabel | None] = mapped_column(
        Enum(EmailLabel, name="email_label", create_type=False),
        default=EmailLabel.work,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    person: Mapped["Person"] = orm_relationship(
        "Person",
        back_populates="emails",
    )

    def __repr__(self) -> str:
        return f"<PersonEmail(email={self.email!r}, label={self.label}, primary={self.is_primary})>"
