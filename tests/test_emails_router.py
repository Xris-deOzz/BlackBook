"""
Tests for the emails router (Gmail email history endpoints).
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import Person, GoogleAccount, EmailCache, Interaction
from app.services.gmail_service import EmailThread


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
def test_person(db_session):
    """Create a test person."""
    person = Person(
        full_name="Test Email Person",
        first_name="Test",
        last_name="Person",
        email="testperson@example.com",
    )
    db_session.add(person)
    db_session.commit()
    return person


@pytest.fixture
def test_google_account(db_session, monkeypatch):
    """Create a test Google account."""
    monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
    from app.config import get_settings
    from app.services.encryption import get_encryption_service
    get_settings.cache_clear()
    get_encryption_service.cache_clear()

    account = GoogleAccount.create_with_credentials(
        email="testaccount@gmail.com",
        credentials={"token": "test", "refresh_token": "test"},
        display_name="Test Account",
    )
    db_session.add(account)
    db_session.commit()
    return account


class TestGetPersonEmails:
    """Test GET /emails/person/{person_id} endpoint."""

    def test_person_not_found(self, client):
        """Test 404 when person doesn't exist."""
        response = client.get(f"/emails/person/{uuid4()}")
        assert response.status_code == 404
        assert "Person not found" in response.json()["detail"]

    def test_returns_cached_results(self, client, test_person, test_google_account, db_session):
        """Test that cached results are returned when fresh."""
        # Create cache entry
        cache = EmailCache(
            person_id=test_person.id,
            google_account_id=test_google_account.id,
            gmail_thread_id="cached_thread_123",
            subject="Cached Subject",
            snippet="Cached snippet...",
            participants=["a@example.com", "b@example.com"],
            last_message_date=datetime.now(timezone.utc),
            message_count=3,
            cached_at=datetime.now(timezone.utc),
        )
        db_session.add(cache)
        db_session.commit()

        response = client.get(f"/emails/person/{test_person.id}")

        assert response.status_code == 200
        # Now returns HTML, check for content
        assert "Cached Subject" in response.text
        assert "cached_thread_123" in response.text
        assert "Cached results" in response.text  # from_cache indicator

    def test_returns_empty_when_no_accounts(self, client, test_person, db_session):
        """Test empty results when no Google accounts connected."""
        # Make sure no accounts exist
        db_session.query(GoogleAccount).delete()
        db_session.commit()

        response = client.get(f"/emails/person/{test_person.id}")

        assert response.status_code == 200
        # Now returns HTML, check for empty state
        assert "No email history found" in response.text
        assert "Connect a Google account" in response.text

    @patch("app.routers.emails.GmailService")
    def test_refresh_bypasses_cache(self, mock_gmail_class, client, test_person, test_google_account, db_session):
        """Test that refresh=true bypasses cache."""
        # Create old cache entry
        cache = EmailCache(
            person_id=test_person.id,
            google_account_id=test_google_account.id,
            gmail_thread_id="old_thread",
            subject="Old Subject",
            cached_at=datetime.now(timezone.utc),
        )
        db_session.add(cache)
        db_session.commit()

        # Mock Gmail service
        mock_service = MagicMock()
        mock_gmail_class.return_value = mock_service
        mock_service.search_emails_for_person.return_value = [
            EmailThread(
                thread_id="new_thread",
                account_id=test_google_account.id,
                account_email="testaccount@gmail.com",
                subject="New Subject",
            )
        ]

        response = client.get(f"/emails/person/{test_person.id}?refresh=true")

        assert response.status_code == 200
        # Now returns HTML, check for new content
        assert "New Subject" in response.text
        assert "new_thread" in response.text
        # Should NOT show cached results indicator when fresh
        assert "Cached results" not in response.text


class TestRefreshPersonEmails:
    """Test GET /emails/person/{person_id}/refresh endpoint."""

    @patch("app.routers.emails.GmailService")
    def test_refresh_endpoint(self, mock_gmail_class, client, test_person, test_google_account):
        """Test the refresh endpoint."""
        mock_service = MagicMock()
        mock_gmail_class.return_value = mock_service
        mock_service.search_emails_for_person.return_value = []

        response = client.get(f"/emails/person/{test_person.id}/refresh")

        assert response.status_code == 200
        mock_service.search_emails_for_person.assert_called_once()


class TestGetThreadDetails:
    """Test GET /emails/thread/{account_id}/{thread_id} endpoint."""

    def test_account_not_found(self, client):
        """Test 404 when account doesn't exist."""
        response = client.get(f"/emails/thread/{uuid4()}/thread123")
        assert response.status_code == 404
        assert "Google account not found" in response.json()["detail"]

    @patch("app.routers.emails.GmailService")
    def test_thread_not_found(self, mock_gmail_class, client, test_google_account):
        """Test 404 when thread doesn't exist."""
        mock_service = MagicMock()
        mock_gmail_class.return_value = mock_service
        mock_service.get_thread_details.return_value = None

        response = client.get(f"/emails/thread/{test_google_account.id}/nonexistent")

        assert response.status_code == 404
        assert "Thread not found" in response.json()["detail"]

    @patch("app.routers.emails.GmailService")
    def test_returns_thread_details(self, mock_gmail_class, client, test_google_account):
        """Test successful thread details retrieval."""
        mock_service = MagicMock()
        mock_gmail_class.return_value = mock_service
        mock_service.get_thread_details.return_value = EmailThread(
            thread_id="thread123",
            account_id=test_google_account.id,
            account_email="testaccount@gmail.com",
            subject="Test Thread",
            snippet="Test snippet...",
            message_count=5,
        )

        response = client.get(f"/emails/thread/{test_google_account.id}/thread123")

        assert response.status_code == 200
        data = response.json()
        assert data["thread_id"] == "thread123"
        assert data["subject"] == "Test Thread"


class TestLogEmailAsInteraction:
    """Test POST /emails/thread/{account_id}/{thread_id}/log endpoint."""

    def test_person_not_found(self, client, test_google_account):
        """Test 404 when person doesn't exist."""
        response = client.post(
            f"/emails/thread/{test_google_account.id}/thread123/log",
            params={"person_id": str(uuid4())},
        )
        assert response.status_code == 404
        assert "Person not found" in response.json()["detail"]

    @patch("app.routers.emails.GmailService")
    def test_creates_interaction(self, mock_gmail_class, client, test_person, test_google_account, db_session):
        """Test successful interaction creation."""
        mock_service = MagicMock()
        mock_gmail_class.return_value = mock_service
        mock_service.get_thread_details.return_value = EmailThread(
            thread_id="newthread",
            account_id=test_google_account.id,
            account_email="testaccount@gmail.com",
            subject="Meeting Follow-up",
            last_message_date=datetime.now(timezone.utc),
        )

        response = client.post(
            f"/emails/thread/{test_google_account.id}/newthread/log",
            params={"person_id": str(test_person.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "interaction_id" in data
        assert data["subject"] == "Meeting Follow-up"

        # Verify interaction was created
        interaction = db_session.query(Interaction).filter_by(
            gmail_thread_id="newthread"
        ).first()
        assert interaction is not None
        assert interaction.person_id == test_person.id
        assert interaction.notes == "Meeting Follow-up"

    @patch("app.routers.emails.GmailService")
    def test_duplicate_interaction_prevented(self, mock_gmail_class, client, test_person, test_google_account, db_session):
        """Test that duplicate interactions are prevented."""
        # Create existing interaction
        existing = Interaction(
            person_id=test_person.id,
            person_name=test_person.full_name,
            gmail_thread_id="duplicate_thread",
        )
        db_session.add(existing)
        db_session.commit()

        response = client.post(
            f"/emails/thread/{test_google_account.id}/duplicate_thread/log",
            params={"person_id": str(test_person.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "already exists" in data["message"]


class TestListEmailAccounts:
    """Test GET /emails/accounts endpoint."""

    def test_list_accounts(self, client, test_google_account):
        """Test listing connected accounts."""
        response = client.get("/emails/accounts")

        assert response.status_code == 200
        accounts = response.json()
        assert len(accounts) >= 1

        # Find our test account
        test_acc = next((a for a in accounts if a["email"] == "testaccount@gmail.com"), None)
        assert test_acc is not None
        assert test_acc["display_name"] == "Test Account"


class TestClearCache:
    """Test cache clearing endpoints."""

    def test_clear_person_cache(self, client, test_person, test_google_account, db_session):
        """Test clearing cache for a specific person."""
        # Create cache entries
        cache = EmailCache(
            person_id=test_person.id,
            google_account_id=test_google_account.id,
            gmail_thread_id="to_delete",
            cached_at=datetime.now(timezone.utc),
        )
        db_session.add(cache)
        db_session.commit()

        response = client.delete(f"/emails/cache/person/{test_person.id}")

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify cache was cleared
        remaining = db_session.query(EmailCache).filter_by(person_id=test_person.id).count()
        assert remaining == 0

    def test_clear_expired_cache(self, client, test_person, test_google_account, db_session):
        """Test clearing expired cache entries."""
        # Create old cache entry
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        cache = EmailCache(
            person_id=test_person.id,
            google_account_id=test_google_account.id,
            gmail_thread_id="old_entry",
            cached_at=old_time,
        )
        db_session.add(cache)
        db_session.commit()

        response = client.delete("/emails/cache/expired?hours=24")

        assert response.status_code == 200
        assert response.json()["success"] is True
