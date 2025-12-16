"""
Tool executor for AI tool calls.

Handles parsing and executing tool calls from AI responses.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.services.ai.tools.base import Tool, ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a tool call from an AI response."""

    id: str
    name: str
    arguments: dict[str, Any]

    @classmethod
    def from_openai_format(cls, tool_call: dict) -> "ToolCall":
        """Parse from OpenAI tool call format."""
        func = tool_call.get("function", {})
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}

        return cls(
            id=tool_call.get("id", ""),
            name=func.get("name", ""),
            arguments=args,
        )

    @classmethod
    def from_anthropic_format(cls, tool_use: dict) -> "ToolCall":
        """Parse from Anthropic tool use format."""
        logger.info(f"Parsing Anthropic tool call: {tool_use}")
        tool_id = tool_use.get("id", "")
        tool_name = tool_use.get("name", "")
        tool_input = tool_use.get("input", {})
        logger.info(f"Parsed: id={tool_id}, name={tool_name}, input={tool_input}")
        return cls(
            id=tool_id,
            name=tool_name,
            arguments=tool_input,
        )

    @classmethod
    def from_google_format(cls, function_call: dict) -> "ToolCall":
        """Parse from Google function call format."""
        return cls(
            id=function_call.get("name", ""),  # Google doesn't have separate ID
            name=function_call.get("name", ""),
            arguments=function_call.get("args", {}),
        )


@dataclass
class ToolExecutionResult:
    """Result of executing one or more tool calls."""

    results: list[tuple[ToolCall, ToolResult]]
    has_errors: bool = False

    def to_openai_messages(self) -> list[dict[str, Any]]:
        """Convert to OpenAI tool response messages."""
        messages = []
        for call, result in self.results:
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result.to_message_content(),
            })
        return messages

    def to_anthropic_content(self) -> list[dict[str, Any]]:
        """Convert to Anthropic tool result content blocks."""
        content = []
        for call, result in self.results:
            content.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": result.to_message_content(),
                "is_error": result.status.value == "error",
            })
        return content

    def to_google_parts(self) -> list[dict[str, Any]]:
        """Convert to Google function response parts."""
        parts = []
        for call, result in self.results:
            parts.append({
                "functionResponse": {
                    "name": call.name,
                    "response": {
                        "content": result.output if result.output else result.error,
                    },
                },
            })
        return parts


class ToolExecutor:
    """
    Executes tool calls from AI responses.

    Handles parsing tool calls from different provider formats,
    executing them, and formatting results for the provider.
    """

    def __init__(self, registry: ToolRegistry, db: Session | None = None, conversation_id: str | None = None):
        self.registry = registry
        self.db = db
        self.conversation_id = conversation_id

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        logger.info(f"Executing tool: {tool_call.name}, id={tool_call.id}")
        logger.info(f"Tool arguments: {tool_call.arguments}")

        tool = self.registry.get(tool_call.name)

        if not tool:
            logger.error(f"Unknown tool: {tool_call.name}")
            return ToolResult.create_error(f"Unknown tool: {tool_call.name}")

        # Get the handler's parameter names to only pass what it accepts
        import inspect
        handler_sig = inspect.signature(tool.handler)
        handler_params = set(handler_sig.parameters.keys())

        # Build args with only parameters the handler accepts
        args = dict(tool_call.arguments)

        # Add db session if handler accepts it
        if "db" in handler_params:
            args["db"] = self.db

        # Add conversation_id if handler accepts it (like suggest_update)
        if "conversation_id" in handler_params and self.conversation_id:
            args["conversation_id"] = self.conversation_id

        try:
            logger.info(f"Calling handler for {tool_call.name} with args: {list(args.keys())}...")
            result = await tool.handler(**args)
            logger.info(f"Tool {tool_call.name} completed: status={result.status.value}")
            return result
        except TypeError as e:
            # Handle missing required arguments
            logger.error(f"Tool {tool_call.name} TypeError: {str(e)}")
            import traceback
            traceback.print_exc()
            return ToolResult.create_error(f"Invalid arguments: {str(e)}")
        except Exception as e:
            logger.error(f"Tool {tool_call.name} Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return ToolResult.create_error(f"Tool execution failed: {str(e)}")

    async def execute_all(
        self, tool_calls: list[ToolCall]
    ) -> ToolExecutionResult:
        """Execute multiple tool calls."""
        results = []
        has_errors = False

        for call in tool_calls:
            result = await self.execute(call)
            results.append((call, result))
            if result.status.value == "error":
                has_errors = True

        return ToolExecutionResult(results=results, has_errors=has_errors)

    def parse_openai_tool_calls(
        self, tool_calls: list[dict]
    ) -> list[ToolCall]:
        """Parse tool calls from OpenAI response."""
        return [ToolCall.from_openai_format(tc) for tc in tool_calls]

    def parse_anthropic_tool_uses(
        self, content: list[dict]
    ) -> list[ToolCall]:
        """Parse tool uses from Anthropic response."""
        tool_uses = [c for c in content if c.get("type") == "tool_use"]
        return [ToolCall.from_anthropic_format(tu) for tu in tool_uses]

    def parse_google_function_calls(
        self, function_calls: list[dict]
    ) -> list[ToolCall]:
        """Parse function calls from Google response."""
        return [ToolCall.from_google_format(fc) for fc in function_calls]

    async def process_openai_response(
        self, response: dict
    ) -> ToolExecutionResult | None:
        """
        Process OpenAI response and execute any tool calls.

        Returns None if no tool calls in response.
        """
        message = response.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            return None

        parsed = self.parse_openai_tool_calls(tool_calls)
        return await self.execute_all(parsed)

    async def process_anthropic_response(
        self, response: dict
    ) -> ToolExecutionResult | None:
        """
        Process Anthropic response and execute any tool uses.

        Returns None if no tool uses in response.
        """
        content = response.get("content", [])
        tool_uses = [c for c in content if c.get("type") == "tool_use"]

        if not tool_uses:
            return None

        parsed = self.parse_anthropic_tool_uses(content)
        return await self.execute_all(parsed)

    def get_tools_requiring_confirmation(
        self, tool_calls: list[ToolCall]
    ) -> list[ToolCall]:
        """Get tool calls that require user confirmation."""
        requiring_confirmation = []

        for call in tool_calls:
            tool = self.registry.get(call.name)
            if tool and tool.requires_confirmation:
                requiring_confirmation.append(call)

        return requiring_confirmation
