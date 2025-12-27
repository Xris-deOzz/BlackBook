"""
TagGoogleLink model for linking BlackBook tags to Google Contacts labels.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.tag import Tag
    from app.models.google_account import GoogleAccount


class SyncDirection(str, Enum):
    """Direction of sync between BlackBook and Google."""
    bidirectional = "bidirectional"
    to_google = "to_google"
    from_google = "from_google"


class TagGoogleLink(Base):
    """
    Links a BlackBook tag to a Google Contacts label (contact group).

    Each tag can be linked to multiple Google accounts.
    Each link specifies the sync direction and tracks sync status.
    """

    __tablename__ = "tag_google_links"
    __table_args__ = (
        UniqueConstraint("tag_id", "google_account_id", name="uq_tag_google_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
    )
    google_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("google_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    google_group_resource_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,  # NULL if label needs to be created
    )
    google_group_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    sync_direction: Mapped[str] = mapped_column(
        String(20),
        default=SyncDirection.bidirectional.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    last_sync_status: Mapped[str | None] = mapped_column(
        String(20),
    )
    last_sync_error: Mapped[str | None] = mapped_column(
        Text,
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
    tag: Mapped["Tag"] = relationship("Tag", back_populates="google_links")
    google_account: Mapped["GoogleAccount"] = relationship(
        "GoogleAccount",
        back_populates="tag_links"
    )

    def __repr__(self) -> str:
        return (
            f"<TagGoogleLink(tag={self.tag_id}, "
            f"account={self.google_account_id}, "
            f"label={self.google_group_name!r})>"
        )
