"""
LinkedIn CSV import service for importing contacts from LinkedIn export.

Handles parsing LinkedIn's Connections.csv export and creating persons.
"""

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import Person, PersonEmail, Organization, PersonOrganization
from app.models.person_email import EmailLabel


class LinkedInImportError(Exception):
    """Base exception for LinkedIn import errors."""
    pass


class LinkedInParseError(LinkedInImportError):
    """Raised when CSV parsing fails."""
    pass


@dataclass
class LinkedInContact:
    """Represents a contact from LinkedIn CSV export."""
    first_name: str | None
    last_name: str | None
    email: str | None
    company: str | None
    position: str | None
    connected_on: str | None
    linkedin_url: str | None

    @property
    def full_name(self) -> str | None:
        """Construct full name from first and last name."""
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) if parts else None


@dataclass
class ImportResult:
    """Result of a LinkedIn import operation."""
    contacts_parsed: int
    contacts_matched: int
    contacts_created: int
    contacts_updated: int
    contacts_skipped: int
    organizations_created: int


class LinkedInImportService:
    """
    Service for importing LinkedIn connections into BlackBook.

    Handles parsing LinkedIn's Connections.csv export format and creating
    or updating person records.
    """

    # Expected CSV headers from LinkedIn export
    EXPECTED_HEADERS = [
        "First Name",
        "Last Name",
        "Email Address",
        "Company",
        "Position",
        "Connected On",
    ]

    def __init__(self, db: Session):
        """Initialize the LinkedIn import service.

        Args:
            db: Database session for querying and creating records
        """
        self.db = db
        self._email_to_person_cache: dict[str, UUID] | None = None
        self._company_to_org_cache: dict[str, UUID] | None = None
        self._name_to_person_cache: dict[str, UUID] | None = None

    def import_from_csv(self, csv_content: str | bytes) -> ImportResult:
        """
        Import contacts from LinkedIn CSV content.

        Args:
            csv_content: CSV file content as string or bytes

        Returns:
            ImportResult with import statistics

        Raises:
            LinkedInParseError: If CSV parsing fails
        """
        # Convert bytes to string if needed
        if isinstance(csv_content, bytes):
            # Try UTF-8 first, then fall back to latin-1
            try:
                csv_content = csv_content.decode("utf-8")
            except UnicodeDecodeError:
                csv_content = csv_content.decode("latin-1")

        # Parse contacts from CSV
        contacts = self._parse_csv(csv_content)

        # Build caches
        self._build_email_cache()
        self._build_company_cache()
        self._build_name_cache()

        logger.info(f"LinkedIn Import: Parsed {len(contacts)} contacts, Name cache has {len(self._name_to_person_cache or {})} entries")

        result = ImportResult(
            contacts_parsed=len(contacts),
            contacts_matched=0,
            contacts_created=0,
            contacts_updated=0,
            contacts_skipped=0,
            organizations_created=0,
        )

        for contact in contacts:
            # Skip contacts without a name
            if not contact.full_name:
                result.contacts_skipped += 1
                continue

            # Try to match by email or name
            person = self._match_contact_to_person(contact)
            logger.debug(f"Contact '{contact.full_name}': matched={person is not None}")

            if person:
                # Update existing person
                updated = self._update_person_from_contact(person, contact)
                if updated:
                    result.contacts_updated += 1
                result.contacts_matched += 1
            else:
                # Create new person
                org_created = self._create_person_from_contact(contact)
                result.contacts_created += 1
                if org_created:
                    result.organizations_created += 1

        self.db.commit()
        return result

    def import_from_file(self, file_path: str) -> ImportResult:
        """
        Import contacts from a LinkedIn CSV file.

        Args:
            file_path: Path to the CSV file

        Returns:
            ImportResult with import statistics
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return self.import_from_csv(f.read())

    def _parse_csv(self, csv_content: str) -> list[LinkedInContact]:
        """Parse LinkedIn CSV content into contact objects."""
        contacts = []

        # Handle potential BOM and normalize line endings
        csv_content = csv_content.lstrip("\ufeff")

        # LinkedIn exports often have a "Notes:" section at the top before the actual CSV
        # We need to skip to the actual header row which contains "First Name"
        lines = csv_content.split('\n')
        header_index = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('First Name') or 'First Name,' in line:
                header_index = i
                break

        # Reconstruct CSV from header onwards
        if header_index > 0:
            logger.info(f"Skipping {header_index} note lines at start of LinkedIn CSV")
            csv_content = '\n'.join(lines[header_index:])

        reader = csv.DictReader(io.StringIO(csv_content))

        # Validate headers
        if reader.fieldnames is None:
            raise LinkedInParseError("CSV file is empty or has no headers")

        logger.info(f"LinkedIn CSV headers found: {reader.fieldnames}")

        # LinkedIn sometimes uses different header variations
        header_map = self._map_headers(reader.fieldnames)
        logger.info(f"Header mapping: {header_map}")

        for row in reader:
            try:
                contact = LinkedInContact(
                    first_name=self._get_field(row, header_map, "first_name"),
                    last_name=self._get_field(row, header_map, "last_name"),
                    email=self._get_field(row, header_map, "email"),
                    company=self._get_field(row, header_map, "company"),
                    position=self._get_field(row, header_map, "position"),
                    connected_on=self._get_field(row, header_map, "connected_on"),
                    linkedin_url=self._get_field(row, header_map, "url"),
                )
                contacts.append(contact)
            except Exception as e:
                # Skip malformed rows
                continue

        return contacts

    def _map_headers(self, fieldnames: list[str]) -> dict[str, str]:
        """Map CSV headers to our internal field names."""
        header_map = {}

        # Normalize headers for comparison
        normalized = {h.lower().strip(): h for h in fieldnames}

        # Map common header variations
        mappings = {
            "first_name": ["first name", "firstname", "first"],
            "last_name": ["last name", "lastname", "last"],
            "email": ["email address", "email", "e-mail"],
            "company": ["company", "organization", "employer"],
            "position": ["position", "title", "job title"],
            "connected_on": ["connected on", "connection date", "date"],
            "url": ["url", "profile url", "linkedin url"],
        }

        for field, variations in mappings.items():
            for variation in variations:
                if variation in normalized:
                    header_map[field] = normalized[variation]
                    break

        return header_map

    def _get_field(
        self,
        row: dict[str, str],
        header_map: dict[str, str],
        field: str,
    ) -> str | None:
        """Get a field value from a row using the header map."""
        header = header_map.get(field)
        if header and header in row:
            value = row[header].strip()
            return value if value else None
        return None

    def _build_email_cache(self) -> None:
        """Build cache mapping emails to person IDs."""
        self._email_to_person_cache = {}

        # Get all PersonEmail records
        person_emails = self.db.query(PersonEmail).all()
        for pe in person_emails:
            self._email_to_person_cache[pe.email.lower()] = pe.person_id

        # Also check legacy email field
        persons = self.db.query(Person).filter(Person.email.isnot(None)).all()
        for p in persons:
            if p.email:
                for email in p.email.split(","):
                    email = email.strip().lower()
                    if email and email not in self._email_to_person_cache:
                        self._email_to_person_cache[email] = p.id

    def _build_company_cache(self) -> None:
        """Build cache mapping company names to organization IDs."""
        self._company_to_org_cache = {}

        organizations = self.db.query(Organization).all()
        for org in organizations:
            self._company_to_org_cache[org.name.lower()] = org.id

    def _build_name_cache(self) -> None:
        """Build cache mapping normalized full names to person IDs."""
        self._name_to_person_cache = {}

        persons = self.db.query(Person).all()
        for p in persons:
            if p.full_name:
                # Normalize: lowercase, strip whitespace
                name_key = self._normalize_name(p.full_name)
                # Only store if not already present (first match wins)
                if name_key and name_key not in self._name_to_person_cache:
                    self._name_to_person_cache[name_key] = p.id

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for matching: lowercase, strip extra whitespace."""
        if not name:
            return ""
        # Lowercase and collapse multiple spaces
        return " ".join(name.lower().split())

    def _match_contact_to_person(self, contact: LinkedInContact) -> Person | None:
        """Try to find an existing person by matching email or name."""
        if self._email_to_person_cache is None:
            self._build_email_cache()

        # First try email matching (most reliable)
        if contact.email:
            email_lower = contact.email.lower()
            if email_lower in self._email_to_person_cache:
                person_id = self._email_to_person_cache[email_lower]
                return self.db.query(Person).filter_by(id=person_id).first()

        # Fall back to name matching
        if self._name_to_person_cache is None:
            self._build_name_cache()

        if contact.full_name:
            name_key = self._normalize_name(contact.full_name)
            if name_key and name_key in self._name_to_person_cache:
                person_id = self._name_to_person_cache[name_key]
                return self.db.query(Person).filter_by(id=person_id).first()

        return None

    def _create_person_from_contact(self, contact: LinkedInContact) -> bool:
        """
        Create a new Person record from a LinkedIn contact.

        Returns:
            True if a new organization was created
        """
        person = Person(
            full_name=contact.full_name or "Unknown",
            first_name=contact.first_name,
            last_name=contact.last_name,
            title=contact.position,
            linkedin=contact.linkedin_url,
            custom_fields={
                "imported_from": "linkedin",
                "linkedin_connected_on": contact.connected_on,
            },
        )

        self.db.add(person)
        self.db.flush()  # Get person.id

        # Add email if present
        if contact.email:
            person_email = PersonEmail(
                person_id=person.id,
                email=contact.email,
                label=EmailLabel.work,  # LinkedIn emails are typically work
                is_primary=True,
            )
            self.db.add(person_email)

            # Update cache
            if self._email_to_person_cache is not None:
                self._email_to_person_cache[contact.email.lower()] = person.id

        # Link to organization if company is provided
        org_created = False
        if contact.company:
            org = self._get_or_create_organization(contact.company)
            if org:
                # Check if this is a newly created org
                if org.id not in [o.id for o in self.db.query(Organization).all() if o.id != org.id]:
                    org_created = True

                # Create person-organization link
                person_org = PersonOrganization(
                    person_id=person.id,
                    organization_id=org.id,
                    role=contact.position,
                    is_current=True,
                )
                self.db.add(person_org)

        return org_created

    def _update_person_from_contact(
        self,
        person: Person,
        contact: LinkedInContact,
    ) -> bool:
        """
        Update existing person with LinkedIn contact data.

        Only fills in empty fields - does not overwrite existing data.

        Returns:
            True if any field was updated
        """
        updated = False

        # Update empty fields only
        if not person.first_name and contact.first_name:
            person.first_name = contact.first_name
            updated = True

        if not person.last_name and contact.last_name:
            person.last_name = contact.last_name
            updated = True

        if not person.title and contact.position:
            person.title = contact.position
            updated = True

        if not person.linkedin and contact.linkedin_url:
            person.linkedin = contact.linkedin_url
            updated = True

        # Store import source in custom_fields
        if person.custom_fields is None:
            person.custom_fields = {}
        if "imported_from" not in person.custom_fields:
            person.custom_fields["imported_from"] = "linkedin"
            updated = True
        if contact.connected_on and "linkedin_connected_on" not in person.custom_fields:
            person.custom_fields["linkedin_connected_on"] = contact.connected_on
            updated = True

        # Add email if not already present
        if contact.email:
            existing_emails = {pe.email.lower() for pe in person.emails}
            if contact.email.lower() not in existing_emails:
                person_email = PersonEmail(
                    person_id=person.id,
                    email=contact.email,
                    label=EmailLabel.work,
                    is_primary=False,
                )
                self.db.add(person_email)

                # Update cache
                if self._email_to_person_cache is not None:
                    self._email_to_person_cache[contact.email.lower()] = person.id

                updated = True

        return updated

    def _get_or_create_organization(self, company_name: str) -> Organization | None:
        """Get existing organization or create new one."""
        if not company_name:
            return None

        if self._company_to_org_cache is None:
            self._build_company_cache()

        company_lower = company_name.lower()

        # Check cache
        if company_lower in self._company_to_org_cache:
            org_id = self._company_to_org_cache[company_lower]
            return self.db.query(Organization).filter_by(id=org_id).first()

        # Create new organization
        org = Organization(
            name=company_name,
            org_type="company",
        )
        self.db.add(org)
        self.db.flush()

        # Update cache
        self._company_to_org_cache[company_lower] = org.id

        return org


def get_linkedin_import_service(db: Session) -> LinkedInImportService:
    """Get a LinkedIn import service instance.

    Args:
        db: Database session

    Returns:
        LinkedInImportService instance
    """
    return LinkedInImportService(db)
