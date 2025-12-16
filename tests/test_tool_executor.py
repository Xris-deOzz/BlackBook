"""
Tests for AI tool system.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai.tools.base import (
    Tool,
    ToolParameter,
    ToolResult,
    ToolResultStatus,
    ToolRegistry,
)
from app.services.ai.tools.executor import (
    ToolCall,
    ToolExecutor,
    ToolExecutionResult,
)
from app.services.ai.tools.definitions import (
    get_default_tools,
    SEARCH_TOOLS,
    CRM_TOOLS,
)


class TestToolResult:
    """Test ToolResult class."""

    def test_success_result(self):
        """Test creating a success result."""
        result = ToolResult.success({"data": "test"}, source="web")

        assert result.status == ToolResultStatus.SUCCESS
        assert result.output == {"data": "test"}
        assert result.error is None
        assert result.metadata["source"] == "web"

    def test_error_result(self):
        """Test creating an error result."""
        result = ToolResult.create_error("Something went wrong", tool="web_search")

        assert result.status == ToolResultStatus.ERROR
        assert result.output is None
        assert result.error == "Something went wrong"
        assert result.metadata["tool"] == "web_search"

    def test_partial_result(self):
        """Test creating a partial result."""
        result = ToolResult.partial(
            {"partial": "data"},
            "Some items failed",
        )

        assert result.status == ToolResultStatus.PARTIAL
        assert result.output == {"partial": "data"}
        assert result.error == "Some items failed"

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = ToolResult.success("test output")
        data = result.to_dict()

        assert data["status"] == "success"
        assert data["output"] == "test output"
        assert data["error"] is None

    def test_to_message_content_success(self):
        """Test converting success result to message."""
        result = ToolResult.success("Plain text result")
        content = result.to_message_content()

        assert content == "Plain text result"

    def test_to_message_content_dict(self):
        """Test converting dict result to message."""
        result = ToolResult.success({"key": "value"})
        content = result.to_message_content()

        assert "key" in content
        assert "value" in content

    def test_to_message_content_error(self):
        """Test converting error result to message."""
        result = ToolResult.create_error("Failed to search")
        content = result.to_message_content()

        assert "Error:" in content
        assert "Failed to search" in content


class TestToolParameter:
    """Test ToolParameter class."""

    def test_basic_parameter(self):
        """Test creating a basic parameter."""
        param = ToolParameter(
            name="query",
            description="The search query",
            type="string",
        )

        assert param.name == "query"
        assert param.type == "string"
        assert param.required is True

    def test_optional_parameter(self):
        """Test creating an optional parameter."""
        param = ToolParameter(
            name="limit",
            description="Max results",
            type="number",
            required=False,
            default=10,
        )

        assert param.required is False
        assert param.default == 10

    def test_enum_parameter(self):
        """Test creating a parameter with enum."""
        param = ToolParameter(
            name="sort",
            description="Sort order",
            type="string",
            enum=["asc", "desc"],
        )

        assert param.enum == ["asc", "desc"]

    def test_to_json_schema(self):
        """Test converting to JSON schema."""
        param = ToolParameter(
            name="query",
            description="Search query",
            type="string",
        )

        schema = param.to_json_schema()

        assert schema["type"] == "string"
        assert schema["description"] == "Search query"


class TestTool:
    """Test Tool class."""

    @pytest.fixture
    def sample_tool(self):
        """Create a sample tool for testing."""
        async def handler(query: str, limit: int = 5, db=None) -> ToolResult:
            return ToolResult.success({"query": query, "limit": limit})

        return Tool(
            name="test_search",
            description="Test search tool",
            parameters=[
                ToolParameter(
                    name="query",
                    description="Search query",
                    type="string",
                ),
                ToolParameter(
                    name="limit",
                    description="Max results",
                    type="number",
                    required=False,
                    default=5,
                ),
            ],
            handler=handler,
            category="search",
        )

    def test_to_openai_format(self, sample_tool):
        """Test converting to OpenAI format."""
        fmt = sample_tool.to_openai_format()

        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "test_search"
        assert "parameters" in fmt["function"]
        assert "query" in fmt["function"]["parameters"]["properties"]

    def test_to_anthropic_format(self, sample_tool):
        """Test converting to Anthropic format."""
        fmt = sample_tool.to_anthropic_format()

        assert fmt["name"] == "test_search"
        assert "input_schema" in fmt
        assert "query" in fmt["input_schema"]["properties"]

    def test_to_google_format(self, sample_tool):
        """Test converting to Google format."""
        fmt = sample_tool.to_google_format()

        assert fmt["name"] == "test_search"
        assert "parameters" in fmt
        assert "query" in fmt["parameters"]["properties"]


class TestToolRegistry:
    """Test ToolRegistry class."""

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()

        async def handler():
            return ToolResult.success("ok")

        tool = Tool(
            name="test",
            description="Test",
            parameters=[],
            handler=handler,
        )

        registry.register(tool)

        assert "test" in registry.list_names()
        assert registry.get("test") is tool

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()

        async def handler():
            return ToolResult.success("ok")

        tool = Tool(name="test", description="Test", parameters=[], handler=handler)
        registry.register(tool)
        registry.unregister("test")

        assert "test" not in registry.list_names()
        assert registry.get("test") is None

    def test_list_tools_by_category(self):
        """Test listing tools by category."""
        registry = ToolRegistry()

        async def handler():
            return ToolResult.success("ok")

        tool1 = Tool(
            name="search1",
            description="Search 1",
            parameters=[],
            handler=handler,
            category="search",
        )
        tool2 = Tool(
            name="crm1",
            description="CRM 1",
            parameters=[],
            handler=handler,
            category="crm",
        )

        registry.register(tool1)
        registry.register(tool2)

        search_tools = registry.list_tools(category="search")
        assert len(search_tools) == 1
        assert search_tools[0].name == "search1"

    def test_to_openai_tools(self):
        """Test getting all tools in OpenAI format."""
        registry = ToolRegistry()

        async def handler():
            return ToolResult.success("ok")

        tool = Tool(name="test", description="Test", parameters=[], handler=handler)
        registry.register(tool)

        tools = registry.to_openai_tools()

        assert len(tools) == 1
        assert tools[0]["type"] == "function"


class TestToolCall:
    """Test ToolCall class."""

    def test_from_openai_format(self):
        """Test parsing OpenAI tool call format."""
        openai_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "web_search",
                "arguments": '{"query": "test", "limit": 5}',
            },
        }

        call = ToolCall.from_openai_format(openai_call)

        assert call.id == "call_123"
        assert call.name == "web_search"
        assert call.arguments["query"] == "test"
        assert call.arguments["limit"] == 5

    def test_from_anthropic_format(self):
        """Test parsing Anthropic tool use format."""
        anthropic_call = {
            "id": "toolu_123",
            "name": "web_search",
            "input": {"query": "test"},
        }

        call = ToolCall.from_anthropic_format(anthropic_call)

        assert call.id == "toolu_123"
        assert call.name == "web_search"
        assert call.arguments["query"] == "test"

    def test_from_google_format(self):
        """Test parsing Google function call format."""
        google_call = {
            "name": "web_search",
            "args": {"query": "test"},
        }

        call = ToolCall.from_google_format(google_call)

        assert call.name == "web_search"
        assert call.arguments["query"] == "test"


class TestToolExecutor:
    """Test ToolExecutor class."""

    @pytest.fixture
    def registry_with_tool(self):
        """Create a registry with a test tool."""
        registry = ToolRegistry()

        async def handler(query: str, db=None) -> ToolResult:
            return ToolResult.success({"query": query})

        tool = Tool(
            name="test_tool",
            description="Test tool",
            parameters=[
                ToolParameter(name="query", description="Query", type="string"),
            ],
            handler=handler,
        )
        registry.register(tool)
        return registry

    @pytest.mark.asyncio
    async def test_execute_tool(self, registry_with_tool):
        """Test executing a tool."""
        executor = ToolExecutor(registry_with_tool)

        call = ToolCall(id="1", name="test_tool", arguments={"query": "test"})
        result = await executor.execute(call)

        assert result.status == ToolResultStatus.SUCCESS
        assert result.output["query"] == "test"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, registry_with_tool):
        """Test executing an unknown tool."""
        executor = ToolExecutor(registry_with_tool)

        call = ToolCall(id="1", name="unknown", arguments={})
        result = await executor.execute(call)

        assert result.status == ToolResultStatus.ERROR
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_all(self, registry_with_tool):
        """Test executing multiple tools."""
        executor = ToolExecutor(registry_with_tool)

        calls = [
            ToolCall(id="1", name="test_tool", arguments={"query": "first"}),
            ToolCall(id="2", name="test_tool", arguments={"query": "second"}),
        ]

        result = await executor.execute_all(calls)

        assert len(result.results) == 2
        assert not result.has_errors


class TestToolExecutionResult:
    """Test ToolExecutionResult class."""

    def test_to_openai_messages(self):
        """Test converting to OpenAI tool response messages."""
        call = ToolCall(id="call_123", name="test", arguments={})
        result = ToolResult.success("Success!")

        exec_result = ToolExecutionResult(results=[(call, result)])
        messages = exec_result.to_openai_messages()

        assert len(messages) == 1
        assert messages[0]["role"] == "tool"
        assert messages[0]["tool_call_id"] == "call_123"
        assert messages[0]["content"] == "Success!"

    def test_to_anthropic_content(self):
        """Test converting to Anthropic tool result content."""
        call = ToolCall(id="toolu_123", name="test", arguments={})
        result = ToolResult.success("Success!")

        exec_result = ToolExecutionResult(results=[(call, result)])
        content = exec_result.to_anthropic_content()

        assert len(content) == 1
        assert content[0]["type"] == "tool_result"
        assert content[0]["tool_use_id"] == "toolu_123"
        assert not content[0]["is_error"]


class TestDefaultTools:
    """Test default tool definitions."""

    def test_get_default_tools(self):
        """Test getting default tools."""
        tools = get_default_tools()

        assert len(tools) > 0
        assert all(isinstance(t, Tool) for t in tools)

    def test_search_tools_defined(self):
        """Test that search tools are defined."""
        assert len(SEARCH_TOOLS) > 0

        tool_names = [t.name for t in SEARCH_TOOLS]
        assert "web_search" in tool_names
        assert "youtube_search" in tool_names
        assert "podcast_search" in tool_names

    def test_crm_tools_defined(self):
        """Test that CRM tools are defined."""
        assert len(CRM_TOOLS) > 0

        tool_names = [t.name for t in CRM_TOOLS]
        assert "lookup_person" in tool_names
        assert "lookup_organization" in tool_names
        assert "search_crm" in tool_names
        assert "suggest_update" in tool_names
