"""
Tests for the auth router (Google OAuth endpoints).
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import GoogleAccount


@pytest.fixture
def client(db_session):
    """Create a test client that uses the test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_google_account(db_session, monkeypatch):
    """Create a mock Google account with encryption configured."""
    # Set up encryption key for testing (valid Fernet key)
    monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")

    # Set up Google OAuth config
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    # Clear cached settings
    from app.config import get_settings
    get_settings.cache_clear()

    # Clear encryption service cache
    from app.services.encryption import get_encryption_service
    get_encryption_service.cache_clear()

    account = GoogleAccount.create_with_credentials(
        email="test@gmail.com",
        credentials={
            "token": "test-access-token",
            "refresh_token": "test-refresh-token",
        },
        display_name="Test User",
        scopes=["gmail.readonly"],
    )
    db_session.add(account)
    db_session.commit()
    return account


class TestConnectGoogle:
    """Test Google OAuth initiation."""

    def test_connect_redirects_to_google(self, client, monkeypatch):
        """Test that /auth/google/connect redirects to Google."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

        from app.config import get_settings
        get_settings.cache_clear()

        response = client.get("/auth/google/connect", follow_redirects=False)

        assert response.status_code == 302
        assert "accounts.google.com" in response.headers["location"]

    def test_connect_without_config_returns_error(self, client, monkeypatch):
        """Test that missing config returns 503."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")

        from app.config import get_settings
        get_settings.cache_clear()

        response = client.get("/auth/google/connect")

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


class TestGoogleCallback:
    """Test Google OAuth callback."""

    def test_callback_error_returns_400(self, client, monkeypatch):
        """Test that callback with error returns 400."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")

        from app.config import get_settings
        get_settings.cache_clear()

        response = client.get(
            "/auth/google/callback",
            params={
                "code": "test-code",
                "state": "test-state",
                "error": "access_denied",
            },
        )

        assert response.status_code == 400
        assert "access_denied" in response.json()["detail"]

    def test_callback_invalid_state_returns_400(self, client, monkeypatch):
        """Test that invalid state parameter returns 400."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test-secret")

        from app.config import get_settings
        get_settings.cache_clear()

        response = client.get(
            "/auth/google/callback",
            params={
                "code": "test-code",
                "state": "invalid-state",
            },
        )

        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]


class TestListAccounts:
    """Test listing Google accounts."""

    def test_list_accounts_empty(self, client, db_session):
        """Test listing when no accounts exist."""
        # Clear any existing accounts
        db_session.query(GoogleAccount).delete()
        db_session.commit()

        response = client.get("/auth/google/accounts")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_accounts_with_account(self, client, mock_google_account, db_session):
        """Test listing accounts returns account info."""
        response = client.get("/auth/google/accounts")

        assert response.status_code == 200
        accounts = response.json()
        assert len(accounts) >= 1

        # Find our test account
        test_account = next((a for a in accounts if a["email"] == "test@gmail.com"), None)
        assert test_account is not None
        assert test_account["display_name"] == "Test User"
        assert test_account["is_active"] is True


class TestDisconnectAccount:
    """Test disconnecting Google accounts."""

    def test_disconnect_nonexistent_returns_404(self, client):
        """Test disconnecting nonexistent account returns 404."""
        response = client.post(f"/auth/google/disconnect/{uuid4()}")

        assert response.status_code == 404

    @patch("app.routers.auth.get_google_auth_service")
    def test_disconnect_removes_account(self, mock_get_service, client, mock_google_account, db_session):
        """Test that disconnect removes the account."""
        # Mock the auth service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.revoke_credentials.return_value = True

        account_id = mock_google_account.id
        account_email = mock_google_account.email

        response = client.post(f"/auth/google/disconnect/{account_id}")

        assert response.status_code == 200
        # Now returns HTML with accounts list - deleted account should not be in it
        assert account_email not in response.text

        # Verify account is deleted
        db_session.expire_all()
        account = db_session.query(GoogleAccount).filter_by(id=account_id).first()
        assert account is None


class TestRefreshCredentials:
    """Test credential refresh."""

    def test_refresh_nonexistent_returns_404(self, client):
        """Test refreshing nonexistent account returns 404."""
        response = client.post(f"/auth/google/refresh/{uuid4()}")

        assert response.status_code == 404

    @patch("app.routers.auth.get_google_auth_service")
    def test_refresh_updates_credentials(self, mock_get_service, client, mock_google_account, db_session):
        """Test that refresh updates account credentials."""
        # Mock the auth service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.refresh_credentials.return_value = {
            "token": "new-access-token",
            "refresh_token": "test-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "scopes": ["gmail.readonly"],
        }

        account_id = mock_google_account.id

        response = client.post(f"/auth/google/refresh/{account_id}")

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestAccountStatus:
    """Test account status check."""

    def test_status_nonexistent_returns_404(self, client):
        """Test status check for nonexistent account returns 404."""
        response = client.get(f"/auth/google/status/{uuid4()}")

        assert response.status_code == 404

    @patch("app.routers.auth.get_google_auth_service")
    def test_status_returns_valid_info(self, mock_get_service, client, mock_google_account):
        """Test status returns account validity info."""
        # Mock the auth service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.validate_credentials.return_value = True

        account_id = mock_google_account.id

        response = client.get(f"/auth/google/status/{account_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@gmail.com"
        assert data["is_valid"] is True

    @patch("app.routers.auth.get_google_auth_service")
    def test_status_returns_invalid_on_error(self, mock_get_service, client, mock_google_account):
        """Test status returns invalid when validation fails."""
        # Mock the auth service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.validate_credentials.side_effect = Exception("Token expired")

        account_id = mock_google_account.id

        response = client.get(f"/auth/google/status/{account_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert "error" in data
