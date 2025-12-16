"""
PersonRelationship model for storing person-to-person relationships.
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
    from app.models.organization import Organization
    from app.models.relationship_type import RelationshipType as RelType


class PersonRelationship(Base):
    """
    Person-to-person relationship.

    Relationships are bidirectional - when A->B is created with type X,
    the inverse B->A with inverse type should also be created.
    """

    __tablename__ = "person_relationships"
    __table_args__ = (
        UniqueConstraint(
            "person_id", "related_person_id", "relationship_type_id",
            name="uq_person_relationships_unique"
        ),
        Index("idx_person_relationships_person_id", "person_id"),
        Index("idx_person_relationships_related_id", "related_person_id"),
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
    related_person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("relationship_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_text: Mapped[str | None] = mapped_column(
        String(255),
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
        foreign_keys=[person_id],
        back_populates="relationships_from",
    )
    related_person: Mapped["Person"] = orm_relationship(
        "Person",
        foreign_keys=[related_person_id],
        back_populates="relationships_to",
    )
    relationship_type: Mapped["RelType | None"] = orm_relationship(
        "RelationshipType",
    )
    context_organization: Mapped["Organization | None"] = orm_relationship(
        "Organization",
    )

    def __repr__(self) -> str:
        return f"<PersonRelationship(from={self.person_id}, to={self.related_person_id})>"
