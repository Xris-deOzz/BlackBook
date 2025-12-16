"""
Organization Type model - Tier 2 of the two-tier type system.

Types are specific classifications within a category:
- Investment Firm: VC, PE, Private Credit, Family Office, etc.
- Company: Startup, Corporation, Bank, InsurCo
- Service Provider: Law Firm, iBank/Consulting, Headhunter, etc.
- Other: Non-Profit, Government, University, etc.

Each type has a profile_style that determines which investment profile fields to show.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, List

from sqlalchemy import String, Text, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization_category import OrganizationCategory
    from app.models.organization import Organization


class ProfileStyle(str, PyEnum):
    """Investment profile styles that determine which fields to show."""
    vc_style = "vc_style"           # VC, Corporate VC, Accelerator, Angel
    pe_style = "pe_style"           # PE, HoldCo
    credit_style = "credit_style"   # Private Credit
    multi_strategy = "multi_strategy"  # Family Office, SWF, Fund of Funds
    public_markets = "public_markets"  # Hedge Funds, AM, RIA, Shortseller


class OrganizationType(Base):
    """
    Organization type lookup table.

    Types are specific classifications within a category.
    Each type optionally has a profile_style that determines investment profile fields.
    """

    __tablename__ = "organization_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organization_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_style: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # 'vc_style', 'pe_style', 'credit_style', 'multi_strategy', 'public_markets', or NULL
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
    category: Mapped["OrganizationCategory"] = relationship(
        "OrganizationCategory",
        back_populates="types",
    )

    organizations: Mapped[List["Organization"]] = relationship(
        "Organization",
        back_populates="type_ref",
        foreign_keys="[Organization.type_id]",
    )

    def __repr__(self) -> str:
        return f"<OrganizationType(code={self.code!r}, name={self.name!r}, profile_style={self.profile_style!r})>"

    @property
    def organization_count(self) -> int:
        """Return count of organizations of this type."""
        return len(self.organizations) if self.organizations else 0

    @property
    def has_investment_profile(self) -> bool:
        """Check if this type should show investment profile fields."""
        return self.profile_style is not None

    @property
    def category_code(self) -> str:
        """Return the category code."""
        return self.category.code if self.category else ""

    @property
    def category_name(self) -> str:
        """Return the category name."""
        return self.category.name if self.category else ""
