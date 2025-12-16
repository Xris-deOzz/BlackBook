"""
RelationshipType model - lookup table for person-to-person relationship types.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RelationshipType(Base):
    """
    Lookup table for person-to-person relationship types.

    Categories:
    - family: Spouse, Child, Parent, Sibling, Family Member
    - education: College Classmate
    - professional: Worked Together, Business Partner, Mentor, Mentee, Reports To, Manages
    - introduction: Introduced By, Introduced To
    - personal: Friend, Acquaintance, Met at Conference, Met at Event, Former Coworker, Referred By/To
    - other: Other, user-defined types

    Display order determines sort within "Their Connections":
    - family: 10-19 (shown first)
    - education: 20-29
    - professional: 30-39
    - introduction: 40-49
    - personal: 50-69
    - other: 100+
    """

    __tablename__ = "relationship_types"
    __table_args__ = (
        UniqueConstraint("name", name="uq_relationship_types_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    inverse_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        default="other",
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=100,
    )
    requires_organization: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<RelationshipType(name={self.name!r}, inverse={self.inverse_name})>"
