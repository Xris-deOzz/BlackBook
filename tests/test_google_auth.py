"""
Tests for Google Auth service.

These tests use mocking to avoid requiring actual Google credentials.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.services.google_auth import (
    GoogleAuthService,
    GoogleAuthError,
    GoogleAuthConfigError,
    GoogleAuthTokenError,
    get_google_auth_service,
    GMAIL_SCOPES,
)


class TestGoogleAuthServiceInit:
    """Test GoogleAuthService initialization."""

    def test_init_with_config(self, monkeypatch):
        """Test initialization with valid config."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

        # Clear cached settings
        from app.config import get_settings
        get_settings.cache_clear()

        service = GoogleAuthService()
        assert service.settings.google_client_id == "test-client-id.apps.googleusercontent.com"

    def test_init_without_config(self, monkeypatch):
        """Test initialization without config raises error."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")

        from app.config import get_settings
        get_settings.cache_clear()

        with pytest.raises(GoogleAuthConfigError) as exc_info:
            GoogleAuthService()
        assert "not configured" in str(exc_info.value)


class TestAuthorizationUrl:
    """Test authorization URL generation."""

    @pytest.fixture
    def auth_service(self, monkeypatch):
        """Create a configured auth service."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

        from app.config import get_settings
        get_settings.cache_clear()

        return GoogleAuthService()

    def test_get_authorization_url(self, auth_service):
        """Test generating authorization URL."""
        url, state = auth_service.get_authorization_url()

        assert "accounts.google.com" in url
        assert "client_id=test-client-id" in url
        assert "redirect_uri=" in url
        assert state is not None

    def test_get_authorization_url_with_state(self, auth_service):
        """Test generating authorization URL with custom state."""
        custom_state = "my-custom-state-123"
        url, state = auth_service.get_authorization_url(state=custom_state)

        assert state == custom_state
        assert f"state={custom_state}" in url

    def test_authorization_url_contains_scopes(self, auth_service):
        """Test that authorization URL includes required scopes."""
        url, _ = auth_service.get_authorization_url()

        # URL-encoded scope values should be present
        assert "gmail.readonly" in url or "scope=" in url


class TestCodeExchange:
    """Test authorization code exchange."""

    @pytest.fixture
    def auth_service(self, monkeypatch):
        """Create a configured auth service."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

        from app.config import get_settings
        get_settings.cache_clear()

        return GoogleAuthService()

    @patch("app.services.google_auth.Flow")
    def test_exchange_code_success(self, mock_flow_class, auth_service):
        """Test successful code exchange."""
        # Setup mock
        mock_flow = MagicMock()
        mock_flow_class.from_client_config.return_value = mock_flow

        mock_credentials = MagicMock()
        mock_credentials.token = "access-token-123"
        mock_credentials.refresh_token = "refresh-token-456"
        mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
        mock_credentials.client_id = "test-client-id"
        mock_credentials.client_secret = "test-secret"
        mock_credentials.scopes = ["gmail.readonly"]
        mock_credentials.expiry = datetime(2025, 12, 8, 12, 0, 0, tzinfo=timezone.utc)
        mock_flow.credentials = mock_credentials

        # Execute
        result = auth_service.exchange_code("auth-code-xyz")

        # Verify
        mock_flow.fetch_token.assert_called_once_with(code="auth-code-xyz")
        assert result["token"] == "access-token-123"
        assert result["refresh_token"] == "refresh-token-456"
        assert "gmail.readonly" in result["scopes"]

    @patch("app.services.google_auth.Flow")
    def test_exchange_code_failure(self, mock_flow_class, auth_service):
        """Test code exchange failure."""
        mock_flow = MagicMock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.fetch_token.side_effect = Exception("Invalid code")

        with pytest.raises(GoogleAuthTokenError) as exc_info:
            auth_service.exchange_code("invalid-code")
        assert "Invalid code" in str(exc_info.value)


class TestTokenRefresh:
    """Test credential refresh."""

    @pytest.fixture
    def auth_service(self, monkeypatch):
        """Create a configured auth service."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

        from app.config import get_settings
        get_settings.cache_clear()

        return GoogleAuthService()

    @patch("app.services.google_auth.Request")
    @patch("app.services.google_auth.Credentials")
    def test_refresh_credentials_success(self, mock_creds_class, mock_request, auth_service):
        """Test successful credential refresh."""
        # Setup mock credentials
        mock_credentials = MagicMock()
        mock_credentials.token = "new-access-token"
        mock_credentials.refresh_token = "refresh-token-456"
        mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
        mock_credentials.client_id = "test-client-id"
        mock_credentials.client_secret = "test-secret"
        mock_credentials.scopes = ["gmail.readonly"]
        mock_credentials.expiry = datetime(2025, 12, 8, 14, 0, 0, tzinfo=timezone.utc)
        mock_creds_class.return_value = mock_credentials

        credentials_dict = {
            "token": "old-access-token",
            "refresh_token": "refresh-token-456",
        }

        result = auth_service.refresh_credentials(credentials_dict)

        mock_credentials.refresh.assert_called_once()
        assert result["token"] == "new-access-token"

    def test_refresh_without_refresh_token(self, auth_service):
        """Test refresh fails without refresh token."""
        credentials_dict = {
            "token": "access-token",
            # No refresh_token
        }

        with pytest.raises(GoogleAuthTokenError) as exc_info:
            auth_service.refresh_credentials(credentials_dict)
        assert "No refresh token" in str(exc_info.value)


class TestValidateCredentials:
    """Test credential validation."""

    @pytest.fixture
    def auth_service(self, monkeypatch):
        """Create a configured auth service."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

        from app.config import get_settings
        get_settings.cache_clear()

        return GoogleAuthService()

    @patch("app.services.google_auth.Credentials")
    def test_validate_valid_credentials(self, mock_creds_class, auth_service):
        """Test validating valid credentials."""
        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_creds_class.return_value = mock_credentials

        credentials_dict = {
            "token": "valid-token",
            "refresh_token": "refresh-token",
        }

        assert auth_service.validate_credentials(credentials_dict) is True

    @patch("app.services.google_auth.Request")
    @patch("app.services.google_auth.Credentials")
    def test_validate_expired_but_refreshable(self, mock_creds_class, mock_request, auth_service):
        """Test validating expired but refreshable credentials."""
        mock_credentials = MagicMock()
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_credentials.refresh_token = "refresh-token"

        # After refresh, should be valid
        def refresh_side_effect(request):
            mock_credentials.valid = True

        mock_credentials.refresh.side_effect = refresh_side_effect
        mock_creds_class.return_value = mock_credentials

        credentials_dict = {
            "token": "expired-token",
            "refresh_token": "refresh-token",
        }

        assert auth_service.validate_credentials(credentials_dict) is True

    @patch("app.services.google_auth.Credentials")
    def test_validate_invalid_credentials(self, mock_creds_class, auth_service):
        """Test validating invalid credentials."""
        mock_credentials = MagicMock()
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_credentials.refresh_token = None  # Can't refresh
        mock_creds_class.return_value = mock_credentials

        credentials_dict = {
            "token": "invalid-token",
        }

        assert auth_service.validate_credentials(credentials_dict) is False


class TestRevokeCredentials:
    """Test credential revocation."""

    @pytest.fixture
    def auth_service(self, monkeypatch):
        """Create a configured auth service."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

        from app.config import get_settings
        get_settings.cache_clear()

        return GoogleAuthService()

    @patch("requests.post")
    def test_revoke_credentials_success(self, mock_post, auth_service):
        """Test successful credential revocation."""
        mock_post.return_value.status_code = 200

        credentials_dict = {
            "token": "access-token",
            "refresh_token": "refresh-token",
        }

        result = auth_service.revoke_credentials(credentials_dict)

        assert result is True
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_revoke_credentials_failure(self, mock_post, auth_service):
        """Test failed credential revocation."""
        mock_post.return_value.status_code = 400

        credentials_dict = {
            "token": "access-token",
        }

        result = auth_service.revoke_credentials(credentials_dict)
        assert result is False

    def test_revoke_empty_credentials(self, auth_service):
        """Test revoking empty credentials."""
        result = auth_service.revoke_credentials({})
        assert result is False


class TestGetUserInfo:
    """Test user info retrieval."""

    @pytest.fixture
    def auth_service(self, monkeypatch):
        """Create a configured auth service."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

        from app.config import get_settings
        get_settings.cache_clear()

        return GoogleAuthService()

    @patch("app.services.google_auth.build")
    @patch("app.services.google_auth.Credentials")
    def test_get_user_info_success(self, mock_creds_class, mock_build, auth_service):
        """Test successful user info retrieval."""
        mock_credentials = MagicMock()
        mock_creds_class.return_value = mock_credentials

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.userinfo.return_value.get.return_value.execute.return_value = {
            "email": "test@gmail.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }

        credentials_dict = {
            "token": "access-token",
            "refresh_token": "refresh-token",
        }

        result = auth_service.get_user_info(credentials_dict)

        assert result["email"] == "test@gmail.com"
        assert result["name"] == "Test User"

    @patch("app.services.google_auth.build")
    @patch("app.services.google_auth.Credentials")
    def test_get_user_info_failure(self, mock_creds_class, mock_build, auth_service):
        """Test user info retrieval failure."""
        mock_credentials = MagicMock()
        mock_creds_class.return_value = mock_credentials

        mock_build.side_effect = Exception("API error")

        credentials_dict = {
            "token": "access-token",
        }

        with pytest.raises(GoogleAuthTokenError) as exc_info:
            auth_service.get_user_info(credentials_dict)
        assert "API error" in str(exc_info.value)


class TestGmailScopes:
    """Test Gmail scopes constant."""

    def test_scopes_include_gmail_readonly(self):
        """Test that scopes include gmail.readonly."""
        assert "https://www.googleapis.com/auth/gmail.readonly" in GMAIL_SCOPES

    def test_scopes_include_userinfo(self):
        """Test that scopes include user info scopes."""
        assert "https://www.googleapis.com/auth/userinfo.email" in GMAIL_SCOPES
        assert "https://www.googleapis.com/auth/userinfo.profile" in GMAIL_SCOPES
