"""
Tests for pending contacts router.

Tests the pending contacts management endpoints.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models import PendingContact, PendingContactStatus, Person, PersonEmail, EmailLabel


@pytest.fixture
def test_client(db_session):
    """Create test client with database session override."""
    from app.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def pending_contact(db_session):
    """Create a test pending contact."""
    contact = PendingContact(
        email="unknown@example.com",
        name="Unknown User",
        occurrence_count=3,
        first_seen_at=datetime.now(timezone.utc),
        status=PendingContactStatus.pending,
    )
    db_session.add(contact)
    db_session.flush()
    return contact


@pytest.fixture
def ignored_contact(db_session):
    """Create a test ignored contact."""
    contact = PendingContact(
        email="ignored@example.com",
        name="Ignored User",
        occurrence_count=1,
        first_seen_at=datetime.now(timezone.utc),
        status=PendingContactStatus.ignored,
    )
    db_session.add(contact)
    db_session.flush()
    return contact


@pytest.fixture
def existing_person(db_session):
    """Create an existing person for merge tests."""
    person = Person(
        first_name="Existing",
        last_name="Person",
        full_name="Existing Person",
        email="existing@example.com",
    )
    db_session.add(person)
    db_session.flush()

    # Add PersonEmail record
    person_email = PersonEmail(
        person_id=person.id,
        email="existing@example.com",
        label=EmailLabel.work,
        is_primary=True,
    )
    db_session.add(person_email)
    db_session.flush()

    return person


class TestListPendingContacts:
    """Tests for GET /pending-contacts endpoint."""

    def test_list_pending_contacts_html(self, test_client, pending_contact):
        """Test listing pending contacts returns HTML."""
        response = test_client.get("/pending-contacts")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]
        assert pending_contact.email in response.text

    def test_list_pending_contacts_default_shows_pending_only(
        self, test_client, pending_contact, ignored_contact
    ):
        """Test that default listing shows only pending contacts."""
        response = test_client.get("/pending-contacts")

        assert response.status_code == status.HTTP_200_OK
        assert pending_contact.email in response.text
        assert ignored_contact.email not in response.text

    def test_list_pending_contacts_filter_by_status(
        self, test_client, pending_contact, ignored_contact
    ):
        """Test filtering contacts by status."""
        response = test_client.get("/pending-contacts?status=ignored")

        assert response.status_code == status.HTTP_200_OK
        assert ignored_contact.email in response.text
        assert pending_contact.email not in response.text

    def test_list_pending_contacts_invalid_status_ignored(
        self, test_client, pending_contact
    ):
        """Test that invalid status filter is ignored (shows pending)."""
        response = test_client.get("/pending-contacts?status=invalid")

        assert response.status_code == status.HTTP_200_OK
        # Should show pending contacts by default
        assert pending_contact.email in response.text


class TestApiListPendingContacts:
    """Tests for GET /pending-contacts/api endpoint."""

    def test_api_list_pending_contacts_json(self, test_client, pending_contact):
        """Test API returns JSON."""
        response = test_client.get("/pending-contacts/api")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "contacts" in data
        assert len(data["contacts"]) == 1
        assert data["contacts"][0]["email"] == pending_contact.email

    def test_api_list_includes_all_fields(self, test_client, pending_contact):
        """Test API response includes all expected fields."""
        response = test_client.get("/pending-contacts/api")

        data = response.json()
        contact = data["contacts"][0]

        assert "id" in contact
        assert "email" in contact
        assert "name" in contact
        assert "occurrence_count" in contact
        assert "status" in contact
        assert "first_seen_at" in contact
        assert contact["status"] == "pending"
        assert contact["occurrence_count"] == 3

    def test_api_filter_by_status(self, test_client, pending_contact, ignored_contact):
        """Test API filtering by status."""
        response = test_client.get("/pending-contacts/api?status=ignored")

        data = response.json()
        assert len(data["contacts"]) == 1
        assert data["contacts"][0]["email"] == ignored_contact.email


class TestGetPendingContactDetail:
    """Tests for GET /pending-contacts/{id} endpoint."""

    def test_get_pending_contact_detail(self, test_client, pending_contact):
        """Test getting pending contact details."""
        response = test_client.get(f"/pending-contacts/{pending_contact.id}")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]
        assert pending_contact.email in response.text
        assert pending_contact.name in response.text

    def test_get_pending_contact_not_found(self, test_client):
        """Test 404 for non-existent contact."""
        fake_id = uuid4()
        response = test_client.get(f"/pending-contacts/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_pending_contact_shows_potential_matches(
        self, test_client, db_session, existing_person
    ):
        """Test that potential matches are shown for contacts with same domain."""
        # Create pending contact with same domain as existing person
        contact = PendingContact(
            email="another@example.com",
            name="Another User",
            occurrence_count=1,
            first_seen_at=datetime.now(timezone.utc),
            status=PendingContactStatus.pending,
        )
        db_session.add(contact)
        db_session.flush()

        response = test_client.get(f"/pending-contacts/{contact.id}")

        assert response.status_code == status.HTTP_200_OK
        assert existing_person.full_name in response.text


class TestCreatePersonFromPending:
    """Tests for POST /pending-contacts/{id}/create endpoint."""

    def test_create_person_from_pending(self, test_client, db_session, pending_contact):
        """Test creating a new person from pending contact."""
        response = test_client.post(f"/pending-contacts/{pending_contact.id}/create")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "person_id" in data
        assert data["person_name"] == "Unknown User"

        # Verify person was created
        db_session.refresh(pending_contact)
        assert pending_contact.status == PendingContactStatus.created
        assert pending_contact.created_person_id is not None

        # Verify person has correct data
        person = db_session.query(Person).filter_by(id=pending_contact.created_person_id).first()
        assert person is not None
        assert person.full_name == "Unknown User"
        assert person.first_name == "Unknown"
        assert person.last_name == "User"

    def test_create_person_parses_name_correctly(self, test_client, db_session):
        """Test that names are parsed into first/last correctly."""
        # Create contact with multi-part name
        contact = PendingContact(
            email="john.van.dam@example.com",
            name="John Van Dam",
            occurrence_count=1,
            first_seen_at=datetime.now(timezone.utc),
            status=PendingContactStatus.pending,
        )
        db_session.add(contact)
        db_session.flush()

        response = test_client.post(f"/pending-contacts/{contact.id}/create")

        assert response.status_code == status.HTTP_200_OK

        db_session.refresh(contact)
        person = db_session.query(Person).filter_by(id=contact.created_person_id).first()
        assert person.first_name == "John"
        assert person.last_name == "Van Dam"  # Rest of name

    def test_create_person_without_name_uses_email(self, test_client, db_session):
        """Test creating person when no name is provided."""
        contact = PendingContact(
            email="noname@example.com",
            name=None,
            occurrence_count=1,
            first_seen_at=datetime.now(timezone.utc),
            status=PendingContactStatus.pending,
        )
        db_session.add(contact)
        db_session.flush()

        response = test_client.post(f"/pending-contacts/{contact.id}/create")

        assert response.status_code == status.HTTP_200_OK

        db_session.refresh(contact)
        person = db_session.query(Person).filter_by(id=contact.created_person_id).first()
        assert person.full_name == "noname"  # Email prefix

    def test_create_person_from_non_pending_fails(
        self, test_client, ignored_contact
    ):
        """Test that creating person from non-pending contact fails."""
        response = test_client.post(f"/pending-contacts/{ignored_contact.id}/create")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already processed" in response.json()["detail"]

    def test_create_person_not_found(self, test_client):
        """Test 404 for non-existent contact."""
        fake_id = uuid4()
        response = test_client.post(f"/pending-contacts/{fake_id}/create")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestIgnorePendingContact:
    """Tests for POST /pending-contacts/{id}/ignore endpoint."""

    def test_ignore_pending_contact(self, test_client, db_session, pending_contact):
        """Test ignoring a pending contact."""
        response = test_client.post(f"/pending-contacts/{pending_contact.id}/ignore")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

        # Verify status changed
        db_session.refresh(pending_contact)
        assert pending_contact.status == PendingContactStatus.ignored

    def test_ignore_already_processed_fails(self, test_client, ignored_contact):
        """Test that ignoring already processed contact fails."""
        response = test_client.post(f"/pending-contacts/{ignored_contact.id}/ignore")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already processed" in response.json()["detail"]

    def test_ignore_not_found(self, test_client):
        """Test 404 for non-existent contact."""
        fake_id = uuid4()
        response = test_client.post(f"/pending-contacts/{fake_id}/ignore")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestMergePendingWithPerson:
    """Tests for POST /pending-contacts/{id}/merge/{person_id} endpoint."""

    def test_merge_pending_with_person(
        self, test_client, db_session, pending_contact, existing_person
    ):
        """Test merging pending contact with existing person."""
        response = test_client.post(
            f"/pending-contacts/{pending_contact.id}/merge/{existing_person.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["person_name"] == "Existing Person"
        assert data["email_added"] is True

        # Verify contact status changed
        db_session.refresh(pending_contact)
        assert pending_contact.status == PendingContactStatus.created
        assert pending_contact.created_person_id == existing_person.id

        # Verify email was added to person
        emails = db_session.query(PersonEmail).filter_by(person_id=existing_person.id).all()
        email_addresses = [e.email for e in emails]
        assert pending_contact.email.lower() in email_addresses

    def test_merge_with_existing_email_doesnt_duplicate(
        self, test_client, db_session, existing_person
    ):
        """Test that merge doesn't duplicate existing email."""
        # Create pending contact with same email as existing person
        contact = PendingContact(
            email="existing@example.com",
            name="Same Email",
            occurrence_count=1,
            first_seen_at=datetime.now(timezone.utc),
            status=PendingContactStatus.pending,
        )
        db_session.add(contact)
        db_session.flush()

        response = test_client.post(
            f"/pending-contacts/{contact.id}/merge/{existing_person.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email_added"] is False

        # Verify only one email record exists
        emails = db_session.query(PersonEmail).filter_by(
            person_id=existing_person.id,
            email="existing@example.com"
        ).all()
        assert len(emails) == 1

    def test_merge_contact_not_found(self, test_client, existing_person):
        """Test 404 for non-existent contact."""
        fake_id = uuid4()
        response = test_client.post(
            f"/pending-contacts/{fake_id}/merge/{existing_person.id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_merge_person_not_found(self, test_client, pending_contact):
        """Test 404 for non-existent person."""
        fake_id = uuid4()
        response = test_client.post(
            f"/pending-contacts/{pending_contact.id}/merge/{fake_id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_merge_already_processed_fails(
        self, test_client, ignored_contact, existing_person
    ):
        """Test that merging already processed contact fails."""
        response = test_client.post(
            f"/pending-contacts/{ignored_contact.id}/merge/{existing_person.id}"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already processed" in response.json()["detail"]


class TestPendingContactsWidget:
    """Tests for GET /pending-contacts/widget endpoint."""

    def test_widget_returns_html(self, test_client, pending_contact):
        """Test widget returns HTML partial."""
        response = test_client.get("/pending-contacts/widget")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]

    def test_widget_shows_pending_contacts(self, test_client, pending_contact):
        """Test widget shows pending contacts."""
        response = test_client.get("/pending-contacts/widget")

        assert response.status_code == status.HTTP_200_OK
        assert pending_contact.email in response.text

    def test_widget_excludes_non_pending(self, test_client, ignored_contact):
        """Test widget excludes non-pending contacts."""
        response = test_client.get("/pending-contacts/widget")

        assert response.status_code == status.HTTP_200_OK
        assert ignored_contact.email not in response.text

    def test_widget_empty_state(self, test_client):
        """Test widget shows empty state when no pending contacts."""
        response = test_client.get("/pending-contacts/widget")

        assert response.status_code == status.HTTP_200_OK
        assert "No pending contacts" in response.text


class TestDeletePendingContact:
    """Tests for DELETE /pending-contacts/{id} endpoint."""

    def test_delete_pending_contact(self, test_client, db_session, pending_contact):
        """Test deleting a pending contact."""
        contact_id = pending_contact.id

        response = test_client.delete(f"/pending-contacts/{contact_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

        # Verify contact was deleted
        deleted = db_session.query(PendingContact).filter_by(id=contact_id).first()
        assert deleted is None

    def test_delete_not_found(self, test_client):
        """Test 404 for non-existent contact."""
        fake_id = uuid4()
        response = test_client.delete(f"/pending-contacts/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_any_status(self, test_client, db_session, ignored_contact):
        """Test that contacts can be deleted regardless of status."""
        contact_id = ignored_contact.id

        response = test_client.delete(f"/pending-contacts/{contact_id}")

        assert response.status_code == status.HTTP_200_OK

        # Verify contact was deleted
        deleted = db_session.query(PendingContact).filter_by(id=contact_id).first()
        assert deleted is None
