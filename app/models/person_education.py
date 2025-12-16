"""
PersonEducation model for storing education history per person.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person


class PersonEducation(Base):
    """
    Education record associated with a Person.

    A person can have up to 6 education entries.
    Degree types: BA, BS, MA, MS, MBA, PhD, JD, MD, Other
    """

    __tablename__ = "person_education"
    __table_args__ = (
        Index("idx_person_education_person_id", "person_id"),
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
    school_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    degree_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    field_of_study: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    graduation_year: Mapped[int | None] = mapped_column(
        Integer,
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
        back_populates="education",
    )

    @property
    def display_text(self) -> str:
        """Get formatted education display text."""
        parts = []
        if self.degree_type:
            parts.append(self.degree_type)
        if self.field_of_study:
            parts.append(f"in {self.field_of_study}")
        parts.append(f"from {self.school_name}")
        if self.graduation_year:
            parts.append(f"({self.graduation_year})")
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"<PersonEducation(school={self.school_name!r}, degree={self.degree_type})>"
