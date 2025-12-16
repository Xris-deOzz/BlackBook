"""
Base classes for AI tool system.

Defines the Tool interface and ToolRegistry for managing
available tools.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from enum import Enum


class ToolResultStatus(str, Enum):
    """Status of tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


@dataclass
class ToolResult:
    """Result from executing a tool."""

    status: ToolResultStatus
    output: Any
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, output: Any, **metadata) -> "ToolResult":
        """Create a successful result."""
        return cls(
            status=ToolResultStatus.SUCCESS,
            output=output,
            metadata=metadata,
        )

    @classmethod
    def create_error(cls, error: str, **metadata) -> "ToolResult":
        """Create an error result."""
        return cls(
            status=ToolResultStatus.ERROR,
            output=None,
            error=error,
            metadata=metadata,
        )

    @classmethod
    def partial(cls, output: Any, error: str, **metadata) -> "ToolResult":
        """Create a partial success result."""
        return cls(
            status=ToolResultStatus.PARTIAL,
            output=output,
            error=error,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }

    def to_message_content(self) -> str:
        """Convert to string for including in AI message."""
        if self.status == ToolResultStatus.SUCCESS:
            if isinstance(self.output, str):
                return self.output
            elif isinstance(self.output, dict):
                import json
                return json.dumps(self.output, indent=2, default=str)
            elif isinstance(self.output, list):
                import json
                return json.dumps(self.output, indent=2, default=str)
            else:
                return str(self.output)
        elif self.status == ToolResultStatus.ERROR:
            return f"Error: {self.error}"
        else:
            result = str(self.output) if self.output else ""
            if self.error:
                result += f"\n\nNote: {self.error}"
            return result


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    description: str
    type: str  # "string", "number", "boolean", "array", "object"
    required: bool = True
    enum: list[str] | None = None
    default: Any = None

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON schema format."""
        schema: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class Tool:
    """
    Definition of a tool that AI can call.

    Tools are functions that the AI can invoke to perform actions
    like searching the web, querying the database, etc.
    """

    name: str
    description: str
    parameters: list[ToolParameter]
    handler: Callable[..., Awaitable[ToolResult]]
    category: str = "general"
    requires_confirmation: bool = False

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool format."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def to_google_format(self) -> dict[str, Any]:
        """Convert to Google Gemini function format."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


class ToolRegistry:
    """
    Registry for managing available tools.

    Provides methods to register, retrieve, and list tools.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[Tool]:
        """List all tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def to_openai_tools(
        self, categories: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get all tools in OpenAI format."""
        tools = self.list_tools()
        if categories:
            tools = [t for t in tools if t.category in categories]
        return [t.to_openai_format() for t in tools]

    def to_anthropic_tools(
        self, categories: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get all tools in Anthropic format."""
        tools = self.list_tools()
        if categories:
            tools = [t for t in tools if t.category in categories]
        return [t.to_anthropic_format() for t in tools]

    def to_google_tools(
        self, categories: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get all tools in Google format."""
        tools = self.list_tools()
        if categories:
            tools = [t for t in tools if t.category in categories]
        return [t.to_google_format() for t in tools]


# Global registry instance
_global_registry: ToolRegistry | None = None


def get_global_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
