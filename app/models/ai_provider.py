"""
AIProvider model for storing AI provider configurations.

Stores available AI providers (OpenAI, Anthropic, Google, Ollama) with their
configuration settings. Each provider can be enabled/disabled independently.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base


class AIProviderType(str, PyEnum):
    """Supported AI provider types."""

    # AI providers
    openai = "openai"
    anthropic = "anthropic"
    google = "google"
    ollama = "ollama"
    # Search providers
    brave_search = "brave_search"
    youtube = "youtube"
    listen_notes = "listen_notes"


class AIProvider(Base):
    """
    Available AI provider configuration.

    Stores provider metadata and settings. Each provider can have
    multiple API keys associated with it via the AIAPIKey model.

    Attributes:
        name: Display name (e.g., "OpenAI", "Claude", "Gemini")
        api_type: Provider type enum (openai, anthropic, google, ollama)
        base_url: Custom API endpoint URL (optional, for self-hosted)
        is_local: True for local providers like Ollama
        is_active: Whether provider is enabled for use
    """

    __tablename__ = "ai_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Display name for the provider",
    )
    api_type: Mapped[AIProviderType] = mapped_column(
        Enum(AIProviderType, name="ai_provider_type", create_type=False),
        nullable=False,
        comment="Provider type (openai, anthropic, google, ollama)",
    )
    base_url: Mapped[str | None] = mapped_column(
        String(255),
        comment="Custom API endpoint URL (optional)",
    )
    is_local: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True for local providers like Ollama",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Whether provider is enabled for use",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    api_keys: Mapped[list["AIAPIKey"]] = orm_relationship(
        "AIAPIKey",
        back_populates="provider",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AIProvider(name={self.name!r}, type={self.api_type.value}, active={self.is_active})>"

    @property
    def has_valid_key(self) -> bool:
        """Check if provider has at least one valid API key."""
        return any(key.is_valid for key in self.api_keys)

    @property
    def active_key(self) -> "AIAPIKey | None":
        """Get the first valid API key for this provider."""
        for key in self.api_keys:
            if key.is_valid:
                return key
        return None


# Import for type hints (after class definition to avoid circular import)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.ai_api_key import AIAPIKey
