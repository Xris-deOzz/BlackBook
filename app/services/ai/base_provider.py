"""
Base provider abstract class for AI integrations.

Defines the common interface that all AI providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator


# Custom exceptions
class ProviderError(Exception):
    """Base exception for AI provider errors."""

    def __init__(self, message: str, provider: str = "unknown"):
        self.message = message
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderAuthError(ProviderError):
    """Raised when API key is invalid or authentication fails."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, provider: str, retry_after: int | None = None):
        super().__init__(message, provider)
        self.retry_after = retry_after


class ProviderConnectionError(ProviderError):
    """Raised when connection to provider fails."""

    pass


# Response data classes
@dataclass
class AIResponse:
    """Response from an AI provider chat completion."""

    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    @property
    def total_tokens(self) -> int:
        """Total tokens used in this response."""
        return self.tokens_in + self.tokens_out


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""

    content: str
    is_final: bool = False
    tokens_in: int | None = None
    tokens_out: int | None = None
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class ChatMessage:
    """A message in a chat conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: str | None = None  # For tool messages
    tool_call_id: str | None = None  # For tool responses


class BaseProvider(ABC):
    """
    Abstract base class for AI providers.

    All AI providers (OpenAI, Anthropic, Google, etc.) must implement
    this interface to work with the chat system.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize the provider.

        Args:
            api_key: The API key for authentication
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self._config = kwargs

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return the display name (e.g., 'OpenAI', 'Claude')."""
        pass

    @property
    @abstractmethod
    def available_models(self) -> list[str]:
        """Return list of available model names."""
        pass

    @property
    def default_model(self) -> str:
        """Return the default model for this provider."""
        models = self.available_models
        return models[0] if models else ""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AIResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of chat messages
            model: Model to use (defaults to provider's default)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            AIResponse with the completion

        Raises:
            ProviderError: If the request fails
            ProviderAuthError: If authentication fails
            ProviderRateLimitError: If rate limit is exceeded
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a chat completion response.

        Args:
            messages: List of chat messages
            model: Model to use (defaults to provider's default)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Yields:
            StreamChunk objects as response tokens arrive

        Raises:
            ProviderError: If the request fails
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str, model: str | None = None) -> int:
        """
        Count the number of tokens in the given text.

        Args:
            text: The text to count tokens for
            model: Model to use for tokenization (affects count)

        Returns:
            Number of tokens
        """
        pass

    @abstractmethod
    async def validate_key(self) -> bool:
        """
        Validate that the API key is working.

        Makes a minimal API call to verify authentication.

        Returns:
            True if key is valid, False otherwise
        """
        pass

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """
        Convert ChatMessage objects to provider-specific format.

        Default implementation returns OpenAI-compatible format.
        Override in subclasses if provider uses different format.

        Args:
            messages: List of ChatMessage objects

        Returns:
            List of message dictionaries in provider format
        """
        result = []
        for msg in messages:
            message_dict = {"role": msg.role, "content": msg.content}
            if msg.name:
                message_dict["name"] = msg.name
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            result.append(message_dict)
        return result
