"""
AI Tool definitions and execution framework.

Provides tools that AI models can call to perform actions like
web search, database queries, and CRM operations.
"""

from app.services.ai.tools.base import Tool, ToolRegistry, ToolResult
from app.services.ai.tools.definitions import (
    get_default_tools,
    SEARCH_TOOLS,
    CRM_TOOLS,
)
from app.services.ai.tools.executor import ToolExecutor

__all__ = [
    # Base classes
    "Tool",
    "ToolRegistry",
    "ToolResult",
    # Tool definitions
    "get_default_tools",
    "SEARCH_TOOLS",
    "CRM_TOOLS",
    # Executor
    "ToolExecutor",
]
