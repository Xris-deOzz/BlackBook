"""
Tests for AI base provider and response dataclasses.
"""

import pytest
from dataclasses import fields

from app.services.ai.base_provider import (
    AIResponse,
    StreamChunk,
    BaseProvider,
    ProviderError,
    ProviderAuthError,
    ProviderRateLimitError,
)


class TestAIResponse:
    """Test AIResponse dataclass."""

    def test_create_basic_response(self):
        """Test creating a basic AIResponse."""
        response = AIResponse(
            content="Hello, world!",
            tokens_in=10,
            tokens_out=5,
            model="gpt-4",
        )
        assert response.content == "Hello, world!"
        assert response.tokens_in == 10
        assert response.tokens_out == 5
        assert response.model == "gpt-4"
        assert response.tool_calls is None
        assert response.finish_reason is None

    def test_create_response_with_tool_calls(self):
        """Test creating AIResponse with tool calls."""
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": "{}"}}
        ]
        response = AIResponse(
            content="",
            tokens_in=10,
            tokens_out=5,
            model="gpt-4",
            tool_calls=tool_calls,
        )
        assert response.tool_calls == tool_calls

    def test_create_response_with_finish_reason(self):
        """Test creating AIResponse with finish_reason."""
        response = AIResponse(
            content="Complete response.",
            tokens_in=10,
            tokens_out=5,
            model="gpt-4",
            finish_reason="stop",
        )
        assert response.finish_reason == "stop"

    def test_response_fields(self):
        """Test that AIResponse has expected fields."""
        field_names = [f.name for f in fields(AIResponse)]
        expected_fields = ["content", "tokens_in", "tokens_out", "model", "tool_calls", "finish_reason"]
        for field in expected_fields:
            assert field in field_names

    def test_total_tokens_property(self):
        """Test total_tokens property."""
        response = AIResponse(
            content="Hello",
            model="gpt-4",
            tokens_in=10,
            tokens_out=5,
        )
        assert response.total_tokens == 15


class TestStreamChunk:
    """Test StreamChunk dataclass."""

    def test_create_basic_chunk(self):
        """Test creating a basic StreamChunk."""
        chunk = StreamChunk(content="Hello")
        assert chunk.content == "Hello"
        assert chunk.is_final is False
        assert chunk.tokens_in is None
        assert chunk.tokens_out is None
        assert chunk.finish_reason is None

    def test_create_final_chunk(self):
        """Test creating a final StreamChunk with token counts."""
        chunk = StreamChunk(
            content="",
            is_final=True,
            tokens_in=100,
            tokens_out=50,
            finish_reason="stop",
        )
        assert chunk.is_final is True
        assert chunk.tokens_in == 100
        assert chunk.tokens_out == 50
        assert chunk.finish_reason == "stop"

    def test_chunk_fields(self):
        """Test that StreamChunk has expected fields."""
        field_names = [f.name for f in fields(StreamChunk)]
        expected_fields = ["content", "is_final", "tokens_in", "tokens_out", "finish_reason"]
        for field in expected_fields:
            assert field in field_names


class TestProviderExceptions:
    """Test provider exception classes."""

    def test_provider_error(self):
        """Test ProviderError exception."""
        error = ProviderError("Something went wrong", provider="openai")
        assert "Something went wrong" in str(error)
        assert "openai" in str(error)
        assert isinstance(error, Exception)

    def test_provider_error_with_default_provider(self):
        """Test ProviderError with default unknown provider."""
        error = ProviderError("Something went wrong")
        assert "Something went wrong" in str(error)
        assert "unknown" in str(error)

    def test_provider_auth_error(self):
        """Test ProviderAuthError exception."""
        error = ProviderAuthError("Invalid API key", provider="anthropic")
        assert "Invalid API key" in str(error)
        assert isinstance(error, ProviderError)

    def test_provider_rate_limit_error(self):
        """Test ProviderRateLimitError exception."""
        error = ProviderRateLimitError("Rate limit exceeded", provider="openai", retry_after=60)
        assert "Rate limit exceeded" in str(error)
        assert isinstance(error, ProviderError)
        assert error.retry_after == 60

    def test_exception_inheritance(self):
        """Test that auth and rate limit errors inherit from ProviderError."""
        with pytest.raises(ProviderError):
            raise ProviderAuthError("Auth failed", provider="test")

        with pytest.raises(ProviderError):
            raise ProviderRateLimitError("Rate limited", provider="test")


class TestBaseProviderAbstract:
    """Test that BaseProvider is abstract and cannot be instantiated."""

    def test_cannot_instantiate_base_provider(self):
        """Test that BaseProvider cannot be directly instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseProvider(api_key="test")

    def test_base_provider_has_abstract_methods(self):
        """Test that BaseProvider defines the expected abstract methods."""
        abstract_methods = BaseProvider.__abstractmethods__
        expected_methods = {"chat", "stream", "count_tokens", "validate_key", "available_models"}
        assert expected_methods.issubset(abstract_methods)


class TestConcreteProviderImplementation:
    """Test creating a concrete provider implementation."""

    def test_can_create_concrete_implementation(self):
        """Test that a concrete implementation can be created."""
        from typing import AsyncGenerator

        class MockProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "mock"

            @property
            def display_name(self) -> str:
                return "Mock Provider"

            async def chat(self, messages, model=None, **kwargs):
                return AIResponse(
                    content="Mock response",
                    tokens_in=10,
                    tokens_out=5,
                    model=model or "mock-model",
                )

            async def stream(self, messages, model=None, **kwargs) -> AsyncGenerator[StreamChunk, None]:
                yield StreamChunk(content="Mock ", is_final=False)
                yield StreamChunk(content="response", is_final=True, tokens_in=10, tokens_out=5)

            def count_tokens(self, text, model=None):
                return len(text.split())

            async def validate_key(self) -> bool:
                return True

            @property
            def available_models(self):
                return ["mock-model"]

        provider = MockProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.name == "mock"
        assert provider.display_name == "Mock Provider"
        assert provider.available_models == ["mock-model"]
        assert provider.count_tokens("Hello world test", None) == 3
