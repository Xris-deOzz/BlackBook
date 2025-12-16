"""
Chat service for AI conversations.

Orchestrates AI chat operations including message handling,
conversation management, and streaming responses.

Updated: now passes conversation_id to ToolExecutor for proper suggestion tracking.
Debug: added logging to trace context sent to AI.
"""

import json
import logging
import traceback
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import (
    AIConversation,
    AIMessage,
    AIMessageRole,
    Person,
    Organization,
)
from app.services.ai.base_provider import AIResponse, StreamChunk, BaseProvider, ChatMessage
from app.services.ai.provider_factory import ProviderFactory
from app.services.ai.context_builder import ContextBuilder
from app.services.ai.privacy_filter import strip_sensitive_data
from app.services.ai.suggestion_service import SuggestionService
from app.services.ai.tools.base import ToolRegistry
from app.services.ai.tools.definitions import create_tool_registry
from app.services.ai.tools.executor import ToolExecutor, ToolCall
from app.config import get_settings


class ChatService:
    """
    Service for managing AI chat conversations.

    Handles message sending, conversation management, and
    coordinates between providers and the database.
    """

    def __init__(self, db: Session):
        """
        Initialize chat service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
        self.context_builder = ContextBuilder(db)

    def create_conversation(
        self,
        title: str | None = None,
        person_id: UUID | None = None,
        org_id: UUID | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> AIConversation:
        """
        Create a new conversation.

        Args:
            title: Optional conversation title
            person_id: Optional person context
            org_id: Optional organization context
            provider_name: AI provider to use
            model_name: Model to use

        Returns:
            Created AIConversation instance
        """
        # Generate title if not provided
        if not title:
            if person_id:
                person = self.db.query(Person).filter_by(id=person_id).first()
                if person:
                    title = f"Chat about {person.full_name}"
            elif org_id:
                org = self.db.query(Organization).filter_by(id=org_id).first()
                if org:
                    title = f"Chat about {org.name}"
            else:
                title = f"New conversation"

        # Use defaults if not specified
        provider_name = provider_name or self.settings.ai_default_provider

        conversation = AIConversation(
            title=title,
            person_id=person_id,
            organization_id=org_id,
            provider_name=provider_name,
            model_name=model_name,
        )
        self.db.add(conversation)
        self.db.flush()

        return conversation

    def get_conversation(self, conversation_id: UUID) -> AIConversation | None:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Conversation UUID

        Returns:
            AIConversation or None if not found
        """
        return self.db.query(AIConversation).filter_by(id=conversation_id).first()

    def list_conversations(
        self,
        person_id: UUID | None = None,
        org_id: UUID | None = None,
        limit: int = 50,
    ) -> list[AIConversation]:
        """
        List conversations, optionally filtered by entity.

        Args:
            person_id: Filter by person
            org_id: Filter by organization
            limit: Maximum results

        Returns:
            List of conversations
        """
        query = self.db.query(AIConversation)

        if person_id:
            query = query.filter(AIConversation.person_id == person_id)
        if org_id:
            query = query.filter(AIConversation.organization_id == org_id)

        return query.order_by(AIConversation.updated_at.desc()).limit(limit).all()

    def delete_conversation(self, conversation_id: UUID) -> bool:
        """
        Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation UUID

        Returns:
            True if deleted, False if not found
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False

        self.db.delete(conversation)
        self.db.flush()
        return True

    def get_messages(self, conversation_id: UUID) -> list[AIMessage]:
        """
        Get all messages in a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of messages ordered by creation time
        """
        return (
            self.db.query(AIMessage)
            .filter_by(conversation_id=conversation_id)
            .order_by(AIMessage.created_at)
            .all()
        )

    def _process_suggestions(
        self,
        response_content: str,
        conversation: AIConversation,
    ) -> None:
        """
        Parse and save any suggestions from the AI response.

        Args:
            response_content: The AI response text
            conversation: The conversation with entity context
        """
        # Determine entity type and ID
        entity_type = None
        entity_id = None

        if conversation.person_id:
            entity_type = "person"
            entity_id = conversation.person_id
        elif conversation.organization_id:
            entity_type = "organization"
            entity_id = conversation.organization_id

        if not entity_type or not entity_id:
            return

        # Parse suggestions from response
        suggestion_service = SuggestionService(self.db)
        suggestions = suggestion_service.parse_suggestions_from_response(
            response_content=response_content,
            conversation_id=conversation.id,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        # Save suggestions
        if suggestions:
            suggestion_service.create_suggestions(suggestions)

    def _build_messages_for_ai(
        self,
        conversation: AIConversation,
        new_message: str,
    ) -> list[dict[str, str]]:
        """
        Build message list for AI provider.

        Args:
            conversation: The conversation
            new_message: New user message to add

        Returns:
            List of messages formatted for AI provider
        """
        # Get existing messages
        existing_messages = self.get_messages(conversation.id)

        # Convert to dict format
        messages = []
        for msg in existing_messages:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

        # Add new user message (filtered)
        messages.append({
            "role": "user",
            "content": strip_sensitive_data(new_message),
        })

        # Build full context with system prompt
        return self.context_builder.build_conversation_context(
            messages,
            person_id=conversation.person_id,
            org_id=conversation.organization_id,
        )

    def _get_tools_for_provider(self, provider_name: str) -> list[dict]:
        """
        Get tools formatted for the specified provider.

        Args:
            provider_name: Provider name ('anthropic', 'google', 'openai')

        Returns:
            List of tool definitions in provider-specific format
        """
        registry = create_tool_registry(include_search=True, include_crm=True)

        if provider_name == "anthropic":
            return registry.to_anthropic_tools()
        elif provider_name == "google":
            return registry.to_google_tools()
        else:
            return registry.to_openai_tools()

    def _parse_tool_calls_from_response(
        self,
        response: AIResponse,
        provider_name: str,
    ) -> list[ToolCall]:
        """
        Parse tool calls from AI response based on provider.

        Args:
            response: The AI response
            provider_name: Provider name

        Returns:
            List of parsed ToolCall objects
        """
        if not response.tool_calls:
            return []

        tool_calls = []
        for tc in response.tool_calls:
            if provider_name == "anthropic":
                tool_calls.append(ToolCall.from_anthropic_format(tc))
            elif provider_name == "google":
                tool_calls.append(ToolCall.from_google_format(tc))
            else:
                tool_calls.append(ToolCall.from_openai_format(tc))

        return tool_calls

    def _build_tool_result_messages(
        self,
        tool_calls: list[ToolCall],
        execution_result,
        provider_name: str,
    ) -> list[dict]:
        """
        Build messages containing tool results for the provider.

        Args:
            tool_calls: The original tool calls
            execution_result: The ToolExecutionResult
            provider_name: Provider name

        Returns:
            List of message dicts to append to conversation
        """
        if provider_name == "anthropic":
            # Anthropic expects tool results as user message content blocks
            return [{
                "role": "user",
                "content": execution_result.to_anthropic_content(),
            }]
        elif provider_name == "google":
            # Google expects function response parts
            return [{
                "role": "user",
                "content": json.dumps(execution_result.to_google_parts()),
            }]
        else:
            # OpenAI format - separate tool messages
            return execution_result.to_openai_messages()

    async def send_message(
        self,
        conversation_id: UUID,
        content: str,
        model: str | None = None,
    ) -> AIMessage:
        """
        Send a message and get AI response.

        Implements a tool execution loop that continues until the AI
        produces a final text response (no more tool calls).

        Args:
            conversation_id: Conversation UUID
            content: Message content
            model: Optional model override

        Returns:
            AI response message

        Raises:
            ValueError: If conversation not found or no provider available
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Save user message
        user_message = AIMessage.create_user_message(
            conversation_id=conversation_id,
            content=content,
        )
        self.db.add(user_message)
        self.db.flush()

        # Get provider
        provider_name = conversation.provider_name or self.settings.ai_default_provider
        factory = ProviderFactory(self.db)
        provider = factory.get_provider(provider_name)

        # Build messages for AI
        messages = self._build_messages_for_ai(conversation, content)

        # Log the system prompt for debugging
        if messages and messages[0].get("role") == "system":
            system_content = messages[0].get("content", "")
            logger.info(f"System prompt length: {len(system_content)} chars")
            # Log key parts to verify context
            for line in system_content.split('\n'):
                if "Employment" in line or "Work Experience" in line:
                    logger.info(f"Context line: {line[:200]}")

        # Get tools in provider-specific format
        tools = self._get_tools_for_provider(provider_name)

        # Debug: log which tools are being sent to the provider
        tool_names = [t.get('name') or t.get('function', {}).get('name') for t in tools] if tools else []
        logger.info(f"Tools being sent to {provider_name}: {tool_names}")
        logger.info(f"Total tools count: {len(tools) if tools else 0}")

        # Detailed logging for add_affiliated_person tool
        for tool in tools:
            name = tool.get('name') or tool.get('function', {}).get('name')
            if name == 'add_affiliated_person':
                logger.info(f"add_affiliated_person tool definition: {tool}")

        # Create tool registry and executor for handling tool calls
        registry = create_tool_registry(include_search=True, include_crm=True)
        executor = ToolExecutor(registry, self.db, conversation_id=str(conversation_id))

        # Get AI response with tool loop
        # Validate that the model is available for this provider
        candidate_model = model or conversation.model_name
        if candidate_model and candidate_model not in provider.available_models:
            logger.warning(f"Model '{candidate_model}' not available for {provider_name}, using default: {provider.default_model}")
            model_to_use = provider.default_model
        else:
            model_to_use = candidate_model or provider.default_model
        max_tool_iterations = 10  # Prevent infinite loops
        iteration = 0
        total_tokens_in = 0
        total_tokens_out = 0
        all_tool_calls = []

        while iteration < max_tool_iterations:
            iteration += 1
            logger.info(f"Tool loop iteration {iteration}")

            try:
                # Call the AI with tools
                response = await provider.chat(
                    messages,
                    model=model_to_use,
                    tools=tools if tools else None,
                )
                logger.info(f"AI response received, content length: {len(response.content or '')}, tool_calls: {len(response.tool_calls or [])}")
                if response.tool_calls:
                    logger.info(f"Tool calls in response: {response.tool_calls}")
            except Exception as e:
                logger.error(f"Error calling AI provider: {str(e)}")
                traceback.print_exc()
                raise

            total_tokens_in += response.tokens_in
            total_tokens_out += response.tokens_out

            # Parse any tool calls from the response
            tool_calls = self._parse_tool_calls_from_response(response, provider_name)
            logger.info(f"Parsed {len(tool_calls)} tool calls")

            if not tool_calls:
                # No tool calls - this is the final response
                logger.info("No tool calls, breaking loop")
                break

            # Store tool calls for logging
            all_tool_calls.extend([{
                "name": tc.name,
                "arguments": tc.arguments,
            } for tc in tool_calls])
            logger.info(f"Tool calls to execute: {[tc.name for tc in tool_calls]}")

            # Add assistant's response (with tool calls) to messages
            if provider_name == "anthropic":
                # Anthropic: include both text and tool_use blocks
                assistant_content = []
                if response.content:
                    assistant_content.append({"type": "text", "text": response.content})
                for tc in response.tool_calls:
                    assistant_content.append(tc)
                messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                })
            else:
                # OpenAI/Google: simple content with tool_calls
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                })

            # Execute all tool calls
            try:
                logger.info(f"Executing tool calls...")
                execution_result = await executor.execute_all(tool_calls)
                logger.info(f"Tool execution complete, has_errors: {execution_result.has_errors}")
                for call, result in execution_result.results:
                    logger.info(f"  Tool {call.name}: status={result.status.value}, error={result.error}")
            except Exception as e:
                logger.error(f"Error executing tools: {str(e)}")
                traceback.print_exc()
                raise

            # Build tool result messages and add to conversation
            try:
                tool_result_messages = self._build_tool_result_messages(
                    tool_calls, execution_result, provider_name
                )
                messages.extend(tool_result_messages)
                logger.info(f"Added {len(tool_result_messages)} tool result messages")
            except Exception as e:
                logger.error(f"Error building tool result messages: {str(e)}")
                traceback.print_exc()
                raise

        # Save assistant message with final response
        logger.info(f"Saving assistant message, content: {response.content[:100] if response.content else 'None'}...")
        try:
            assistant_message = AIMessage.create_assistant_message(
                conversation_id=conversation_id,
                content=response.content or "",  # Ensure not None
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                tool_calls=all_tool_calls if all_tool_calls else None,
            )
            self.db.add(assistant_message)
        except Exception as e:
            logger.error(f"Error creating assistant message: {str(e)}")
            traceback.print_exc()
            raise

        # Parse and save any suggestions in the response
        try:
            self._process_suggestions(
                response_content=response.content or "",
                conversation=conversation,
            )
        except Exception as e:
            logger.error(f"Error processing suggestions: {str(e)}")
            traceback.print_exc()
            # Don't raise - suggestions are optional

        # Update conversation
        conversation.updated_at = datetime.utcnow()
        if not conversation.model_name:
            conversation.model_name = model_to_use

        try:
            self.db.flush()
            logger.info("Message saved successfully")
        except Exception as e:
            logger.error(f"Error flushing to database: {str(e)}")
            traceback.print_exc()
            raise

        return assistant_message

    async def send_message_stream(
        self,
        conversation_id: UUID,
        content: str,
        model: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Send a message and stream AI response.

        Implements tool execution loop - uses non-streaming for tool calls,
        then streams the final response.

        Args:
            conversation_id: Conversation UUID
            content: Message content
            model: Optional model override

        Yields:
            StreamChunk objects as response streams in

        Raises:
            ValueError: If conversation not found or no provider available
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Save user message
        user_message = AIMessage.create_user_message(
            conversation_id=conversation_id,
            content=content,
        )
        self.db.add(user_message)
        self.db.flush()

        # Get provider
        provider_name = conversation.provider_name or self.settings.ai_default_provider
        factory = ProviderFactory(self.db)
        provider = factory.get_provider(provider_name)

        # Build messages for AI
        messages = self._build_messages_for_ai(conversation, content)

        # Get tools in provider-specific format
        tools = self._get_tools_for_provider(provider_name)

        # Create tool registry and executor for handling tool calls
        registry = create_tool_registry(include_search=True, include_crm=True)
        executor = ToolExecutor(registry, self.db, conversation_id=str(conversation_id))

        # Validate that the model is available for this provider
        candidate_model = model or conversation.model_name
        if candidate_model and candidate_model not in provider.available_models:
            logger.warning(f"Model '{candidate_model}' not available for {provider_name}, using default: {provider.default_model}")
            model_to_use = provider.default_model
        else:
            model_to_use = candidate_model or provider.default_model
        max_tool_iterations = 10
        iteration = 0
        total_tokens_in = 0
        total_tokens_out = 0
        all_tool_calls = []

        # Tool execution loop (non-streaming)
        while iteration < max_tool_iterations:
            iteration += 1

            # Call the AI with tools (non-streaming to handle tool calls)
            response = await provider.chat(
                messages,
                model=model_to_use,
                tools=tools if tools else None,
            )

            total_tokens_in += response.tokens_in
            total_tokens_out += response.tokens_out

            # Parse any tool calls from the response
            tool_calls = self._parse_tool_calls_from_response(response, provider_name)

            if not tool_calls:
                # No tool calls - stream the final response
                # First yield the content we already have from the non-streaming call
                if response.content:
                    yield StreamChunk(content=response.content, is_final=False)

                # Final chunk with metadata
                yield StreamChunk(
                    content="",
                    is_final=True,
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    finish_reason=response.finish_reason,
                )

                # Save assistant message
                assistant_message = AIMessage.create_assistant_message(
                    conversation_id=conversation_id,
                    content=response.content,
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    tool_calls=all_tool_calls if all_tool_calls else None,
                )
                self.db.add(assistant_message)

                # Parse and save any suggestions in the response
                self._process_suggestions(
                    response_content=response.content,
                    conversation=conversation,
                )

                # Update conversation
                conversation.updated_at = datetime.utcnow()
                if not conversation.model_name:
                    conversation.model_name = model_to_use

                self.db.flush()
                return

            # Store tool calls for logging
            all_tool_calls.extend([{
                "name": tc.name,
                "arguments": tc.arguments,
            } for tc in tool_calls])

            # Yield status update about tool execution
            tool_names = ", ".join(tc.name for tc in tool_calls)
            yield StreamChunk(
                content=f"\n\n*Using tools: {tool_names}...*\n\n",
                is_final=False,
            )

            # Add assistant's response (with tool calls) to messages
            if provider_name == "anthropic":
                assistant_content = []
                if response.content:
                    assistant_content.append({"type": "text", "text": response.content})
                for tc in response.tool_calls:
                    assistant_content.append(tc)
                messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                })

            # Execute all tool calls
            execution_result = await executor.execute_all(tool_calls)

            # Build tool result messages and add to conversation
            tool_result_messages = self._build_tool_result_messages(
                tool_calls, execution_result, provider_name
            )
            messages.extend(tool_result_messages)

        # If we hit max iterations, return what we have
        yield StreamChunk(
            content="\n\n*Maximum tool iterations reached.*",
            is_final=True,
        )

    async def quick_chat(
        self,
        content: str,
        person_id: UUID | None = None,
        org_id: UUID | None = None,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> tuple[AIConversation, AIMessage]:
        """
        Start a new conversation and send first message.

        Convenience method for creating conversation and sending
        first message in one call.

        Args:
            content: Message content
            person_id: Optional person context
            org_id: Optional organization context
            provider_name: Optional provider
            model: Optional model

        Returns:
            Tuple of (conversation, response_message)
        """
        conversation = self.create_conversation(
            person_id=person_id,
            org_id=org_id,
            provider_name=provider_name,
            model_name=model,
        )
        self.db.flush()

        response = await self.send_message(
            conversation_id=conversation.id,
            content=content,
            model=model,
        )

        return conversation, response

    def update_conversation_title(
        self,
        conversation_id: UUID,
        title: str,
    ) -> AIConversation | None:
        """
        Update a conversation's title.

        Args:
            conversation_id: Conversation UUID
            title: New title

        Returns:
            Updated conversation or None if not found
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None

        conversation.title = title
        conversation.updated_at = datetime.utcnow()
        self.db.flush()

        return conversation

    def get_conversation_stats(self, conversation_id: UUID) -> dict:
        """
        Get statistics for a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Dictionary with message count, token usage, etc.
        """
        messages = self.get_messages(conversation_id)

        total_tokens_in = sum(m.tokens_in or 0 for m in messages)
        total_tokens_out = sum(m.tokens_out or 0 for m in messages)

        return {
            "message_count": len(messages),
            "user_messages": sum(1 for m in messages if m.role == AIMessageRole.user),
            "assistant_messages": sum(1 for m in messages if m.role == AIMessageRole.assistant),
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_tokens": total_tokens_in + total_tokens_out,
        }


def get_chat_service(db: Session) -> ChatService:
    """
    Factory function to get chat service instance.

    Args:
        db: Database session

    Returns:
        ChatService instance
    """
    return ChatService(db)
