"""
Tests for Calendar service.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch

from app.models import (
    GoogleAccount,
    CalendarEvent,
    PendingContact,
    PendingContactStatus,
    Person,
    PersonEmail,
    Interaction,
    InteractionMedium,
    InteractionSource,
)
from app.services.calendar_service import (
    CalendarService,
    CalendarServiceError,
    CalendarAuthError,
    CalendarAPIError,
    get_calendar_service,
)


@pytest.fixture
def google_account(db_session, monkeypatch):
    """Create a test Google account."""
    monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
    from app.config import get_settings
    from app.services.encryption import get_encryption_service
    get_settings.cache_clear()
    get_encryption_service.cache_clear()

    account = GoogleAccount.create_with_credentials(
        email="calendar-service-test@gmail.com",
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
def person_with_email(db_session):
    """Create a test person with email."""
    person = Person(
        first_name="Test",
        last_name="Person",
        full_name="Test Person",
        email="testperson@example.com",
    )
    db_session.add(person)
    db_session.commit()

    # Add to PersonEmail table
    person_email = PersonEmail(
        person_id=person.id,
        email="testperson@example.com",
        is_primary=True,
    )
    db_session.add(person_email)
    db_session.commit()

    return person


@pytest.fixture
def calendar_service(db_session):
    """Create a calendar service instance."""
    return CalendarService(db_session)


class TestCalendarServiceInit:
    """Test CalendarService initialization."""

    def test_init(self, db_session):
        """Test service initializes correctly."""
        service = CalendarService(db_session)
        assert service.db is db_session
        assert service._email_to_person_cache is None


class TestCalendarServiceCaching:
    """Test event caching functionality."""

    def test_cache_event_creates_new(self, db_session, google_account, calendar_service):
        """Test caching a new event."""
        event_data = {
            "id": "test_event_123",
            "summary": "Test Meeting",
            "description": "A test meeting",
            "start": {"dateTime": "2025-12-08T10:00:00-05:00"},
            "end": {"dateTime": "2025-12-08T11:00:00-05:00"},
            "location": "https://zoom.us/j/123",
            "attendees": [
                {"email": "alice@example.com", "displayName": "Alice"},
                {"email": "bob@example.com", "displayName": "Bob"},
            ],
            "organizer": {"email": "organizer@example.com"},
        }

        cached = calendar_service._cache_event(google_account, event_data)
        db_session.commit()

        assert cached is not None
        assert cached.google_event_id == "test_event_123"
        assert cached.summary == "Test Meeting"
        assert cached.location == "https://zoom.us/j/123"
        assert len(cached.attendees) == 2

    def test_cache_event_updates_existing(self, db_session, google_account, calendar_service):
        """Test caching updates existing event."""
        # Create initial event
        now = datetime.now(timezone.utc)
        existing = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="update_event_123",
            summary="Original Summary",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        db_session.add(existing)
        db_session.commit()

        # Update via cache
        event_data = {
            "id": "update_event_123",
            "summary": "Updated Summary",
            "start": {"dateTime": now.isoformat()},
            "end": {"dateTime": (now + timedelta(hours=1)).isoformat()},
        }

        cached = calendar_service._cache_event(google_account, event_data)
        db_session.commit()

        assert cached.summary == "Updated Summary"

        # Verify only one event exists
        count = db_session.query(CalendarEvent).filter_by(
            google_event_id="update_event_123"
        ).count()
        assert count == 1

    def test_parse_event_time_datetime(self, calendar_service):
        """Test parsing dateTime format."""
        time_data = {"dateTime": "2025-12-08T10:00:00-05:00"}
        result = calendar_service._parse_event_time(time_data)
        assert result is not None
        # The datetime preserves the original timezone
        assert result.hour == 10
        # But it's timezone-aware and equals 15:00 UTC
        assert result.astimezone(timezone.utc).hour == 15

    def test_parse_event_time_date(self, calendar_service):
        """Test parsing date (all-day event) format."""
        time_data = {"date": "2025-12-08"}
        result = calendar_service._parse_event_time(time_data)
        assert result is not None
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 8


class TestAttendeeMatching:
    """Test attendee to person matching."""

    def test_find_person_by_email(self, db_session, person_with_email, calendar_service):
        """Test finding person by email."""
        # Reset cache
        calendar_service._email_to_person_cache = None

        person_id = calendar_service._find_person_by_email("testperson@example.com")
        assert person_id == person_with_email.id

    def test_find_person_by_email_case_insensitive(self, db_session, person_with_email, calendar_service):
        """Test case insensitive email lookup."""
        calendar_service._email_to_person_cache = None

        person_id = calendar_service._find_person_by_email("TESTPERSON@EXAMPLE.COM")
        assert person_id == person_with_email.id

    def test_find_person_by_email_not_found(self, db_session, calendar_service):
        """Test email not found returns None."""
        calendar_service._email_to_person_cache = None

        person_id = calendar_service._find_person_by_email("unknown@example.com")
        assert person_id is None

    def test_match_attendees_to_persons(self, db_session, google_account, person_with_email, calendar_service):
        """Test matching attendees to persons."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="match_test_event",
            summary="Test Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=[
                {"email": "testperson@example.com", "displayName": "Test Person"},
                {"email": "unknown@example.com", "displayName": "Unknown"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        # Reset cache
        calendar_service._email_to_person_cache = None

        matched = calendar_service.match_attendees_to_persons(event)

        assert len(matched) == 2

        # First attendee should be matched
        assert matched[0]["email"] == "testperson@example.com"
        assert matched[0]["person_id"] == str(person_with_email.id)
        assert matched[0]["person_name"] == "Test Person"

        # Second attendee should not be matched
        assert matched[1]["email"] == "unknown@example.com"
        assert matched[1]["person_id"] is None


class TestPendingContactProcessing:
    """Test pending contact creation from attendees."""

    def test_process_attendees_creates_pending(self, db_session, google_account, calendar_service):
        """Test processing creates pending contacts."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="pending_test_event",
            summary="Test Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=[
                {"email": "newcontact@example.com", "displayName": "New Contact"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        # Reset cache
        calendar_service._email_to_person_cache = None

        created = calendar_service._process_attendees_for_pending(event)
        db_session.commit()

        assert created == 1

        pending = db_session.query(PendingContact).filter_by(
            email="newcontact@example.com"
        ).first()
        assert pending is not None
        assert pending.name == "New Contact"
        assert pending.source_event_id == event.id

    def test_process_attendees_increments_existing(self, db_session, google_account, calendar_service):
        """Test processing increments existing pending contact."""
        # Create existing pending contact
        existing = PendingContact(
            email="existing@example.com",
            occurrence_count=1,
        )
        db_session.add(existing)
        db_session.commit()

        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="increment_test_event",
            summary="Test Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=[
                {"email": "existing@example.com", "displayName": "Existing"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        created = calendar_service._process_attendees_for_pending(event)
        db_session.commit()

        assert created == 0  # No new contacts

        db_session.refresh(existing)
        assert existing.occurrence_count == 2

    def test_process_attendees_skips_known(self, db_session, google_account, person_with_email, calendar_service):
        """Test processing skips known persons."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="known_test_event",
            summary="Test Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=[
                {"email": "testperson@example.com", "displayName": "Test Person"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        created = calendar_service._process_attendees_for_pending(event)

        assert created == 0

    def test_process_attendees_skips_self(self, db_session, google_account, calendar_service):
        """Test processing skips self attendee."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="self_test_event",
            summary="Test Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=[
                {"email": "self@example.com", "displayName": "Self", "self": True},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        created = calendar_service._process_attendees_for_pending(event)

        assert created == 0


class TestFetchEvents:
    """Test fetching events from Google Calendar API."""

    def test_fetch_events_account_not_found(self, db_session, calendar_service):
        """Test fetch_events raises error for unknown account."""
        with pytest.raises(CalendarServiceError, match="Account not found"):
            calendar_service.fetch_events(uuid4())

    @patch("app.services.calendar_service.build")
    def test_fetch_events_with_mocked_api(self, mock_build, db_session, google_account, calendar_service):
        """Test fetch_events with mocked Google API."""
        now = datetime.now(timezone.utc)

        # Mock the Google Calendar API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.events().list().execute.return_value = {
            "items": [
                {
                    "id": "mocked_event_1",
                    "summary": "Mocked Meeting",
                    "start": {"dateTime": now.isoformat()},
                    "end": {"dateTime": (now + timedelta(hours=1)).isoformat()},
                    "attendees": [],
                },
            ]
        }

        events = calendar_service.fetch_events(
            account_id=google_account.id,
            time_min=now,
            time_max=now + timedelta(days=1),
        )

        assert len(events) == 1
        assert events[0].summary == "Mocked Meeting"


class TestAutoCreateInteractions:
    """Test automatic interaction creation."""

    def test_create_interactions_for_event(
        self, db_session, google_account, person_with_email, calendar_service
    ):
        """Test creating interactions for a single event."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="interaction_test_event",
            summary="Past Meeting",
            start_time=past,
            end_time=past + timedelta(hours=1),
            attendees=[
                {"email": "testperson@example.com", "displayName": "Test Person"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        created = calendar_service._create_interactions_for_event(event)
        db_session.commit()

        assert created == 1

        # Verify interaction was created
        interaction = db_session.query(Interaction).filter_by(
            calendar_event_id="interaction_test_event"
        ).first()
        assert interaction is not None
        assert interaction.person_id == person_with_email.id
        assert interaction.source == InteractionSource.calendar
        assert interaction.medium == InteractionMedium.meeting

    def test_create_interactions_for_video_call(
        self, db_session, google_account, person_with_email, calendar_service
    ):
        """Test creating interaction for video call sets correct medium."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="video_call_event",
            summary="Video Meeting",
            start_time=past,
            end_time=past + timedelta(hours=1),
            location="https://meet.google.com/abc-def-ghi",
            attendees=[
                {"email": "testperson@example.com", "displayName": "Test Person"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        created = calendar_service._create_interactions_for_event(event)
        db_session.commit()

        assert created == 1

        interaction = db_session.query(Interaction).filter_by(
            calendar_event_id="video_call_event"
        ).first()
        assert interaction.medium == InteractionMedium.video_call

    def test_create_interactions_skips_duplicate(
        self, db_session, google_account, person_with_email, calendar_service
    ):
        """Test that duplicate interactions are not created."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="duplicate_test_event",
            summary="Test Meeting",
            start_time=past,
            end_time=past + timedelta(hours=1),
            attendees=[
                {"email": "testperson@example.com", "displayName": "Test Person"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        # Create existing interaction
        existing = Interaction(
            person_id=person_with_email.id,
            medium=InteractionMedium.meeting,
            interaction_date=past,
            calendar_event_id="duplicate_test_event",
            source="calendar",
        )
        db_session.add(existing)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        created = calendar_service._create_interactions_for_event(event)

        assert created == 0

        # Verify only one interaction exists
        count = db_session.query(Interaction).filter_by(
            calendar_event_id="duplicate_test_event"
        ).count()
        assert count == 1

    def test_create_interactions_skips_unknown(
        self, db_session, google_account, calendar_service
    ):
        """Test that unknown attendees are skipped."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="unknown_test_event",
            summary="Test Meeting",
            start_time=past,
            end_time=past + timedelta(hours=1),
            attendees=[
                {"email": "unknown@example.com", "displayName": "Unknown"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        created = calendar_service._create_interactions_for_event(event)

        assert created == 0

    def test_create_interactions_skips_self(
        self, db_session, google_account, calendar_service
    ):
        """Test that self attendee is skipped."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="self_skip_event",
            summary="Test Meeting",
            start_time=past,
            end_time=past + timedelta(hours=1),
            attendees=[
                {"email": "me@example.com", "displayName": "Me", "self": True},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        created = calendar_service._create_interactions_for_event(event)

        assert created == 0

    def test_auto_create_interactions(
        self, db_session, google_account, person_with_email, calendar_service
    ):
        """Test auto_create_interactions method."""
        # Create a past event with known attendee
        past = datetime.now(timezone.utc) - timedelta(days=2)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="auto_create_event",
            summary="Auto Create Meeting",
            start_time=past,
            end_time=past + timedelta(hours=1),
            attendees=[
                {"email": "testperson@example.com", "displayName": "Test Person"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        result = calendar_service.auto_create_interactions(days=7)

        assert result["events_processed"] >= 1
        assert result["interactions_created"] >= 1

    def test_auto_create_interactions_only_past(
        self, db_session, google_account, person_with_email, calendar_service
    ):
        """Test auto_create_interactions only processes past events by default."""
        # Create a future event
        future = datetime.now(timezone.utc) + timedelta(days=1)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="future_event",
            summary="Future Meeting",
            start_time=future,
            end_time=future + timedelta(hours=1),
            attendees=[
                {"email": "testperson@example.com", "displayName": "Test Person"},
            ],
        )
        db_session.add(event)
        db_session.commit()

        calendar_service._email_to_person_cache = None

        result = calendar_service.auto_create_interactions(days=7, only_past=True)

        # Future event should not be processed
        interaction = db_session.query(Interaction).filter_by(
            calendar_event_id="future_event"
        ).first()
        assert interaction is None


class TestGetCalendarService:
    """Test get_calendar_service factory function."""

    def test_get_calendar_service(self, db_session):
        """Test factory function returns service."""
        service = get_calendar_service(db_session)
        assert isinstance(service, CalendarService)
        assert service.db is db_session
