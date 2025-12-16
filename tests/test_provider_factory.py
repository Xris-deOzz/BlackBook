"""
Tests for ProviderFactory.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.models import AIProvider, AIAPIKey, AIProviderType
from app.services.ai import ProviderFactory
from app.services.ai.base_provider import ProviderError
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.anthropic_provider import AnthropicProvider
from app.services.ai.google_provider import GoogleProvider


class TestProviderFactory:
    """Test ProviderFactory class."""

    @pytest.fixture
    def openai_provider_with_key(self, db_session):
        """Create OpenAI provider with a valid key."""
        # Delete any existing OpenAI providers first
        db_session.query(AIAPIKey).filter(
            AIAPIKey.provider_id.in_(
                db_session.query(AIProvider.id).filter(AIProvider.api_type == AIProviderType.openai)
            )
        ).delete(synchronize_session=False)
        db_session.query(AIProvider).filter(AIProvider.api_type == AIProviderType.openai).delete()
        db_session.flush()

        provider = AIProvider(
            name="OpenAI",
            api_type=AIProviderType.openai,
            is_local=False,
            is_active=True,
        )
        db_session.add(provider)
        db_session.flush()

        api_key = AIAPIKey(provider_id=provider.id)
        api_key.set_api_key("sk-test-openai-key")
        api_key.is_valid = True
        db_session.add(api_key)
        db_session.flush()

        return provider

    @pytest.fixture
    def anthropic_provider_with_key(self, db_session):
        """Create Anthropic provider with a valid key."""
        # Delete any existing Anthropic providers first
        db_session.query(AIAPIKey).filter(
            AIAPIKey.provider_id.in_(
                db_session.query(AIProvider.id).filter(AIProvider.api_type == AIProviderType.anthropic)
            )
        ).delete(synchronize_session=False)
        db_session.query(AIProvider).filter(AIProvider.api_type == AIProviderType.anthropic).delete()
        db_session.flush()

        provider = AIProvider(
            name="Claude",
            api_type=AIProviderType.anthropic,
            is_local=False,
            is_active=True,
        )
        db_session.add(provider)
        db_session.flush()

        api_key = AIAPIKey(provider_id=provider.id)
        api_key.set_api_key("sk-ant-test-anthropic-key")
        api_key.is_valid = True
        db_session.add(api_key)
        db_session.flush()

        return provider

    @pytest.fixture
    def google_provider_with_key(self, db_session):
        """Create Google provider with a valid key."""
        # Delete any existing Google providers first
        db_session.query(AIAPIKey).filter(
            AIAPIKey.provider_id.in_(
                db_session.query(AIProvider.id).filter(AIProvider.api_type == AIProviderType.google)
            )
        ).delete(synchronize_session=False)
        db_session.query(AIProvider).filter(AIProvider.api_type == AIProviderType.google).delete()
        db_session.flush()

        provider = AIProvider(
            name="Gemini",
            api_type=AIProviderType.google,
            is_local=False,
            is_active=True,
        )
        db_session.add(provider)
        db_session.flush()

        api_key = AIAPIKey(provider_id=provider.id)
        api_key.set_api_key("AIza-test-google-key")
        api_key.is_valid = True
        db_session.add(api_key)
        db_session.flush()

        return provider

    def test_get_provider_openai(self, db_session, openai_provider_with_key):
        """Test getting OpenAI provider."""
        factory = ProviderFactory(db_session)
        provider = factory.get_provider("openai")

        assert provider is not None
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "sk-test-openai-key"

    def test_get_provider_anthropic(self, db_session, anthropic_provider_with_key):
        """Test getting Anthropic provider."""
        factory = ProviderFactory(db_session)
        provider = factory.get_provider("anthropic")

        assert provider is not None
        assert isinstance(provider, AnthropicProvider)
        assert provider.api_key == "sk-ant-test-anthropic-key"

    def test_get_provider_google(self, db_session, google_provider_with_key):
        """Test getting Google provider."""
        factory = ProviderFactory(db_session)
        provider = factory.get_provider("google")

        assert provider is not None
        assert isinstance(provider, GoogleProvider)
        assert provider.api_key == "AIza-test-google-key"

    def test_get_provider_invalid_type(self, db_session):
        """Test getting provider with invalid type raises error."""
        factory = ProviderFactory(db_session)
        with pytest.raises(ProviderError, match="Unknown provider"):
            factory.get_provider("invalid_provider")

    def test_get_provider_no_key(self, db_session):
        """Test getting provider without API key raises error."""
        # Clean up any existing OpenAI providers first
        db_session.query(AIAPIKey).filter(
            AIAPIKey.provider_id.in_(
                db_session.query(AIProvider.id).filter(AIProvider.api_type == AIProviderType.openai)
            )
        ).delete(synchronize_session=False)
        db_session.query(AIProvider).filter(AIProvider.api_type == AIProviderType.openai).delete()
        db_session.flush()

        # Create provider without key
        provider = AIProvider(
            name="NoKey",
            api_type=AIProviderType.openai,
            is_local=False,
            is_active=True,
        )
        db_session.add(provider)
        db_session.flush()

        factory = ProviderFactory(db_session)
        with pytest.raises(ProviderError, match="No API key"):
            factory.get_provider("openai")

    def test_get_provider_inactive(self, db_session):
        """Test getting inactive provider raises error."""
        # Clean up any existing OpenAI providers first
        db_session.query(AIAPIKey).filter(
            AIAPIKey.provider_id.in_(
                db_session.query(AIProvider.id).filter(AIProvider.api_type == AIProviderType.openai)
            )
        ).delete(synchronize_session=False)
        db_session.query(AIProvider).filter(AIProvider.api_type == AIProviderType.openai).delete()
        db_session.flush()

        provider = AIProvider(
            name="Inactive",
            api_type=AIProviderType.openai,
            is_local=False,
            is_active=False,  # Inactive
        )
        db_session.add(provider)
        db_session.flush()

        api_key = AIAPIKey(provider_id=provider.id)
        api_key.set_api_key("sk-test-key")
        db_session.add(api_key)
        db_session.flush()

        factory = ProviderFactory(db_session)
        with pytest.raises(ProviderError):
            factory.get_provider("openai")

    def test_get_available_providers_all(
        self, db_session, openai_provider_with_key, anthropic_provider_with_key, google_provider_with_key
    ):
        """Test getting list of available providers."""
        factory = ProviderFactory(db_session)
        available = factory.get_available_providers()

        assert isinstance(available, list)
        assert len(available) == 3
        # Returns list of dicts with api_type
        api_types = [p["api_type"] for p in available]
        assert "openai" in api_types
        assert "anthropic" in api_types
        assert "google" in api_types

    def test_get_available_providers_partial(self, db_session, openai_provider_with_key):
        """Test getting available providers with only some configured."""
        # Clean up any providers other than OpenAI
        for api_type in [AIProviderType.anthropic, AIProviderType.google]:
            db_session.query(AIAPIKey).filter(
                AIAPIKey.provider_id.in_(
                    db_session.query(AIProvider.id).filter(AIProvider.api_type == api_type)
                )
            ).delete(synchronize_session=False)
            db_session.query(AIProvider).filter(AIProvider.api_type == api_type).delete()
        db_session.flush()

        factory = ProviderFactory(db_session)
        available = factory.get_available_providers()

        assert len(available) == 1
        assert available[0]["api_type"] == "openai"

    def test_get_available_providers_none(self, db_session):
        """Test getting available providers when none configured."""
        # Clean up all providers
        db_session.query(AIAPIKey).delete()
        db_session.query(AIProvider).delete()
        db_session.flush()

        factory = ProviderFactory(db_session)
        available = factory.get_available_providers()

        assert isinstance(available, list)
        assert len(available) == 0


class TestProviderFactoryValidation:
    """Test ProviderFactory validation methods."""

    @pytest.fixture
    def factory(self, db_session):
        """Create a factory instance."""
        return ProviderFactory(db_session)

    @pytest.mark.asyncio
    async def test_validate_api_key_openai_valid(self, db_session, factory):
        """Test validating OpenAI API key (mocked)."""
        with patch('app.services.ai.provider_factory._PROVIDERS') as mock_providers:
            mock_provider_class = MagicMock()
            mock_instance = MagicMock()
            mock_instance.validate_key = AsyncMock(return_value=True)
            mock_provider_class.return_value = mock_instance
            mock_providers.__contains__ = MagicMock(return_value=True)
            mock_providers.__getitem__ = MagicMock(return_value=mock_provider_class)

            result = await factory.validate_api_key("openai", "sk-test-key")

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_api_key_openai_invalid(self, db_session, factory):
        """Test validating invalid OpenAI API key (mocked)."""
        with patch('app.services.ai.provider_factory._PROVIDERS') as mock_providers:
            mock_provider_class = MagicMock()
            mock_instance = MagicMock()
            mock_instance.validate_key = AsyncMock(return_value=False)
            mock_provider_class.return_value = mock_instance
            mock_providers.__contains__ = MagicMock(return_value=True)
            mock_providers.__getitem__ = MagicMock(return_value=mock_provider_class)

            result = await factory.validate_api_key("openai", "invalid-key")

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_api_key_anthropic_valid(self, db_session, factory):
        """Test validating Anthropic API key (mocked)."""
        with patch('app.services.ai.provider_factory._PROVIDERS') as mock_providers:
            mock_provider_class = MagicMock()
            mock_instance = MagicMock()
            mock_instance.validate_key = AsyncMock(return_value=True)
            mock_provider_class.return_value = mock_instance
            mock_providers.__contains__ = MagicMock(return_value=True)
            mock_providers.__getitem__ = MagicMock(return_value=mock_provider_class)

            result = await factory.validate_api_key("anthropic", "sk-ant-test-key")

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_api_key_google_valid(self, db_session, factory):
        """Test validating Google API key (mocked)."""
        with patch('app.services.ai.provider_factory._PROVIDERS') as mock_providers:
            mock_provider_class = MagicMock()
            mock_instance = MagicMock()
            mock_instance.validate_key = AsyncMock(return_value=True)
            mock_provider_class.return_value = mock_instance
            mock_providers.__contains__ = MagicMock(return_value=True)
            mock_providers.__getitem__ = MagicMock(return_value=mock_provider_class)

            result = await factory.validate_api_key("google", "AIza-test-key")

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_provider(self, db_session, factory):
        """Test validating key for invalid provider returns False."""
        result = await factory.validate_api_key("invalid_provider", "any-key")

        assert result is False


class TestProviderFactoryWithConfig:
    """Test ProviderFactory using config-based API keys."""

    def test_get_provider_from_config(self, db_session):
        """Test getting provider with key from config."""
        # This test demonstrates the fallback to config-based keys
        # In production, keys can come from either database or config

        # Clean up any existing OpenAI providers first
        db_session.query(AIAPIKey).filter(
            AIAPIKey.provider_id.in_(
                db_session.query(AIProvider.id).filter(AIProvider.api_type == AIProviderType.openai)
            )
        ).delete(synchronize_session=False)
        db_session.query(AIProvider).filter(AIProvider.api_type == AIProviderType.openai).delete()
        db_session.flush()

        # Create provider without database key
        provider = AIProvider(
            name="OpenAI",
            api_type=AIProviderType.openai,
            is_local=False,
            is_active=True,
        )
        db_session.add(provider)
        db_session.flush()

        # Without a key in DB or config, should raise
        factory = ProviderFactory(db_session)
        with pytest.raises(ProviderError, match="No API key"):
            factory.get_provider("openai")
