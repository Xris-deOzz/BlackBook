"""
Person model and person-organization relationship model.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base import Base
from app.models.organization import RelationshipType

if TYPE_CHECKING:
    from app.models.tag import Tag
    from app.models.organization import Organization
    from app.models.interaction import Interaction
    from app.models.person_email import PersonEmail
    from app.models.person_phone import PersonPhone
    from app.models.person_website import PersonWebsite
    from app.models.person_address import PersonAddress
    from app.models.person_education import PersonEducation
    from app.models.person_employment import PersonEmployment
    from app.models.person_relationship import PersonRelationship
    from app.models.relationship_type import RelationshipType as RelationshipTypeLookup
    from app.models.ai_conversation import AIConversation
    from app.models.email_person_link import EmailPersonLink


class Person(Base):
    """Person/contact entity."""

    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    first_name: Mapped[str | None] = mapped_column(String(150))
    middle_name: Mapped[str | None] = mapped_column(String(150))
    last_name: Mapped[str | None] = mapped_column(String(150))
    full_name: Mapped[str] = mapped_column(String(300), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(150))
    title: Mapped[str | None] = mapped_column(Text)
    contacted: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    # Contact info
    phone: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(Text)
    linkedin: Mapped[str | None] = mapped_column(Text)
    crunchbase: Mapped[str | None] = mapped_column(Text)
    angellist: Mapped[str | None] = mapped_column(Text)
    twitter: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)

    # Profile picture
    profile_picture: Mapped[str | None] = mapped_column(Text)

    # Birthday
    birthday: Mapped[date | None] = mapped_column(Date)

    # Other fields
    location: Mapped[str | None] = mapped_column(Text)
    investment_type: Mapped[str | None] = mapped_column(Text)
    amount_funded: Mapped[str | None] = mapped_column(Text)
    potential_intro_vc: Mapped[str | None] = mapped_column(Text)

    custom_fields: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        default=dict,
    )

    # My Relationship - how the user knows this person
    my_relationship_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("relationship_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    my_relationship_notes: Mapped[str | None] = mapped_column(Text)

    # Google Contacts sync tracking
    google_resource_name: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
        comment="Google People API resource name (e.g., people/c1234567890)",
    )
    google_etag: Mapped[str | None] = mapped_column(
        String(100),
        comment="Google etag for change detection",
    )
    google_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Last sync timestamp with Google Contacts",
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
        secondary="person_tags",
        back_populates="persons",
    )

    # Organizations this person is linked TO (unified table)
    organizations: Mapped[list["PersonOrganization"]] = orm_relationship(
        "PersonOrganization",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Interactions
    interactions: Mapped[list["Interaction"]] = orm_relationship(
        "Interaction",
        back_populates="person",
    )

    # Email addresses (multiple per person)
    emails: Mapped[list["PersonEmail"]] = orm_relationship(
        "PersonEmail",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Phone numbers (multiple per person)
    phones: Mapped[list["PersonPhone"]] = orm_relationship(
        "PersonPhone",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Websites (multiple per person, max 3)
    websites: Mapped[list["PersonWebsite"]] = orm_relationship(
        "PersonWebsite",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Addresses (max 2: home, work)
    addresses: Mapped[list["PersonAddress"]] = orm_relationship(
        "PersonAddress",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Education history (max 6)
    education: Mapped[list["PersonEducation"]] = orm_relationship(
        "PersonEducation",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Employment history (max 10)
    employment: Mapped[list["PersonEmployment"]] = orm_relationship(
        "PersonEmployment",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Relationships FROM this person (outgoing)
    relationships_from: Mapped[list["PersonRelationship"]] = orm_relationship(
        "PersonRelationship",
        foreign_keys="PersonRelationship.person_id",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # Relationships TO this person (incoming)
    relationships_to: Mapped[list["PersonRelationship"]] = orm_relationship(
        "PersonRelationship",
        foreign_keys="PersonRelationship.related_person_id",
        back_populates="related_person",
        cascade="all, delete-orphan",
    )

    # AI conversations about this person
    ai_conversations: Mapped[list["AIConversation"]] = orm_relationship(
        "AIConversation",
        back_populates="person",
    )

    # Email links (emails involving this person)
    email_links: Mapped[list["EmailPersonLink"]] = orm_relationship(
        "EmailPersonLink",
        back_populates="person",
        cascade="all, delete-orphan",
    )

    # My Relationship type (how user knows this person)
    my_relationship_type: Mapped["RelationshipTypeLookup | None"] = orm_relationship(
        "RelationshipType",
        foreign_keys=[my_relationship_type_id],
    )

    @hybrid_property
    def last_contact(self) -> datetime | None:
        """Get the most recent interaction date for this person."""
        if not self.interactions:
            return None
        dates = [
            i.interaction_date or i.created_at
            for i in self.interactions
            if i.interaction_date or i.created_at
        ]
        return max(dates) if dates else None

    @property
    def primary_email(self) -> str | None:
        """Get the primary email address for this person.

        Returns the email marked as primary, or the first email if none is primary,
        or falls back to the legacy 'email' field.
        """
        if self.emails:
            # First try to find one marked as primary
            for email_obj in self.emails:
                if email_obj.is_primary:
                    return email_obj.email
            # If none marked primary, return the first one
            return self.emails[0].email
        # Fall back to legacy email field
        return self.email

    def __repr__(self) -> str:
        return f"<Person(name={self.full_name!r})>"


class PersonOrganization(Base):
    """
    Unified Person <-> Organization relationship table.
    - person_id can be NULL for unlinked person references (just names)
    - person_name stores the display name (especially for unlinked references)
    - Supports various relationship types: employee, contact, advisor, etc.
    """

    __tablename__ = "person_organizations"
    __table_args__ = (
        UniqueConstraint("person_id", "organization_id", "relationship"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=True,  # Can be NULL for unlinked person references
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType, name="relationship_type", create_type=False),
        nullable=False,
        default=RelationshipType.affiliated_with,
    )
    person_name: Mapped[str | None] = mapped_column(Text)  # For unlinked references
    role: Mapped[str | None] = mapped_column(String(300))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    person: Mapped["Person | None"] = orm_relationship(
        "Person",
        back_populates="organizations",
    )
    organization: Mapped["Organization"] = orm_relationship(
        "Organization",
        back_populates="affiliated_persons",
    )

    @property
    def display_name(self) -> str:
        """Get the display name for this relationship."""
        if self.person:
            return self.person.full_name
        return self.person_name or "Unknown"

    def __repr__(self) -> str:
        return f"<PersonOrganization(person={self.person_id}, org={self.organization_id})>"
