"""
Tests for PendingContact model.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.models import (
    PendingContact,
    PendingContactStatus,
    CalendarEvent,
    GoogleAccount,
    Person,
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
        email="pending-contact-test@gmail.com",
        credentials={"token": "test", "refresh_token": "test"},
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
        google_event_id="source_event_123",
        summary="Test Meeting",
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    db_session.add(event)
    db_session.commit()
    return event


@pytest.fixture
def person(db_session):
    """Create a test person."""
    person = Person(
        first_name="Test",
        last_name="Person",
        full_name="Test Person",
        email="testperson@example.com",
    )
    db_session.add(person)
    db_session.commit()
    return person


class TestPendingContactModel:
    """Test PendingContact model CRUD operations."""

    def test_create_pending_contact(self, db_session):
        """Test creating a pending contact."""
        contact = PendingContact(
            email="unknown@example.com",
            name="Unknown Person",
        )
        db_session.add(contact)
        db_session.commit()

        assert contact.id is not None
        assert contact.email == "unknown@example.com"
        assert contact.name == "Unknown Person"
        assert contact.status == PendingContactStatus.pending
        assert contact.occurrence_count == 1

    def test_create_with_source_event(self, db_session, calendar_event):
        """Test creating pending contact linked to calendar event."""
        contact = PendingContact(
            email="attendee@example.com",
            name="Event Attendee",
            source_event_id=calendar_event.id,
        )
        db_session.add(contact)
        db_session.commit()

        db_session.refresh(contact)
        assert contact.source_event is not None
        assert contact.source_event.summary == "Test Meeting"

    def test_unique_email_constraint(self, db_session):
        """Test that duplicate emails raise error."""
        contact1 = PendingContact(email="duplicate@example.com")
        db_session.add(contact1)
        db_session.commit()

        contact2 = PendingContact(email="duplicate@example.com")
        db_session.add(contact2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_source_event_set_null_on_delete(self, db_session, google_account):
        """Test that source_event_id is set to NULL when event is deleted."""
        now = datetime.now(timezone.utc)
        event = CalendarEvent(
            google_account_id=google_account.id,
            google_event_id="delete_me_event",
            summary="Will Be Deleted",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        db_session.add(event)
        db_session.commit()

        contact = PendingContact(
            email="orphan@example.com",
            source_event_id=event.id,
        )
        db_session.add(contact)
        db_session.commit()
        contact_id = contact.id

        # Delete the event
        db_session.delete(event)
        db_session.commit()

        # Contact should still exist with NULL source_event_id
        remaining = db_session.query(PendingContact).filter_by(id=contact_id).first()
        assert remaining is not None
        assert remaining.source_event_id is None


class TestPendingContactStatus:
    """Test PendingContact status transitions."""

    def test_default_status_pending(self, db_session):
        """Test default status is pending."""
        contact = PendingContact(email="default@example.com")
        db_session.add(contact)
        db_session.commit()

        assert contact.status == PendingContactStatus.pending
        assert contact.is_pending is True
        assert contact.is_created is False
        assert contact.is_ignored is False

    def test_mark_created(self, db_session, person):
        """Test marking contact as created."""
        contact = PendingContact(email="tocreate@example.com")
        db_session.add(contact)
        db_session.commit()

        contact.mark_created(person.id)
        db_session.commit()

        db_session.refresh(contact)
        assert contact.status == PendingContactStatus.created
        assert contact.is_created is True
        assert contact.created_person_id == person.id

    def test_mark_ignored(self, db_session):
        """Test marking contact as ignored."""
        contact = PendingContact(email="toignore@example.com")
        db_session.add(contact)
        db_session.commit()

        contact.mark_ignored()
        db_session.commit()

        db_session.refresh(contact)
        assert contact.status == PendingContactStatus.ignored
        assert contact.is_ignored is True

    def test_increment_occurrence(self, db_session):
        """Test incrementing occurrence count."""
        contact = PendingContact(email="frequent@example.com")
        db_session.add(contact)
        db_session.commit()

        assert contact.occurrence_count == 1

        contact.increment_occurrence()
        db_session.commit()

        db_session.refresh(contact)
        assert contact.occurrence_count == 2

        contact.increment_occurrence()
        contact.increment_occurrence()
        db_session.commit()

        db_session.refresh(contact)
        assert contact.occurrence_count == 4


class TestPendingContactRelationships:
    """Test PendingContact relationships."""

    def test_created_person_relationship(self, db_session, person):
        """Test relationship to created person."""
        contact = PendingContact(
            email="linked@example.com",
            status=PendingContactStatus.created,
            created_person_id=person.id,
        )
        db_session.add(contact)
        db_session.commit()

        db_session.refresh(contact)
        assert contact.created_person is not None
        assert contact.created_person.first_name == "Test"
        assert contact.created_person.last_name == "Person"

    def test_created_person_set_null_on_delete(self, db_session):
        """Test that created_person_id is set to NULL when person is deleted."""
        person = Person(
            first_name="Deletable",
            last_name="Person",
            full_name="Deletable Person",
            email="deletable@example.com",
        )
        db_session.add(person)
        db_session.commit()

        contact = PendingContact(
            email="orphaned@example.com",
            status=PendingContactStatus.created,
            created_person_id=person.id,
        )
        db_session.add(contact)
        db_session.commit()
        contact_id = contact.id

        # Delete the person
        db_session.delete(person)
        db_session.commit()

        # Contact should still exist with NULL created_person_id
        remaining = db_session.query(PendingContact).filter_by(id=contact_id).first()
        assert remaining is not None
        assert remaining.created_person_id is None


class TestPendingContactRepr:
    """Test PendingContact __repr__ method."""

    def test_repr(self, db_session):
        """Test string representation."""
        contact = PendingContact(email="repr@example.com")
        db_session.add(contact)
        db_session.commit()

        repr_str = repr(contact)
        assert "repr@example.com" in repr_str
        assert "pending" in repr_str
