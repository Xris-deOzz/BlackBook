"""
Tests for PersonEmail model CRUD operations.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import PersonEmail, EmailLabel


class TestPersonEmailCreate:
    """Test PersonEmail creation."""

    def test_create_person_email(self, db_session, sample_person):
        """Test creating a basic person email."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="test@example.com",
            label=EmailLabel.work,
            is_primary=True,
        )
        db_session.add(email)
        db_session.flush()

        assert email.id is not None
        assert email.email == "test@example.com"
        assert email.label == EmailLabel.work
        assert email.is_primary is True
        assert email.created_at is not None

    def test_create_person_email_default_values(self, db_session, sample_person):
        """Test that default values are applied correctly."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="default@example.com",
        )
        db_session.add(email)
        db_session.flush()

        assert email.label == EmailLabel.work  # Default
        assert email.is_primary is False  # Default

    def test_create_multiple_emails_for_person(self, db_session, sample_person):
        """Test adding multiple emails to a single person."""
        work_email = PersonEmail(
            person_id=sample_person.id,
            email="work@example.com",
            label=EmailLabel.work,
            is_primary=True,
        )
        personal_email = PersonEmail(
            person_id=sample_person.id,
            email="personal@example.com",
            label=EmailLabel.personal,
            is_primary=False,
        )
        db_session.add_all([work_email, personal_email])
        db_session.flush()

        assert work_email.id is not None
        assert personal_email.id is not None
        assert work_email.id != personal_email.id

    def test_unique_constraint_same_email_same_person(self, db_session, sample_person):
        """Test that the same email cannot be added twice to the same person."""
        email1 = PersonEmail(
            person_id=sample_person.id,
            email="duplicate@example.com",
        )
        db_session.add(email1)
        db_session.flush()

        email2 = PersonEmail(
            person_id=sample_person.id,
            email="duplicate@example.com",
        )
        db_session.add(email2)

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestPersonEmailRead:
    """Test PersonEmail read operations."""

    def test_read_person_email(self, db_session, sample_person):
        """Test reading a person email by ID."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="read@example.com",
            label=EmailLabel.personal,
        )
        db_session.add(email)
        db_session.flush()

        # Query the email back
        found_email = db_session.query(PersonEmail).filter_by(id=email.id).first()

        assert found_email is not None
        assert found_email.email == "read@example.com"
        assert found_email.label == EmailLabel.personal

    def test_read_emails_by_person(self, db_session, sample_person):
        """Test reading all emails for a person."""
        emails = [
            PersonEmail(person_id=sample_person.id, email="email1@example.com"),
            PersonEmail(person_id=sample_person.id, email="email2@example.com"),
            PersonEmail(person_id=sample_person.id, email="email3@example.com"),
        ]
        db_session.add_all(emails)
        db_session.flush()

        # Query all emails for the person
        person_emails = (
            db_session.query(PersonEmail)
            .filter_by(person_id=sample_person.id)
            .all()
        )

        assert len(person_emails) == 3

    def test_read_email_by_address(self, db_session, sample_person):
        """Test finding emails by email address."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="findme@example.com",
        )
        db_session.add(email)
        db_session.flush()

        # Find by email address
        found = (
            db_session.query(PersonEmail)
            .filter_by(email="findme@example.com")
            .first()
        )

        assert found is not None
        assert found.person_id == sample_person.id

    def test_person_relationship(self, db_session, sample_person):
        """Test accessing person through the relationship."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="relationship@example.com",
        )
        db_session.add(email)
        db_session.flush()

        # Access person through relationship
        assert email.person is not None
        assert email.person.id == sample_person.id
        assert email.person.full_name == "Test Person"


class TestPersonEmailUpdate:
    """Test PersonEmail update operations."""

    def test_update_email_address(self, db_session, sample_person):
        """Test updating an email address."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="old@example.com",
        )
        db_session.add(email)
        db_session.flush()

        # Update the email
        email.email = "new@example.com"
        db_session.flush()

        # Verify update
        found = db_session.query(PersonEmail).filter_by(id=email.id).first()
        assert found.email == "new@example.com"

    def test_update_label(self, db_session, sample_person):
        """Test updating the email label."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="label@example.com",
            label=EmailLabel.work,
        )
        db_session.add(email)
        db_session.flush()

        # Update the label
        email.label = EmailLabel.personal
        db_session.flush()

        # Verify update
        found = db_session.query(PersonEmail).filter_by(id=email.id).first()
        assert found.label == EmailLabel.personal

    def test_update_primary_status(self, db_session, sample_person):
        """Test updating the primary status."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="primary@example.com",
            is_primary=False,
        )
        db_session.add(email)
        db_session.flush()

        # Update to primary
        email.is_primary = True
        db_session.flush()

        # Verify update
        found = db_session.query(PersonEmail).filter_by(id=email.id).first()
        assert found.is_primary is True


class TestPersonEmailDelete:
    """Test PersonEmail delete operations."""

    def test_delete_person_email(self, db_session, sample_person):
        """Test deleting a person email."""
        email = PersonEmail(
            person_id=sample_person.id,
            email="delete@example.com",
        )
        db_session.add(email)
        db_session.flush()
        email_id = email.id

        # Delete the email
        db_session.delete(email)
        db_session.flush()

        # Verify deletion
        found = db_session.query(PersonEmail).filter_by(id=email_id).first()
        assert found is None

    def test_cascade_delete_on_person_delete(self, db_session):
        """Test that emails are deleted when the person is deleted."""
        from app.models import Person, PersonStatus

        # Create a new person (not using fixture to control lifecycle)
        person = Person(
            full_name="Delete Test Person",
            status=PersonStatus.active,
        )
        db_session.add(person)
        db_session.flush()
        person_id = person.id

        # Add emails
        email1 = PersonEmail(person_id=person_id, email="cascade1@example.com")
        email2 = PersonEmail(person_id=person_id, email="cascade2@example.com")
        db_session.add_all([email1, email2])
        db_session.flush()

        # Delete the person
        db_session.delete(person)
        db_session.flush()

        # Verify emails are deleted too
        remaining = (
            db_session.query(PersonEmail)
            .filter_by(person_id=person_id)
            .all()
        )
        assert len(remaining) == 0


class TestEmailLabelEnum:
    """Test EmailLabel enum values."""

    def test_all_label_values(self, db_session, sample_person):
        """Test that all enum values can be used."""
        for label in EmailLabel:
            email = PersonEmail(
                person_id=sample_person.id,
                email=f"{label.value}@example.com",
                label=label,
            )
            db_session.add(email)
            db_session.flush()

            found = db_session.query(PersonEmail).filter_by(email=f"{label.value}@example.com").first()
            assert found.label == label

    def test_label_string_representation(self):
        """Test enum string values."""
        assert EmailLabel.work.value == "work"
        assert EmailLabel.personal.value == "personal"
        assert EmailLabel.other.value == "other"
