"""
Organization model and organization-person relationship model.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.tag import Tag
    from app.models.person import Person, PersonOrganization
    from app.models.person_employment import PersonEmployment
    from app.models.ai_conversation import AIConversation
    from app.models.org_relationship import OrganizationRelationship
    from app.models.organization_office import OrganizationOffice
    from app.models.organization_relationship_status import OrganizationRelationshipStatus
    from app.models.organization_category import OrganizationCategory
    from app.models.organization_type_lookup import OrganizationType


class OrgType(str, PyEnum):
    """Organization type enum (matches PostgreSQL org_type)."""

    investment_firm = "investment_firm"
    company = "company"
    law_firm = "law_firm"
    bank = "bank"
    accelerator = "accelerator"
    other = "other"


class RelationshipType(str, PyEnum):
    """Relationship type enum (matches PostgreSQL relationship_type)."""

    # Original types
    affiliated_with = "affiliated_with"
    peer_history = "peer_history"
    key_person = "key_person"
    connection = "connection"
    contact_at = "contact_at"
    # New employee/role types
    current_employee = "current_employee"
    former_employee = "former_employee"
    board_member = "board_member"
    advisor = "advisor"
    investor = "investor"
    founder = "founder"


class Organization(Base):
    """Organization entity (investment firms, companies, etc.)."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    org_type: Mapped[OrgType] = mapped_column(
        Enum(OrgType, name="org_type", create_type=False),
        nullable=False,
        default=OrgType.other,
    )
    category: Mapped[str | None] = mapped_column(String(200))
    logo: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(500))
    crunchbase: Mapped[str | None] = mapped_column(String(500))
    # Social Links
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    twitter_url: Mapped[str | None] = mapped_column(String(500))
    pitchbook_url: Mapped[str | None] = mapped_column(String(500))
    angellist_url: Mapped[str | None] = mapped_column(String(500))
    # Investment Profile (for VC/PE firms)
    investment_stages: Mapped[str | None] = mapped_column(Text)  # Comma-separated: seed,series_a,series_b
    check_size_min: Mapped[int | None] = mapped_column(Integer)  # In thousands USD
    check_size_max: Mapped[int | None] = mapped_column(Integer)  # In thousands USD
    investment_sectors: Mapped[str | None] = mapped_column(Text)  # Comma-separated sectors
    geographic_focus: Mapped[str | None] = mapped_column(Text)  # Comma-separated regions
    fund_size: Mapped[int | None] = mapped_column(Integer)  # In millions USD
    current_fund_name: Mapped[str | None] = mapped_column(String(200))
    current_fund_year: Mapped[int | None] = mapped_column(Integer)

    # Two-tier type system (new)
    category_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organization_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organization_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # PE-Style Investment Profile fields
    deal_types: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))  # LBO, Growth Equity, Recap, etc.
    target_revenue_min: Mapped[int | None] = mapped_column(Integer)  # In millions USD
    target_revenue_max: Mapped[int | None] = mapped_column(Integer)  # In millions USD
    target_ebitda_min: Mapped[int | None] = mapped_column(Integer)  # In millions USD
    target_ebitda_max: Mapped[int | None] = mapped_column(Integer)  # In millions USD
    control_preference: Mapped[str | None] = mapped_column(String(20))  # majority, minority, either
    industry_focus: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))  # PE industry focus

    # Credit-Style Investment Profile fields
    credit_strategies: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))  # Direct Lending, Mezzanine, etc.

    # Multi-Strategy Investment Profile fields
    investment_styles: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))  # Direct, Co-Invest, Fund Investor
    asset_classes: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))  # Asset classes

    # Public Markets Investment Profile fields
    trading_strategies: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))  # Long/Short, Activist, etc.

    priority_rank: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    custom_fields: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        default=dict,
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
    tags: Mapped[list["Tag"]] = orm_relationship(
        "Tag",
        secondary="organization_tags",
        back_populates="organizations",
    )

    # All persons linked to this org (via person_organizations - unified table)
    affiliated_persons: Mapped[list["PersonOrganization"]] = orm_relationship(
        "PersonOrganization",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    # Employment records linked to this org (via person_employment)
    employees: Mapped[list["PersonEmployment"]] = orm_relationship(
        "PersonEmployment",
        back_populates="organization",
    )

    # AI conversations about this organization
    ai_conversations: Mapped[list["AIConversation"]] = orm_relationship(
        "AIConversation",
        back_populates="organization",
    )

    # Organization-to-Organization relationships (outgoing: this org is "from")
    outgoing_relationships: Mapped[list["OrganizationRelationship"]] = orm_relationship(
        "OrganizationRelationship",
        foreign_keys="[OrganizationRelationship.from_organization_id]",
        back_populates="from_organization",
        cascade="all, delete-orphan",
    )

    # Organization-to-Organization relationships (incoming: this org is "to")
    incoming_relationships: Mapped[list["OrganizationRelationship"]] = orm_relationship(
        "OrganizationRelationship",
        foreign_keys="[OrganizationRelationship.to_organization_id]",
        back_populates="to_organization",
        cascade="all, delete-orphan",
    )

    # Office locations
    offices: Mapped[list["OrganizationOffice"]] = orm_relationship(
        "OrganizationOffice",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    # Personal relationship status with this organization
    relationship_status: Mapped["OrganizationRelationshipStatus | None"] = orm_relationship(
        "OrganizationRelationshipStatus",
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Two-tier type system relationships
    category_ref: Mapped["OrganizationCategory | None"] = orm_relationship(
        "OrganizationCategory",
        back_populates="organizations",
        foreign_keys=[category_id],
    )

    type_ref: Mapped["OrganizationType | None"] = orm_relationship(
        "OrganizationType",
        back_populates="organizations",
        foreign_keys=[type_id],
    )

    def __repr__(self) -> str:
        return f"<Organization(name={self.name!r}, type={self.org_type.value})>"
