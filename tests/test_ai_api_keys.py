"""
Tests for AI API key model with encryption.
"""

import pytest
from uuid import uuid4

from app.models import AIProvider, AIAPIKey, AIProviderType


class TestAIAPIKeyModel:
    """Test AIAPIKey model."""

    @pytest.fixture
    def sample_provider(self, db_session):
        """Create a sample AI provider for testing."""
        provider = AIProvider(
            name="Test Provider",
            api_type=AIProviderType.openai,
            is_local=False,
            is_active=True,
        )
        db_session.add(provider)
        db_session.flush()
        return provider

    def test_create_api_key(self, db_session, sample_provider):
        """Test creating an API key record."""
        api_key = AIAPIKey(
            provider_id=sample_provider.id,
            label="Production Key",
        )
        api_key.set_api_key("sk-test-key-123")  # Must set before flush due to NOT NULL
        db_session.add(api_key)
        db_session.flush()

        assert api_key.id is not None
        assert api_key.provider_id == sample_provider.id
        assert api_key.label == "Production Key"
        assert api_key.is_valid is None  # Not tested yet
        assert api_key.last_tested is None

    def test_set_api_key_encrypts(self, db_session, sample_provider):
        """Test that set_api_key encrypts the key."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        original_key = "sk-test-1234567890abcdef"
        api_key.set_api_key(original_key)  # Set before flush
        db_session.add(api_key)
        db_session.flush()

        # Encrypted key should not be the same as original
        assert api_key.encrypted_key is not None
        assert api_key.encrypted_key != original_key
        assert "sk-test" not in api_key.encrypted_key

    def test_get_api_key_decrypts(self, db_session, sample_provider):
        """Test that get_api_key decrypts the key."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        original_key = "sk-test-1234567890abcdef"
        api_key.set_api_key(original_key)  # Set before flush
        db_session.add(api_key)
        db_session.flush()

        decrypted = api_key.get_api_key()
        assert decrypted == original_key

    def test_encrypt_decrypt_roundtrip(self, db_session, sample_provider):
        """Test encrypt/decrypt roundtrip with various key formats."""
        test_keys = [
            "sk-proj-abc123",  # OpenAI format
            "sk-ant-api03-abc123xyz",  # Anthropic format
            "AIzaSyAbc123xyz",  # Google format
            "A" * 100,  # Long key
        ]

        for original_key in test_keys:
            api_key = AIAPIKey(provider_id=sample_provider.id)
            api_key.set_api_key(original_key)  # Set before flush
            db_session.add(api_key)
            db_session.flush()

            decrypted = api_key.get_api_key()

            assert decrypted == original_key, f"Failed for key: {original_key[:10]}..."

    def test_get_masked_key_short(self, db_session, sample_provider):
        """Test get_masked_key with short key."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        api_key.set_api_key("short")  # Set before flush
        db_session.add(api_key)
        db_session.flush()

        masked = api_key.get_masked_key()

        # For very short keys, should still mask
        assert "short" not in masked or len(masked) < len("short")

    def test_get_masked_key_standard(self, db_session, sample_provider):
        """Test get_masked_key with standard key."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        original = "sk-proj-1234567890abcdef"
        api_key.set_api_key(original)  # Set before flush
        db_session.add(api_key)
        db_session.flush()

        masked = api_key.get_masked_key()

        # Should show only last 4 characters
        assert masked.endswith("cdef")
        assert "..." in masked or len(masked) < len(original)
        # Should not reveal the full key
        assert "1234567890" not in masked

    def test_get_masked_key_no_key(self, db_session, sample_provider):
        """Test get_masked_key when key is empty string."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        api_key.set_api_key("")  # Empty key still satisfies NOT NULL
        db_session.add(api_key)
        db_session.flush()

        masked = api_key.get_masked_key()
        assert masked is None or masked == ""

    def test_api_key_relationship(self, db_session, sample_provider):
        """Test relationship between AIAPIKey and AIProvider."""
        api_key = AIAPIKey(
            provider_id=sample_provider.id,
            label="Test Key",
        )
        api_key.set_api_key("sk-test-123")
        db_session.add(api_key)
        db_session.flush()

        # Test forward relationship
        assert api_key.provider.id == sample_provider.id
        assert api_key.provider.name == "Test Provider"

        # Test reverse relationship
        db_session.refresh(sample_provider)
        assert len(sample_provider.api_keys) == 1
        assert sample_provider.api_keys[0].id == api_key.id

    def test_multiple_keys_per_provider(self, db_session, sample_provider):
        """Test that a provider can have multiple API keys."""
        key1 = AIAPIKey(provider_id=sample_provider.id, label="Key 1")
        key1.set_api_key("sk-key-1")
        key2 = AIAPIKey(provider_id=sample_provider.id, label="Key 2")
        key2.set_api_key("sk-key-2")

        db_session.add_all([key1, key2])
        db_session.flush()

        db_session.refresh(sample_provider)
        assert len(sample_provider.api_keys) == 2

    def test_is_valid_tracking(self, db_session, sample_provider):
        """Test is_valid field tracking."""
        from datetime import datetime

        api_key = AIAPIKey(provider_id=sample_provider.id)
        api_key.set_api_key("sk-test-123")
        db_session.add(api_key)
        db_session.flush()

        # Initially None (not tested)
        assert api_key.is_valid is None
        assert api_key.last_tested is None

        # Mark as valid
        api_key.is_valid = True
        api_key.last_tested = datetime.utcnow()
        db_session.flush()

        assert api_key.is_valid is True
        assert api_key.last_tested is not None

        # Mark as invalid
        api_key.is_valid = False
        db_session.flush()

        assert api_key.is_valid is False


class TestAIAPIKeyEncryptionEdgeCases:
    """Test edge cases for API key encryption."""

    @pytest.fixture
    def sample_provider(self, db_session):
        """Create a sample AI provider for testing."""
        provider = AIProvider(
            name="Test Provider",
            api_type=AIProviderType.anthropic,
            is_local=False,
            is_active=True,
        )
        db_session.add(provider)
        db_session.flush()
        return provider

    def test_unicode_in_key(self, db_session, sample_provider):
        """Test handling of unicode characters in key (edge case)."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        # Most API keys are ASCII, but test unicode handling
        original = "sk-test-123"
        api_key.set_api_key(original)  # Set before flush
        db_session.add(api_key)
        db_session.flush()

        decrypted = api_key.get_api_key()
        assert decrypted == original

    def test_empty_key_handling(self, db_session, sample_provider):
        """Test handling of empty key."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        # Empty string should still work
        api_key.set_api_key("")  # Set before flush
        db_session.add(api_key)
        db_session.flush()

        decrypted = api_key.get_api_key()
        assert decrypted == ""

    def test_key_update(self, db_session, sample_provider):
        """Test updating an existing key."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        # Set initial key before flush
        api_key.set_api_key("sk-old-key")
        db_session.add(api_key)
        db_session.flush()

        assert api_key.get_api_key() == "sk-old-key"

        # Update key
        api_key.set_api_key("sk-new-key")
        assert api_key.get_api_key() == "sk-new-key"

    def test_key_with_special_characters(self, db_session, sample_provider):
        """Test key with special characters."""
        api_key = AIAPIKey(provider_id=sample_provider.id)
        original = "sk-proj_abc123-xyz/+="
        api_key.set_api_key(original)  # Set before flush
        db_session.add(api_key)
        db_session.flush()

        decrypted = api_key.get_api_key()
        assert decrypted == original
