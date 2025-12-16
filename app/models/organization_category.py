"""
Organization Category model - Tier 1 of the two-tier type system.

Categories are high-level classifications: Investment Firm, Company, Service Provider, Other.
Each category can have investment profile fields enabled/disabled.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import String, Text, Integer, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization_type_lookup import OrganizationType
    from app.models.organization import Organization


class OrganizationCategory(Base):
    """
    Organization category lookup table.

    Categories:
    - investment_firm: Investment firms (VC, PE, etc.) - has investment profile
    - company: Operating businesses - no investment profile
    - service_provider: Professional services - no investment profile
    - other: Non-profits, government, academic, etc. - no investment profile
    """

    __tablename__ = "organization_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_investment_profile: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    types: Mapped[List["OrganizationType"]] = relationship(
        "OrganizationType",
        back_populates="category",
        order_by="OrganizationType.sort_order",
    )

    organizations: Mapped[List["Organization"]] = relationship(
        "Organization",
        back_populates="category_ref",
        foreign_keys="[Organization.category_id]",
    )

    def __repr__(self) -> str:
        return f"<OrganizationCategory(code={self.code!r}, name={self.name!r})>"

    @property
    def organization_count(self) -> int:
        """Return count of organizations in this category."""
        return len(self.organizations) if self.organizations else 0

    @property
    def active_types(self) -> List["OrganizationType"]:
        """Return only active types in this category."""
        return [t for t in self.types if t.is_active]
