"""
Tests for settings router.
"""

import pytest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import GoogleAccount, EmailIgnoreList
from app.models.email_ignore import IgnorePatternType


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


class TestSettingsPage:
    """Test GET /settings endpoint."""

    def test_settings_page_loads(self, client):
        """Test that settings page loads successfully."""
        response = client.get("/settings")
        assert response.status_code == 200
        assert "Settings" in response.text
        assert "Google Accounts" in response.text

    def test_accounts_tab(self, client):
        """Test accounts/syncing tab."""
        response = client.get("/settings?tab=syncing")
        assert response.status_code == 200
        assert "Connected Google Accounts" in response.text
        assert "Connect Google Account" in response.text

    def test_email_tab(self, client):
        """Test email tab."""
        response = client.get("/settings?tab=email")
        assert response.status_code == 200
        assert "Email Ignore Patterns" in response.text
        assert "Add New Pattern" in response.text


class TestPatternManagement:
    """Test pattern management endpoints."""

    def test_get_patterns_list(self, client):
        """Test getting patterns list."""
        response = client.get("/settings/patterns")
        assert response.status_code == 200

    def test_add_pattern(self, client, db_session):
        """Test adding a new pattern."""
        response = client.post(
            "/settings/patterns",
            data={"pattern": "newspam.com", "pattern_type": "domain"},
        )
        assert response.status_code == 200

        # Verify pattern was added
        pattern = db_session.query(EmailIgnoreList).filter_by(pattern="newspam.com").first()
        assert pattern is not None
        assert pattern.pattern_type == IgnorePatternType.domain

    def test_add_email_pattern(self, client, db_session):
        """Test adding an email pattern."""
        response = client.post(
            "/settings/patterns",
            data={"pattern": "testnoreply@*", "pattern_type": "email"},
        )
        assert response.status_code == 200

        pattern = db_session.query(EmailIgnoreList).filter_by(pattern="testnoreply@*").first()
        assert pattern is not None
        assert pattern.pattern_type == IgnorePatternType.email

    def test_add_duplicate_pattern_ignored(self, client, db_session):
        """Test that duplicate patterns are ignored."""
        # Add initial pattern
        initial = EmailIgnoreList(
            pattern="duplicate-test.com",
            pattern_type=IgnorePatternType.domain,
        )
        db_session.add(initial)
        db_session.commit()

        # Try to add duplicate
        response = client.post(
            "/settings/patterns",
            data={"pattern": "duplicate-test.com", "pattern_type": "domain"},
        )
        assert response.status_code == 200

        # Verify only one exists
        count = db_session.query(EmailIgnoreList).filter_by(pattern="duplicate-test.com").count()
        assert count == 1

    def test_delete_pattern(self, client, db_session):
        """Test deleting a pattern."""
        pattern = EmailIgnoreList(
            pattern="todelete-test.com",
            pattern_type=IgnorePatternType.domain,
        )
        db_session.add(pattern)
        db_session.commit()
        pattern_id = pattern.id

        response = client.delete(f"/settings/patterns/{pattern_id}")
        assert response.status_code == 200

        # Verify pattern was deleted
        deleted = db_session.query(EmailIgnoreList).filter_by(id=pattern_id).first()
        assert deleted is None

    def test_delete_nonexistent_pattern_ok(self, client):
        """Test deleting nonexistent pattern doesn't error."""
        response = client.delete(f"/settings/patterns/{uuid4()}")
        assert response.status_code == 200


class TestAccountManagement:
    """Test account management endpoints."""

    def test_get_accounts_list(self, client):
        """Test getting accounts list."""
        response = client.get("/settings/accounts")
        assert response.status_code == 200

    def test_toggle_account_status(self, client, db_session, monkeypatch):
        """Test toggling account active status."""
        monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
        from app.config import get_settings
        from app.services.encryption import get_encryption_service
        get_settings.cache_clear()
        get_encryption_service.cache_clear()

        account = GoogleAccount.create_with_credentials(
            email="toggle@gmail.com",
            credentials={"token": "test", "refresh_token": "test"},
        )
        account.is_active = True
        db_session.add(account)
        db_session.commit()
        account_id = account.id

        # Toggle to inactive
        response = client.post(f"/settings/accounts/{account_id}/toggle")
        assert response.status_code == 200

        db_session.refresh(account)
        assert account.is_active is False

        # Toggle back to active
        response = client.post(f"/settings/accounts/{account_id}/toggle")
        assert response.status_code == 200

        db_session.refresh(account)
        assert account.is_active is True

    def test_accounts_displayed(self, client, db_session, monkeypatch):
        """Test that accounts are displayed in the list."""
        monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
        from app.config import get_settings
        from app.services.encryption import get_encryption_service
        get_settings.cache_clear()
        get_encryption_service.cache_clear()

        account = GoogleAccount.create_with_credentials(
            email="display@gmail.com",
            credentials={"token": "test", "refresh_token": "test"},
            display_name="Display Test Account",
        )
        db_session.add(account)
        db_session.commit()

        response = client.get("/settings?tab=syncing")
        assert response.status_code == 200
        assert "display@gmail.com" in response.text
