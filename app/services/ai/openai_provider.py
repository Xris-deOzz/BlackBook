"""
OpenAI provider implementation.

Supports GPT-4, GPT-4 Turbo, and GPT-3.5 Turbo models.
"""

from typing import Any, AsyncGenerator

from app.services.ai.base_provider import (
    BaseProvider,
    AIResponse,
    StreamChunk,
    ChatMessage,
    ProviderError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderConnectionError,
)


class OpenAIProvider(BaseProvider):
    """
    OpenAI API provider.

    Uses the official OpenAI Python SDK for chat completions.
    Supports both regular and streaming responses.
    """

    # Available models (most capable first)
    MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ]

    def __init__(self, api_key: str, base_url: str | None = None, **kwargs):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            base_url: Optional custom base URL (for Azure or proxies)
            **kwargs: Additional configuration
        """
        super().__init__(api_key, **kwargs)
        self.base_url = base_url
        self._client = None
        self._async_client = None

    def _get_client(self):
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI

                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url

                self._client = OpenAI(**kwargs)
            except ImportError:
                raise ProviderError(
                    "OpenAI package not installed. Run: pip install openai",
                    provider=self.name,
                )
        return self._client

    def _get_async_client(self):
        """Lazily initialize the async OpenAI client."""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI

                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url

                self._async_client = AsyncOpenAI(**kwargs)
            except ImportError:
                raise ProviderError(
                    "OpenAI package not installed. Run: pip install openai",
                    provider=self.name,
                )
        return self._async_client

    @property
    def name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI"

    @property
    def available_models(self) -> list[str]:
        return self.MODELS.copy()

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    def _convert_messages(self, messages: list[ChatMessage | dict]) -> list[dict[str, Any]]:
        """
        Convert messages to OpenAI format.

        Accepts both ChatMessage objects and plain dictionaries.

        Args:
            messages: List of ChatMessage objects or dicts

        Returns:
            List of message dictionaries in OpenAI format
        """
        result = []
        for msg in messages:
            # Handle both ChatMessage objects and dicts
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                name = msg.get("name")
                tool_call_id = msg.get("tool_call_id")
                tool_calls = msg.get("tool_calls")
            else:
                role = msg.role
                content = msg.content
                name = msg.name if hasattr(msg, 'name') else None
                tool_call_id = msg.tool_call_id if hasattr(msg, 'tool_call_id') else None
                tool_calls = None

            message_dict = {"role": role, "content": content}
            if name:
                message_dict["name"] = name
            if tool_call_id:
                message_dict["tool_call_id"] = tool_call_id
            if tool_calls:
                message_dict["tool_calls"] = tool_calls

            result.append(message_dict)
        return result

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AIResponse:
        """Send a chat completion request to OpenAI."""
        try:
            from openai import APIError, AuthenticationError, RateLimitError

            client = self._get_async_client()
            model = model or self.default_model

            # Build request parameters
            params = {
                "model": model,
                "messages": self._convert_messages(messages),
                "temperature": temperature,
            }
            if max_tokens:
                params["max_tokens"] = max_tokens

            # Add tools if provided
            if tools:
                params["tools"] = tools
                # Explicitly tell OpenAI it can choose to use tools
                params["tool_choice"] = "auto"

            # Add any additional parameters
            params.update(kwargs)

            # Make the request
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"OpenAI request - model: {model}, tools count: {len(tools) if tools else 0}")
            if tools:
                tool_names = [t.get('function', {}).get('name') for t in tools]
                logger.info(f"OpenAI tools being sent: {tool_names}")

            response = await client.chat.completions.create(**params)

            # Log the response for debugging
            choice = response.choices[0]
            logger.info(f"OpenAI response - finish_reason: {choice.finish_reason}, has_tool_calls: {bool(choice.message.tool_calls)}")

            # Extract response data
            choice = response.choices[0]
            usage = response.usage

            return AIResponse(
                content=choice.message.content or "",
                model=response.model,
                tokens_in=usage.prompt_tokens if usage else 0,
                tokens_out=usage.completion_tokens if usage else 0,
                finish_reason=choice.finish_reason,
                tool_calls=self._extract_tool_calls(choice.message) if hasattr(choice.message, 'tool_calls') else None,
            )

        except AuthenticationError as e:
            raise ProviderAuthError(
                f"Invalid API key: {e}",
                provider=self.name,
            )
        except RateLimitError as e:
            raise ProviderRateLimitError(
                f"Rate limit exceeded: {e}",
                provider=self.name,
            )
        except APIError as e:
            raise ProviderError(
                f"API error: {e}",
                provider=self.name,
            )
        except Exception as e:
            raise ProviderError(
                f"Unexpected error: {e}",
                provider=self.name,
            )

    async def stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a chat completion response from OpenAI."""
        try:
            from openai import APIError, AuthenticationError, RateLimitError

            client = self._get_async_client()
            model = model or self.default_model

            # Build request parameters
            params = {
                "model": model,
                "messages": self._convert_messages(messages),
                "temperature": temperature,
                "stream": True,
            }
            if max_tokens:
                params["max_tokens"] = max_tokens

            # Add tools if provided
            if tools:
                params["tools"] = tools

            params.update(kwargs)

            # Create streaming response
            stream = await client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    delta = choice.delta

                    content = delta.content if delta.content else ""
                    is_final = choice.finish_reason is not None

                    yield StreamChunk(
                        content=content,
                        is_final=is_final,
                        finish_reason=choice.finish_reason,
                    )

        except AuthenticationError as e:
            raise ProviderAuthError(
                f"Invalid API key: {e}",
                provider=self.name,
            )
        except RateLimitError as e:
            raise ProviderRateLimitError(
                f"Rate limit exceeded: {e}",
                provider=self.name,
            )
        except APIError as e:
            raise ProviderError(
                f"API error: {e}",
                provider=self.name,
            )
        except Exception as e:
            raise ProviderError(
                f"Unexpected error: {e}",
                provider=self.name,
            )

    def count_tokens(self, text: str, model: str | None = None) -> int:
        """Count tokens using tiktoken."""
        try:
            import tiktoken

            model = model or self.default_model

            # Get the encoding for the model
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fall back to cl100k_base for unknown models
                encoding = tiktoken.get_encoding("cl100k_base")

            return len(encoding.encode(text))

        except ImportError:
            # Rough estimate if tiktoken not installed
            # Average ~4 chars per token for English
            return len(text) // 4

    async def validate_key(self) -> bool:
        """Validate API key by listing models."""
        try:
            client = self._get_async_client()
            # Make a minimal API call to verify the key
            await client.models.list()
            return True
        except Exception:
            return False

    def _extract_tool_calls(self, message) -> list[dict[str, Any]] | None:
        """Extract tool calls from message if present."""
        if not hasattr(message, 'tool_calls') or not message.tool_calls:
            return None

        tool_calls = []
        for tc in message.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            })
        return tool_calls
