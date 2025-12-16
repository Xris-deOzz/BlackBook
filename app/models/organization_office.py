"""
Organization Office model for tracking multiple office locations per organization.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class OfficeType(str, PyEnum):
    """Types of office locations."""
    headquarters = "headquarters"
    regional = "regional"
    satellite = "satellite"
    branch = "branch"


class OrganizationOffice(Base):
    """
    Tracks office locations for an organization.
    An organization can have multiple offices (HQ, regional offices, etc.)
    """

    __tablename__ = "organization_offices"

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
    office_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="regional",
    )
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_headquarters: Mapped[bool] = mapped_column(Boolean, default=False)
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
        back_populates="offices",
    )

    def __repr__(self) -> str:
        location = f"{self.city}, {self.country}" if self.city else self.country
        return f"<OrganizationOffice({location}, {self.office_type})>"

    @property
    def display_location(self) -> str:
        """Human-readable location string."""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts) if parts else "Unknown Location"
