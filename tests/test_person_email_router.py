"""
Tests for person email management endpoints.
"""

import pytest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import Person, PersonEmail
from app.models.person_email import EmailLabel


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
        full_name="Email Test Person",
        first_name="Email",
        last_name="Person",
    )
    db_session.add(person)
    db_session.commit()
    return person


class TestGetEmailManageModal:
    """Test GET /people/{person_id}/emails/manage endpoint."""

    def test_person_not_found(self, client):
        """Test 404 when person doesn't exist."""
        response = client.get(f"/people/{uuid4()}/emails/manage")
        assert response.status_code == 404

    def test_returns_modal_html(self, client, test_person):
        """Test that modal HTML is returned."""
        response = client.get(f"/people/{test_person.id}/emails/manage")

        assert response.status_code == 200
        assert "Manage Email Addresses" in response.text
        assert "Add New Email" in response.text

    def test_shows_existing_emails(self, client, test_person, db_session):
        """Test that existing emails are shown."""
        email = PersonEmail(
            person_id=test_person.id,
            email="existing@example.com",
            label=EmailLabel.work,
            is_primary=True,
        )
        db_session.add(email)
        db_session.commit()

        response = client.get(f"/people/{test_person.id}/emails/manage")

        assert response.status_code == 200
        assert "existing@example.com" in response.text
        assert "Primary" in response.text


class TestAddPersonEmail:
    """Test POST /people/{person_id}/emails endpoint."""

    def test_person_not_found(self, client):
        """Test 404 when person doesn't exist."""
        response = client.post(
            f"/people/{uuid4()}/emails",
            data={"email": "test@example.com", "label": "work"},
        )
        assert response.status_code == 404

    def test_adds_new_email(self, client, test_person, db_session):
        """Test adding a new email."""
        response = client.post(
            f"/people/{test_person.id}/emails",
            data={"email": "new@example.com", "label": "work"},
        )

        assert response.status_code == 200

        # Verify email was added
        email = db_session.query(PersonEmail).filter_by(
            person_id=test_person.id,
            email="new@example.com",
        ).first()
        assert email is not None
        assert email.label == EmailLabel.work

    def test_adds_email_as_primary(self, client, test_person, db_session):
        """Test adding a new email as primary."""
        # Add existing email
        existing = PersonEmail(
            person_id=test_person.id,
            email="existing@example.com",
            is_primary=True,
        )
        db_session.add(existing)
        db_session.commit()

        response = client.post(
            f"/people/{test_person.id}/emails",
            data={"email": "primary@example.com", "label": "work", "is_primary": "true"},
        )

        assert response.status_code == 200

        # Verify new email is primary
        db_session.refresh(existing)
        new_email = db_session.query(PersonEmail).filter_by(email="primary@example.com").first()

        assert new_email.is_primary is True
        assert existing.is_primary is False

    def test_duplicate_email_ignored(self, client, test_person, db_session):
        """Test that duplicate emails are ignored."""
        # Add existing email
        existing = PersonEmail(
            person_id=test_person.id,
            email="duplicate@example.com",
        )
        db_session.add(existing)
        db_session.commit()

        response = client.post(
            f"/people/{test_person.id}/emails",
            data={"email": "duplicate@example.com", "label": "work"},
        )

        assert response.status_code == 200

        # Verify only one email exists
        count = db_session.query(PersonEmail).filter_by(
            person_id=test_person.id,
            email="duplicate@example.com",
        ).count()
        assert count == 1

    def test_email_lowercased(self, client, test_person, db_session):
        """Test that emails are lowercased."""
        response = client.post(
            f"/people/{test_person.id}/emails",
            data={"email": "UPPERCASE@EXAMPLE.COM", "label": "work"},
        )

        assert response.status_code == 200

        email = db_session.query(PersonEmail).filter_by(person_id=test_person.id).first()
        assert email.email == "uppercase@example.com"


class TestDeletePersonEmail:
    """Test DELETE /people/{person_id}/emails/{email_id} endpoint."""

    def test_deletes_email(self, client, test_person, db_session):
        """Test deleting an email."""
        email = PersonEmail(
            person_id=test_person.id,
            email="todelete@example.com",
        )
        db_session.add(email)
        db_session.commit()
        email_id = email.id

        response = client.delete(f"/people/{test_person.id}/emails/{email_id}")

        assert response.status_code == 200

        # Verify email was deleted
        deleted = db_session.query(PersonEmail).filter_by(id=email_id).first()
        assert deleted is None

    def test_promotes_new_primary(self, client, test_person, db_session):
        """Test that deleting primary promotes another email."""
        primary = PersonEmail(
            person_id=test_person.id,
            email="primary@example.com",
            is_primary=True,
        )
        secondary = PersonEmail(
            person_id=test_person.id,
            email="secondary@example.com",
            is_primary=False,
        )
        db_session.add_all([primary, secondary])
        db_session.commit()
        primary_id = primary.id

        response = client.delete(f"/people/{test_person.id}/emails/{primary_id}")

        assert response.status_code == 200

        # Verify secondary is now primary
        db_session.refresh(secondary)
        assert secondary.is_primary is True

    def test_nonexistent_email_ok(self, client, test_person):
        """Test deleting nonexistent email doesn't error."""
        response = client.delete(f"/people/{test_person.id}/emails/{uuid4()}")
        assert response.status_code == 200


class TestSetPrimaryEmail:
    """Test POST /people/{person_id}/emails/{email_id}/primary endpoint."""

    def test_email_not_found(self, client, test_person):
        """Test 404 when email doesn't exist."""
        response = client.post(f"/people/{test_person.id}/emails/{uuid4()}/primary")
        assert response.status_code == 404

    def test_sets_primary(self, client, test_person, db_session):
        """Test setting an email as primary."""
        email1 = PersonEmail(
            person_id=test_person.id,
            email="first@example.com",
            is_primary=True,
        )
        email2 = PersonEmail(
            person_id=test_person.id,
            email="second@example.com",
            is_primary=False,
        )
        db_session.add_all([email1, email2])
        db_session.commit()
        email2_id = email2.id

        response = client.post(f"/people/{test_person.id}/emails/{email2_id}/primary")

        assert response.status_code == 200

        # Verify email2 is now primary and email1 is not
        db_session.refresh(email1)
        db_session.refresh(email2)

        assert email2.is_primary is True
        assert email1.is_primary is False
