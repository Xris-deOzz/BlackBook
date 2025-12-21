"""
Google Contacts service for syncing contacts from Google People API.

Handles fetching contacts, matching to existing persons, and creating new persons.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.models import GoogleAccount, Person, PersonEmail, Tag
from app.models.person_email import EmailLabel
from app.models.tag import PersonTag
from app.models.tag_subcategory import (
    get_subcategory_for_label,
    get_color_for_subcategory,
    GOOGLE_LABEL_TO_SUBCATEGORY,
)
from app.services.google_auth import CONTACTS_SCOPES


class ContactsServiceError(Exception):
    """Base exception for Contacts service errors."""
    pass


class ContactsAuthError(ContactsServiceError):
    """Raised when Contacts authentication fails."""
    pass


class ContactsAPIError(ContactsServiceError):
    """Raised when Contacts API calls fail."""
    pass


@dataclass
class GoogleContact:
    """Represents a contact from Google People API."""
    resource_name: str  # e.g., "people/c12345"
    display_name: str | None
    given_name: str | None
    family_name: str | None
    emails: list[dict[str, Any]]  # [{"value": "...", "type": "work", "primary": True}]
    phones: list[dict[str, Any]]  # [{"value": "...", "type": "mobile"}]
    photo_url: str | None
    organization_title: str | None
    organization_name: str | None
    # New fields for enhanced import
    birthday: date | None = None
    notes: str | None = None  # From biographies
    addresses: list[dict[str, Any]] = field(default_factory=list)  # Home/Work addresses
    labels: list[str] = field(default_factory=list)  # Contact group names (Labels)
    # Additional fields for sync tracking and URLs
    etag: str | None = None  # Google etag for change detection
    urls: list[dict[str, Any]] = field(default_factory=list)  # Website URLs
    nickname: str | None = None  # Nickname

    @property
    def google_contact_id(self) -> str:
        """Extract the contact ID from resource_name."""
        # resource_name is like "people/c12345678901234567"
        return self.resource_name.replace("people/", "")

    @property
    def primary_email(self) -> str | None:
        """Get the primary email address."""
        for email in self.emails:
            if email.get("metadata", {}).get("primary"):
                return email.get("value")
        # Fall back to first email
        return self.emails[0].get("value") if self.emails else None

    @property
    def formatted_address(self) -> str | None:
        """Get first formatted address or construct from components."""
        if not self.addresses:
            return None
        addr = self.addresses[0]
        # Try formatted address first
        if addr.get("formattedValue"):
            return addr.get("formattedValue")
        # Otherwise construct from components
        parts = []
        if addr.get("streetAddress"):
            parts.append(addr["streetAddress"])
        if addr.get("city"):
            parts.append(addr["city"])
        if addr.get("region"):
            parts.append(addr["region"])
        if addr.get("postalCode"):
            parts.append(addr["postalCode"])
        if addr.get("country"):
            parts.append(addr["country"])
        return ", ".join(parts) if parts else None


@dataclass
class SyncResult:
    """Result of a contact sync operation."""
    contacts_fetched: int
    contacts_matched: int
    contacts_created: int
    contacts_updated: int
    contacts_skipped: int
    # Additional detail for full sync
    saved_contacts_fetched: int = 0  # From connections().list() - explicitly saved
    other_contacts_fetched: int = 0  # From otherContacts().list() - people emailed


class ContactsService:
    """
    Service for syncing Google Contacts into BlackBook.

    Handles fetching contacts from Google People API, matching them to existing
    persons by email, and creating/updating person records.
    """

    def __init__(self, db: Session):
        """Initialize the Contacts service.

        Args:
            db: Database session for querying and creating records
        """
        self.db = db
        self._email_to_person_cache: dict[str, UUID] | None = None
        self._contact_groups_cache: dict[str, str] | None = None  # resourceName -> displayName

    def _fetch_contact_groups(self, service: Any) -> dict[str, str]:
        """
        Fetch all contact groups and build a mapping of resourceName to display name.

        Args:
            service: Google People API service instance

        Returns:
            Dict mapping contact group resourceName to display name
        """
        groups_map: dict[str, str] = {}
        try:
            page_token = None
            while True:
                results = service.contactGroups().list(
                    pageSize=200,
                    pageToken=page_token,
                ).execute()

                for group in results.get("contactGroups", []):
                    resource_name = group.get("resourceName", "")
                    name = group.get("name", "")
                    # Skip system groups - they have groupType == "SYSTEM_CONTACT_GROUP"
                    group_type = group.get("groupType", "")
                    if group_type != "SYSTEM_CONTACT_GROUP" and name:
                        groups_map[resource_name] = name

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

        except HttpError:
            # If fetching groups fails, continue without labels
            pass

        return groups_map

    def fetch_contacts(
        self, 
        account: GoogleAccount,
        include_other_contacts: bool = True,
    ) -> tuple[list[GoogleContact], int, int]:
        """
        Fetch all contacts from a Google account.
        
        Fetches both:
        1. Saved contacts (connections) - contacts explicitly added to "My Contacts"
        2. Other contacts - people you've interacted with but not explicitly saved

        Args:
            account: GoogleAccount to fetch contacts from
            include_other_contacts: Whether to also fetch "Other contacts" (default True)

        Returns:
            Tuple of (contacts_list, saved_count, other_count)

        Raises:
            ContactsAuthError: If authentication fails
            ContactsAPIError: If API call fails
        """
        try:
            credentials = self._get_credentials(account)
            service = build("people", "v1", credentials=credentials)

            # First, fetch contact groups to map IDs to names
            self._contact_groups_cache = self._fetch_contact_groups(service)

            contacts: list[GoogleContact] = []
            saved_count = 0
            other_count = 0

            # ========================================
            # 1. Fetch SAVED contacts (My Contacts)
            # ========================================
            page_token = None
            while True:
                results = service.people().connections().list(
                    resourceName="people/me",
                    pageSize=1000,
                    personFields="names,nicknames,emailAddresses,phoneNumbers,photos,organizations,metadata,birthdays,biographies,addresses,memberships,urls",
                    pageToken=page_token,
                ).execute()

                connections = results.get("connections", [])
                for person_data in connections:
                    contact = self._parse_contact(person_data)
                    if contact:
                        contacts.append(contact)
                        saved_count += 1

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            # ========================================
            # 2. Fetch OTHER contacts (people emailed)
            # ========================================
            if include_other_contacts:
                page_token = None
                seen_emails: set[str] = set()
                
                # Build set of emails already in saved contacts to avoid duplicates
                for contact in contacts:
                    for email_data in contact.emails:
                        email = email_data.get("value", "").lower()
                        if email:
                            seen_emails.add(email)
                
                while True:
                    try:
                        # Note: otherContacts has limited fields available
                        results = service.otherContacts().list(
                            pageSize=1000,
                            readMask="names,emailAddresses,phoneNumbers,photos,metadata",
                            pageToken=page_token,
                        ).execute()

                        other_contacts_data = results.get("otherContacts", [])
                        for person_data in other_contacts_data:
                            contact = self._parse_contact(person_data, is_other_contact=True)
                            if contact:
                                # Skip if we already have this email from saved contacts
                                primary_email = contact.primary_email
                                if primary_email and primary_email.lower() in seen_emails:
                                    continue
                                
                                # Add email to seen set
                                if primary_email:
                                    seen_emails.add(primary_email.lower())
                                
                                contacts.append(contact)
                                other_count += 1

                        page_token = results.get("nextPageToken")
                        if not page_token:
                            break
                    except HttpError as e:
                        # If otherContacts fails (missing scope), continue without it
                        if "403" in str(e) or "insufficient" in str(e).lower():
                            break
                        raise

            return contacts, saved_count, other_count

        except HttpError as e:
            raise ContactsAPIError(f"Google Contacts API error: {e}")
        except Exception as e:
            raise ContactsAuthError(f"Failed to fetch contacts: {e}")

    def sync_contacts(
        self, 
        account_id: UUID,
        include_other_contacts: bool = True,
    ) -> SyncResult:
        """
        Sync contacts from a Google account into BlackBook.
        
        Syncs both saved contacts AND "Other contacts" (people you've emailed).

        For each contact:
        1. Try to match by email to existing person
        2. If matched: update person with Google data (only empty fields - MERGE behavior)
        3. If not matched: create new person

        Args:
            account_id: UUID of the Google account to sync
            include_other_contacts: Whether to include "Other contacts" (default True)

        Returns:
            SyncResult with sync statistics

        Raises:
            ContactsServiceError: If account not found
        """
        account = self.db.query(GoogleAccount).filter_by(id=account_id).first()
        if not account:
            raise ContactsServiceError(f"Account not found: {account_id}")

        # Build email lookup cache
        self._build_email_cache()

        # Fetch contacts from Google (both saved and other contacts)
        contacts, saved_count, other_count = self.fetch_contacts(
            account, 
            include_other_contacts=include_other_contacts
        )

        result = SyncResult(
            contacts_fetched=len(contacts),
            contacts_matched=0,
            contacts_created=0,
            contacts_updated=0,
            contacts_skipped=0,
            saved_contacts_fetched=saved_count,
            other_contacts_fetched=other_count,
        )

        for contact in contacts:
            # Skip contacts without a name
            if not contact.display_name:
                result.contacts_skipped += 1
                continue

            # Try to match by email
            person = self._match_contact_to_person(contact)

            if person:
                # Update existing person (MERGE: fill blanks only, never overwrite)
                updated = self._update_person_from_contact(person, contact)
                if updated:
                    result.contacts_updated += 1
                result.contacts_matched += 1
            else:
                # Create new person
                self._create_person_from_contact(contact, account.id)
                result.contacts_created += 1

        # Update last sync timestamp
        account.last_sync_at = datetime.now(timezone.utc)
        self.db.commit()

        return result

    def sync_all_accounts(self) -> dict[str, SyncResult]:
        """
        Sync contacts from all active Google accounts.

        Returns:
            Dict mapping account email to SyncResult
        """
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
        results = {}

        for account in accounts:
            try:
                result = self.sync_contacts(account.id)
                results[account.email] = result
            except (ContactsAuthError, ContactsAPIError) as e:
                # Log error but continue with other accounts
                results[account.email] = SyncResult(
                    contacts_fetched=0,
                    contacts_matched=0,
                    contacts_created=0,
                    contacts_updated=0,
                    contacts_skipped=0,
                )

        return results

    def _get_credentials(self, account: GoogleAccount) -> Credentials:
        """Get OAuth credentials for a Google account."""
        try:
            creds_dict = account.get_credentials()
            return Credentials(
                token=creds_dict.get("token"),
                refresh_token=creds_dict.get("refresh_token"),
                token_uri=creds_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=creds_dict.get("client_id"),
                client_secret=creds_dict.get("client_secret"),
                scopes=creds_dict.get("scopes", CONTACTS_SCOPES),
            )
        except Exception as e:
            raise ContactsAuthError(f"Failed to get credentials: {e}")

    def _parse_contact(
        self, 
        person_data: dict[str, Any],
        is_other_contact: bool = False,
    ) -> GoogleContact | None:
        """Parse Google People API response into GoogleContact.
        
        Args:
            person_data: Raw data from Google People API
            is_other_contact: True if this is from otherContacts (limited fields)
        """
        resource_name = person_data.get("resourceName")
        if not resource_name:
            return None

        # Get name
        names = person_data.get("names", [])
        name_data = names[0] if names else {}
        display_name = name_data.get("displayName")
        given_name = name_data.get("givenName")
        family_name = name_data.get("familyName")

        # Get emails
        emails = person_data.get("emailAddresses", [])

        # Get phones
        phones = person_data.get("phoneNumbers", [])

        # Get photo
        photos = person_data.get("photos", [])
        photo_url = None
        for photo in photos:
            # Skip default photos
            if not photo.get("metadata", {}).get("default"):
                photo_url = photo.get("url")
                break

        # Get organization
        organizations = person_data.get("organizations", [])
        org_data = organizations[0] if organizations else {}
        org_title = org_data.get("title")
        org_name = org_data.get("name")

        # Get birthday
        birthday = None
        birthdays = person_data.get("birthdays", [])
        if birthdays:
            birthday_data = birthdays[0].get("date", {})
            year = birthday_data.get("year")
            month = birthday_data.get("month")
            day = birthday_data.get("day")
            if month and day:
                # Use 1900 as placeholder year if not provided
                birthday = date(year or 1900, month, day)

        # Get notes from biographies
        notes = None
        biographies = person_data.get("biographies", [])
        if biographies:
            notes = biographies[0].get("value")

        # Get addresses
        addresses = person_data.get("addresses", [])

        # Get labels from memberships (contact groups)
        labels: list[str] = []
        memberships = person_data.get("memberships", [])
        for membership in memberships:
            contact_group = membership.get("contactGroupMembership", {})
            group_resource = contact_group.get("contactGroupResourceName", "")
            # Look up the group display name in our cache
            if group_resource and self._contact_groups_cache:
                group_display_name = self._contact_groups_cache.get(group_resource)
                if group_display_name:
                    labels.append(group_display_name)

        # Get etag for change detection
        etag = None
        metadata = person_data.get("metadata", {})
        sources = metadata.get("sources", [])
        if sources:
            etag = sources[0].get("etag")

        # Get URLs (websites, social profiles)
        urls = person_data.get("urls", [])

        # Get nickname
        nickname = None
        nicknames = person_data.get("nicknames", [])
        if nicknames:
            nickname = nicknames[0].get("value")

        return GoogleContact(
            resource_name=resource_name,
            display_name=display_name,
            given_name=given_name,
            family_name=family_name,
            emails=emails,
            phones=phones,
            photo_url=photo_url,
            organization_title=org_title,
            organization_name=org_name,
            birthday=birthday,
            notes=notes,
            addresses=addresses,
            labels=labels,
            etag=etag,
            urls=urls,
            nickname=nickname,
        )

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

    def _parse_urls(self, urls: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Parse Google Contact URLs into categorized fields.
        
        Returns dict with keys: linkedin, twitter, website, other_urls
        """
        result = {
            "linkedin": None,
            "twitter": None, 
            "website": None,
            "other_urls": []
        }
        
        for url_data in urls:
            url = url_data.get("value", "")
            url_lower = url.lower()
            url_type = url_data.get("type", "").lower()
            
            if "linkedin.com" in url_lower:
                result["linkedin"] = url
            elif "twitter.com" in url_lower or "x.com" in url_lower:
                result["twitter"] = url
            elif url_type in ("homepage", "home", "work", "blog") and not result["website"]:
                result["website"] = url
            else:
                result["other_urls"].append({
                    "url": url,
                    "label": url_data.get("type", "other")
                })
        
        return result

    def _match_contact_to_person(self, contact: GoogleContact) -> Person | None:
        """
        Try to find an existing person using 3-tier matching:
        1. Match by google_resource_name (exact Google ID) 
        2. Match by email address
        3. (Future) Match by phone + similar name
        """
        # Tier 1: Match by google_resource_name (most reliable)
        if contact.resource_name:
            person = self.db.query(Person).filter(
                Person.google_resource_name == contact.resource_name
            ).first()
            if person:
                return person

        # Tier 2: Match by email
        if self._email_to_person_cache is None:
            self._build_email_cache()

        for email_data in contact.emails:
            email = email_data.get("value", "").lower()
            if email and email in self._email_to_person_cache:
                person_id = self._email_to_person_cache[email]
                return self.db.query(Person).filter_by(id=person_id).first()

        # Tier 3: TODO - Match by phone + similar name (future enhancement)

        return None

    def _create_person_from_contact(
        self,
        contact: GoogleContact,
        account_id: UUID,
    ) -> Person:
        """Create a new Person record from a Google Contact."""
        # Build custom_fields with addresses if available
        custom_fields: dict[str, Any] = {
            "google_contact_id": contact.google_contact_id,
            "google_account_id": str(account_id),
            "imported_from": "google_contacts",
        }

        # Store all addresses in custom_fields
        if contact.addresses:
            custom_fields["addresses"] = contact.addresses

        person = Person(
            full_name=contact.display_name or "Unknown",
            first_name=contact.given_name,
            last_name=contact.family_name,
            title=contact.organization_title,
            profile_picture=contact.photo_url,
            birthday=contact.birthday,
            notes=contact.notes,
            location=contact.formatted_address,  # Primary address to location
            custom_fields=custom_fields,
            # Google Contacts sync tracking
            google_resource_name=contact.resource_name,
            google_etag=contact.etag,
            google_synced_at=datetime.now(timezone.utc),
            # New fields from Google
            nickname=contact.nickname,
        )

        # Set phone from first phone number
        if contact.phones:
            person.phone = contact.phones[0].get("value")

        # Parse URLs into linkedin, twitter, website fields
        if contact.urls:
            parsed_urls = self._parse_urls(contact.urls)
            if parsed_urls["linkedin"]:
                person.linkedin = parsed_urls["linkedin"]
            if parsed_urls["twitter"]:
                person.twitter = parsed_urls["twitter"]
            if parsed_urls["website"]:
                person.website = parsed_urls["website"]
            # Store other URLs in custom_fields
            if parsed_urls["other_urls"]:
                person.custom_fields["other_urls"] = parsed_urls["other_urls"]

        self.db.add(person)
        self.db.flush()  # Get person.id

        # Add emails (deduplicate by email address)
        # First, collect unique emails using a dict keyed by lowercase email
        unique_emails: dict[str, dict] = {}
        for email_data in contact.emails:
            email_value = email_data.get("value")
            if not email_value:
                continue
            email_lower = email_value.lower()
            # Only keep the first occurrence of each email
            if email_lower not in unique_emails:
                unique_emails[email_lower] = email_data

        # Then add unique emails to the database one by one
        for email_lower, email_data in unique_emails.items():
            email_value = email_data.get("value")
            email_type = email_data.get("type", "").lower()
            label = self._map_email_type(email_type)
            is_primary = email_data.get("metadata", {}).get("primary", False)

            person_email = PersonEmail(
                person_id=person.id,
                email=email_value,
                label=label,
                is_primary=is_primary,
            )
            self.db.add(person_email)
            self.db.flush()  # Flush each email immediately to catch duplicates early

            # Update cache
            if self._email_to_person_cache is not None:
                self._email_to_person_cache[email_lower] = person.id

        # Assign Google labels as tags
        if contact.labels:
            self._assign_tags_to_person(person, contact.labels)

        return person

    def _update_person_from_contact(
        self,
        person: Person,
        contact: GoogleContact,
    ) -> bool:
        """
        Update existing person with Google Contact data.

        Only fills in empty fields - does not overwrite existing data.

        Returns:
            True if any field was updated
        """
        updated = False

        # Update empty fields only
        if not person.first_name and contact.given_name:
            person.first_name = contact.given_name
            updated = True

        if not person.last_name and contact.family_name:
            person.last_name = contact.family_name
            updated = True

        if not person.phone and contact.phones:
            person.phone = contact.phones[0].get("value")
            updated = True

        if not person.profile_picture and contact.photo_url:
            person.profile_picture = contact.photo_url
            updated = True

        if not person.title and contact.organization_title:
            person.title = contact.organization_title
            updated = True

        # Update birthday if not set
        if not person.birthday and contact.birthday:
            person.birthday = contact.birthday
            updated = True

        # Update notes if not set
        if not person.notes and contact.notes:
            person.notes = contact.notes
            updated = True

        # Update location if not set
        if not person.location and contact.formatted_address:
            person.location = contact.formatted_address
            updated = True

        # Update nickname if not set
        if not person.nickname and contact.nickname:
            person.nickname = contact.nickname
            updated = True

        # Update URL fields if not set
        if contact.urls:
            parsed_urls = self._parse_urls(contact.urls)
            if not person.linkedin and parsed_urls["linkedin"]:
                person.linkedin = parsed_urls["linkedin"]
                updated = True
            if not person.twitter and parsed_urls["twitter"]:
                person.twitter = parsed_urls["twitter"]
                updated = True
            if not person.website and parsed_urls["website"]:
                person.website = parsed_urls["website"]
                updated = True

        # Always update Google sync tracking fields
        if contact.resource_name and person.google_resource_name != contact.resource_name:
            person.google_resource_name = contact.resource_name
            updated = True
        if contact.etag:
            person.google_etag = contact.etag
        person.google_synced_at = datetime.now(timezone.utc)

        # Store Google Contact ID and addresses in custom_fields
        if person.custom_fields is None:
            person.custom_fields = {}
        if "google_contact_id" not in person.custom_fields:
            person.custom_fields["google_contact_id"] = contact.google_contact_id
            updated = True

        # Store addresses in custom_fields if not already there
        if "addresses" not in person.custom_fields and contact.addresses:
            person.custom_fields["addresses"] = contact.addresses
            updated = True

        # Add any new email addresses
        existing_emails = {pe.email.lower() for pe in person.emails}
        for email_data in contact.emails:
            email = email_data.get("value")
            if email and email.lower() not in existing_emails:
                email_type = email_data.get("type", "").lower()
                label = self._map_email_type(email_type)

                person_email = PersonEmail(
                    person_id=person.id,
                    email=email,
                    label=label,
                    is_primary=False,
                )
                self.db.add(person_email)
                existing_emails.add(email.lower())

                # Update cache
                if self._email_to_person_cache is not None:
                    self._email_to_person_cache[email.lower()] = person.id

                updated = True

        # Assign Google labels as tags (for existing persons too)
        if contact.labels:
            tags_assigned = self._assign_tags_to_person(person, contact.labels)
            if tags_assigned:
                updated = True

        return updated

    def _map_email_type(self, email_type: str) -> EmailLabel:
        """Map Google email type to PersonEmail label."""
        type_lower = email_type.lower()
        if "work" in type_lower:
            return EmailLabel.work
        elif "home" in type_lower or "personal" in type_lower:
            return EmailLabel.personal
        else:
            return EmailLabel.other

    def _get_or_create_tag(self, tag_name: str) -> Tag:
        """Get existing tag or create a new one.

        Args:
            tag_name: Name of the tag (from Google contact label)

        Returns:
            Tag object (existing or newly created)
            
        Note:
            When creating new tags, this method auto-assigns subcategories
            based on the GOOGLE_LABEL_TO_SUBCATEGORY mapping in tag_subcategory.py.
            See docs/TAG_SUBCATEGORY_MAPPING_2024.12.21.1.md for the full mapping.
        """
        # Normalize tag name (strip whitespace)
        normalized_name = tag_name.strip()
        if not normalized_name:
            normalized_name = "Google Contact"

        # Try to find existing tag (case-insensitive)
        tag = self.db.query(Tag).filter(
            Tag.name.ilike(normalized_name)
        ).first()

        if not tag:
            # Look up subcategory from mapping
            subcategory = get_subcategory_for_label(normalized_name)
            
            # Get color based on subcategory (or default Google blue if no mapping)
            if subcategory:
                color = get_color_for_subcategory(subcategory)
            else:
                color = "#4285F4"  # Google blue for unmapped labels
            
            # Create new tag with subcategory and color
            tag = Tag(
                name=normalized_name,
                color=color,
                subcategory=subcategory,  # Will be None if not in mapping
            )
            self.db.add(tag)
            self.db.flush()  # Flush to get tag.id

        return tag

    def _assign_tags_to_person(self, person: Person, labels: list[str]) -> bool:
        """Assign Google labels as tags to a person.

        Args:
            person: Person to assign tags to
            labels: List of Google contact label names

        Returns:
            True if any tags were assigned
        """
        if not labels:
            return False

        # Deduplicate labels (case-insensitive)
        seen_labels: set[str] = set()
        unique_labels: list[str] = []
        for label in labels:
            label_lower = label.lower().strip()
            if label_lower and label_lower not in seen_labels:
                seen_labels.add(label_lower)
                unique_labels.append(label)

        assigned_any = False
        
        # Query existing tag IDs directly from DB (relationship may not be loaded)
        from app.models.tag import PersonTag as PT
        existing_person_tags = self.db.query(PT.tag_id).filter(PT.person_id == person.id).all()
        existing_tag_ids = {pt.tag_id for pt in existing_person_tags}
        
        # Track tag IDs we've added in THIS call (handles duplicate labels resolving to same tag)
        added_tag_ids: set = set()

        for label_name in unique_labels:
            tag = self._get_or_create_tag(label_name)
            # Skip if already exists OR already added in this batch
            if tag.id in existing_tag_ids or tag.id in added_tag_ids:
                continue
            # Create PersonTag link - use merge to handle duplicates
            try:
                person_tag = PersonTag(
                    person_id=person.id,
                    tag_id=tag.id,
                )
                self.db.add(person_tag)
                self.db.flush()  # Flush each tag individually to catch duplicates early
                added_tag_ids.add(tag.id)
                assigned_any = True
            except Exception:
                # Duplicate - rollback this specific insert and continue
                self.db.rollback()
                added_tag_ids.add(tag.id)

        return assigned_any


    def push_to_google(self, person_id: UUID, account_id: UUID) -> dict[str, Any]:
        """Push a BlackBook person to Google Contacts."""
        from app.models import PersonEmail

        person = self.db.query(Person).filter_by(id=person_id).first()
        if not person:
            raise ContactsServiceError(f"Person not found: {person_id}")

        if person.google_resource_name:
            raise ContactsServiceError("Person is already linked to Google Contacts")

        account = self.db.query(GoogleAccount).filter_by(id=account_id).first()
        if not account:
            raise ContactsServiceError(f"Google account not found: {account_id}")

        try:
            credentials = self._get_credentials(account)
            service = build("people", "v1", credentials=credentials)

            contact_body: dict[str, Any] = {
                "names": [{"givenName": person.first_name or "", "familyName": person.last_name or ""}]
            }

            emails = self.db.query(PersonEmail).filter_by(person_id=person_id).all()
            if emails:
                contact_body["emailAddresses"] = [
                    {"value": email.email, "type": email.label.value if email.label else "other"}
                    for email in emails
                ]

            if person.phone:
                contact_body["phoneNumbers"] = [{"value": person.phone, "type": "mobile"}]

            current_org = next((po for po in person.organizations if po.is_current), None)
            if person.title or current_org:
                contact_body["organizations"] = [{
                    "title": person.title or (current_org.role if current_org else "") or "",
                    "name": current_org.organization.name if current_org else "",
                }]

            if person.birthday:
                contact_body["birthdays"] = [{"date": {
                    "year": person.birthday.year if person.birthday.year != 1900 else None,
                    "month": person.birthday.month,
                    "day": person.birthday.day,
                }}]

            if person.location:
                contact_body["addresses"] = [{"formattedValue": person.location, "type": "home"}]

            if person.notes:
                contact_body["biographies"] = [{"value": person.notes, "contentType": "TEXT_PLAIN"}]

            result = service.people().createContact(
                body=contact_body,
                personFields="names,nicknames,emailAddresses,phoneNumbers,organizations,birthdays,addresses,biographies,metadata,urls"
            ).execute()

            person.google_resource_name = result.get("resourceName")
            person.google_etag = result.get("etag")
            person.google_synced_at = datetime.now(timezone.utc)
            self.db.commit()

            return {"success": True, "resource_name": person.google_resource_name,
                    "message": f"Successfully pushed {person.full_name} to Google Contacts"}

        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "invalid_grant" in error_msg:
                raise ContactsAuthError(f"Authentication failed: {e}")
            elif "403" in error_msg:
                raise ContactsAPIError(f"Permission denied: {e}")
            else:
                raise ContactsServiceError(f"Failed to push contact: {e}")

    def delete_contact_from_google(
        self,
        resource_name: str,
        account_id: UUID | None = None
    ) -> bool:
        """
        Delete a contact from Google Contacts.

        Args:
            resource_name: Google People API resource name (e.g., "people/c1234567890")
            account_id: Optional specific Google account to use. If not provided,
                       tries all active accounts.

        Returns:
            True if successfully deleted from Google

        Raises:
            ContactsAuthError: If authentication fails
            ContactsAPIError: If API call fails
            ContactsServiceError: If no valid account found or other error
        """
        if not resource_name:
            raise ContactsServiceError("No Google resource name provided")

        # Get account(s) to try
        if account_id:
            accounts = [self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()]
            if not accounts[0]:
                raise ContactsServiceError(f"Google account not found or inactive: {account_id}")
        else:
            accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
            if not accounts:
                raise ContactsServiceError("No active Google accounts configured")

        last_error = None
        for account in accounts:
            try:
                credentials = self._get_credentials(account)
                service = build("people", "v1", credentials=credentials)

                # Delete the contact
                # Google People API: DELETE https://people.googleapis.com/v1/{resourceName}:deleteContact
                service.people().deleteContact(resourceName=resource_name).execute()

                return True

            except HttpError as e:
                error_str = str(e)
                if "404" in error_str:
                    # Contact doesn't exist in Google - consider this a success
                    return True
                elif "403" in error_str or "401" in error_str:
                    # Permission denied or auth failed - try next account
                    last_error = e
                    continue
                else:
                    last_error = e
                    continue
            except Exception as e:
                last_error = e
                continue

        # All accounts failed
        if last_error:
            error_msg = str(last_error)
            if "401" in error_msg or "invalid_grant" in error_msg:
                raise ContactsAuthError(f"Authentication failed: {last_error}")
            elif "403" in error_msg:
                raise ContactsAPIError(f"Permission denied: {last_error}")
            else:
                raise ContactsAPIError(f"Failed to delete from Google: {last_error}")

        raise ContactsServiceError("Failed to delete contact from Google - no accounts succeeded")

    def delete_person_with_scope(
        self,
        person_id: UUID,
        scope: str = "both",
    ) -> dict[str, Any]:
        """
        Delete a person with the specified scope.

        Args:
            person_id: UUID of the person to delete
            scope: One of "blackbook_only", "google_only", or "both" (default)

        Returns:
            Dict with deletion results

        Raises:
            ContactsServiceError: If person not found or deletion fails
        """
        person = self.db.query(Person).filter_by(id=person_id).first()
        if not person:
            raise ContactsServiceError(f"Person not found: {person_id}")

        result = {
            "success": True,
            "person_id": str(person_id),
            "person_name": person.full_name,
            "blackbook_deleted": False,
            "google_deleted": False,
            "google_resource_name": person.google_resource_name,
            "error": None,
        }

        # Handle Google deletion first (so we can rollback if it fails)
        if scope in ("google_only", "both") and person.google_resource_name:
            try:
                self.delete_contact_from_google(person.google_resource_name)
                result["google_deleted"] = True

                # If only deleting from Google, clear the sync fields
                if scope == "google_only":
                    person.google_resource_name = None
                    person.google_etag = None
                    person.google_synced_at = None
                    self.db.commit()

            except (ContactsAuthError, ContactsAPIError, ContactsServiceError) as e:
                result["success"] = False
                result["error"] = str(e)
                # Don't proceed with BlackBook deletion if Google deletion failed
                if scope == "both":
                    return result

        # Handle BlackBook deletion
        if scope in ("blackbook_only", "both"):
            try:
                self.db.delete(person)
                self.db.commit()
                result["blackbook_deleted"] = True
            except Exception as e:
                self.db.rollback()
                result["success"] = False
                result["error"] = f"Failed to delete from BlackBook: {e}"

        return result

    def delete_persons_bulk_with_scope(
        self,
        person_ids: list[UUID],
        scope: str = "both",
    ) -> dict[str, Any]:
        """
        Delete multiple persons with the specified scope.

        Args:
            person_ids: List of person UUIDs to delete
            scope: One of "blackbook_only", "google_only", or "both" (default)

        Returns:
            Dict with bulk deletion results
        """
        results = []
        blackbook_deleted = 0
        google_deleted = 0
        failed = 0
        errors = []

        for person_id in person_ids:
            try:
                result = self.delete_person_with_scope(person_id, scope)
                results.append(result)

                if result["blackbook_deleted"]:
                    blackbook_deleted += 1
                if result["google_deleted"]:
                    google_deleted += 1
                if not result["success"]:
                    failed += 1
                    if result["error"]:
                        errors.append(f"{result['person_name']}: {result['error']}")

            except Exception as e:
                failed += 1
                errors.append(f"Person {person_id}: {e}")

        return {
            "success": failed == 0,
            "total_requested": len(person_ids),
            "blackbook_deleted": blackbook_deleted,
            "google_deleted": google_deleted,
            "failed": failed,
            "errors": errors,
            "results": results,
        }


def get_contacts_service(db: Session) -> ContactsService:
    """Get a Contacts service instance."""
    return ContactsService(db)
