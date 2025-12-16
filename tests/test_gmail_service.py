"""
Tests for Gmail service.

These tests use mocking to avoid requiring actual Gmail API access.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from uuid import uuid4

from app.models import Person, PersonEmail, GoogleAccount, EmailIgnoreList
from app.models.person_email import EmailLabel
from app.models.email_ignore import IgnorePatternType
from app.services.gmail_service import (
    GmailService,
    GmailServiceError,
    EmailThread,
    get_gmail_service,
)


class TestBuildSearchQuery:
    """Test search query building."""

    def test_build_query_with_person_emails(self, db_session):
        """Test building query from person_emails (direct correspondence only)."""
        person = Person(full_name="John Doe")
        db_session.add(person)
        db_session.flush()

        email1 = PersonEmail(
            person_id=person.id,
            email="john.doe@work.com",
            label=EmailLabel.work,
        )
        email2 = PersonEmail(
            person_id=person.id,
            email="john@personal.com",
            label=EmailLabel.personal,
        )
        db_session.add_all([email1, email2])
        db_session.flush()

        # Refresh to load relationships
        db_session.refresh(person)

        service = GmailService(db_session)
        query = service.build_search_query(person)

        assert "from:john.doe@work.com" in query
        assert "to:john.doe@work.com" in query
        assert "from:john@personal.com" in query
        assert "to:john@personal.com" in query
        # Should NOT include name search to avoid matching notification emails
        assert '"John Doe"' not in query

    def test_build_query_with_legacy_email(self, db_session):
        """Test building query from legacy email field."""
        person = Person(
            full_name="Jane Smith",
            email="jane@example.com",
        )
        db_session.add(person)
        db_session.flush()

        service = GmailService(db_session)
        query = service.build_search_query(person)

        assert "from:jane@example.com" in query
        assert "to:jane@example.com" in query
        # Should NOT include name search to avoid matching notification emails
        assert '"Jane Smith"' not in query

    def test_build_query_with_multiple_legacy_emails(self, db_session):
        """Test building query from comma-separated legacy emails."""
        person = Person(
            full_name="Bob Wilson",
            email="bob@work.com, bob@home.com",
        )
        db_session.add(person)
        db_session.flush()

        service = GmailService(db_session)
        query = service.build_search_query(person)

        assert "from:bob@work.com" in query
        assert "from:bob@home.com" in query

    def test_build_query_name_only_returns_empty(self, db_session):
        """Test building query with only name (no emails) returns empty.

        When a person has no email addresses, we return an empty query
        rather than searching by name, to avoid matching notification
        emails that merely mention the person's name.
        """
        person = Person(full_name="No Email Person")
        db_session.add(person)
        db_session.flush()

        service = GmailService(db_session)
        query = service.build_search_query(person)

        # Should return empty query - no emails to search for
        assert query == ""


class TestEmailThread:
    """Test EmailThread class."""

    def test_email_thread_creation(self):
        """Test creating an EmailThread."""
        account_id = uuid4()
        thread = EmailThread(
            thread_id="abc123",
            account_id=account_id,
            account_email="test@gmail.com",
            subject="Test Subject",
            snippet="This is a test...",
            participants=["alice@example.com", "bob@example.com"],
            last_message_date=datetime(2025, 12, 8, 12, 0, 0, tzinfo=timezone.utc),
            message_count=5,
        )

        assert thread.thread_id == "abc123"
        assert thread.subject == "Test Subject"
        assert thread.message_count == 5
        assert len(thread.participants) == 2

    def test_email_thread_gmail_link(self):
        """Test Gmail link generation."""
        thread = EmailThread(
            thread_id="xyz789",
            account_id=uuid4(),
            account_email="test@gmail.com",
        )

        assert thread.gmail_link == "https://mail.google.com/mail/u/0/#all/xyz789"

    def test_email_thread_to_dict(self):
        """Test converting thread to dictionary."""
        account_id = uuid4()
        thread = EmailThread(
            thread_id="dict123",
            account_id=account_id,
            account_email="test@gmail.com",
            subject="Dict Test",
        )

        data = thread.to_dict()

        assert data["thread_id"] == "dict123"
        assert data["account_id"] == str(account_id)
        assert data["account_email"] == "test@gmail.com"
        assert data["subject"] == "Dict Test"
        assert "gmail_link" in data


class TestIgnorePatternFiltering:
    """Test ignore pattern filtering."""

    def test_filter_by_domain(self, db_session):
        """Test filtering by domain pattern."""
        # Add a unique ignore pattern for this test
        pattern = EmailIgnoreList(
            pattern="testspam123.com",
            pattern_type=IgnorePatternType.domain,
        )
        db_session.add(pattern)
        db_session.flush()

        service = GmailService(db_session)

        threads = [
            EmailThread(
                thread_id="1",
                account_id=uuid4(),
                account_email="test@gmail.com",
                participants=["newsletter@testspam123.com", "user@example.com"],
            ),
            EmailThread(
                thread_id="2",
                account_id=uuid4(),
                account_email="test@gmail.com",
                participants=["friend@gmail.com"],
            ),
        ]

        filtered = service._filter_ignored_threads(threads)

        assert len(filtered) == 1
        assert filtered[0].thread_id == "2"

    def test_filter_by_email_pattern(self, db_session):
        """Test filtering by email pattern with wildcard."""
        # Add a unique ignore pattern for this test
        pattern = EmailIgnoreList(
            pattern="testbot@*",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        service = GmailService(db_session)

        threads = [
            EmailThread(
                thread_id="1",
                account_id=uuid4(),
                account_email="test@gmail.com",
                participants=["testbot@company.com"],
            ),
            EmailThread(
                thread_id="2",
                account_id=uuid4(),
                account_email="test@gmail.com",
                participants=["support@company.com"],
            ),
        ]

        filtered = service._filter_ignored_threads(threads)

        assert len(filtered) == 1
        assert filtered[0].thread_id == "2"

    def test_filter_exact_email_match(self, db_session):
        """Test filtering by exact email match."""
        pattern = EmailIgnoreList(
            pattern="spam@example.com",
            pattern_type=IgnorePatternType.email,
        )
        db_session.add(pattern)
        db_session.flush()

        service = GmailService(db_session)

        threads = [
            EmailThread(
                thread_id="1",
                account_id=uuid4(),
                account_email="test@gmail.com",
                participants=["spam@example.com"],
            ),
            EmailThread(
                thread_id="2",
                account_id=uuid4(),
                account_email="test@gmail.com",
                participants=["notspam@example.com"],
            ),
        ]

        filtered = service._filter_ignored_threads(threads)

        assert len(filtered) == 1
        assert filtered[0].thread_id == "2"


class TestEmailPatternMatching:
    """Test email pattern matching."""

    def test_matches_exact_email(self, db_session):
        """Test matching exact email."""
        service = GmailService(db_session)

        assert service._matches_email_pattern("test@example.com", "test@example.com") is True
        assert service._matches_email_pattern("other@example.com", "test@example.com") is False

    def test_matches_wildcard_pattern(self, db_session):
        """Test matching wildcard patterns."""
        service = GmailService(db_session)

        # noreply@* should match noreply@anything.com
        assert service._matches_email_pattern("noreply@company.com", "noreply@*") is True
        assert service._matches_email_pattern("noreply@test.org", "noreply@*") is True
        assert service._matches_email_pattern("support@company.com", "noreply@*") is False

    def test_matches_prefix_wildcard(self, db_session):
        """Test matching prefix wildcards."""
        service = GmailService(db_session)

        # *@domain.com should match any email at that domain
        assert service._matches_email_pattern("user@domain.com", "*@domain.com") is True
        assert service._matches_email_pattern("admin@domain.com", "*@domain.com") is True
        assert service._matches_email_pattern("user@other.com", "*@domain.com") is False


class TestExtractEmails:
    """Test email extraction from headers."""

    def test_extract_simple_email(self, db_session):
        """Test extracting simple email address."""
        service = GmailService(db_session)

        emails = service._extract_emails("test@example.com")
        assert emails == ["test@example.com"]

    def test_extract_email_with_name(self, db_session):
        """Test extracting email from 'Name <email>' format."""
        service = GmailService(db_session)

        emails = service._extract_emails("John Doe <john@example.com>")
        assert "john@example.com" in emails

    def test_extract_multiple_emails(self, db_session):
        """Test extracting multiple email addresses."""
        service = GmailService(db_session)

        emails = service._extract_emails("Alice <alice@example.com>, Bob <bob@example.com>")
        assert len(emails) == 2
        assert "alice@example.com" in emails
        assert "bob@example.com" in emails

    def test_extract_normalizes_case(self, db_session):
        """Test that extracted emails are lowercased."""
        service = GmailService(db_session)

        emails = service._extract_emails("John@EXAMPLE.COM")
        assert emails == ["john@example.com"]


class TestSearchEmailsForPerson:
    """Test searching emails for a person."""

    def test_search_person_not_found(self, db_session):
        """Test searching for non-existent person."""
        service = GmailService(db_session)

        with pytest.raises(GmailServiceError) as exc_info:
            service.search_emails_for_person(uuid4())

        assert "Person not found" in str(exc_info.value)

    def test_search_no_google_accounts(self, db_session):
        """Test searching when no Google accounts are connected."""
        person = Person(full_name="Test Person", email="test@example.com")
        db_session.add(person)
        db_session.flush()

        service = GmailService(db_session)
        results = service.search_emails_for_person(person.id)

        assert results == []

    @patch("app.services.gmail_service.build")
    def test_search_returns_sorted_threads(self, mock_build, db_session, monkeypatch):
        """Test that search results are sorted by date."""
        # Set up encryption
        monkeypatch.setenv("ENCRYPTION_KEY", "izZY7IUIzei-kSYNOCgiIpwOSv9_hioCMBrs2mD9drs=")
        from app.config import get_settings
        from app.services.encryption import get_encryption_service
        get_settings.cache_clear()
        get_encryption_service.cache_clear()

        # Create person and account
        person = Person(full_name="Test Person", email="test@example.com")
        db_session.add(person)
        db_session.flush()

        account = GoogleAccount.create_with_credentials(
            email="myaccount@gmail.com",
            credentials={"token": "test", "refresh_token": "test"},
        )
        db_session.add(account)
        db_session.flush()

        # Mock Gmail API
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.users.return_value.threads.return_value.list.return_value.execute.return_value = {
            "threads": [
                {"id": "older"},
                {"id": "newer"},
            ]
        }

        def mock_get_thread(userId, id, format, metadataHeaders):
            mock_response = MagicMock()
            if id == "older":
                mock_response.execute.return_value = {
                    "id": "older",
                    "snippet": "Older message",
                    "messages": [{
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Older"},
                                {"name": "Date", "value": "Mon, 01 Dec 2025 10:00:00 +0000"},
                            ]
                        }
                    }]
                }
            else:
                mock_response.execute.return_value = {
                    "id": "newer",
                    "snippet": "Newer message",
                    "messages": [{
                        "payload": {
                            "headers": [
                                {"name": "Subject", "value": "Newer"},
                                {"name": "Date", "value": "Sun, 07 Dec 2025 10:00:00 +0000"},
                            ]
                        }
                    }]
                }
            return mock_response

        mock_service.users.return_value.threads.return_value.get = mock_get_thread

        service = GmailService(db_session)
        results = service.search_emails_for_person(person.id)

        # Should be sorted newest first
        assert len(results) == 2
        assert results[0].thread_id == "newer"
        assert results[1].thread_id == "older"


class TestGetThreadDetails:
    """Test getting thread details."""

    def test_get_thread_account_not_found(self, db_session):
        """Test getting thread for non-existent account."""
        service = GmailService(db_session)

        result = service.get_thread_details("thread123", uuid4())
        assert result is None


class TestGetGmailService:
    """Test get_gmail_service factory."""

    def test_get_gmail_service(self, db_session):
        """Test getting Gmail service instance."""
        service = get_gmail_service(db_session)

        assert isinstance(service, GmailService)
        assert service.db == db_session
