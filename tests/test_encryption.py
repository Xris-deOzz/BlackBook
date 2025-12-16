"""
Tests for EncryptionService.
"""

import pytest
from cryptography.fernet import Fernet

from app.services.encryption import (
    EncryptionService,
    EncryptionError,
    EncryptionKeyError,
    DecryptionError,
    get_encryption_service,
)


@pytest.fixture
def valid_key():
    """Generate a valid Fernet key for testing."""
    return Fernet.generate_key().decode()


@pytest.fixture
def encryption_service(valid_key):
    """Create an EncryptionService with a valid key."""
    return EncryptionService(valid_key)


class TestEncryptionServiceInit:
    """Test EncryptionService initialization."""

    def test_init_with_valid_key(self, valid_key):
        """Test initialization with valid key."""
        service = EncryptionService(valid_key)
        assert service is not None

    def test_init_with_empty_key_raises_error(self):
        """Test that empty key raises EncryptionKeyError."""
        with pytest.raises(EncryptionKeyError, match="Encryption key is required"):
            EncryptionService("")

    def test_init_with_none_key_raises_error(self):
        """Test that None key raises EncryptionKeyError."""
        with pytest.raises(EncryptionKeyError, match="Encryption key is required"):
            EncryptionService(None)

    def test_init_with_invalid_key_raises_error(self):
        """Test that invalid key raises EncryptionKeyError."""
        with pytest.raises(EncryptionKeyError, match="Invalid encryption key"):
            EncryptionService("not-a-valid-fernet-key")


class TestEncryptDecrypt:
    """Test basic encrypt/decrypt operations."""

    def test_encrypt_returns_string(self, encryption_service):
        """Test that encrypt returns a string."""
        result = encryption_service.encrypt("test data")
        assert isinstance(result, str)

    def test_encrypt_produces_different_output_each_time(self, encryption_service):
        """Test that encrypt produces different ciphertext each time (due to IV)."""
        data = "same data"
        result1 = encryption_service.encrypt(data)
        result2 = encryption_service.encrypt(data)
        assert result1 != result2

    def test_decrypt_returns_original_data(self, encryption_service):
        """Test encrypt/decrypt roundtrip."""
        original = "Hello, World!"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_decrypt_with_unicode(self, encryption_service):
        """Test encrypt/decrypt with unicode characters."""
        original = "Hello, 世界! 🔐"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_decrypt_with_long_data(self, encryption_service):
        """Test encrypt/decrypt with longer data."""
        original = "x" * 10000
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_decrypt_invalid_data_raises_error(self, encryption_service):
        """Test that decrypting invalid data raises DecryptionError."""
        with pytest.raises(DecryptionError, match="Invalid or corrupted"):
            encryption_service.decrypt("not-valid-encrypted-data")

    def test_decrypt_with_wrong_key_raises_error(self, valid_key):
        """Test that decrypting with wrong key raises DecryptionError."""
        service1 = EncryptionService(valid_key)
        service2 = EncryptionService(Fernet.generate_key().decode())

        encrypted = service1.encrypt("secret data")

        with pytest.raises(DecryptionError):
            service2.decrypt(encrypted)


class TestEncryptDecryptJson:
    """Test JSON encrypt/decrypt operations."""

    def test_encrypt_json_dict(self, encryption_service):
        """Test encrypting a dictionary."""
        data = {"access_token": "ya29.xxx", "refresh_token": "1//xxx"}
        encrypted = encryption_service.encrypt_json(data)
        assert isinstance(encrypted, str)

    def test_decrypt_json_returns_dict(self, encryption_service):
        """Test decrypting to a dictionary."""
        original = {"key": "value", "number": 42}
        encrypted = encryption_service.encrypt_json(original)
        decrypted = encryption_service.decrypt_json(encrypted)
        assert decrypted == original

    def test_encrypt_json_list(self, encryption_service):
        """Test encrypting a list."""
        data = ["item1", "item2", {"nested": "value"}]
        encrypted = encryption_service.encrypt_json(data)
        decrypted = encryption_service.decrypt_json(encrypted)
        assert decrypted == data

    def test_encrypt_json_complex_structure(self, encryption_service):
        """Test encrypting complex nested structure."""
        data = {
            "credentials": {
                "access_token": "ya29.xxx",
                "refresh_token": "1//xxx",
                "scopes": ["gmail.readonly", "calendar.readonly"],
            },
            "metadata": {
                "created_at": "2024-01-01T00:00:00Z",
                "user_id": 12345,
            },
        }
        encrypted = encryption_service.encrypt_json(data)
        decrypted = encryption_service.decrypt_json(encrypted)
        assert decrypted == data

    def test_encrypt_json_with_non_serializable_raises_error(self, encryption_service):
        """Test that non-serializable data raises EncryptionError."""
        data = {"func": lambda x: x}  # Functions are not JSON serializable

        with pytest.raises(EncryptionError, match="Failed to serialize"):
            encryption_service.encrypt_json(data)


class TestGenerateKey:
    """Test key generation."""

    def test_generate_key_returns_string(self):
        """Test that generate_key returns a string."""
        key = EncryptionService.generate_key()
        assert isinstance(key, str)

    def test_generated_key_is_valid(self):
        """Test that generated key can be used."""
        key = EncryptionService.generate_key()
        service = EncryptionService(key)

        # Should work for encrypt/decrypt
        encrypted = service.encrypt("test")
        decrypted = service.decrypt(encrypted)
        assert decrypted == "test"

    def test_generate_key_produces_different_keys(self):
        """Test that each call generates a different key."""
        key1 = EncryptionService.generate_key()
        key2 = EncryptionService.generate_key()
        assert key1 != key2


class TestGetEncryptionService:
    """Test get_encryption_service factory function."""

    def test_get_encryption_service_returns_service(self):
        """Test that get_encryption_service returns a valid service."""
        # This relies on .env having a valid ENCRYPTION_KEY
        service = get_encryption_service()
        assert isinstance(service, EncryptionService)

    def test_get_encryption_service_works_for_encrypt_decrypt(self):
        """Test that the service from factory works correctly."""
        service = get_encryption_service()

        original = "test oauth credentials"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        assert decrypted == original

    def test_get_encryption_service_is_cached(self):
        """Test that get_encryption_service returns the same instance."""
        # Clear cache first
        get_encryption_service.cache_clear()

        service1 = get_encryption_service()
        service2 = get_encryption_service()
        assert service1 is service2


class TestOAuthCredentialsScenario:
    """Test realistic OAuth credentials encryption scenario."""

    def test_oauth_credentials_roundtrip(self, encryption_service):
        """Test encrypting and decrypting OAuth credentials like we would in the app."""
        # Simulate OAuth credentials from Google
        credentials = {
            "access_token": "ya29.a0AfB_byC1234567890",
            "refresh_token": "1//0g1234567890-abcdefg",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "123456789.apps.googleusercontent.com",
            "client_secret": "GOCSPX-abcdefg123456",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/calendar.readonly",
            ],
            "expiry": "2024-12-08T12:00:00.000000Z",
        }

        # Encrypt for storage
        encrypted = encryption_service.encrypt_json(credentials)

        # Verify it's not plaintext
        assert "ya29" not in encrypted
        assert "refresh_token" not in encrypted

        # Decrypt for use
        decrypted = encryption_service.decrypt_json(encrypted)

        # Verify all fields are intact
        assert decrypted["access_token"] == credentials["access_token"]
        assert decrypted["refresh_token"] == credentials["refresh_token"]
        assert decrypted["scopes"] == credentials["scopes"]
