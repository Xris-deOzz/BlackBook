"""
PersonEmployment model for storing employment/affiliation history per person.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.organization import Organization
    from app.models.affiliation_type import AffiliationType


class PersonEmployment(Base):
    """
    Employment/affiliation record associated with a Person.

    A person can have up to 10 employment entries.
    Links to organizations or stores organization name as fallback.
    """

    __tablename__ = "person_employment"
    __table_args__ = (
        Index("idx_person_employment_person_id", "person_id"),
        Index("idx_person_employment_org_id", "organization_id"),
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
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    affiliation_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("affiliation_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
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
        back_populates="employment",
    )
    organization: Mapped["Organization | None"] = orm_relationship(
        "Organization",
        back_populates="employees",
    )
    affiliation_type: Mapped["AffiliationType | None"] = orm_relationship(
        "AffiliationType",
    )

    @property
    def display_organization(self) -> str:
        """Get organization name for display."""
        if self.organization:
            return self.organization.name
        return self.organization_name or "Unknown"

    def __repr__(self) -> str:
        return f"<PersonEmployment(title={self.title!r}, org={self.display_organization})>"
