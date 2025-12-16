"""
Tests for AI chat service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models import (
    AIConversation,
    AIMessage,
    AIMessageRole,
    AIProvider,
    AIAPIKey,
    AIProviderType,
    Person,
    PersonStatus,
)
from app.services.ai.chat_service import ChatService, get_chat_service
from app.services.ai.base_provider import AIResponse


@pytest.fixture
def sample_ai_provider(db_session):
    """Create sample AI provider with key."""
    provider = AIProvider(
        name="OpenAI",
        api_type=AIProviderType.openai,
        is_local=False,
        is_active=True,
    )
    db_session.add(provider)
    db_session.flush()

    api_key = AIAPIKey(provider_id=provider.id)
    api_key.set_api_key("sk-test-key")
    api_key.is_valid = True
    db_session.add(api_key)
    db_session.flush()

    return provider


class TestChatServiceConversations:
    """Test conversation management."""

    def test_create_conversation_basic(self, db_session):
        """Test creating a basic conversation."""
        service = ChatService(db_session)
        conversation = service.create_conversation(title="Test Chat")

        assert conversation.id is not None
        assert conversation.title == "Test Chat"

    def test_create_conversation_with_person_context(self, db_session, sample_person):
        """Test creating conversation with person context."""
        service = ChatService(db_session)
        conversation = service.create_conversation(person_id=sample_person.id)

        assert conversation.person_id == sample_person.id
        assert sample_person.full_name in conversation.title

    def test_create_conversation_auto_title(self, db_session, sample_person):
        """Test auto-generated title from person name."""
        service = ChatService(db_session)
        conversation = service.create_conversation(person_id=sample_person.id)

        assert "Test Person" in conversation.title

    def test_get_conversation(self, db_session):
        """Test getting a conversation by ID."""
        service = ChatService(db_session)
        created = service.create_conversation(title="Test")
        db_session.flush()

        retrieved = service.get_conversation(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "Test"

    def test_get_conversation_not_found(self, db_session):
        """Test getting non-existent conversation."""
        service = ChatService(db_session)
        result = service.get_conversation(uuid4())
        assert result is None

    def test_list_conversations(self, db_session):
        """Test listing conversations."""
        service = ChatService(db_session)
        service.create_conversation(title="Conv 1")
        service.create_conversation(title="Conv 2")
        db_session.flush()

        conversations = service.list_conversations()
        assert len(conversations) >= 2

    def test_list_conversations_by_person(self, db_session, sample_person):
        """Test filtering conversations by person."""
        service = ChatService(db_session)
        service.create_conversation(title="General")
        service.create_conversation(title="Person Chat", person_id=sample_person.id)
        db_session.flush()

        conversations = service.list_conversations(person_id=sample_person.id)
        assert len(conversations) == 1
        assert conversations[0].person_id == sample_person.id

    def test_delete_conversation(self, db_session):
        """Test deleting a conversation."""
        service = ChatService(db_session)
        conversation = service.create_conversation(title="To Delete")
        db_session.flush()

        conv_id = conversation.id
        result = service.delete_conversation(conv_id)

        assert result is True
        assert service.get_conversation(conv_id) is None

    def test_delete_conversation_not_found(self, db_session):
        """Test deleting non-existent conversation."""
        service = ChatService(db_session)
        result = service.delete_conversation(uuid4())
        assert result is False

    def test_update_conversation_title(self, db_session):
        """Test updating conversation title."""
        service = ChatService(db_session)
        conversation = service.create_conversation(title="Old Title")
        db_session.flush()

        updated = service.update_conversation_title(conversation.id, "New Title")

        assert updated is not None
        assert updated.title == "New Title"


class TestChatServiceMessages:
    """Test message handling."""

    def test_get_messages_empty(self, db_session):
        """Test getting messages from empty conversation."""
        service = ChatService(db_session)
        conversation = service.create_conversation(title="Empty")
        db_session.flush()

        messages = service.get_messages(conversation.id)
        assert messages == []

    def test_get_messages_ordered(self, db_session):
        """Test that messages are ordered by creation time."""
        service = ChatService(db_session)
        conversation = service.create_conversation(title="Test")
        db_session.flush()

        # Add messages directly
        msg1 = AIMessage.create_user_message(conversation.id, "First")
        msg2 = AIMessage.create_assistant_message(conversation.id, "Response")
        msg3 = AIMessage.create_user_message(conversation.id, "Second")
        db_session.add_all([msg1, msg2, msg3])
        db_session.flush()

        messages = service.get_messages(conversation.id)
        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[1].content == "Response"
        assert messages[2].content == "Second"

    @pytest.mark.asyncio
    async def test_send_message(self, db_session, sample_ai_provider):
        """Test sending a message (mocked AI response)."""
        service = ChatService(db_session)
        conversation = service.create_conversation(
            title="Test",
            provider_name="openai",
        )
        db_session.flush()

        mock_response = AIResponse(
            content="This is the AI response",
            tokens_in=10,
            tokens_out=5,
            model="gpt-4o",
        )

        with patch.object(service, '_build_messages_for_ai', return_value=[]):
            with patch('app.services.ai.chat_service.ProviderFactory') as MockFactory:
                mock_provider = MagicMock()
                mock_provider.chat = AsyncMock(return_value=mock_response)
                mock_provider.default_model = "gpt-4o"
                # ProviderFactory is now instantiated, so mock the instance method
                mock_factory_instance = MagicMock()
                mock_factory_instance.get_provider.return_value = mock_provider
                MockFactory.return_value = mock_factory_instance

                response = await service.send_message(
                    conversation_id=conversation.id,
                    content="Hello, AI!",
                )

                assert response.content == "This is the AI response"
                assert response.role == AIMessageRole.assistant

    @pytest.mark.asyncio
    async def test_send_message_conversation_not_found(self, db_session):
        """Test sending message to non-existent conversation."""
        service = ChatService(db_session)

        with pytest.raises(ValueError, match="not found"):
            await service.send_message(
                conversation_id=uuid4(),
                content="Hello",
            )


class TestChatServiceStats:
    """Test conversation statistics."""

    def test_get_conversation_stats_empty(self, db_session):
        """Test stats for empty conversation."""
        service = ChatService(db_session)
        conversation = service.create_conversation(title="Empty")
        db_session.flush()

        stats = service.get_conversation_stats(conversation.id)

        assert stats["message_count"] == 0
        assert stats["user_messages"] == 0
        assert stats["assistant_messages"] == 0
        assert stats["total_tokens"] == 0

    def test_get_conversation_stats_with_messages(self, db_session):
        """Test stats with messages."""
        service = ChatService(db_session)
        conversation = service.create_conversation(title="Test")
        db_session.flush()

        # Add messages
        msg1 = AIMessage.create_user_message(conversation.id, "Hello")
        msg2 = AIMessage.create_assistant_message(
            conversation.id, "Hi there",
            tokens_in=10, tokens_out=5,
        )
        db_session.add_all([msg1, msg2])
        db_session.flush()

        stats = service.get_conversation_stats(conversation.id)

        assert stats["message_count"] == 2
        assert stats["user_messages"] == 1
        assert stats["assistant_messages"] == 1
        assert stats["total_tokens_in"] == 10
        assert stats["total_tokens_out"] == 5
        assert stats["total_tokens"] == 15


class TestGetChatService:
    """Test factory function."""

    def test_returns_chat_service(self, db_session):
        """Test that factory returns ChatService instance."""
        service = get_chat_service(db_session)
        assert isinstance(service, ChatService)

    def test_service_has_db_session(self, db_session):
        """Test that service has database session."""
        service = get_chat_service(db_session)
        assert service.db is db_session
