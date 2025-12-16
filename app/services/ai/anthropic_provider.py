"""
Anthropic (Claude) provider implementation.

Supports Claude 3 family models: Opus, Sonnet, and Haiku.
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
)


class AnthropicProvider(BaseProvider):
    """
    Anthropic API provider for Claude models.

    Uses the official Anthropic Python SDK for chat completions.
    Supports both regular and streaming responses.
    """

    # Available models (most capable first)
    # Use "latest" aliases for models that support them
    MODELS = [
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-opus-latest",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]

    # Model aliases for user convenience
    MODEL_ALIASES = {
        "claude-4-sonnet": "claude-sonnet-4-20250514",
        "claude-3-opus": "claude-3-opus-latest",
        "claude-3-sonnet": "claude-3-5-sonnet-latest",
        "claude-3-haiku": "claude-3-haiku-20240307",
        "claude-3.5-sonnet": "claude-3-5-sonnet-latest",
        "claude-3.5-haiku": "claude-3-5-haiku-latest",
    }

    # Cheapest model for key validation
    VALIDATION_MODEL = "claude-3-haiku-20240307"

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            **kwargs: Additional configuration
        """
        super().__init__(api_key, **kwargs)
        self._client = None
        self._async_client = None

    def _get_client(self):
        """Lazily initialize the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise ProviderError(
                    "Anthropic package not installed. Run: pip install anthropic",
                    provider=self.name,
                )
        return self._client

    def _get_async_client(self):
        """Lazily initialize the async Anthropic client."""
        if self._async_client is None:
            try:
                from anthropic import AsyncAnthropic

                self._async_client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ProviderError(
                    "Anthropic package not installed. Run: pip install anthropic",
                    provider=self.name,
                )
        return self._async_client

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def display_name(self) -> str:
        return "Claude"

    @property
    def available_models(self) -> list[str]:
        return self.MODELS.copy()

    @property
    def default_model(self) -> str:
        return "claude-3-haiku-20240307"

    def _resolve_model(self, model: str | None) -> str:
        """Resolve model aliases to full model names."""
        if model is None:
            return self.default_model
        return self.MODEL_ALIASES.get(model, model)

    def _convert_messages(self, messages: list[ChatMessage | dict]) -> tuple[str | None, list[dict]]:
        """
        Convert messages to Anthropic format.

        Anthropic requires system message as separate parameter.
        Accepts both ChatMessage objects and plain dictionaries.

        Anthropic has specific requirements for tool use conversations:
        - Assistant messages with tool calls have content as list of blocks
        - Tool results are sent as user messages with tool_result content blocks

        Returns:
            Tuple of (system_prompt, messages)
        """
        system_prompt = None
        converted = []

        for msg in messages:
            # Handle both ChatMessage objects and dicts
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                tool_calls = msg.get("tool_calls")
            else:
                role = msg.role
                content = msg.content
                tool_calls = None

            if role == "system":
                # Anthropic takes system message as separate parameter
                system_prompt = content
            elif role == "tool":
                # Tool results should be user messages with tool_result content blocks
                # This shouldn't happen as we handle tool results specially
                role = "user"
                converted.append({
                    "role": role,
                    "content": content,
                })
            elif role == "assistant":
                # Assistant messages may have tool_use blocks
                # If content is already a list (tool_use blocks), use it directly
                if isinstance(content, list):
                    converted.append({
                        "role": "assistant",
                        "content": content,
                    })
                elif tool_calls:
                    # Build content blocks from text + tool calls
                    content_blocks = []
                    if content:
                        content_blocks.append({"type": "text", "text": content})
                    # tool_calls from our system are already in Anthropic format
                    for tc in tool_calls:
                        if isinstance(tc, dict) and tc.get("type") == "tool_use":
                            content_blocks.append(tc)
                        elif isinstance(tc, dict) and "name" in tc and "input" in tc:
                            # Our internal format
                            content_blocks.append({
                                "type": "tool_use",
                                "id": tc.get("id", ""),
                                "name": tc["name"],
                                "input": tc["input"],
                            })
                    converted.append({
                        "role": "assistant",
                        "content": content_blocks if content_blocks else content,
                    })
                else:
                    converted.append({
                        "role": "assistant",
                        "content": content,
                    })
            else:
                # User messages - content may be a list of tool_result blocks
                if isinstance(content, list):
                    # This is likely tool results - use as-is
                    converted.append({
                        "role": "user",
                        "content": content,
                    })
                else:
                    converted.append({
                        "role": "user",
                        "content": content,
                    })

        return system_prompt, converted

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AIResponse:
        """Send a chat completion request to Anthropic."""
        import logging
        logger = logging.getLogger(__name__)

        try:
            from anthropic import APIError, AuthenticationError, RateLimitError

            client = self._get_async_client()
            model = self._resolve_model(model)
            system_prompt, converted_messages = self._convert_messages(messages)

            logger.info(f"Anthropic chat: model={model}, tools={len(tools) if tools else 0}, messages={len(converted_messages)}")

            # Build request parameters
            params = {
                "model": model,
                "messages": converted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,  # Anthropic requires max_tokens
            }

            if system_prompt:
                params["system"] = system_prompt

            # Add tools if provided (Anthropic format)
            if tools:
                params["tools"] = tools

            # Make the request
            logger.info(f"Calling Anthropic API...")
            response = await client.messages.create(**params)
            logger.info(f"Anthropic response: stop_reason={response.stop_reason}, content_blocks={len(response.content) if response.content else 0}")

            # Extract response data
            content = ""
            tool_calls = self._extract_tool_calls(response.content) if response.content else None

            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
                    if hasattr(block, 'type') and block.type == 'tool_use':
                        logger.info(f"Tool use block: name={block.name}, id={block.id}")

            logger.info(f"Extracted: content_len={len(content)}, tool_calls={len(tool_calls) if tool_calls else 0}")

            return AIResponse(
                content=content,
                model=response.model,
                tokens_in=response.usage.input_tokens if response.usage else 0,
                tokens_out=response.usage.output_tokens if response.usage else 0,
                finish_reason=response.stop_reason,
                tool_calls=tool_calls,
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
        """Stream a chat completion response from Anthropic."""
        try:
            from anthropic import APIError, AuthenticationError, RateLimitError

            client = self._get_async_client()
            model = self._resolve_model(model)
            system_prompt, converted_messages = self._convert_messages(messages)

            # Build request parameters
            params = {
                "model": model,
                "messages": converted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }

            if system_prompt:
                params["system"] = system_prompt

            # Add tools if provided (Anthropic format)
            if tools:
                params["tools"] = tools

            # Create streaming response
            async with client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(
                        content=text,
                        is_final=False,
                    )

                # Get final message for usage stats
                final_message = await stream.get_final_message()
                yield StreamChunk(
                    content="",
                    is_final=True,
                    tokens_in=final_message.usage.input_tokens if final_message.usage else None,
                    tokens_out=final_message.usage.output_tokens if final_message.usage else None,
                    finish_reason=final_message.stop_reason,
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
        """
        Estimate token count for Anthropic models.

        Anthropic doesn't provide a public tokenizer, so we estimate.
        Claude uses a similar tokenization to GPT models.
        """
        try:
            # Try to use tiktoken for estimation
            import tiktoken

            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # Rough estimate: ~4 chars per token
            return len(text) // 4

    async def validate_key(self) -> bool:
        """Validate API key by making a minimal request."""
        import logging
        logger = logging.getLogger(__name__)

        try:
            client = self._get_async_client()
            # Use the cheapest model for validation to minimize cost
            await client.messages.create(
                model=self.VALIDATION_MODEL,
                max_tokens=1,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            logger.error(f"Anthropic API key validation failed: {type(e).__name__}: {e}")
            return False

    def _extract_tool_calls(self, content) -> list[dict[str, Any]] | None:
        """Extract tool use blocks from response content."""
        if not content:
            return None

        tool_calls = []
        for block in content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                tool_calls.append({
                    "id": block.id,
                    "type": "tool_use",
                    "name": block.name,
                    "input": block.input,
                })

        return tool_calls if tool_calls else None
