"""
Pydantic models for AI service operations.

These models are used for request/response validation and serialization.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessageSchema(BaseModel):
    """Schema for a chat message."""

    role: str = Field(..., description="Message role: user, assistant, system, tool")
    content: str = Field(..., description="Message content")
    name: str | None = Field(None, description="Name for tool messages")
    tool_call_id: str | None = Field(None, description="Tool call ID for responses")

    class Config:
        from_attributes = True


class ToolCallSchema(BaseModel):
    """Schema for an AI tool call."""

    id: str = Field(..., description="Unique tool call ID")
    type: str = Field(default="function", description="Tool type")
    name: str = Field(..., description="Tool/function name")
    arguments: dict[str, Any] | str = Field(..., description="Tool arguments")


class ToolResultSchema(BaseModel):
    """Schema for a tool execution result."""

    tool_call_id: str = Field(..., description="ID of the tool call this responds to")
    result: str | dict[str, Any] = Field(..., description="Tool execution result")
    error: str | None = Field(None, description="Error message if tool failed")


class SourceSchema(BaseModel):
    """Schema for a source citation."""

    title: str = Field(..., description="Source title")
    url: str = Field(..., description="Source URL")
    snippet: str | None = Field(None, description="Relevant excerpt")


class AIResponseSchema(BaseModel):
    """Schema for an AI response."""

    content: str = Field(..., description="Response content")
    model: str = Field(..., description="Model used")
    tokens_in: int = Field(default=0, description="Input tokens")
    tokens_out: int = Field(default=0, description="Output tokens")
    finish_reason: str | None = Field(None, description="Why generation stopped")
    tool_calls: list[ToolCallSchema] | None = Field(None, description="Tool calls")
    sources: list[SourceSchema] | None = Field(None, description="Source citations")


class StreamChunkSchema(BaseModel):
    """Schema for a streaming response chunk."""

    content: str = Field(..., description="Content chunk")
    is_final: bool = Field(default=False, description="Is this the final chunk")
    tokens_in: int | None = Field(None, description="Total input tokens (final only)")
    tokens_out: int | None = Field(None, description="Total output tokens (final only)")
    finish_reason: str | None = Field(None, description="Finish reason (final only)")


# Request schemas

class SendMessageRequest(BaseModel):
    """Request to send a message."""

    content: str = Field(..., min_length=1, description="Message content")
    conversation_id: UUID | None = Field(None, description="Existing conversation ID")
    person_id: UUID | None = Field(None, description="Person context")
    organization_id: UUID | None = Field(None, description="Organization context")
    model: str | None = Field(None, description="Model to use")
    provider: str | None = Field(None, description="Provider to use")


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    title: str | None = Field(None, description="Conversation title")
    person_id: UUID | None = Field(None, description="Person context")
    organization_id: UUID | None = Field(None, description="Organization context")
    provider: str | None = Field(None, description="Provider to use")
    model: str | None = Field(None, description="Model to use")


class UpdateConversationRequest(BaseModel):
    """Request to update a conversation."""

    title: str | None = Field(None, description="New title")


class SaveAPIKeyRequest(BaseModel):
    """Request to save an API key."""

    provider_id: UUID = Field(..., description="Provider UUID")
    api_key: str = Field(..., min_length=1, description="API key value")
    label: str | None = Field(None, description="Optional label")


class TestAPIKeyRequest(BaseModel):
    """Request to test an API key."""

    provider_name: str = Field(..., description="Provider name (openai, anthropic, etc.)")
    api_key: str = Field(..., min_length=1, description="API key to test")


class UpdateDataAccessRequest(BaseModel):
    """Request to update data access settings."""

    allow_notes: bool | None = Field(None)
    allow_tags: bool | None = Field(None)
    allow_interactions: bool | None = Field(None)
    allow_linkedin: bool | None = Field(None)
    auto_apply_suggestions: bool | None = Field(None)


# Response schemas

class ProviderInfoSchema(BaseModel):
    """Schema for provider information."""

    id: UUID
    name: str
    api_type: str
    is_local: bool
    is_active: bool
    has_valid_key: bool
    models: list[str]


class ConversationSchema(BaseModel):
    """Schema for a conversation."""

    id: UUID
    title: str
    person_id: UUID | None
    organization_id: UUID | None
    provider_name: str | None
    model_name: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageSchema(BaseModel):
    """Schema for a message."""

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    tokens_in: int | None
    tokens_out: int | None
    tool_calls: list[dict] | None
    sources: list[dict] | None
    created_at: datetime

    class Config:
        from_attributes = True


class SuggestionSchema(BaseModel):
    """Schema for an AI suggestion."""

    id: UUID
    conversation_id: UUID
    entity_type: str
    entity_id: UUID
    field_name: str
    current_value: str | None
    suggested_value: str
    confidence: float | None
    source_url: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None

    class Config:
        from_attributes = True


class DataAccessSettingsSchema(BaseModel):
    """Schema for data access settings."""

    allow_notes: bool
    allow_tags: bool
    allow_interactions: bool
    allow_linkedin: bool
    auto_apply_suggestions: bool

    class Config:
        from_attributes = True


class APIKeyStatusSchema(BaseModel):
    """Schema for API key status."""

    id: UUID
    provider_id: UUID
    label: str | None
    is_valid: bool | None
    last_tested: datetime | None
    masked_key: str
    created_at: datetime

    class Config:
        from_attributes = True
