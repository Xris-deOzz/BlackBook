"""
Google (Gemini) provider implementation.

Uses the new google-genai SDK to support Gemini 3 Pro and other models.
Supports thinking levels for advanced reasoning with Gemini 3.
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


class GoogleProvider(BaseProvider):
    """
    Google AI (Gemini) provider.

    Uses the google-genai SDK for chat completions.
    Supports both regular and streaming responses.
    Includes Gemini 3 Pro with thinking levels for advanced reasoning.
    """

    # Available models (most capable first)
    # Note: gemini-3-pro-preview requires thinking_level parameter
    MODELS = [
        "gemini-3-pro-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]

    # Models that support thinking levels
    THINKING_MODELS = ["gemini-3-pro-preview"]

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Google provider.

        Args:
            api_key: Google AI API key
            **kwargs: Additional configuration
        """
        super().__init__(api_key, **kwargs)
        self._client = None

    def _get_client(self):
        """Get or create the Gemini client."""
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise ProviderError(
                    "Google GenAI package not installed. Run: pip install google-genai",
                    provider=self.name,
                )
        return self._client

    @property
    def name(self) -> str:
        return "google"

    @property
    def display_name(self) -> str:
        return "Gemini"

    @property
    def available_models(self) -> list[str]:
        return self.MODELS.copy()

    @property
    def default_model(self) -> str:
        return "gemini-2.0-flash"

    def _is_thinking_model(self, model: str) -> bool:
        """Check if the model supports thinking levels."""
        return model in self.THINKING_MODELS

    def _convert_messages(self, messages: list[ChatMessage | dict]) -> tuple[str | None, list[dict]]:
        """
        Convert messages to Gemini format.

        Gemini uses a different format with "user" and "model" roles.
        Accepts both ChatMessage objects and plain dictionaries.

        Returns:
            Tuple of (system_instruction, contents)
        """
        system_instruction = None
        contents = []

        for msg in messages:
            # Handle both ChatMessage objects and dicts
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
            else:
                role = msg.role
                content = msg.content

            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            elif role == "tool":
                # Tool results go as user messages in Gemini
                contents.append({"role": "user", "parts": [{"text": content}]})

        return system_instruction, contents

    def _build_config(
        self,
        model: str,
        temperature: float,
        max_tokens: int | None,
        system_instruction: str | None,
        thinking_level: str | None = None,
        tools: list[dict] | None = None,
    ):
        """Build the GenerateContentConfig for the request."""
        from google.genai import types

        config_kwargs = {}

        # For Gemini 3 models, use temperature=1.0 as recommended
        if self._is_thinking_model(model):
            config_kwargs["temperature"] = 1.0
        else:
            config_kwargs["temperature"] = temperature

        if max_tokens:
            config_kwargs["max_output_tokens"] = max_tokens

        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        # Add thinking config for Gemini 3 models
        if self._is_thinking_model(model):
            level = thinking_level or "high"
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=level
            )

        # Add tools if provided
        if tools:
            config_kwargs["tools"] = self._convert_tools_to_gemini(tools)
            # Configure function calling mode to AUTO (model decides when to use tools)
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            )

        return types.GenerateContentConfig(**config_kwargs)

    def _convert_tools_to_gemini(self, tools: list[dict]) -> list:
        """
        Convert tool definitions to Gemini function declarations.

        Accepts tools in either OpenAI format or Google format.
        """
        from google.genai import types
        import logging
        logger = logging.getLogger(__name__)

        function_declarations = []

        for tool in tools:
            # Handle OpenAI format (type: function, function: {...})
            if tool.get("type") == "function":
                func = tool.get("function", {})
                params = func.get("parameters", {})
            # Handle Google/direct format (name, description, parameters at top level)
            elif "name" in tool:
                params = tool.get("parameters", tool.get("input_schema", {}))
                func = tool
            else:
                logger.warning(f"Skipping unknown tool format: {tool.keys()}")
                continue

            tool_name = func.get("name", "")
            function_declarations.append(
                types.FunctionDeclaration(
                    name=tool_name,
                    description=func.get("description", ""),
                    parameters=params if params else None,
                )
            )

        logger.info(f"Gemini: converted {len(function_declarations)} function declarations: {[fd.name for fd in function_declarations]}")
        return [types.Tool(function_declarations=function_declarations)]

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        thinking_level: str | None = None,
        **kwargs,
    ) -> AIResponse:
        """
        Send a chat completion request to Gemini.

        Args:
            messages: List of chat messages
            model: Model to use (defaults to gemini-2.0-flash)
            temperature: Sampling temperature (ignored for Gemini 3)
            max_tokens: Maximum tokens to generate
            tools: Tool definitions for function calling
            thinking_level: For Gemini 3 models: "low" or "high" (default: "high")
            **kwargs: Additional parameters

        Returns:
            AIResponse with the completion
        """
        try:
            from google.genai import types
            from google.api_core import exceptions as google_exceptions

            client = self._get_client()
            model_name = model or self.default_model
            system_instruction, contents = self._convert_messages(messages)

            # Build configuration (including tools)
            config = self._build_config(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                system_instruction=system_instruction,
                thinking_level=thinking_level,
                tools=tools,
            )

            # Generate response using async client
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )

            # Extract token counts from usage metadata
            tokens_in = 0
            tokens_out = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                tokens_in = getattr(usage, 'prompt_token_count', 0) or 0
                tokens_out = getattr(usage, 'candidates_token_count', 0) or 0

            # Extract tool calls if any
            tool_calls = self._extract_tool_calls(response)

            # Extract text content (may be empty if only tool calls)
            content = self._extract_text_content(response)

            return AIResponse(
                content=content,
                model=model_name,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                finish_reason=self._get_finish_reason(response),
                tool_calls=tool_calls,
            )

        except Exception as e:
            error_str = str(e).lower()
            if "invalid" in error_str and "key" in error_str:
                raise ProviderAuthError(
                    f"Invalid API key or configuration: {e}",
                    provider=self.name,
                )
            elif "rate" in error_str or "quota" in error_str or "exhausted" in error_str:
                raise ProviderRateLimitError(
                    f"Rate limit exceeded: {e}",
                    provider=self.name,
                )
            else:
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
        thinking_level: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a chat completion response from Gemini.

        Args:
            messages: List of chat messages
            model: Model to use (defaults to gemini-2.0-flash)
            temperature: Sampling temperature (ignored for Gemini 3)
            max_tokens: Maximum tokens to generate
            tools: Tool definitions for function calling
            thinking_level: For Gemini 3 models: "low" or "high" (default: "high")
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects as response tokens arrive
        """
        try:
            from google.genai import types

            client = self._get_client()
            model_name = model or self.default_model
            system_instruction, contents = self._convert_messages(messages)

            # Build configuration (including tools)
            config = self._build_config(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                system_instruction=system_instruction,
                thinking_level=thinking_level,
                tools=tools,
            )

            # Generate streaming response using async client
            async for chunk in client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config,
            ):
                # Extract text from chunk
                text = self._extract_text_content(chunk)
                if text:
                    yield StreamChunk(
                        content=text,
                        is_final=False,
                    )

            # Final chunk
            yield StreamChunk(
                content="",
                is_final=True,
            )

        except Exception as e:
            error_str = str(e).lower()
            if "invalid" in error_str and "key" in error_str:
                raise ProviderAuthError(
                    f"Invalid API key or configuration: {e}",
                    provider=self.name,
                )
            elif "rate" in error_str or "quota" in error_str or "exhausted" in error_str:
                raise ProviderRateLimitError(
                    f"Rate limit exceeded: {e}",
                    provider=self.name,
                )
            else:
                raise ProviderError(
                    f"Unexpected error: {e}",
                    provider=self.name,
                )

    def count_tokens(self, text: str, model: str | None = None) -> int:
        """
        Count tokens for Gemini models.

        Uses Gemini's built-in token counting.
        """
        try:
            client = self._get_client()
            model_name = model or self.default_model

            # Use the sync client for token counting
            result = client.models.count_tokens(
                model=model_name,
                contents=text,
            )
            return result.total_tokens

        except Exception:
            # Fall back to rough estimate
            return len(text) // 4

    async def validate_key(self) -> bool:
        """Validate API key by making a minimal request."""
        try:
            client = self._get_client()

            # Try to list models to verify the key
            # Use sync method for simplicity in validation
            models = client.models.list()
            # Just check if we can iterate (doesn't need to fully consume)
            for _ in models:
                break
            return True
        except Exception:
            return False

    def _get_finish_reason(self, response) -> str | None:
        """Extract finish reason from Gemini response."""
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                    return str(candidate.finish_reason).lower()
        except Exception:
            pass
        return None

    def _extract_text_content(self, response) -> str:
        """
        Extract text content from Gemini response.

        Handles cases where response may contain function calls
        instead of (or in addition to) text.
        """
        try:
            # Try the simple .text property first
            if hasattr(response, 'text') and response.text:
                return response.text
        except (ValueError, AttributeError):
            pass

        # Manual extraction from parts
        try:
            if not hasattr(response, 'candidates') or not response.candidates:
                return ""

            candidate = response.candidates[0]
            if not hasattr(candidate, 'content') or not candidate.content:
                return ""

            text_parts = []
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)

            return "".join(text_parts)

        except Exception:
            return ""

    def _extract_tool_calls(self, response) -> list[dict] | None:
        """Extract function calls from Gemini response."""
        import logging
        logger = logging.getLogger(__name__)

        try:
            if not hasattr(response, 'candidates') or not response.candidates:
                logger.debug("No candidates in response")
                return None

            candidate = response.candidates[0]
            if not hasattr(candidate, 'content') or not candidate.content:
                logger.debug("No content in candidate")
                return None

            tool_calls = []
            parts_info = []
            for part in candidate.content.parts:
                part_type = type(part).__name__
                has_fc = hasattr(part, 'function_call') and part.function_call
                parts_info.append(f"{part_type}(has_fc={has_fc})")

                if has_fc:
                    fc = part.function_call
                    logger.info(f"Found function_call: name={fc.name}, args_type={type(fc.args)}")
                    # Convert args to dict if needed
                    args = {}
                    if hasattr(fc, 'args') and fc.args:
                        # Gemini returns args that can be converted to dict
                        try:
                            for key, value in fc.args.items():
                                args[key] = value
                        except Exception as arg_err:
                            logger.error(f"Error extracting args: {arg_err}")
                            # Try direct dict conversion
                            args = dict(fc.args) if fc.args else {}

                    tool_calls.append({
                        "name": fc.name,
                        "args": args,
                    })

            logger.info(f"Response parts: {parts_info}")
            logger.info(f"Extracted {len(tool_calls)} tool calls: {[tc['name'] for tc in tool_calls]}")
            return tool_calls if tool_calls else None

        except Exception as e:
            logger.error(f"Error extracting tool calls: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
