"""
AI Services module for Perun's BlackBook.

Provides multi-provider AI chat capabilities with support for:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Ollama (local models - future)

Key Components:
- BaseProvider: Abstract base class for AI providers
- ProviderFactory: Factory for creating provider instances
- ChatService: Main service for chat operations
- ContextBuilder: Builds AI context from CRM data
- PrivacyFilter: Strips sensitive data before sending to AI
"""

from app.services.ai.base_provider import (
    BaseProvider,
    AIResponse,
    StreamChunk,
    ProviderError,
    ProviderAuthError,
    ProviderRateLimitError,
)
from app.services.ai.provider_factory import ProviderFactory
from app.services.ai.chat_service import ChatService, get_chat_service
from app.services.ai.context_builder import ContextBuilder
from app.services.ai.privacy_filter import (
    PrivacyFilter,
    strip_sensitive_data,
    strip_emails,
    strip_phone_numbers,
    filter_person_for_ai,
    filter_organization_for_ai,
)
from app.services.ai.tools import (
    Tool,
    ToolRegistry,
    ToolResult,
    ToolExecutor,
    get_default_tools,
    SEARCH_TOOLS,
    CRM_TOOLS,
)

__all__ = [
    # Base classes
    "BaseProvider",
    "ProviderFactory",
    # Response types
    "AIResponse",
    "StreamChunk",
    # Exceptions
    "ProviderError",
    "ProviderAuthError",
    "ProviderRateLimitError",
    # Chat service
    "ChatService",
    "get_chat_service",
    # Context building
    "ContextBuilder",
    # Privacy
    "PrivacyFilter",
    "strip_sensitive_data",
    "strip_emails",
    "strip_phone_numbers",
    "filter_person_for_ai",
    "filter_organization_for_ai",
    # Tools
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "ToolExecutor",
    "get_default_tools",
    "SEARCH_TOOLS",
    "CRM_TOOLS",
]
