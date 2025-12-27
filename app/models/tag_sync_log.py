"""
TagSyncLog model for auditing tag-label sync operations.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.tag import Tag
    from app.models.tag_google_link import TagGoogleLink
    from app.models.google_account import GoogleAccount
    from app.models.person import Person


class TagSyncLog(Base):
    """
    Audit log for tag-label synchronization operations.

    Records all sync actions including member additions/removals,
    link creation/deletion, and errors.
    """

    __tablename__ = "tag_sync_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tag_google_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tag_google_links.id", ondelete="SET NULL"),
        nullable=True,
    )
    tag_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="SET NULL"),
        nullable=True,
    )
    google_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("google_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    person_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    direction: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="success",
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships (optional - for queries)
    tag_google_link: Mapped["TagGoogleLink | None"] = relationship(
        "TagGoogleLink",
        foreign_keys=[tag_google_link_id],
    )
    tag: Mapped["Tag | None"] = relationship("Tag", foreign_keys=[tag_id])
    google_account: Mapped["GoogleAccount | None"] = relationship(
        "GoogleAccount",
        foreign_keys=[google_account_id]
    )
    person: Mapped["Person | None"] = relationship("Person", foreign_keys=[person_id])

    def __repr__(self) -> str:
        return f"<TagSyncLog(action={self.action!r}, status={self.status!r})>"
