"""
Organization-to-Organization relationship model for tracking investments, subsidiaries, etc.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class OrgRelationshipType(str, Enum):
    """Types of relationships between organizations."""
    # Investment relationships
    invested_in = "invested_in"           # VC/PE invested in a company (portfolio company)
    investor = "investor"                 # Investor in this company (inverse of invested_in)
    co_investor = "co_investor"           # Frequently co-invests with
    limited_partner = "limited_partner"   # LP in this fund
    fund_manager = "fund_manager"         # Manages fund for this LP
    # Corporate structure
    subsidiary_of = "subsidiary_of"       # Company is subsidiary of parent
    parent_company = "parent_company"     # Organization is parent of another
    # M&A
    acquired = "acquired"                 # Organization acquired another
    acquired_by = "acquired_by"           # Organization was acquired
    spun_off_from = "spun_off_from"       # Company spun off from another
    # Strategic
    partner = "partner"                   # Strategic partnership
    competitor = "competitor"             # Competitor


class OrganizationRelationship(Base):
    """
    Tracks relationships between organizations.

    The relationship is directional: from_organization has a relationship TO to_organization.
    For example: "8VC invested_in Acme Corp" would have:
      - from_organization = 8VC
      - to_organization = Acme Corp
      - relationship_type = invested_in
    """

    __tablename__ = "organization_relationships"
    __table_args__ = (
        UniqueConstraint(
            "from_organization_id", "to_organization_id", "relationship_type",
            name="uq_org_relationship"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    from_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[OrgRelationshipType] = mapped_column(
        String(50),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    from_organization: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[from_organization_id],
        back_populates="outgoing_relationships",
    )
    to_organization: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[to_organization_id],
        back_populates="incoming_relationships",
    )

    def __repr__(self) -> str:
        return f"<OrganizationRelationship({self.from_organization_id} {self.relationship_type.value} {self.to_organization_id})>"

    @property
    def relationship_display(self) -> str:
        """Human-readable relationship type."""
        display_names = {
            OrgRelationshipType.invested_in: "Invested In",
            OrgRelationshipType.investor: "Investor",
            OrgRelationshipType.co_investor: "Co-Investor",
            OrgRelationshipType.limited_partner: "Limited Partner",
            OrgRelationshipType.fund_manager: "Fund Manager",
            OrgRelationshipType.subsidiary_of: "Subsidiary Of",
            OrgRelationshipType.parent_company: "Parent Company Of",
            OrgRelationshipType.acquired: "Acquired",
            OrgRelationshipType.acquired_by: "Acquired By",
            OrgRelationshipType.spun_off_from: "Spun Off From",
            OrgRelationshipType.partner: "Partner With",
            OrgRelationshipType.competitor: "Competitor",
        }
        return display_names.get(self.relationship_type, self.relationship_type.value)

    @staticmethod
    def get_inverse_type(rel_type: "OrgRelationshipType") -> "OrgRelationshipType | None":
        """Get the inverse relationship type for bidirectional relationships."""
        inverse_map = {
            OrgRelationshipType.invested_in: OrgRelationshipType.investor,
            OrgRelationshipType.investor: OrgRelationshipType.invested_in,
            OrgRelationshipType.co_investor: OrgRelationshipType.co_investor,
            OrgRelationshipType.limited_partner: OrgRelationshipType.fund_manager,
            OrgRelationshipType.fund_manager: OrgRelationshipType.limited_partner,
            OrgRelationshipType.subsidiary_of: OrgRelationshipType.parent_company,
            OrgRelationshipType.parent_company: OrgRelationshipType.subsidiary_of,
            OrgRelationshipType.acquired: OrgRelationshipType.acquired_by,
            OrgRelationshipType.acquired_by: OrgRelationshipType.acquired,
            OrgRelationshipType.spun_off_from: None,  # One-directional
            OrgRelationshipType.partner: OrgRelationshipType.partner,
            OrgRelationshipType.competitor: OrgRelationshipType.competitor,
        }
        return inverse_map.get(rel_type)
