"""
AIAPIKey model for storing encrypted API keys for AI providers.

Each AI provider can have multiple API keys. Keys are encrypted using
AES-256 encryption via the encryption service.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_provider import AIProvider


class AIAPIKey(Base):
    """
    Encrypted API key for an AI provider.

    Stores API keys with AES-256 encryption. Use set_api_key() and
    get_api_key() to handle encryption automatically.

    Attributes:
        provider_id: Foreign key to ai_providers
        encrypted_key: AES-256 encrypted API key
        label: User-defined label (e.g., "Personal", "Work")
        is_valid: Result of last validation test
        last_tested: Timestamp of last successful test
    """

    __tablename__ = "ai_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    encrypted_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="AES-256 encrypted API key",
    )
    label: Mapped[str | None] = mapped_column(
        String(100),
        comment="User-defined label for this key",
    )
    is_valid: Mapped[bool | None] = mapped_column(
        Boolean,
        default=None,
        comment="Result of last validation test (null = not tested)",
    )
    last_tested: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Timestamp of last validation test",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    provider: Mapped["AIProvider"] = orm_relationship(
        "AIProvider",
        back_populates="api_keys",
    )

    def __repr__(self) -> str:
        return f"<AIAPIKey(provider_id={self.provider_id}, label={self.label!r}, valid={self.is_valid})>"

    def set_api_key(self, api_key: str) -> None:
        """
        Encrypt and store an API key.

        Args:
            api_key: Plain text API key to encrypt and store

        Example:
            key.set_api_key("sk-abc123...")
        """
        from app.services.encryption import get_encryption_service

        service = get_encryption_service()
        self.encrypted_key = service.encrypt(api_key)

    def get_api_key(self) -> str:
        """
        Decrypt and return the stored API key.

        Returns:
            Plain text API key

        Raises:
            DecryptionError: If the key cannot be decrypted
        """
        from app.services.encryption import get_encryption_service

        service = get_encryption_service()
        return service.decrypt(self.encrypted_key)

    def get_masked_key(self) -> str:
        """
        Return a masked version of the API key for display.

        Shows only the prefix and last 4 characters.
        Example: "sk-...abc1" for OpenAI keys

        Returns:
            Masked API key string
        """
        try:
            key = self.get_api_key()
            if len(key) <= 8:
                return "*" * len(key)

            # Show prefix (e.g., "sk-" for OpenAI) and last 4 chars
            if key.startswith("sk-"):
                return f"sk-...{key[-4:]}"
            elif key.startswith("sk-ant-"):
                return f"sk-ant-...{key[-4:]}"
            else:
                return f"...{key[-4:]}"
        except Exception:
            return "***"

    @classmethod
    def create_with_key(
        cls,
        provider_id: uuid.UUID,
        api_key: str,
        label: str | None = None,
    ) -> "AIAPIKey":
        """
        Factory method to create an AIAPIKey with encrypted key.

        Args:
            provider_id: UUID of the AI provider
            api_key: Plain text API key to encrypt
            label: Optional user-defined label

        Returns:
            New AIAPIKey instance with encrypted key

        Example:
            key = AIAPIKey.create_with_key(
                provider_id=openai_provider.id,
                api_key="sk-abc123...",
                label="Personal"
            )
        """
        from app.services.encryption import get_encryption_service

        service = get_encryption_service()
        encrypted = service.encrypt(api_key)

        return cls(
            provider_id=provider_id,
            encrypted_key=encrypted,
            label=label,
        )

    def mark_valid(self) -> None:
        """Mark the key as valid after successful test."""
        self.is_valid = True
        self.last_tested = datetime.utcnow()

    def mark_invalid(self) -> None:
        """Mark the key as invalid after failed test."""
        self.is_valid = False
        self.last_tested = datetime.utcnow()
