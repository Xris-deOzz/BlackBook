"""
Organization Relationship Status model for tracking your personal relationship with an organization.
"""

import uuid
from datetime import datetime, date
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, Text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.person import Person


class RelationshipWarmth(str, PyEnum):
    """Warmth levels for relationship tracking."""
    hot = "hot"           # Active deal/discussion
    warm = "warm"         # Regular contact, good relationship
    met_once = "met_once" # Had one meeting/interaction
    cold = "cold"         # No recent contact or new relationship
    unknown = "unknown"   # Haven't assessed yet


class OrganizationRelationshipStatus(Base):
    """
    Tracks your personal relationship status with an organization.
    One record per organization - tracks primary contact, warmth level,
    intro opportunities, and follow-up dates.
    """

    __tablename__ = "organization_relationship_status"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One status record per organization
    )
    # Primary contact at the organization
    primary_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Warmth level of the relationship
    relationship_warmth: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default="unknown",
    )
    # Who can introduce you to this organization
    intro_available_via_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Next planned follow-up date
    next_followup_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    # Additional notes about the relationship
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="relationship_status",
    )
    primary_contact: Mapped["Person | None"] = relationship(
        "Person",
        foreign_keys=[primary_contact_id],
    )
    intro_available_via: Mapped["Person | None"] = relationship(
        "Person",
        foreign_keys=[intro_available_via_id],
    )

    def __repr__(self) -> str:
        return f"<OrganizationRelationshipStatus(org={self.organization_id}, warmth={self.relationship_warmth})>"

    @property
    def warmth_display(self) -> str:
        """Human-readable warmth level with emoji."""
        display_map = {
            "hot": "Hot",
            "warm": "Warm",
            "met_once": "Met Once",
            "cold": "Cold",
            "unknown": "Unknown",
        }
        return display_map.get(self.relationship_warmth, "Unknown")

    @property
    def warmth_emoji(self) -> str:
        """Emoji for warmth level."""
        emoji_map = {
            "hot": "🔥",
            "warm": "🟢",
            "met_once": "🟡",
            "cold": "🔴",
            "unknown": "⚪",
        }
        return emoji_map.get(self.relationship_warmth, "⚪")
