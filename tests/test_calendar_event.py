"""
Tests for CalendarEvent model.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.models import CalendarEvent, GoogleAccount


@pytest.fixture
def google_account(db_session, monkeypatch):
    """Create a test Google account."""
    monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
    from app.config import get_settings
    from app.services.encryption import get_encryption_service
    get_settings.cache_clear()
    get_encryption_service.cache_clear()

    account = GoogleAccount.create_with_credentials(
        email="calendar-test@gmail.com",
        credentials={"token": "test", "refresh_token": "test"},
    )
    db_session.add(account)
    db_session.commit()
    return account


class TestCalendarEventModel:
    """Test CalendarEvent model CRUD operations."""

    def test_create_calendar_event(self, db_session, google_account):
        """Test creating a calendar event."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="test_event_123",
            summary="Test Meeting",
            description="A test meeting description",
            start_time=now,
            end_time=now + timedelta(hours=1),
            location="Conference Room A",
            organizer_email="organizer@example.com",
        )
        db_session.add(event)
        db_session.commit()

        assert event.id is not None
        assert event.google_event_id == "test_event_123"
        assert event.summary == "Test Meeting"
        assert event.google_account_id == google_account.id

    def test_event_with_attendees(self, db_session, google_account):
        """Test event with attendees JSONB field."""
        now = datetime.now(timezone.utc)
        attendees = [
            {"email": "alice@example.com", "name": "Alice", "response_status": "accepted"},
            {"email": "bob@example.com", "name": "Bob", "response_status": "tentative"},
        ]
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="event_with_attendees",
            summary="Team Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=attendees,
        )
        db_session.add(event)
        db_session.commit()

        # Refresh from DB
        db_session.refresh(event)
        assert event.attendees is not None
        assert len(event.attendees) == 2
        assert event.attendees[0]["email"] == "alice@example.com"

    def test_unique_constraint(self, db_session, google_account):
        """Test that duplicate google_event_id for same account raises error."""
        now = datetime.now(timezone.utc)
        event1 = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="duplicate_event",
            summary="First Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        db_session.add(event1)
        db_session.commit()

        event2 = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="duplicate_event",
            summary="Second Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        db_session.add(event2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_cascade_delete(self, db_session, google_account):
        """Test that events are deleted when account is deleted."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="cascade_test_event",
            summary="Cascade Test",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        # Delete the account
        db_session.delete(google_account)
        db_session.commit()

        # Event should be gone
        deleted_event = db_session.query(CalendarEvent).filter_by(id=event_id).first()
        assert deleted_event is None


class TestCalendarEventProperties:
    """Test CalendarEvent helper properties."""

    def test_duration_minutes(self, db_session, google_account):
        """Test duration_minutes property."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="duration_test",
            summary="Duration Test",
            start_time=now,
            end_time=now + timedelta(hours=1, minutes=30),
        )
        assert event.duration_minutes == 90

    def test_is_all_day(self, db_session, google_account):
        """Test is_all_day property."""
        now = datetime.now(timezone.utc)

        # Regular event
        regular_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="regular_event",
            summary="Regular",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert regular_event.is_all_day is False

        # All-day event
        all_day_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="all_day_event",
            summary="All Day",
            start_time=now,
            end_time=now + timedelta(hours=24),
        )
        assert all_day_event.is_all_day is True

    def test_is_past(self, db_session, google_account):
        """Test is_past property."""
        now = datetime.now(timezone.utc)

        past_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="past_event",
            summary="Past Event",
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
        )
        assert past_event.is_past is True

        future_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="future_event",
            summary="Future Event",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )
        assert future_event.is_past is False

    def test_is_upcoming(self, db_session, google_account):
        """Test is_upcoming property."""
        now = datetime.now(timezone.utc)

        future_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="upcoming_test",
            summary="Upcoming",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )
        assert future_event.is_upcoming is True

        past_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="past_test",
            summary="Past",
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
        )
        assert past_event.is_upcoming is False

    def test_is_happening_now(self, db_session, google_account):
        """Test is_happening_now property."""
        now = datetime.now(timezone.utc)

        current_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="current_event",
            summary="Happening Now",
            start_time=now - timedelta(minutes=30),
            end_time=now + timedelta(minutes=30),
        )
        assert current_event.is_happening_now is True

    def test_attendee_emails(self, db_session, google_account):
        """Test attendee_emails property."""
        now = datetime.now(timezone.utc)

        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="attendee_emails_test",
            summary="Test",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=[
                {"email": "ALICE@Example.com", "name": "Alice"},
                {"email": "Bob@example.com", "name": "Bob"},
            ],
        )
        emails = event.attendee_emails
        assert len(emails) == 2
        assert "alice@example.com" in emails  # Should be lowercased
        assert "bob@example.com" in emails

    def test_attendee_emails_empty(self, db_session, google_account):
        """Test attendee_emails with no attendees."""
        now = datetime.now(timezone.utc)

        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="no_attendees",
            summary="Solo Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert event.attendee_emails == []

    def test_attendee_count(self, db_session, google_account):
        """Test attendee_count property."""
        now = datetime.now(timezone.utc)

        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="count_test",
            summary="Test",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=[
                {"email": "a@test.com"},
                {"email": "b@test.com"},
                {"email": "c@test.com"},
            ],
        )
        assert event.attendee_count == 3

    def test_is_video_call(self, db_session, google_account):
        """Test is_video_call property."""
        now = datetime.now(timezone.utc)

        zoom_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="zoom_event",
            summary="Zoom Call",
            start_time=now,
            end_time=now + timedelta(hours=1),
            location="https://zoom.us/j/123456789",
        )
        assert zoom_event.is_video_call is True

        meet_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="meet_event",
            summary="Google Meet",
            start_time=now,
            end_time=now + timedelta(hours=1),
            location="https://meet.google.com/abc-defg-hij",
        )
        assert meet_event.is_video_call is True

        in_person_event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="in_person",
            summary="In Person",
            start_time=now,
            end_time=now + timedelta(hours=1),
            location="123 Main Street",
        )
        assert in_person_event.is_video_call is False

    def test_get_attendee_by_email(self, db_session, google_account):
        """Test get_attendee_by_email method."""
        now = datetime.now(timezone.utc)

        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="get_attendee_test",
            summary="Test",
            start_time=now,
            end_time=now + timedelta(hours=1),
            attendees=[
                {"email": "alice@example.com", "name": "Alice", "response_status": "accepted"},
                {"email": "bob@example.com", "name": "Bob", "response_status": "declined"},
            ],
        )

        alice = event.get_attendee_by_email("ALICE@Example.com")  # Case insensitive
        assert alice is not None
        assert alice["name"] == "Alice"
        assert alice["response_status"] == "accepted"

        unknown = event.get_attendee_by_email("unknown@example.com")
        assert unknown is None

    def test_google_calendar_url(self, db_session, google_account):
        """Test google_calendar_url property."""
        now = datetime.now(timezone.utc)

        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="url_test_event_123",
            summary="Test",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert event.google_calendar_url == "https://calendar.google.com/calendar/event?eid=url_test_event_123"


class TestCalendarEventRelationship:
    """Test CalendarEvent relationships."""

    def test_google_account_relationship(self, db_session, google_account):
        """Test the relationship to GoogleAccount."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="relationship_test",
            summary="Relationship Test",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        # Access relationship
        assert event.google_account is not None
        assert event.google_account.email == "calendar-test@gmail.com"

    def test_account_calendar_events_relationship(self, db_session, google_account):
        """Test the reverse relationship from GoogleAccount."""
        now = datetime.now(timezone.utc)

        event1 = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="rel_event_1",
            summary="Event 1",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        event2 = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="rel_event_2",
            summary="Event 2",
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
        )
        db_session.add_all([event1, event2])
        db_session.commit()
        db_session.refresh(google_account)

        # Access events through account
        assert len(google_account.calendar_events) == 2
        summaries = [e.summary for e in google_account.calendar_events]
        assert "Event 1" in summaries
        assert "Event 2" in summaries
