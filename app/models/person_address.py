"""
PersonAddress model for storing multiple addresses per person.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person


class PersonAddress(Base):
    """
    Address associated with a Person.

    A person can have up to 2 addresses: home and work.
    """

    __tablename__ = "person_addresses"
    __table_args__ = (
        UniqueConstraint("person_id", "address_type", name="uq_person_addresses_person_type"),
        Index("idx_person_addresses_person_id", "person_id"),
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
    address_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    street: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    zip: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
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
    person: Mapped["Person"] = orm_relationship(
        "Person",
        back_populates="addresses",
    )

    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [self.street, self.city, self.state, self.zip, self.country]
        return ", ".join(p for p in parts if p)

    def __repr__(self) -> str:
        return f"<PersonAddress(type={self.address_type}, city={self.city})>"
