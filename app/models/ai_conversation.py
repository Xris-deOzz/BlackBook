"""
AIConversation model for storing AI chat conversation metadata.

Each conversation can optionally be linked to a Person or Organization,
providing context for the AI research assistant.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.organization import Organization
    from app.models.ai_message import AIMessage
    from app.models.ai_suggestion import AISuggestion


class AIConversation(Base):
    """
    AI chat conversation metadata.

    Stores conversation history for the AI research assistant.
    Conversations can be standalone or linked to a specific
    Person or Organization for contextual research.

    Attributes:
        person_id: Optional link to a Person being researched
        organization_id: Optional link to an Organization being researched
        title: Conversation title (auto-generated or user-defined)
        provider_name: AI provider used (e.g., "openai", "anthropic")
        model_name: Specific model used (e.g., "gpt-4o", "claude-3-sonnet")
    """

    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional link to Person being researched",
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional link to Organization being researched",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Conversation",
        comment="Conversation title",
    )
    provider_name: Mapped[str | None] = mapped_column(
        String(50),
        comment="AI provider used (e.g., openai, anthropic)",
    )
    model_name: Mapped[str | None] = mapped_column(
        String(100),
        comment="Specific model used (e.g., gpt-4o, claude-3-sonnet)",
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
    person: Mapped["Person | None"] = orm_relationship(
        "Person",
        back_populates="ai_conversations",
    )
    organization: Mapped["Organization | None"] = orm_relationship(
        "Organization",
        back_populates="ai_conversations",
    )
    messages: Mapped[list["AIMessage"]] = orm_relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )
    suggestions: Mapped[list["AISuggestion"]] = orm_relationship(
        "AISuggestion",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        context = ""
        if self.person_id:
            context = f", person_id={self.person_id}"
        elif self.organization_id:
            context = f", org_id={self.organization_id}"
        return f"<AIConversation(title={self.title!r}{context})>"

    @property
    def message_count(self) -> int:
        """Return the number of messages in this conversation."""
        return len(self.messages)

    @property
    def entity_type(self) -> str | None:
        """Return the type of linked entity, if any."""
        if self.person_id:
            return "person"
        elif self.organization_id:
            return "organization"
        return None

    @property
    def entity_id(self) -> uuid.UUID | None:
        """Return the ID of the linked entity, if any."""
        return self.person_id or self.organization_id

    def update_title_from_first_message(self) -> None:
        """
        Auto-generate title from first user message.

        Takes the first 50 characters of the first user message
        as the conversation title.
        """
        for msg in self.messages:
            if msg.role.value == "user" and msg.content:
                # Truncate to 50 chars and add ellipsis if needed
                content = msg.content.strip()
                if len(content) > 50:
                    self.title = content[:47] + "..."
                else:
                    self.title = content
                break
