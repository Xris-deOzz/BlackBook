"""
AIQuickPrompt model for storing customizable quick action prompts.

These are the quick action buttons shown in the AI sidebar that users
can click to quickly send common prompts.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Boolean, DateTime, Integer, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.models.base import Base


class PromptEntityType(str, PyEnum):
    """Entity types that prompts can apply to."""
    person = "person"
    organization = "organization"
    both = "both"  # Shows for both entity types


class AIQuickPrompt(Base):
    """
    Customizable quick action prompts for the AI sidebar.

    Users can edit these to customize what quick action buttons
    appear in the AI research sidebar.

    Attributes:
        label: Short button text (e.g., "Recent news")
        prompt_text: Full prompt sent to AI when clicked
        entity_type: Which entity types this prompt applies to
        display_order: Order in which prompts are displayed
        is_active: Whether this prompt is currently enabled
    """

    __tablename__ = "ai_quick_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Short button text displayed to user",
    )
    prompt_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full prompt text sent to AI",
    )
    entity_type: Mapped[PromptEntityType] = mapped_column(
        Enum(PromptEntityType, name="prompt_entity_type", create_type=False),
        default=PromptEntityType.both,
        comment="Which entity types this prompt applies to",
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Order in which prompts are displayed",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Whether this prompt is currently enabled",
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

    def __repr__(self) -> str:
        return f"<AIQuickPrompt(label={self.label!r}, type={self.entity_type.value})>"

    @classmethod
    def get_prompts_for_entity(
        cls,
        db: Session,
        entity_type: str,
    ) -> list["AIQuickPrompt"]:
        """
        Get active prompts for a specific entity type.

        Args:
            db: Database session
            entity_type: 'person' or 'organization'

        Returns:
            List of active prompts for the entity type, ordered by display_order
        """
        entity_enum = PromptEntityType(entity_type) if entity_type in ("person", "organization") else None

        return (
            db.query(cls)
            .filter(cls.is_active == True)
            .filter(
                (cls.entity_type == PromptEntityType.both) |
                (cls.entity_type == entity_enum)
            )
            .order_by(cls.display_order, cls.created_at)
            .all()
        )

    @classmethod
    def get_all_prompts(cls, db: Session) -> list["AIQuickPrompt"]:
        """
        Get all prompts (for settings page).

        Args:
            db: Database session

        Returns:
            List of all prompts ordered by display_order
        """
        return (
            db.query(cls)
            .order_by(cls.display_order, cls.created_at)
            .all()
        )

    @classmethod
    def seed_defaults(cls, db: Session) -> list["AIQuickPrompt"]:
        """
        Create default prompts if none exist.

        Args:
            db: Database session

        Returns:
            List of created prompts (empty if prompts already exist)
        """
        existing = db.query(cls).first()
        if existing:
            return []

        defaults = [
            cls(
                label="Recent news",
                prompt_text="Find recent news and articles about this {entity_type}",
                entity_type=PromptEntityType.both,
                display_order=1,
            ),
            cls(
                label="Podcasts",
                prompt_text="Search for podcast appearances or interviews featuring this {entity_type}",
                entity_type=PromptEntityType.both,
                display_order=2,
            ),
            cls(
                label="Background",
                prompt_text="Provide a comprehensive background summary on this {entity_type}",
                entity_type=PromptEntityType.both,
                display_order=3,
            ),
            cls(
                label="Suggest updates",
                prompt_text="Suggest profile updates based on online research",
                entity_type=PromptEntityType.both,
                display_order=4,
            ),
        ]

        for prompt in defaults:
            db.add(prompt)

        db.flush()
        return defaults

    def to_dict(self) -> dict:
        """Return prompt as a dictionary."""
        return {
            "id": str(self.id),
            "label": self.label,
            "prompt_text": self.prompt_text,
            "entity_type": self.entity_type.value,
            "display_order": self.display_order,
            "is_active": self.is_active,
        }
