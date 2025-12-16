"""
AIMessage model for storing individual messages within AI conversations.

Stores user messages, assistant responses, system prompts, and tool results
with optional token usage tracking and source citations.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_conversation import AIConversation


class AIMessageRole(str, PyEnum):
    """Role of the message sender."""

    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class AIMessage(Base):
    """
    Individual message within an AI conversation.

    Stores the content, role, token usage, and optional tool calls
    or source citations for each message in a conversation.

    Attributes:
        conversation_id: Foreign key to the parent conversation
        role: Message role (user, assistant, system, tool)
        content: Message text content
        tokens_in: Input tokens used (for billing tracking)
        tokens_out: Output tokens used (for billing tracking)
        tool_calls_json: JSON array of tool calls made by assistant
        sources_json: JSON array of source citations
    """

    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[AIMessageRole] = mapped_column(
        Enum(AIMessageRole, name="ai_message_role", create_type=False),
        nullable=False,
        comment="Message role (user, assistant, system, tool)",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message text content",
    )
    tokens_in: Mapped[int | None] = mapped_column(
        Integer,
        comment="Input tokens used (for API calls)",
    )
    tokens_out: Mapped[int | None] = mapped_column(
        Integer,
        comment="Output tokens generated (for API calls)",
    )
    tool_calls_json: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="Tool calls made by assistant (JSON array)",
    )
    sources_json: Mapped[list | None] = mapped_column(
        JSONB,
        comment="Source citations (JSON array)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    conversation: Mapped["AIConversation"] = orm_relationship(
        "AIConversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        content_preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"<AIMessage(role={self.role.value}, content={content_preview!r})>"

    @property
    def total_tokens(self) -> int:
        """Return total tokens used (input + output)."""
        return (self.tokens_in or 0) + (self.tokens_out or 0)

    @property
    def has_tool_calls(self) -> bool:
        """Check if this message contains tool calls."""
        return bool(self.tool_calls_json)

    @property
    def has_sources(self) -> bool:
        """Check if this message has source citations."""
        return bool(self.sources_json)

    def get_tool_calls(self) -> list[dict[str, Any]]:
        """
        Return parsed tool calls from JSON.

        Returns:
            List of tool call dictionaries, or empty list if none
        """
        if not self.tool_calls_json:
            return []
        if isinstance(self.tool_calls_json, list):
            return self.tool_calls_json
        return self.tool_calls_json.get("calls", [])

    def get_sources(self) -> list[dict[str, Any]]:
        """
        Return parsed source citations from JSON.

        Returns:
            List of source dictionaries with keys like:
            - title: Source title
            - url: Source URL
            - snippet: Relevant excerpt
        """
        if not self.sources_json:
            return []
        return self.sources_json

    def add_source(self, title: str, url: str, snippet: str | None = None) -> None:
        """
        Add a source citation to this message.

        Args:
            title: Source title or page name
            url: Source URL
            snippet: Optional relevant excerpt from source
        """
        if self.sources_json is None:
            self.sources_json = []

        self.sources_json.append({
            "title": title,
            "url": url,
            "snippet": snippet,
        })

    @classmethod
    def create_user_message(
        cls,
        conversation_id: uuid.UUID,
        content: str,
    ) -> "AIMessage":
        """Create a user message."""
        return cls(
            conversation_id=conversation_id,
            role=AIMessageRole.user,
            content=content,
        )

    @classmethod
    def create_assistant_message(
        cls,
        conversation_id: uuid.UUID,
        content: str,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        tool_calls: list[dict] | None = None,
        sources: list[dict] | None = None,
    ) -> "AIMessage":
        """Create an assistant response message."""
        return cls(
            conversation_id=conversation_id,
            role=AIMessageRole.assistant,
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tool_calls_json={"calls": tool_calls} if tool_calls else None,
            sources_json=sources,
        )

    @classmethod
    def create_system_message(
        cls,
        conversation_id: uuid.UUID,
        content: str,
    ) -> "AIMessage":
        """Create a system prompt message."""
        return cls(
            conversation_id=conversation_id,
            role=AIMessageRole.system,
            content=content,
        )

    @classmethod
    def create_tool_message(
        cls,
        conversation_id: uuid.UUID,
        content: str,
        tool_name: str | None = None,
    ) -> "AIMessage":
        """Create a tool result message."""
        tool_calls = [{"name": tool_name, "result": content}] if tool_name else None
        return cls(
            conversation_id=conversation_id,
            role=AIMessageRole.tool,
            content=content,
            tool_calls_json={"calls": tool_calls} if tool_calls else None,
        )
