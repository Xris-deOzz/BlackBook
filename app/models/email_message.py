"""
EmailMessage model for storing Gmail message metadata.

This model stores metadata about emails for fast querying and filtering.
Full email content is fetched on-demand from Gmail API, not stored locally.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.google_account import GoogleAccount
    from app.models.email_person_link import EmailPersonLink


class EmailMessage(Base):
    """
    Gmail message metadata stored locally for fast filtering and search.

    Full email content (body, attachments) is NOT stored here - it's fetched
    on-demand from Gmail API when viewing the email.

    This allows for:
    - Fast inbox listing without API calls
    - Local search and filtering
    - CRM contact linking
    - Tracking read/unread status
    """

    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint(
            "google_account_id", "gmail_message_id", name="uq_email_message_account_msg"
        ),
        Index("idx_email_messages_account", "google_account_id"),
        Index("idx_email_messages_thread", "gmail_thread_id"),
        Index("idx_email_messages_date", "internal_date", postgresql_ops={"internal_date": "DESC"}),
        Index("idx_email_messages_from", "from_email"),
        Index("idx_email_messages_read", "is_read"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    google_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("google_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    gmail_message_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Gmail API message ID",
    )
    gmail_thread_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Gmail API thread ID (groups related messages)",
    )

    # Core metadata
    subject: Mapped[str | None] = mapped_column(
        String(1000),
    )
    snippet: Mapped[str | None] = mapped_column(
        Text,
        comment="Short preview of email body from Gmail",
    )

    # Sender/Recipients
    from_email: Mapped[str | None] = mapped_column(
        String(255),
    )
    from_name: Mapped[str | None] = mapped_column(
        String(255),
    )
    to_emails: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
        comment="Array of {email, name} objects",
    )
    cc_emails: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
    )
    bcc_emails: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
    )

    # Status flags
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    is_starred: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    is_draft: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    is_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True if from user's sent folder",
    )
    labels: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
        comment="Gmail labels (INBOX, SENT, etc.)",
    )

    # Dates
    internal_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Gmail internal timestamp (when message was received)",
    )
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    # Attachment info (metadata only, not content)
    has_attachments: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    attachment_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # Sync tracking
    history_id: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="Gmail history ID for incremental sync",
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    google_account: Mapped["GoogleAccount"] = orm_relationship(
        "GoogleAccount",
        back_populates="email_messages",
    )
    person_links: Mapped[list["EmailPersonLink"]] = orm_relationship(
        "EmailPersonLink",
        back_populates="email_message",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<EmailMessage(id={self.gmail_message_id!r}, subject={self.subject!r})>"

    @property
    def gmail_web_url(self) -> str:
        """Generate URL to view this email in Gmail web interface."""
        return f"https://mail.google.com/mail/u/0/#inbox/{self.gmail_thread_id}"

    @property
    def is_inbox(self) -> bool:
        """Check if this email is in the inbox."""
        return "INBOX" in (self.labels or [])

    @property
    def is_unread(self) -> bool:
        """Check if this email is unread."""
        return "UNREAD" in (self.labels or [])

    @property
    def all_recipients(self) -> list[str]:
        """Get all recipient email addresses (to + cc + bcc)."""
        recipients = []
        for recipient_list in [self.to_emails, self.cc_emails, self.bcc_emails]:
            if recipient_list:
                for r in recipient_list:
                    if isinstance(r, dict) and r.get("email"):
                        recipients.append(r["email"])
                    elif isinstance(r, str):
                        recipients.append(r)
        return recipients

    @property
    def display_from(self) -> str:
        """Get display string for sender (name if available, else email)."""
        if self.from_name:
            return self.from_name
        return self.from_email or "Unknown"
