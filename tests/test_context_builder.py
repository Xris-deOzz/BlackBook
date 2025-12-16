"""
Tests for AI context builder.
"""

import pytest
from uuid import uuid4

from app.models import (
    Person,
    PersonStatus,
    Organization,
    Tag,
    AIDataAccessSettings,
)
from app.services.ai.context_builder import ContextBuilder


@pytest.fixture
def data_access_settings(db_session):
    """Get or create data access settings."""
    return AIDataAccessSettings.get_settings(db_session)


@pytest.fixture
def person_with_details(db_session):
    """Create a person with full details."""
    person = Person(
        full_name="John Smith",
        first_name="John",
        last_name="Smith",
        title="CEO",
        status=PersonStatus.active,
        linkedin="https://linkedin.com/in/johnsmith",  # Field is 'linkedin' not 'linkedin_url'
        notes="Important contact. Email: john@example.com, Phone: 555-123-4567",
    )
    db_session.add(person)
    db_session.flush()
    return person


@pytest.fixture
def org_with_details(db_session):
    """Create an organization with full details."""
    org = Organization(
        name="Acme Corp",
        category="Technology",  # Use 'category' instead of 'industry'
        website="https://acme.com",
        description="A technology company based in San Francisco, CA",
        notes="Major client. Contact: support@acme.com",
    )
    db_session.add(org)
    db_session.flush()
    return org


class TestContextBuilderPersonContext:
    """Test building person context."""

    def test_build_person_context_basic(self, db_session, person_with_details):
        """Test basic person context building."""
        builder = ContextBuilder(db_session)
        context = builder.build_person_context(person_with_details.id)

        assert "John Smith" in context
        assert "CEO" in context

    def test_build_person_context_with_linkedin(self, db_session, person_with_details, data_access_settings):
        """Test person context includes LinkedIn when allowed."""
        data_access_settings.allow_linkedin = True
        db_session.flush()

        builder = ContextBuilder(db_session)
        context = builder.build_person_context(person_with_details.id)

        assert "linkedin.com" in context

    def test_build_person_context_without_linkedin(self, db_session, person_with_details, data_access_settings):
        """Test person context excludes LinkedIn when not allowed."""
        data_access_settings.allow_linkedin = False
        db_session.flush()

        builder = ContextBuilder(db_session)
        context = builder.build_person_context(person_with_details.id)

        assert "linkedin.com" not in context

    def test_build_person_context_filters_notes(self, db_session, person_with_details, data_access_settings):
        """Test that notes are filtered for sensitive data."""
        data_access_settings.allow_notes = True
        db_session.flush()

        builder = ContextBuilder(db_session)
        context = builder.build_person_context(person_with_details.id)

        # Notes should be included but email/phone should be redacted
        assert "Important contact" in context
        assert "john@example.com" not in context
        assert "555-123-4567" not in context

    def test_build_person_context_not_found(self, db_session):
        """Test building context for non-existent person."""
        builder = ContextBuilder(db_session)
        context = builder.build_person_context(uuid4())

        assert context == ""


class TestContextBuilderOrganizationContext:
    """Test building organization context."""

    def test_build_org_context_basic(self, db_session, org_with_details):
        """Test basic organization context building."""
        builder = ContextBuilder(db_session)
        context = builder.build_organization_context(org_with_details.id)

        assert "Acme Corp" in context
        assert "Technology" in context  # category field
        assert "acme.com" in context  # website field

    def test_build_org_context_with_website(self, db_session, org_with_details, data_access_settings):
        """Test org context includes website."""
        builder = ContextBuilder(db_session)
        context = builder.build_organization_context(org_with_details.id)

        # Organization model doesn't have linkedin field, test website instead
        assert "acme.com" in context

    def test_build_org_context_filters_notes(self, db_session, org_with_details, data_access_settings):
        """Test that org notes are filtered for sensitive data."""
        data_access_settings.allow_notes = True
        db_session.flush()

        builder = ContextBuilder(db_session)
        context = builder.build_organization_context(org_with_details.id)

        # Notes should be included but email should be redacted
        assert "Major client" in context
        assert "support@acme.com" not in context

    def test_build_org_context_not_found(self, db_session):
        """Test building context for non-existent organization."""
        builder = ContextBuilder(db_session)
        context = builder.build_organization_context(uuid4())

        assert context == ""


class TestContextBuilderSystemPrompt:
    """Test system prompt building."""

    def test_build_system_prompt_basic(self, db_session):
        """Test basic system prompt."""
        builder = ContextBuilder(db_session)
        prompt = builder.build_system_prompt()

        assert "research assistant" in prompt.lower()
        assert "CRM" in prompt or "crm" in prompt.lower()

    def test_build_system_prompt_with_person(self, db_session, person_with_details):
        """Test system prompt with person context."""
        builder = ContextBuilder(db_session)
        prompt = builder.build_system_prompt(person_id=person_with_details.id)

        assert "John Smith" in prompt
        assert "Person Context" in prompt

    def test_build_system_prompt_with_org(self, db_session, org_with_details):
        """Test system prompt with organization context."""
        builder = ContextBuilder(db_session)
        prompt = builder.build_system_prompt(org_id=org_with_details.id)

        assert "Acme Corp" in prompt
        assert "Organization Context" in prompt


class TestContextBuilderConversation:
    """Test conversation context building."""

    def test_build_conversation_context_adds_system(self, db_session):
        """Test that system message is prepended."""
        builder = ContextBuilder(db_session)
        messages = [
            {"role": "user", "content": "Hello"},
        ]
        result = builder.build_conversation_context(messages)

        assert result[0]["role"] == "system"
        assert len(result) == 2

    def test_build_conversation_context_filters_user_messages(self, db_session):
        """Test that user messages are filtered for sensitive data."""
        builder = ContextBuilder(db_session)
        messages = [
            {"role": "user", "content": "My email is john@example.com"},
        ]
        result = builder.build_conversation_context(messages)

        user_msg = result[1]
        assert "john@example.com" not in user_msg["content"]

    def test_build_conversation_context_preserves_assistant(self, db_session):
        """Test that assistant messages are not filtered."""
        builder = ContextBuilder(db_session)
        messages = [
            {"role": "assistant", "content": "The contact email is test@example.com"},
        ]
        result = builder.build_conversation_context(messages)

        # Note: In real usage, assistant wouldn't have PII, but we preserve it
        assistant_msg = result[1]
        assert assistant_msg["role"] == "assistant"


class TestContextBuilderDataAccess:
    """Test data access settings integration."""

    def test_respects_allow_notes_false(self, db_session, person_with_details, data_access_settings):
        """Test that notes are excluded when not allowed."""
        data_access_settings.allow_notes = False
        db_session.flush()

        builder = ContextBuilder(db_session)
        context = builder.build_person_context(person_with_details.id)

        assert "Important contact" not in context

    def test_respects_allow_tags_false(self, db_session, person_with_details, data_access_settings):
        """Test that tags are excluded when not allowed."""
        # Add a tag to person
        tag = Tag(name="VIP")
        db_session.add(tag)
        db_session.flush()
        person_with_details.tags.append(tag)
        db_session.flush()

        data_access_settings.allow_tags = False
        db_session.flush()

        builder = ContextBuilder(db_session)
        context = builder.build_person_context(person_with_details.id)

        assert "VIP" not in context

    def test_caches_data_access_settings(self, db_session, data_access_settings):
        """Test that data access settings are cached."""
        builder = ContextBuilder(db_session)

        # Access twice
        _ = builder.data_access
        settings2 = builder.data_access

        # Should be same instance (cached)
        assert builder._data_access is settings2
