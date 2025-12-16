"""Tests for the Google Contacts service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from app.models import Person, PersonEmail, GoogleAccount
from app.models.person_email import EmailLabel
from app.services.contacts_service import (
    ContactsService,
    GoogleContact,
    SyncResult,
    ContactsServiceError,
    ContactsAuthError,
    ContactsAPIError,
    get_contacts_service,
)


class TestGoogleContact:
    """Tests for GoogleContact dataclass."""

    def test_google_contact_id_extraction(self):
        """Test extracting contact ID from resource name."""
        contact = GoogleContact(
            resource_name="people/c12345678901234567",
            display_name="Test User",
            given_name="Test",
            family_name="User",
            emails=[{"value": "test@example.com"}],
            phones=[],
            photo_url=None,
            organization_title=None,
            organization_name=None,
        )
        assert contact.google_contact_id == "c12345678901234567"

    def test_primary_email_with_metadata(self):
        """Test getting primary email when metadata.primary is set."""
        contact = GoogleContact(
            resource_name="people/c123",
            display_name="Test",
            given_name="Test",
            family_name="User",
            emails=[
                {"value": "secondary@example.com"},
                {"value": "primary@example.com", "metadata": {"primary": True}},
            ],
            phones=[],
            photo_url=None,
            organization_title=None,
            organization_name=None,
        )
        assert contact.primary_email == "primary@example.com"

    def test_primary_email_fallback_to_first(self):
        """Test getting first email when no primary is set."""
        contact = GoogleContact(
            resource_name="people/c123",
            display_name="Test",
            given_name="Test",
            family_name="User",
            emails=[
                {"value": "first@example.com"},
                {"value": "second@example.com"},
            ],
            phones=[],
            photo_url=None,
            organization_title=None,
            organization_name=None,
        )
        assert contact.primary_email == "first@example.com"

    def test_primary_email_none_when_no_emails(self):
        """Test primary_email returns None when no emails."""
        contact = GoogleContact(
            resource_name="people/c123",
            display_name="Test",
            given_name="Test",
            family_name="User",
            emails=[],
            phones=[],
            photo_url=None,
            organization_title=None,
            organization_name=None,
        )
        assert contact.primary_email is None


class TestContactsService:
    """Tests for ContactsService."""

    def test_get_contacts_service(self, db_session):
        """Test factory function returns service instance."""
        service = get_contacts_service(db_session)
        assert isinstance(service, ContactsService)
        assert service.db == db_session

    def test_build_email_cache(self, db_session):
        """Test building email lookup cache."""
        # Create a person with emails
        person = Person(full_name="Test Person")
        db_session.add(person)
        db_session.flush()

        email1 = PersonEmail(
            person_id=person.id,
            email="test1@example.com",
            label=EmailLabel.work,
        )
        email2 = PersonEmail(
            person_id=person.id,
            email="test2@example.com",
            label=EmailLabel.personal,
        )
        db_session.add_all([email1, email2])
        db_session.flush()

        service = ContactsService(db_session)
        service._build_email_cache()

        assert "test1@example.com" in service._email_to_person_cache
        assert "test2@example.com" in service._email_to_person_cache
        assert service._email_to_person_cache["test1@example.com"] == person.id

    def test_match_contact_to_person_found(self, db_session):
        """Test matching contact by email to existing person."""
        # Create existing person with email
        person = Person(full_name="Existing Person")
        db_session.add(person)
        db_session.flush()

        email = PersonEmail(
            person_id=person.id,
            email="existing@example.com",
            label=EmailLabel.work,
        )
        db_session.add(email)
        db_session.flush()

        service = ContactsService(db_session)

        contact = GoogleContact(
            resource_name="people/c123",
            display_name="Google Contact",
            given_name="Google",
            family_name="Contact",
            emails=[{"value": "existing@example.com"}],
            phones=[],
            photo_url=None,
            organization_title=None,
            organization_name=None,
        )

        matched = service._match_contact_to_person(contact)
        assert matched is not None
        assert matched.id == person.id

    def test_match_contact_to_person_not_found(self, db_session):
        """Test no match when email doesn't exist."""
        service = ContactsService(db_session)

        contact = GoogleContact(
            resource_name="people/c123",
            display_name="New Contact",
            given_name="New",
            family_name="Contact",
            emails=[{"value": "new@example.com"}],
            phones=[],
            photo_url=None,
            organization_title=None,
            organization_name=None,
        )

        matched = service._match_contact_to_person(contact)
        assert matched is None

    def test_create_person_from_contact(self, db_session):
        """Test creating new person from Google contact."""
        account_id = uuid4()
        service = ContactsService(db_session)

        contact = GoogleContact(
            resource_name="people/c12345",
            display_name="John Doe",
            given_name="John",
            family_name="Doe",
            emails=[
                {"value": "john@work.com", "type": "work"},
                {"value": "john@home.com", "type": "home"},
            ],
            phones=[{"value": "+1234567890"}],
            photo_url="https://example.com/photo.jpg",
            organization_title="Engineer",
            organization_name="Tech Corp",
        )

        person = service._create_person_from_contact(contact, account_id)

        assert person.full_name == "John Doe"
        assert person.first_name == "John"
        assert person.last_name == "Doe"
        assert person.phone == "+1234567890"
        assert person.profile_picture == "https://example.com/photo.jpg"
        assert person.title == "Engineer"
        assert person.custom_fields["google_contact_id"] == "c12345"
        assert person.custom_fields["imported_from"] == "google_contacts"

        # Check emails were created
        db_session.flush()
        assert len(person.emails) == 2

    def test_create_person_from_contact_no_name(self, db_session):
        """Test creating person with Unknown name when display_name is None."""
        account_id = uuid4()
        service = ContactsService(db_session)

        contact = GoogleContact(
            resource_name="people/c123",
            display_name=None,
            given_name=None,
            family_name=None,
            emails=[{"value": "anon@example.com"}],
            phones=[],
            photo_url=None,
            organization_title=None,
            organization_name=None,
        )

        person = service._create_person_from_contact(contact, account_id)
        assert person.full_name == "Unknown"

    def test_update_person_from_contact_empty_fields(self, db_session):
        """Test updating existing person only fills empty fields."""
        # Create person with some fields filled
        person = Person(
            full_name="Jane Doe",
            first_name="Jane",
            # last_name, phone, profile_picture, title are empty
        )
        db_session.add(person)
        db_session.flush()

        service = ContactsService(db_session)

        contact = GoogleContact(
            resource_name="people/c123",
            display_name="Jane Smith",  # Different name
            given_name="Janet",  # Different first name
            family_name="Smith",
            emails=[],
            phones=[{"value": "+9876543210"}],
            photo_url="https://example.com/photo.jpg",
            organization_title="Manager",
            organization_name="Corp",
        )

        updated = service._update_person_from_contact(person, contact)

        assert updated is True
        # first_name should NOT be updated (was already set)
        assert person.first_name == "Jane"
        # last_name SHOULD be updated (was empty)
        assert person.last_name == "Smith"
        # phone SHOULD be updated
        assert person.phone == "+9876543210"
        # profile_picture SHOULD be updated
        assert person.profile_picture == "https://example.com/photo.jpg"
        # title SHOULD be updated
        assert person.title == "Manager"

    def test_update_person_adds_new_emails(self, db_session):
        """Test update adds new email addresses."""
        person = Person(full_name="Test Person")
        db_session.add(person)
        db_session.flush()

        # Add existing email
        existing_email = PersonEmail(
            person_id=person.id,
            email="existing@example.com",
            label=EmailLabel.work,
        )
        db_session.add(existing_email)
        db_session.flush()

        service = ContactsService(db_session)

        contact = GoogleContact(
            resource_name="people/c123",
            display_name="Test Person",
            given_name="Test",
            family_name="Person",
            emails=[
                {"value": "existing@example.com"},  # Already exists
                {"value": "new@example.com"},  # New
            ],
            phones=[],
            photo_url=None,
            organization_title=None,
            organization_name=None,
        )

        updated = service._update_person_from_contact(person, contact)

        assert updated is True
        db_session.flush()
        # Query all emails for this person directly
        all_emails = db_session.query(PersonEmail).filter_by(person_id=person.id).all()
        emails = [pe.email for pe in all_emails]
        assert "existing@example.com" in emails
        assert "new@example.com" in emails

    def test_map_email_type(self, db_session):
        """Test mapping Google email types to labels."""
        service = ContactsService(db_session)

        assert service._map_email_type("work") == EmailLabel.work
        assert service._map_email_type("WORK") == EmailLabel.work
        assert service._map_email_type("home") == EmailLabel.personal
        assert service._map_email_type("personal") == EmailLabel.personal
        assert service._map_email_type("other") == EmailLabel.other
        assert service._map_email_type("unknown") == EmailLabel.other

    def test_sync_contacts_account_not_found(self, db_session):
        """Test sync raises error when account not found."""
        service = ContactsService(db_session)

        with pytest.raises(ContactsServiceError, match="Account not found"):
            service.sync_contacts(uuid4())

    @patch.object(ContactsService, "fetch_contacts")
    def test_sync_contacts_creates_new_persons(self, mock_fetch, db_session):
        """Test syncing creates new persons for unmatched contacts."""
        # Create Google account
        account = GoogleAccount.create_with_credentials(
            email="test@gmail.com",
            credentials={"token": "test", "refresh_token": "refresh"},
        )
        db_session.add(account)
        db_session.flush()

        # Mock fetch_contacts to return contacts
        mock_fetch.return_value = [
            GoogleContact(
                resource_name="people/c1",
                display_name="New Person",
                given_name="New",
                family_name="Person",
                emails=[{"value": "new@example.com"}],
                phones=[],
                photo_url=None,
                organization_title=None,
                organization_name=None,
            ),
        ]

        service = ContactsService(db_session)
        result = service.sync_contacts(account.id)

        assert result.contacts_fetched == 1
        assert result.contacts_created == 1
        assert result.contacts_matched == 0

        # Verify person was created
        person = db_session.query(Person).filter_by(full_name="New Person").first()
        assert person is not None

    @patch.object(ContactsService, "fetch_contacts")
    def test_sync_contacts_updates_existing(self, mock_fetch, db_session):
        """Test syncing updates existing persons matched by email."""
        # Create existing person with email
        person = Person(full_name="Existing User")
        db_session.add(person)
        db_session.flush()

        email = PersonEmail(
            person_id=person.id,
            email="existing@example.com",
            label=EmailLabel.work,
        )
        db_session.add(email)

        # Create Google account
        account = GoogleAccount.create_with_credentials(
            email="test@gmail.com",
            credentials={"token": "test", "refresh_token": "refresh"},
        )
        db_session.add(account)
        db_session.flush()

        # Mock fetch_contacts
        mock_fetch.return_value = [
            GoogleContact(
                resource_name="people/c1",
                display_name="Existing User",
                given_name="Existing",
                family_name="User",
                emails=[{"value": "existing@example.com"}],
                phones=[{"value": "+1111111111"}],
                photo_url=None,
                organization_title="Developer",
                organization_name=None,
            ),
        ]

        service = ContactsService(db_session)
        result = service.sync_contacts(account.id)

        assert result.contacts_fetched == 1
        assert result.contacts_matched == 1
        assert result.contacts_created == 0
        assert result.contacts_updated == 1

        # Verify person was updated
        db_session.refresh(person)
        assert person.phone == "+1111111111"
        assert person.title == "Developer"

    @patch.object(ContactsService, "fetch_contacts")
    def test_sync_contacts_skips_no_name(self, mock_fetch, db_session):
        """Test syncing skips contacts without display name."""
        # Create Google account
        account = GoogleAccount.create_with_credentials(
            email="test@gmail.com",
            credentials={"token": "test", "refresh_token": "refresh"},
        )
        db_session.add(account)
        db_session.flush()

        # Mock fetch_contacts with no name
        mock_fetch.return_value = [
            GoogleContact(
                resource_name="people/c1",
                display_name=None,
                given_name=None,
                family_name=None,
                emails=[{"value": "anon@example.com"}],
                phones=[],
                photo_url=None,
                organization_title=None,
                organization_name=None,
            ),
        ]

        service = ContactsService(db_session)
        result = service.sync_contacts(account.id)

        assert result.contacts_fetched == 1
        assert result.contacts_skipped == 1
        assert result.contacts_created == 0

    def test_parse_contact(self, db_session):
        """Test parsing Google People API response."""
        service = ContactsService(db_session)

        person_data = {
            "resourceName": "people/c123456",
            "names": [
                {
                    "displayName": "John Doe",
                    "givenName": "John",
                    "familyName": "Doe",
                }
            ],
            "emailAddresses": [
                {"value": "john@example.com", "type": "work"},
            ],
            "phoneNumbers": [
                {"value": "+1234567890", "type": "mobile"},
            ],
            "photos": [
                {"url": "https://example.com/photo.jpg"},
            ],
            "organizations": [
                {"name": "Tech Corp", "title": "Engineer"},
            ],
        }

        contact = service._parse_contact(person_data)

        assert contact is not None
        assert contact.resource_name == "people/c123456"
        assert contact.display_name == "John Doe"
        assert contact.given_name == "John"
        assert contact.family_name == "Doe"
        assert len(contact.emails) == 1
        assert contact.emails[0]["value"] == "john@example.com"
        assert len(contact.phones) == 1
        assert contact.photo_url == "https://example.com/photo.jpg"
        assert contact.organization_name == "Tech Corp"
        assert contact.organization_title == "Engineer"

    def test_parse_contact_missing_resource(self, db_session):
        """Test parsing returns None for missing resource name."""
        service = ContactsService(db_session)

        person_data = {"names": [{"displayName": "Test"}]}
        contact = service._parse_contact(person_data)
        assert contact is None

    def test_parse_contact_skips_default_photo(self, db_session):
        """Test parsing skips default photos."""
        service = ContactsService(db_session)

        person_data = {
            "resourceName": "people/c123",
            "photos": [
                {"url": "https://default.jpg", "metadata": {"default": True}},
            ],
        }

        contact = service._parse_contact(person_data)
        assert contact.photo_url is None


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_creation(self):
        """Test creating SyncResult with all fields."""
        result = SyncResult(
            contacts_fetched=100,
            contacts_matched=50,
            contacts_created=30,
            contacts_updated=20,
            contacts_skipped=0,
        )

        assert result.contacts_fetched == 100
        assert result.contacts_matched == 50
        assert result.contacts_created == 30
        assert result.contacts_updated == 20
        assert result.contacts_skipped == 0
