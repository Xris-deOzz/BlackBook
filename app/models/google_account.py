"""
GoogleAccount model for storing connected Google OAuth accounts.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    String,
    Text,
    Boolean,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.calendar_event import CalendarEvent
    from app.models.email_message import EmailMessage
    from app.models.email_sync_state import EmailSyncState


class GoogleAccount(Base):
    """
    Connected Google account for Gmail/Calendar integration.

    Stores OAuth credentials (encrypted) for accessing Google APIs.
    Each account represents one connected Google email address.

    Use set_credentials() and get_credentials() to handle encryption
    automatically when storing/retrieving OAuth tokens.
    """

    __tablename__ = "google_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
    )
    credentials_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="AES-256 encrypted OAuth refresh token",
    )
    scopes: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        comment="OAuth scopes granted (e.g., gmail.readonly, calendar.readonly)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
    calendar_events: Mapped[list["CalendarEvent"]] = orm_relationship(
        "CalendarEvent",
        back_populates="google_account",
        cascade="all, delete-orphan",
    )
    email_messages: Mapped[list["EmailMessage"]] = orm_relationship(
        "EmailMessage",
        back_populates="google_account",
        cascade="all, delete-orphan",
    )
    email_sync_state: Mapped["EmailSyncState | None"] = orm_relationship(
        "EmailSyncState",
        back_populates="google_account",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<GoogleAccount(email={self.email!r}, active={self.is_active})>"

    def set_credentials(self, credentials: dict[str, Any]) -> None:
        """
        Encrypt and store OAuth credentials.

        Args:
            credentials: Dictionary containing OAuth tokens and metadata
                Expected keys: access_token, refresh_token, token_uri, etc.

        Example:
            account.set_credentials({
                "access_token": "ya29.xxx",
                "refresh_token": "1//xxx",
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["gmail.readonly"],
            })
        """
        from app.services.encryption import get_encryption_service

        service = get_encryption_service()
        self.credentials_encrypted = service.encrypt_json(credentials)

    def get_credentials(self) -> dict[str, Any]:
        """
        Decrypt and return stored OAuth credentials.

        Returns:
            Dictionary containing OAuth tokens and metadata

        Raises:
            DecryptionError: If credentials cannot be decrypted
        """
        from app.services.encryption import get_encryption_service

        service = get_encryption_service()
        return service.decrypt_json(self.credentials_encrypted)

    @classmethod
    def create_with_credentials(
        cls,
        email: str,
        credentials: dict[str, Any],
        display_name: str | None = None,
        scopes: list[str] | None = None,
    ) -> "GoogleAccount":
        """
        Factory method to create a GoogleAccount with encrypted credentials.

        Args:
            email: Google account email address
            credentials: OAuth credentials dictionary to encrypt
            display_name: Optional display name for the account
            scopes: Optional list of OAuth scopes granted

        Returns:
            New GoogleAccount instance with encrypted credentials

        Example:
            account = GoogleAccount.create_with_credentials(
                email="user@gmail.com",
                credentials={"refresh_token": "1//xxx", ...},
                scopes=["gmail.readonly"],
            )
        """
        from app.services.encryption import get_encryption_service

        service = get_encryption_service()
        encrypted = service.encrypt_json(credentials)

        return cls(
            email=email,
            display_name=display_name,
            credentials_encrypted=encrypted,
            scopes=scopes,
        )
