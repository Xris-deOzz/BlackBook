"""
Tests for Calendar router.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import GoogleAccount, CalendarEvent, Person, PersonEmail, Interaction


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
def google_account(db_session, monkeypatch):
    """Create a test Google account."""
    monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
    from app.config import get_settings
    from app.services.encryption import get_encryption_service
    get_settings.cache_clear()
    get_encryption_service.cache_clear()

    account = GoogleAccount.create_with_credentials(
        email="calendar-router-test@gmail.com",
        credentials={
            "token": "test_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        },
    )
    db_session.add(account)
    db_session.commit()
    return account


@pytest.fixture
def calendar_event(db_session, google_account):
    """Create a test calendar event."""
    now = datetime.now(timezone.utc)
    event = CalendarEvent(
        google_account_id=google_account.id,
        google_event_id="router_test_event_123",
        summary="Test Meeting",
        description="A test meeting",
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        location="https://zoom.us/j/123",
        attendees=[
            {"email": "alice@example.com", "displayName": "Alice", "responseStatus": "accepted"},
            {"email": "bob@example.com", "displayName": "Bob", "responseStatus": "tentative"},
        ],
    )
    db_session.add(event)
    db_session.commit()
    return event


@pytest.fixture
def person_with_email(db_session):
    """Create a test person with email."""
    person = Person(
        first_name="Alice",
        last_name="Test",
        full_name="Alice Test",
        email="alice@example.com",
    )
    db_session.add(person)
    db_session.commit()

    person_email = PersonEmail(
        person_id=person.id,
        email="alice@example.com",
        is_primary=True,
    )
    db_session.add(person_email)
    db_session.commit()

    return person


class TestGetEventDetails:
    """Test GET /calendar/event/{id} endpoint."""

    def test_get_event_details(self, client, calendar_event, person_with_email, monkeypatch):
        """Test getting event details."""
        monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
        from app.config import get_settings
        from app.services.encryption import get_encryption_service
        get_settings.cache_clear()
        get_encryption_service.cache_clear()

        response = client.get(f"/calendar/event/{calendar_event.id}")
        assert response.status_code == 200
        assert "Test Meeting" in response.text
        assert "alice@example.com" in response.text

    def test_get_event_not_found(self, client):
        """Test event not found returns 404."""
        response = client.get(f"/calendar/event/{uuid4()}")
        assert response.status_code == 404


class TestLogMeetingAsInteraction:
    """Test POST /calendar/event/{id}/log endpoint."""

    def test_log_meeting_creates_interactions(self, client, db_session, calendar_event, person_with_email, monkeypatch):
        """Test logging meeting creates interactions for known attendees."""
        monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
        from app.config import get_settings
        from app.services.encryption import get_encryption_service
        get_settings.cache_clear()
        get_encryption_service.cache_clear()

        response = client.post(f"/calendar/event/{calendar_event.id}/log")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["interactions_created"] == 1  # Only Alice is known

        # Verify interaction was created
        interaction = db_session.query(Interaction).filter_by(
            person_id=person_with_email.id,
            calendar_event_id="router_test_event_123",
        ).first()
        assert interaction is not None
        assert interaction.notes == "Test Meeting"

    def test_log_meeting_event_not_found(self, client):
        """Test logging non-existent event returns 404."""
        response = client.post(f"/calendar/event/{uuid4()}/log")
        assert response.status_code == 404

    def test_log_meeting_no_duplicates(self, client, db_session, calendar_event, person_with_email, monkeypatch):
        """Test logging same meeting twice doesn't create duplicates."""
        monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
        from app.config import get_settings
        from app.services.encryption import get_encryption_service
        get_settings.cache_clear()
        get_encryption_service.cache_clear()

        # Log first time
        response1 = client.post(f"/calendar/event/{calendar_event.id}/log")
        assert response1.json()["interactions_created"] == 1

        # Log second time
        response2 = client.post(f"/calendar/event/{calendar_event.id}/log")
        assert response2.json()["interactions_created"] == 0  # No new interactions

        # Verify only one interaction exists
        count = db_session.query(Interaction).filter_by(
            calendar_event_id="router_test_event_123",
        ).count()
        assert count == 1


class TestSyncEndpoint:
    """Test POST /calendar/sync endpoint."""

    @patch("app.services.calendar_service.CalendarService.sync_past_events")
    def test_sync_calendar_events(self, mock_sync, client):
        """Test calendar sync endpoint (returns HTML partial)."""
        mock_sync.return_value = {
            "events_synced": 10,
            "pending_contacts_created": 3,
        }

        response = client.post("/calendar/sync?days=30")
        assert response.status_code == 200

        # Sync endpoint returns HTML partial, not JSON
        assert "text/html" in response.headers.get("content-type", "")
        # The template should contain success information
        assert "10" in response.text or "events" in response.text.lower()


class TestAPIEndpoints:
    """Test JSON API endpoints."""

    @patch("app.services.calendar_service.CalendarService.get_todays_events")
    @patch("app.services.calendar_service.CalendarService.match_attendees_to_persons")
    def test_api_get_todays_events(self, mock_match, mock_today, client, google_account, monkeypatch):
        """Test API endpoint for today's events."""
        monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
        from app.config import get_settings
        from app.services.encryption import get_encryption_service
        get_settings.cache_clear()
        get_encryption_service.cache_clear()

        now = datetime.now(timezone.utc)
        mock_event = MagicMock()
        mock_event.id = uuid4()
        mock_event.google_event_id = "test_123"
        mock_event.summary = "API Test Meeting"
        mock_event.start_time = now
        mock_event.end_time = now + timedelta(hours=1)
        mock_event.location = None
        mock_event.is_video_call = False
        mock_event.duration_minutes = 60

        mock_today.return_value = [mock_event]
        mock_match.return_value = []

        response = client.get("/calendar/api/today")
        assert response.status_code == 200

        data = response.json()
        assert "events" in data
        assert len(data["events"]) == 1
        assert data["events"][0]["summary"] == "API Test Meeting"

    @patch("app.services.calendar_service.CalendarService.get_upcoming_events")
    @patch("app.services.calendar_service.CalendarService.match_attendees_to_persons")
    def test_api_get_upcoming_events(self, mock_match, mock_upcoming, client, google_account, monkeypatch):
        """Test API endpoint for upcoming events."""
        monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
        from app.config import get_settings
        from app.services.encryption import get_encryption_service
        get_settings.cache_clear()
        get_encryption_service.cache_clear()

        mock_upcoming.return_value = []
        mock_match.return_value = []

        response = client.get("/calendar/api/upcoming?days=7")
        assert response.status_code == 200

        data = response.json()
        assert "events" in data
