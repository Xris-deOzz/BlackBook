"""
PersonGoogleLink model for tracking person-to-Google-contact relationships.

A person can exist in multiple Google accounts (e.g., work and personal).
This table tracks each link separately, enabling multi-account sync.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base


class PersonGoogleLink(Base):
    """
    Links a Person to a Google Contact in a specific Google account.

    This allows:
    - Same person to exist in multiple Google accounts
    - Track sync state per account
    - Preserve all google_resource_names for a person
    """

    __tablename__ = "person_google_links"
    __table_args__ = (
        # Each google_resource_name should only appear once per google_account
        UniqueConstraint(
            "google_account_id",
            "google_resource_name",
            name="uq_google_account_resource"
        ),
        # Index for fast lookups by google_account
        Index("ix_person_google_links_google_account", "google_account_id"),
        # Index for fast lookups by person
        Index("ix_person_google_links_person", "person_id"),
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
    google_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("google_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    google_resource_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Google People API resource name (e.g., people/c1234567890)",
    )
    google_etag: Mapped[str | None] = mapped_column(
        String(100),
        comment="Google etag for change detection",
    )
    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Last sync timestamp for this link",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    person: Mapped["Person"] = orm_relationship(
        "Person",
        back_populates="google_links",
    )
    google_account: Mapped["GoogleAccount"] = orm_relationship(
        "GoogleAccount",
        back_populates="person_links",
    )

    def __repr__(self) -> str:
        return f"<PersonGoogleLink(person={self.person_id}, account={self.google_account_id}, resource={self.google_resource_name})>"
