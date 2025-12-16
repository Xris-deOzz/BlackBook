"""
Tests for person merge service and router endpoints.

Tests the merge functionality for combining duplicate persons.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    Person,
    PersonEmail,
    PersonOrganization,
    Interaction,
    InteractionMedium,
    InteractionSource,
    Tag,
    Organization,
    OrgType,
    PendingContact,
    PendingContactStatus,
)
from app.models.tag import PersonTag
from app.models.organization import RelationshipType
from app.models.person_email import EmailLabel
from app.services.person_merge import (
    merge_persons,
    find_potential_duplicates,
    PersonNotFoundError,
    SamePersonError,
)


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
def source_person(db_session):
    """Create source person (will be merged into target)."""
    person = Person(
        first_name="John",
        last_name="Duplicate",
        full_name="John Duplicate",
        email="john.dup@example.com",
        notes="Source person notes",
    )
    db_session.add(person)
    db_session.flush()
    return person


@pytest.fixture
def target_person(db_session):
    """Create target person (will keep)."""
    person = Person(
        first_name="John",
        last_name="Original",
        full_name="John Original",
        email="john.orig@example.com",
        notes="Target person notes",
    )
    db_session.add(person)
    db_session.flush()
    return person


@pytest.fixture
def source_with_data(db_session, source_person):
    """Add emails, interactions, tags, and org links to source person."""
    # Add emails
    email1 = PersonEmail(
        person_id=source_person.id,
        email="john.work@example.com",
        label=EmailLabel.work,
        is_primary=True,
    )
    email2 = PersonEmail(
        person_id=source_person.id,
        email="john.personal@gmail.com",
        label=EmailLabel.personal,
    )
    db_session.add_all([email1, email2])

    # Add interactions
    interaction1 = Interaction(
        person_id=source_person.id,
        medium=InteractionMedium.email,
        interaction_date=datetime.now(timezone.utc).date(),
        notes="Source interaction 1",
        source=InteractionSource.manual,
    )
    interaction2 = Interaction(
        person_id=source_person.id,
        medium=InteractionMedium.meeting,
        interaction_date=datetime.now(timezone.utc).date(),
        notes="Source interaction 2",
        source=InteractionSource.calendar,
    )
    db_session.add_all([interaction1, interaction2])

    # Add tags
    tag = Tag(name="Test Tag", color="#ff0000")
    db_session.add(tag)
    db_session.flush()
    person_tag = PersonTag(person_id=source_person.id, tag_id=tag.id)
    db_session.add(person_tag)

    # Add organization
    org = Organization(name="Test Org", org_type=OrgType.company)
    db_session.add(org)
    db_session.flush()
    person_org = PersonOrganization(
        person_id=source_person.id,
        organization_id=org.id,
        relationship=RelationshipType.affiliated_with,
        role="Developer",
    )
    db_session.add(person_org)

    db_session.flush()
    return source_person


class TestMergePersonsService:
    """Tests for merge_persons service function."""

    def test_merge_transfers_emails(self, db_session, source_with_data, target_person):
        """Test that emails are transferred to target."""
        source_email_count = db_session.query(PersonEmail).filter_by(
            person_id=source_with_data.id
        ).count()
        assert source_email_count == 2

        stats = merge_persons(db_session, source_with_data.id, target_person.id)

        assert stats["emails_transferred"] == 2

        # Verify emails now belong to target
        target_emails = db_session.query(PersonEmail).filter_by(
            person_id=target_person.id
        ).all()
        assert len(target_emails) == 2

    def test_merge_avoids_duplicate_emails(self, db_session, source_person, target_person):
        """Test that duplicate emails are not transferred."""
        # Add same email to both
        source_email = PersonEmail(
            person_id=source_person.id,
            email="shared@example.com",
            label=EmailLabel.work,
        )
        target_email = PersonEmail(
            person_id=target_person.id,
            email="shared@example.com",
            label=EmailLabel.work,
        )
        db_session.add_all([source_email, target_email])
        db_session.flush()

        stats = merge_persons(db_session, source_person.id, target_person.id)

        assert stats["emails_transferred"] == 0

        # Only one email should exist
        all_emails = db_session.query(PersonEmail).filter_by(
            email="shared@example.com"
        ).all()
        assert len(all_emails) == 1

    def test_merge_transfers_interactions(self, db_session, source_with_data, target_person):
        """Test that interactions are transferred to target."""
        stats = merge_persons(db_session, source_with_data.id, target_person.id)

        assert stats["interactions_transferred"] == 2

        # Verify interactions now belong to target
        target_interactions = db_session.query(Interaction).filter_by(
            person_id=target_person.id
        ).all()
        assert len(target_interactions) == 2

    def test_merge_transfers_tags(self, db_session, source_with_data, target_person):
        """Test that tags are transferred to target."""
        stats = merge_persons(db_session, source_with_data.id, target_person.id)

        assert stats["tags_transferred"] == 1

        # Verify tags now belong to target
        target_tags = db_session.query(PersonTag).filter_by(
            person_id=target_person.id
        ).all()
        assert len(target_tags) == 1

    def test_merge_avoids_duplicate_tags(self, db_session, source_person, target_person):
        """Test that duplicate tags are not transferred."""
        # Add same tag to both
        tag = Tag(name="Shared Tag", color="#00ff00")
        db_session.add(tag)
        db_session.flush()

        source_tag = PersonTag(person_id=source_person.id, tag_id=tag.id)
        target_tag = PersonTag(person_id=target_person.id, tag_id=tag.id)
        db_session.add_all([source_tag, target_tag])
        db_session.flush()

        stats = merge_persons(db_session, source_person.id, target_person.id)

        assert stats["tags_transferred"] == 0

        # Only one tag association should exist
        target_tags = db_session.query(PersonTag).filter_by(
            person_id=target_person.id
        ).all()
        assert len(target_tags) == 1

    def test_merge_transfers_organizations(self, db_session, source_with_data, target_person):
        """Test that organization relationships are transferred."""
        stats = merge_persons(db_session, source_with_data.id, target_person.id)

        assert stats["organizations_transferred"] == 1

        # Verify org now linked to target
        target_orgs = db_session.query(PersonOrganization).filter_by(
            person_id=target_person.id
        ).all()
        assert len(target_orgs) == 1
        assert target_orgs[0].role == "Developer"

    def test_merge_deletes_source_person(self, db_session, source_person, target_person):
        """Test that source person is deleted after merge."""
        source_id = source_person.id

        merge_persons(db_session, source_id, target_person.id)
        db_session.flush()

        # Source should no longer exist
        deleted = db_session.query(Person).filter_by(id=source_id).first()
        assert deleted is None

    def test_merge_appends_notes(self, db_session, source_person, target_person):
        """Test that notes are appended from source to target."""
        source_person.notes = "Important source notes"
        target_person.notes = "Existing target notes"
        db_session.flush()

        merge_persons(db_session, source_person.id, target_person.id)

        db_session.refresh(target_person)
        assert "Important source notes" in target_person.notes
        assert "Existing target notes" in target_person.notes

    def test_merge_sets_notes_when_target_empty(self, db_session, source_person, target_person):
        """Test that source notes are set when target has no notes."""
        source_person.notes = "Important source notes"
        target_person.notes = None
        db_session.flush()

        merge_persons(db_session, source_person.id, target_person.id)

        db_session.refresh(target_person)
        assert target_person.notes == "Important source notes"

    def test_merge_same_person_raises_error(self, db_session, source_person):
        """Test that merging person with themselves raises error."""
        with pytest.raises(SamePersonError):
            merge_persons(db_session, source_person.id, source_person.id)

    def test_merge_source_not_found_raises_error(self, db_session, target_person):
        """Test that missing source raises error."""
        fake_id = uuid4()
        with pytest.raises(PersonNotFoundError):
            merge_persons(db_session, fake_id, target_person.id)

    def test_merge_target_not_found_raises_error(self, db_session, source_person):
        """Test that missing target raises error."""
        fake_id = uuid4()
        with pytest.raises(PersonNotFoundError):
            merge_persons(db_session, source_person.id, fake_id)

    def test_merge_updates_pending_contacts(self, db_session, source_person, target_person):
        """Test that pending contacts referencing source are updated."""
        # Create pending contact that was converted to source person
        pending = PendingContact(
            email="pending@example.com",
            name="Pending User",
            status=PendingContactStatus.created,
            created_person_id=source_person.id,
        )
        db_session.add(pending)
        db_session.flush()

        stats = merge_persons(db_session, source_person.id, target_person.id)

        assert stats["pending_contacts_updated"] == 1

        # Verify pending contact now references target
        db_session.refresh(pending)
        assert pending.created_person_id == target_person.id


class TestFindPotentialDuplicates:
    """Tests for find_potential_duplicates function."""

    def test_finds_by_same_email(self, db_session, source_person, target_person):
        """Test finding duplicates by matching email."""
        # Give both persons the same email
        email1 = PersonEmail(
            person_id=source_person.id,
            email="shared@company.com",
            label=EmailLabel.work,
        )
        email2 = PersonEmail(
            person_id=target_person.id,
            email="shared@company.com",
            label=EmailLabel.work,
        )
        db_session.add_all([email1, email2])
        db_session.flush()

        duplicates = find_potential_duplicates(db_session, source_person.id)

        assert len(duplicates) >= 1
        person_ids = [d["person"].id for d in duplicates]
        assert target_person.id in person_ids
        # Should have high confidence
        match = next(d for d in duplicates if d["person"].id == target_person.id)
        assert match["confidence"] == "high"

    def test_finds_by_same_last_name(self, db_session, source_person, target_person):
        """Test finding duplicates by same last name."""
        target_person.last_name = source_person.last_name
        db_session.flush()

        duplicates = find_potential_duplicates(db_session, source_person.id)

        person_ids = [d["person"].id for d in duplicates]
        assert target_person.id in person_ids
        match = next(d for d in duplicates if d["person"].id == target_person.id)
        assert match["confidence"] == "medium"

    def test_finds_by_same_domain(self, db_session, source_person, target_person):
        """Test finding duplicates by same email domain."""
        email1 = PersonEmail(
            person_id=source_person.id,
            email="john@acmecorp.com",
            label=EmailLabel.work,
        )
        email2 = PersonEmail(
            person_id=target_person.id,
            email="jane@acmecorp.com",
            label=EmailLabel.work,
        )
        db_session.add_all([email1, email2])
        db_session.flush()

        duplicates = find_potential_duplicates(db_session, source_person.id)

        person_ids = [d["person"].id for d in duplicates]
        assert target_person.id in person_ids
        match = next(d for d in duplicates if d["person"].id == target_person.id)
        assert match["confidence"] == "low"

    def test_excludes_common_domains(self, db_session, source_person, target_person):
        """Test that common domains like gmail.com are excluded."""
        email1 = PersonEmail(
            person_id=source_person.id,
            email="john@gmail.com",
            label=EmailLabel.personal,
        )
        email2 = PersonEmail(
            person_id=target_person.id,
            email="jane@gmail.com",
            label=EmailLabel.personal,
        )
        # Make last names different so they don't match that way
        source_person.last_name = "Smith"
        target_person.last_name = "Jones"
        db_session.add_all([email1, email2])
        db_session.flush()

        duplicates = find_potential_duplicates(db_session, source_person.id)

        person_ids = [d["person"].id for d in duplicates]
        assert target_person.id not in person_ids

    def test_respects_limit(self, db_session, source_person):
        """Test that limit parameter is respected."""
        # Create many potential duplicates
        for i in range(15):
            p = Person(
                first_name=f"John{i}",
                last_name=source_person.last_name,  # Same last name
                full_name=f"John{i} {source_person.last_name}",
            )
            db_session.add(p)
        db_session.flush()

        duplicates = find_potential_duplicates(db_session, source_person.id, limit=5)

        assert len(duplicates) <= 5


class TestMergeRouterEndpoints:
    """Tests for merge router endpoints."""

    def test_get_merge_page(self, test_client, db_session, source_person):
        """Test getting merge page."""
        response = test_client.get(f"/people/{source_person.id}/merge")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]
        assert source_person.full_name in response.text

    def test_get_merge_page_not_found(self, test_client):
        """Test 404 for non-existent person."""
        fake_id = uuid4()
        response = test_client.get(f"/people/{fake_id}/merge")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_search_for_merge(self, test_client, db_session, source_person, target_person):
        """Test search endpoint for merge."""
        response = test_client.get(
            f"/people/{source_person.id}/merge/search?q=Original"
        )

        assert response.status_code == status.HTTP_200_OK
        assert target_person.full_name in response.text

    def test_search_excludes_self(self, test_client, db_session, source_person):
        """Test that search excludes the source person."""
        response = test_client.get(
            f"/people/{source_person.id}/merge/search?q=Duplicate"
        )

        assert response.status_code == status.HTTP_200_OK
        # Source person should not appear in results
        assert "No matching persons found" in response.text or source_person.full_name not in response.text

    def test_perform_merge_success(self, test_client, db_session, source_person, target_person):
        """Test successful merge via API."""
        response = test_client.post(
            f"/people/{source_person.id}/merge/{target_person.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "redirect_url" in data
        assert str(target_person.id) in data["redirect_url"]

    def test_perform_merge_same_person(self, test_client, db_session, source_person):
        """Test merge same person returns error."""
        response = test_client.post(
            f"/people/{source_person.id}/merge/{source_person.id}"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_perform_merge_source_not_found(self, test_client, db_session, target_person):
        """Test merge with non-existent source."""
        fake_id = uuid4()
        response = test_client.post(
            f"/people/{fake_id}/merge/{target_person.id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_perform_merge_target_not_found(self, test_client, db_session, source_person):
        """Test merge with non-existent target."""
        fake_id = uuid4()
        response = test_client.post(
            f"/people/{source_person.id}/merge/{fake_id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_duplicates_widget(self, test_client, db_session, source_person, target_person):
        """Test duplicates widget endpoint."""
        # Make them share a last name
        target_person.last_name = source_person.last_name
        db_session.flush()

        response = test_client.get(f"/people/{source_person.id}/duplicates")

        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]

    def test_get_duplicates_widget_empty(self, test_client, db_session, source_person):
        """Test duplicates widget when no duplicates found."""
        response = test_client.get(f"/people/{source_person.id}/duplicates")

        assert response.status_code == status.HTTP_200_OK
        assert "No potential duplicates" in response.text
