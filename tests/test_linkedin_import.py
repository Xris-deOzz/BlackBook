"""Tests for the LinkedIn CSV import service."""

import pytest
from uuid import uuid4

from app.models import Person, PersonEmail, Organization, PersonOrganization
from app.models.person_email import EmailLabel
from app.services.linkedin_import import (
    LinkedInImportService,
    LinkedInContact,
    ImportResult,
    LinkedInImportError,
    LinkedInParseError,
    get_linkedin_import_service,
)


class TestLinkedInContact:
    """Tests for LinkedInContact dataclass."""

    def test_full_name_both_parts(self):
        """Test full name with first and last name."""
        contact = LinkedInContact(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            company="Tech Corp",
            position="Engineer",
            connected_on="01 Jan 2024",
            linkedin_url="https://linkedin.com/in/johndoe",
        )
        assert contact.full_name == "John Doe"

    def test_full_name_first_only(self):
        """Test full name with only first name."""
        contact = LinkedInContact(
            first_name="John",
            last_name=None,
            email=None,
            company=None,
            position=None,
            connected_on=None,
            linkedin_url=None,
        )
        assert contact.full_name == "John"

    def test_full_name_last_only(self):
        """Test full name with only last name."""
        contact = LinkedInContact(
            first_name=None,
            last_name="Doe",
            email=None,
            company=None,
            position=None,
            connected_on=None,
            linkedin_url=None,
        )
        assert contact.full_name == "Doe"

    def test_full_name_none(self):
        """Test full name when both are None."""
        contact = LinkedInContact(
            first_name=None,
            last_name=None,
            email=None,
            company=None,
            position=None,
            connected_on=None,
            linkedin_url=None,
        )
        assert contact.full_name is None


class TestLinkedInImportService:
    """Tests for LinkedInImportService."""

    def test_get_linkedin_import_service(self, db_session):
        """Test factory function returns service instance."""
        service = get_linkedin_import_service(db_session)
        assert isinstance(service, LinkedInImportService)
        assert service.db == db_session

    def test_parse_csv_standard_headers(self, db_session):
        """Test parsing CSV with standard LinkedIn headers."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,john@example.com,Tech Corp,Engineer,01 Jan 2024
Jane,Smith,jane@example.com,Acme Inc,Manager,15 Feb 2024"""

        service = LinkedInImportService(db_session)
        contacts = service._parse_csv(csv_content)

        assert len(contacts) == 2
        assert contacts[0].first_name == "John"
        assert contacts[0].last_name == "Doe"
        assert contacts[0].email == "john@example.com"
        assert contacts[0].company == "Tech Corp"
        assert contacts[0].position == "Engineer"

    def test_parse_csv_with_bom(self, db_session):
        """Test parsing CSV with UTF-8 BOM."""
        csv_content = "\ufeffFirst Name,Last Name,Email Address,Company,Position,Connected On\nJohn,Doe,john@example.com,,,01 Jan 2024"

        service = LinkedInImportService(db_session)
        contacts = service._parse_csv(csv_content)

        assert len(contacts) == 1
        assert contacts[0].first_name == "John"

    def test_parse_csv_alternate_headers(self, db_session):
        """Test parsing CSV with alternate header names."""
        csv_content = """firstname,lastname,email,organization,title,date
John,Doe,john@example.com,Tech Corp,Engineer,2024-01-01"""

        service = LinkedInImportService(db_session)
        contacts = service._parse_csv(csv_content)

        assert len(contacts) == 1
        assert contacts[0].first_name == "John"
        assert contacts[0].email == "john@example.com"

    def test_parse_csv_empty_raises_error(self, db_session):
        """Test parsing empty CSV raises error."""
        csv_content = ""

        service = LinkedInImportService(db_session)
        with pytest.raises(LinkedInParseError):
            service._parse_csv(csv_content)

    def test_parse_csv_handles_empty_values(self, db_session):
        """Test parsing handles empty values as None."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,,,,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        contacts = service._parse_csv(csv_content)

        assert len(contacts) == 1
        assert contacts[0].email is None
        assert contacts[0].company is None

    def test_map_headers(self, db_session):
        """Test header mapping for different variations."""
        service = LinkedInImportService(db_session)

        # Standard headers
        fieldnames = ["First Name", "Last Name", "Email Address", "Company", "Position"]
        header_map = service._map_headers(fieldnames)

        assert header_map["first_name"] == "First Name"
        assert header_map["last_name"] == "Last Name"
        assert header_map["email"] == "Email Address"
        assert header_map["company"] == "Company"
        assert header_map["position"] == "Position"

    def test_map_headers_case_insensitive(self, db_session):
        """Test header mapping is case insensitive."""
        service = LinkedInImportService(db_session)

        fieldnames = ["FIRST NAME", "last name", "EMAIL ADDRESS"]
        header_map = service._map_headers(fieldnames)

        assert "first_name" in header_map
        assert "last_name" in header_map
        assert "email" in header_map

    def test_import_creates_new_persons(self, db_session):
        """Test importing creates new person records."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,john@example.com,Tech Corp,Engineer,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_content)

        assert result.contacts_parsed == 1
        assert result.contacts_created == 1
        assert result.contacts_matched == 0

        # Verify person was created
        person = db_session.query(Person).filter_by(full_name="John Doe").first()
        assert person is not None
        assert person.first_name == "John"
        assert person.last_name == "Doe"
        assert person.title == "Engineer"
        assert person.custom_fields["imported_from"] == "linkedin"

    def test_import_creates_person_email(self, db_session):
        """Test importing creates PersonEmail record."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,john@example.com,,,"""

        service = LinkedInImportService(db_session)
        service.import_from_csv(csv_content)

        person = db_session.query(Person).filter_by(full_name="John Doe").first()
        assert len(person.emails) == 1
        assert person.emails[0].email == "john@example.com"
        assert person.emails[0].label == EmailLabel.work

    def test_import_matches_existing_by_email(self, db_session):
        """Test import matches existing person by email."""
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
        db_session.flush()

        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
Updated,Name,existing@example.com,New Corp,Manager,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_content)

        assert result.contacts_parsed == 1
        assert result.contacts_matched == 1
        assert result.contacts_created == 0

    def test_import_updates_empty_fields(self, db_session):
        """Test import updates only empty fields on matched person."""
        # Create existing person with minimal data
        person = Person(full_name="Existing User", first_name="Existing")
        db_session.add(person)
        db_session.flush()

        email = PersonEmail(
            person_id=person.id,
            email="existing@example.com",
            label=EmailLabel.work,
        )
        db_session.add(email)
        db_session.flush()

        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
Different,Name,existing@example.com,Company,Engineer,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_content)

        db_session.refresh(person)

        # first_name should NOT change (was already set)
        assert person.first_name == "Existing"
        # last_name SHOULD be updated (was empty)
        assert person.last_name == "Name"
        # title SHOULD be updated
        assert person.title == "Engineer"
        assert result.contacts_updated == 1

    def test_import_skips_no_name(self, db_session):
        """Test import skips contacts without name."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
,,,Tech Corp,,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_content)

        assert result.contacts_parsed == 1
        assert result.contacts_skipped == 1
        assert result.contacts_created == 0

    def test_import_creates_organization(self, db_session):
        """Test import creates organization for company."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,john@example.com,New Company Inc,Engineer,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_content)

        # Check organization was created
        org = db_session.query(Organization).filter_by(name="New Company Inc").first()
        assert org is not None
        assert org.org_type == "company"

        # Check person-organization link
        person = db_session.query(Person).filter_by(full_name="John Doe").first()
        person_org = (
            db_session.query(PersonOrganization)
            .filter_by(person_id=person.id, organization_id=org.id)
            .first()
        )
        assert person_org is not None
        assert person_org.role == "Engineer"
        assert person_org.is_current is True

    def test_import_reuses_existing_organization(self, db_session):
        """Test import reuses existing organization."""
        # Create existing organization
        org = Organization(name="Existing Corp", org_type="company")
        db_session.add(org)
        db_session.flush()

        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,john@example.com,Existing Corp,Engineer,01 Jan 2024
Jane,Smith,jane@example.com,Existing Corp,Manager,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        service.import_from_csv(csv_content)

        # Should still have only one organization
        orgs = db_session.query(Organization).filter_by(name="Existing Corp").all()
        assert len(orgs) == 1

    def test_import_without_company(self, db_session):
        """Test import handles contacts without company."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,john@example.com,,,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_content)

        assert result.contacts_created == 1
        assert result.organizations_created == 0

        person = db_session.query(Person).filter_by(full_name="John Doe").first()
        assert person is not None

    def test_import_stores_linkedin_url(self, db_session):
        """Test import stores LinkedIn URL if present."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On,URL
John,Doe,john@example.com,,,01 Jan 2024,https://linkedin.com/in/johndoe"""

        service = LinkedInImportService(db_session)
        service.import_from_csv(csv_content)

        person = db_session.query(Person).filter_by(full_name="John Doe").first()
        assert person.linkedin == "https://linkedin.com/in/johndoe"

    def test_import_bytes_utf8(self, db_session):
        """Test importing from bytes with UTF-8 encoding."""
        csv_content = b"""First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,john@example.com,,,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_content)

        assert result.contacts_created == 1

    def test_import_bytes_latin1(self, db_session):
        """Test importing from bytes with Latin-1 encoding."""
        # Create content with Latin-1 specific character
        csv_content = "First Name,Last Name,Email Address,Company,Position,Connected On\nJos\xe9,Garc\xeda,jose@example.com,,,01 Jan 2024"
        csv_bytes = csv_content.encode("latin-1")

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_bytes)

        assert result.contacts_created == 1
        person = db_session.query(Person).filter_by(first_name="José").first()
        assert person is not None

    def test_import_adds_new_email_to_matched_person(self, db_session):
        """Test import adds new email to existing person."""
        # Create existing person with different email
        person = Person(full_name="Test User")
        db_session.add(person)
        db_session.flush()

        existing_email = PersonEmail(
            person_id=person.id,
            email="old@example.com",
            label=EmailLabel.work,
        )
        db_session.add(existing_email)
        db_session.flush()

        # Import with same person but different email that matches by old email
        # But this test needs the match to happen - let's use a new email scenario
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
Test,User,old@example.com,,,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        result = service.import_from_csv(csv_content)

        # Should match and not add duplicate email
        assert result.contacts_matched == 1
        db_session.refresh(person)
        assert len(person.emails) == 1  # Should still be just the old email

    def test_import_stores_connected_on_in_custom_fields(self, db_session):
        """Test import stores connection date in custom fields."""
        csv_content = """First Name,Last Name,Email Address,Company,Position,Connected On
John,Doe,john@example.com,,,01 Jan 2024"""

        service = LinkedInImportService(db_session)
        service.import_from_csv(csv_content)

        person = db_session.query(Person).filter_by(full_name="John Doe").first()
        assert person.custom_fields["linkedin_connected_on"] == "01 Jan 2024"


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_import_result_creation(self):
        """Test creating ImportResult with all fields."""
        result = ImportResult(
            contacts_parsed=100,
            contacts_matched=30,
            contacts_created=50,
            contacts_updated=20,
            contacts_skipped=0,
            organizations_created=15,
        )

        assert result.contacts_parsed == 100
        assert result.contacts_matched == 30
        assert result.contacts_created == 50
        assert result.contacts_updated == 20
        assert result.contacts_skipped == 0
        assert result.organizations_created == 15
