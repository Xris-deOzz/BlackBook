"""
Tests for application configuration settings.
"""

import pytest
from app.config import Settings, get_settings


class TestConfigSettings:
    """Test configuration settings loading."""

    def test_settings_loads_from_env(self):
        """Test that settings load from .env file."""
        settings = get_settings()

        # Database settings should be loaded
        assert settings.db_host is not None
        assert settings.db_port == 5432
        assert settings.db_name == "perunsblackbook"

    def test_database_url_property(self):
        """Test database URL is correctly constructed."""
        settings = get_settings()

        url = settings.database_url
        assert url.startswith("postgresql://")
        assert settings.db_user in url
        assert settings.db_name in url

    def test_google_oauth_settings_loaded(self):
        """Test Google OAuth settings are loaded from env."""
        settings = get_settings()

        # These should be loaded from .env
        assert settings.google_client_id != ""
        assert settings.google_client_secret != ""
        assert settings.google_redirect_uri != ""

    def test_google_oauth_configured_property(self):
        """Test google_oauth_configured property."""
        settings = get_settings()

        # With valid credentials in .env, should be True
        assert settings.google_oauth_configured is True

    def test_encryption_key_loaded(self):
        """Test encryption key is loaded from env."""
        settings = get_settings()

        assert settings.encryption_key != ""
        # Fernet keys are base64 encoded, typically 44 chars
        assert len(settings.encryption_key) > 0

    def test_encryption_configured_property(self):
        """Test encryption_configured property."""
        settings = get_settings()

        assert settings.encryption_configured is True

    def test_google_redirect_uri_format(self):
        """Test redirect URI has expected format."""
        settings = get_settings()

        assert settings.google_redirect_uri.startswith("http")
        assert "/auth/google/callback" in settings.google_redirect_uri


class TestSettingsDefaults:
    """Test settings default values."""

    def test_default_values_when_env_missing(self):
        """Test that defaults are used when env vars missing."""
        # Create settings without env file to test defaults
        settings = Settings(
            _env_file=None,  # Don't load .env
            db_password="test",  # Required field
        )

        assert settings.db_host == "localhost"
        assert settings.db_port == 5432
        assert settings.google_redirect_uri == "http://localhost:8000/auth/google/callback"

    def test_unconfigured_oauth_returns_false(self):
        """Test that unconfigured OAuth returns False."""
        settings = Settings(
            _env_file=None,
            db_password="test",
            google_client_id="",
            google_client_secret="",
        )

        assert settings.google_oauth_configured is False

    def test_unconfigured_encryption_returns_false(self):
        """Test that unconfigured encryption returns False."""
        settings = Settings(
            _env_file=None,
            db_password="test",
            encryption_key="",
        )

        assert settings.encryption_configured is False


class TestSettingsValidation:
    """Test settings validation."""

    def test_google_client_id_format(self):
        """Test Google client ID has expected format."""
        settings = get_settings()

        # Google client IDs end with .apps.googleusercontent.com
        assert settings.google_client_id.endswith(".apps.googleusercontent.com")

    def test_encryption_key_is_valid_fernet_key(self):
        """Test encryption key can be used with Fernet."""
        from cryptography.fernet import Fernet

        settings = get_settings()

        # Should not raise an exception
        fernet = Fernet(settings.encryption_key.encode())
        assert fernet is not None

        # Test encrypt/decrypt roundtrip
        test_data = b"test data"
        encrypted = fernet.encrypt(test_data)
        decrypted = fernet.decrypt(encrypted)
        assert decrypted == test_data
