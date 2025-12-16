"""
Tests for EmailCache model CRUD operations and cache expiration logic.
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError

from app.models import EmailCache


class TestEmailCacheCreate:
    """Test EmailCache creation."""

    def test_create_email_cache(self, db_session, sample_person, sample_google_account):
        """Test creating a basic email cache entry."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="thread123abc",
            subject="Re: Meeting Tomorrow",
            snippet="Looking forward to our meeting...",
            participants=["test@example.com", "other@example.com"],
            last_message_date=datetime.now(timezone.utc),
            message_count=5,
        )
        db_session.add(cache)
        db_session.flush()

        assert cache.id is not None
        assert cache.gmail_thread_id == "thread123abc"
        assert cache.subject == "Re: Meeting Tomorrow"
        assert cache.message_count == 5
        assert cache.cached_at is not None
        assert len(cache.participants) == 2

    def test_create_minimal_cache_entry(self, db_session, sample_person, sample_google_account):
        """Test creating cache entry with only required fields."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="minimal_thread",
        )
        db_session.add(cache)
        db_session.flush()

        assert cache.id is not None
        assert cache.subject is None
        assert cache.snippet is None
        assert cache.participants is None

    def test_unique_person_thread_constraint(self, db_session, sample_person, sample_google_account):
        """Test that person_id + gmail_thread_id must be unique."""
        cache1 = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="duplicate_thread",
        )
        db_session.add(cache1)
        db_session.flush()

        cache2 = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="duplicate_thread",
        )
        db_session.add(cache2)

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestEmailCacheRead:
    """Test EmailCache read operations."""

    def test_read_by_thread_id(self, db_session, sample_person, sample_google_account):
        """Test finding cache entry by thread ID."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="findable_thread",
            subject="Find Me",
        )
        db_session.add(cache)
        db_session.flush()

        found = db_session.query(EmailCache).filter_by(
            gmail_thread_id="findable_thread"
        ).first()

        assert found is not None
        assert found.subject == "Find Me"

    def test_read_by_person(self, db_session, sample_person, sample_google_account):
        """Test reading all cache entries for a person."""
        for i in range(3):
            cache = EmailCache(
                person_id=sample_person.id,
                google_account_id=sample_google_account.id,
                gmail_thread_id=f"person_thread_{i}",
            )
            db_session.add(cache)
        db_session.flush()

        caches = db_session.query(EmailCache).filter_by(
            person_id=sample_person.id
        ).all()

        assert len(caches) >= 3

    def test_relationships(self, db_session, sample_person, sample_google_account):
        """Test accessing related objects through relationships."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="relationship_thread",
        )
        db_session.add(cache)
        db_session.flush()

        assert cache.person is not None
        assert cache.person.full_name == "Test Person"
        assert cache.google_account is not None
        assert cache.google_account.email == "test@gmail.com"


class TestEmailCacheUpdate:
    """Test EmailCache update operations."""

    def test_update_subject(self, db_session, sample_person, sample_google_account):
        """Test updating cache entry subject."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="update_subject_thread",
            subject="Old Subject",
        )
        db_session.add(cache)
        db_session.flush()

        cache.subject = "New Subject"
        db_session.flush()

        found = db_session.query(EmailCache).filter_by(id=cache.id).first()
        assert found.subject == "New Subject"

    def test_update_cached_at(self, db_session, sample_person, sample_google_account):
        """Test refreshing the cache timestamp."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="refresh_thread",
        )
        db_session.add(cache)
        db_session.flush()

        old_cached_at = cache.cached_at

        # Simulate cache refresh
        cache.cached_at = datetime.now(timezone.utc)
        db_session.flush()

        assert cache.cached_at >= old_cached_at


class TestEmailCacheDelete:
    """Test EmailCache delete operations."""

    def test_delete_cache_entry(self, db_session, sample_person, sample_google_account):
        """Test deleting a cache entry."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="delete_thread",
        )
        db_session.add(cache)
        db_session.flush()
        cache_id = cache.id

        db_session.delete(cache)
        db_session.flush()

        found = db_session.query(EmailCache).filter_by(id=cache_id).first()
        assert found is None

    def test_cascade_delete_on_person_delete(self, db_session, sample_google_account):
        """Test that cache entries are deleted when person is deleted."""
        from app.models import Person, PersonStatus

        person = Person(
            full_name="Cascade Test Person",
            status=PersonStatus.active,
        )
        db_session.add(person)
        db_session.flush()
        person_id = person.id

        cache = EmailCache(
            person_id=person_id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="cascade_person_thread",
        )
        db_session.add(cache)
        db_session.flush()

        db_session.delete(person)
        db_session.flush()

        remaining = db_session.query(EmailCache).filter_by(person_id=person_id).all()
        assert len(remaining) == 0

    def test_cascade_delete_on_google_account_delete(self, db_session, sample_person):
        """Test that cache entries are deleted when Google account is deleted."""
        from app.models import GoogleAccount

        account = GoogleAccount(
            email="cascade_test@gmail.com",
            credentials_encrypted="token",
        )
        db_session.add(account)
        db_session.flush()
        account_id = account.id

        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=account_id,
            gmail_thread_id="cascade_account_thread",
        )
        db_session.add(cache)
        db_session.flush()

        db_session.delete(account)
        db_session.flush()

        remaining = db_session.query(EmailCache).filter_by(google_account_id=account_id).all()
        assert len(remaining) == 0


class TestCacheExpiration:
    """Test cache expiration logic."""

    def test_fresh_cache_is_not_expired(self, db_session, sample_person, sample_google_account):
        """Test that newly created cache entry is not expired."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="fresh_thread",
        )
        db_session.add(cache)
        db_session.flush()

        assert cache.is_expired() is False
        assert cache.is_fresh() is True

    def test_old_cache_is_expired(self, db_session, sample_person, sample_google_account):
        """Test that old cache entry is expired."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="old_thread",
        )
        db_session.add(cache)
        db_session.flush()

        # Set cached_at to 2 hours ago
        cache.cached_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.flush()

        # Default TTL is 1 hour
        assert cache.is_expired() is True
        assert cache.is_fresh() is False

    def test_custom_ttl(self, db_session, sample_person, sample_google_account):
        """Test cache expiration with custom TTL."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="custom_ttl_thread",
        )
        db_session.add(cache)
        db_session.flush()

        # Set cached_at to 30 minutes ago
        cache.cached_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        db_session.flush()

        # With 1 hour TTL, should be fresh
        assert cache.is_expired(ttl_hours=1) is False

        # With 15 minute TTL, should be expired
        assert cache.is_expired(ttl_hours=0.25) is True

    def test_expiry_at_exact_boundary(self, db_session, sample_person, sample_google_account):
        """Test cache expiration at exact TTL boundary."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="boundary_thread",
        )
        db_session.add(cache)
        db_session.flush()

        # Set to exactly 1 hour + 1 second ago
        cache.cached_at = datetime.now(timezone.utc) - timedelta(hours=1, seconds=1)
        db_session.flush()

        assert cache.is_expired(ttl_hours=1) is True

    def test_age_seconds(self, db_session, sample_person, sample_google_account):
        """Test age_seconds property."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="age_thread",
        )
        db_session.add(cache)
        db_session.flush()

        # Set cached_at to 5 minutes ago
        cache.cached_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.flush()

        # Allow for some tolerance
        assert 299 <= cache.age_seconds <= 301
        assert 4.9 <= cache.age_minutes <= 5.1


class TestGmailWebUrl:
    """Test Gmail web URL generation."""

    def test_gmail_web_url(self, db_session, sample_person, sample_google_account):
        """Test generating Gmail web URL."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="abc123xyz",
        )
        db_session.add(cache)
        db_session.flush()

        expected_url = "https://mail.google.com/mail/u/0/#inbox/abc123xyz"
        assert cache.gmail_web_url == expected_url


class TestParticipantsArray:
    """Test participants array field."""

    def test_empty_participants(self, db_session, sample_person, sample_google_account):
        """Test cache with empty participants."""
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="empty_participants_thread",
            participants=[],
        )
        db_session.add(cache)
        db_session.flush()

        found = db_session.query(EmailCache).filter_by(id=cache.id).first()
        assert found.participants == []

    def test_multiple_participants(self, db_session, sample_person, sample_google_account):
        """Test cache with multiple participants."""
        participants = [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com",
        ]
        cache = EmailCache(
            person_id=sample_person.id,
            google_account_id=sample_google_account.id,
            gmail_thread_id="multi_participants_thread",
            participants=participants,
        )
        db_session.add(cache)
        db_session.flush()

        found = db_session.query(EmailCache).filter_by(id=cache.id).first()
        assert len(found.participants) == 3
        assert "bob@example.com" in found.participants
