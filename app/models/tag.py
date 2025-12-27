"""
Tag model for categorizing persons and organizations.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.organization import Organization
    from app.models.tag_google_link import TagGoogleLink


class Tag(Base):
    """Tag for categorizing persons and organizations."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), default="#6B7280")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "Firm Category", "Company Category"
    subcategory: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "Investor Type", "Location", "Relationship"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    persons: Mapped[list["Person"]] = relationship(
        "Person",
        secondary="person_tags",
        back_populates="tags",
    )
    organizations: Mapped[list["Organization"]] = relationship(
        "Organization",
        secondary="organization_tags",
        back_populates="tags",
    )
    google_links: Mapped[list["TagGoogleLink"]] = relationship(
        "TagGoogleLink",
        back_populates="tag",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Tag(name={self.name!r})>"


class PersonTag(Base):
    """Junction table for Person <-> Tag many-to-many relationship."""

    __tablename__ = "person_tags"
    __table_args__ = (UniqueConstraint("person_id", "tag_id"),)

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
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )


class OrganizationTag(Base):
    """Junction table for Organization <-> Tag many-to-many relationship."""

    __tablename__ = "organization_tags"
    __table_args__ = (UniqueConstraint("organization_id", "tag_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
