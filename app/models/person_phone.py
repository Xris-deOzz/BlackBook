"""
PersonPhone model for storing multiple phone numbers per person.
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


class PhoneLabel(str, PyEnum):
    """Phone label/type enum."""

    mobile = "mobile"
    work = "work"
    home = "home"
    other = "other"


class PersonPhone(Base):
    """
    Phone number associated with a Person.

    A person can have multiple phone numbers (mobile, work, home, etc.).
    One phone can be marked as primary for display purposes.
    """

    __tablename__ = "person_phones"
    __table_args__ = (
        UniqueConstraint("person_id", "phone", name="uq_person_phones_person_phone"),
        Index("idx_person_phones_phone", "phone"),
        Index("idx_person_phones_person_id", "person_id"),
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
    phone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    label: Mapped[PhoneLabel | None] = mapped_column(
        Enum(PhoneLabel, name="phone_label", create_type=False),
        default=PhoneLabel.mobile,
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
        back_populates="phones",
    )

    def __repr__(self) -> str:
        return f"<PersonPhone(phone={self.phone!r}, label={self.label}, primary={self.is_primary})>"
