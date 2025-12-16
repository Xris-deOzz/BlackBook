"""
AISuggestion model for storing AI-generated field suggestions.

When the AI researches a person or organization, it can suggest values
for CRM fields. These suggestions require user approval before being applied.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_conversation import AIConversation


class AISuggestionStatus(str, PyEnum):
    """Status of an AI suggestion."""

    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class AISuggestion(Base):
    """
    AI-generated suggestion for updating a CRM field.

    When the AI discovers information about a person or organization,
    it creates suggestions that the user can accept, reject, or edit.

    Attributes:
        conversation_id: The conversation that generated this suggestion
        entity_type: "person" or "organization"
        entity_id: UUID of the entity to update
        field_name: Name of the field to update (e.g., "title", "website")
        current_value: Current value of the field (for comparison)
        suggested_value: AI-suggested new value
        confidence: AI confidence score (0.0 to 1.0)
        source_url: URL where AI found this information
        status: pending, accepted, or rejected
    """

    __tablename__ = "ai_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=True,  # Allow suggestions without conversation (e.g., standalone tools)
    )
    entity_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Entity type: 'person' or 'organization'",
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="UUID of the entity to update",
    )
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Field name to update (e.g., 'title', 'website')",
    )
    current_value: Mapped[str | None] = mapped_column(
        Text,
        comment="Current field value (for comparison)",
    )
    suggested_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="AI-suggested new value",
    )
    confidence: Mapped[float | None] = mapped_column(
        Float,
        comment="AI confidence score (0.0 to 1.0)",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(500),
        comment="URL where AI found this information",
    )
    status: Mapped[AISuggestionStatus] = mapped_column(
        Enum(AISuggestionStatus, name="ai_suggestion_status", create_type=False),
        default=AISuggestionStatus.pending,
        nullable=False,
        comment="Suggestion status: pending, accepted, rejected",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="When the suggestion was accepted or rejected",
    )

    # Relationships
    conversation: Mapped["AIConversation"] = orm_relationship(
        "AIConversation",
        back_populates="suggestions",
    )

    def __repr__(self) -> str:
        return (
            f"<AISuggestion("
            f"entity={self.entity_type}:{self.entity_id}, "
            f"field={self.field_name!r}, "
            f"status={self.status.value})>"
        )

    @property
    def is_pending(self) -> bool:
        """Check if suggestion is still pending."""
        return self.status == AISuggestionStatus.pending

    @property
    def is_accepted(self) -> bool:
        """Check if suggestion was accepted."""
        return self.status == AISuggestionStatus.accepted

    @property
    def is_rejected(self) -> bool:
        """Check if suggestion was rejected."""
        return self.status == AISuggestionStatus.rejected

    @property
    def has_value_change(self) -> bool:
        """Check if the suggested value differs from current."""
        return self.current_value != self.suggested_value

    @property
    def confidence_percent(self) -> int | None:
        """Return confidence as percentage (0-100)."""
        if self.confidence is None:
            return None
        return int(self.confidence * 100)

    def accept(self) -> None:
        """Mark suggestion as accepted."""
        self.status = AISuggestionStatus.accepted
        self.resolved_at = datetime.utcnow()

    def reject(self) -> None:
        """Mark suggestion as rejected."""
        self.status = AISuggestionStatus.rejected
        self.resolved_at = datetime.utcnow()

    @classmethod
    def create_for_person(
        cls,
        conversation_id: uuid.UUID,
        person_id: uuid.UUID,
        field_name: str,
        suggested_value: str,
        current_value: str | None = None,
        confidence: float | None = None,
        source_url: str | None = None,
    ) -> "AISuggestion":
        """
        Create a suggestion for a person field.

        Args:
            conversation_id: The conversation that generated this
            person_id: UUID of the person
            field_name: Field to update (e.g., "title", "linkedin_url")
            suggested_value: AI-suggested value
            current_value: Current value for comparison
            confidence: AI confidence score (0.0-1.0)
            source_url: Source URL for this information

        Returns:
            New AISuggestion instance
        """
        return cls(
            conversation_id=conversation_id,
            entity_type="person",
            entity_id=person_id,
            field_name=field_name,
            suggested_value=suggested_value,
            current_value=current_value,
            confidence=confidence,
            source_url=source_url,
        )

    @classmethod
    def create_for_organization(
        cls,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        field_name: str,
        suggested_value: str,
        current_value: str | None = None,
        confidence: float | None = None,
        source_url: str | None = None,
    ) -> "AISuggestion":
        """
        Create a suggestion for an organization field.

        Args:
            conversation_id: The conversation that generated this
            organization_id: UUID of the organization
            field_name: Field to update (e.g., "website", "industry")
            suggested_value: AI-suggested value
            current_value: Current value for comparison
            confidence: AI confidence score (0.0-1.0)
            source_url: Source URL for this information

        Returns:
            New AISuggestion instance
        """
        return cls(
            conversation_id=conversation_id,
            entity_type="organization",
            entity_id=organization_id,
            field_name=field_name,
            suggested_value=suggested_value,
            current_value=current_value,
            confidence=confidence,
            source_url=source_url,
        )


# Allowed fields for suggestions per entity type
# These map to actual model fields
PERSON_SUGGESTABLE_FIELDS = [
    "title",
    "linkedin",
    "twitter",
    "website",
    "location",
    "notes",
]

ORGANIZATION_SUGGESTABLE_FIELDS = [
    "website",
    "category",
    "description",
    "notes",
]
