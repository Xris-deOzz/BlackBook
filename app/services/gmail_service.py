"""
Gmail service for searching and retrieving email data.

Handles Gmail API interactions for email history lookup.
"""

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.models import GoogleAccount, Person, PersonEmail, EmailIgnoreList
from app.services.google_auth import GMAIL_SCOPES


class GmailServiceError(Exception):
    """Base exception for Gmail service errors."""

    pass


class GmailAuthError(GmailServiceError):
    """Raised when Gmail authentication fails."""

    pass


class GmailAPIError(GmailServiceError):
    """Raised when Gmail API calls fail."""

    pass


class EmailThread:
    """Represents an email thread from Gmail."""

    def __init__(
        self,
        thread_id: str,
        account_id: UUID,
        account_email: str,
        subject: str = "",
        snippet: str = "",
        participants: list[str] | None = None,
        last_message_date: datetime | None = None,
        message_count: int = 0,
    ):
        self.thread_id = thread_id
        self.account_id = account_id
        self.account_email = account_email
        self.subject = subject
        self.snippet = snippet
        self.participants = participants or []
        self.last_message_date = last_message_date
        self.message_count = message_count

    @property
    def gmail_link(self) -> str:
        """Generate Gmail web link for this thread."""
        return f"https://mail.google.com/mail/u/0/#all/{self.thread_id}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "thread_id": self.thread_id,
            "account_id": str(self.account_id),
            "account_email": self.account_email,
            "subject": self.subject,
            "snippet": self.snippet,
            "participants": self.participants,
            "last_message_date": self.last_message_date.isoformat() if self.last_message_date else None,
            "message_count": self.message_count,
            "gmail_link": self.gmail_link,
        }


class GmailService:
    """
    Service for interacting with Gmail API.

    Handles searching emails, retrieving threads, and filtering results.
    """

    def __init__(self, db: Session):
        """Initialize the Gmail service.

        Args:
            db: Database session for querying accounts and ignore patterns
        """
        self.db = db
        self._ignore_patterns: list[tuple[str, str]] | None = None

    def build_search_query(self, person: Person) -> str:
        """
        Build Gmail search query from person's email addresses only.

        Only searches for direct correspondence (from/to the person's email addresses)
        to avoid matching notification emails that merely mention the person's name.

        Args:
            person: Person to search emails for

        Returns:
            Gmail search query string

        Example:
            For person with emails [work@example.com, personal@gmail.com],
            generates:
            "from:work@example.com OR to:work@example.com OR from:personal@gmail.com OR to:personal@gmail.com"
        """
        queries = []

        # Add email address queries - only from/to for direct correspondence
        for person_email in person.emails:
            email = person_email.email
            queries.append(f"from:{email}")
            queries.append(f"to:{email}")

        # Also check legacy email field if no person_emails exist
        if not person.emails and person.email:
            # Split by common delimiters
            for email in re.split(r'[,;\s]+', person.email):
                email = email.strip()
                if email and '@' in email:
                    queries.append(f"from:{email}")
                    queries.append(f"to:{email}")

        # NOTE: Intentionally NOT searching by name to avoid matching
        # notification emails (LinkedIn, newsletters, etc.) that mention
        # the person but aren't direct correspondence

        return " OR ".join(queries)

    def search_emails_for_person(
        self,
        person_id: UUID,
        max_results: int = 50,
    ) -> list[EmailThread]:
        """
        Search all connected Google accounts for emails related to a person.

        Args:
            person_id: UUID of the person to search for
            max_results: Maximum number of threads to return per account

        Returns:
            List of EmailThread objects sorted by date (newest first)

        Raises:
            GmailServiceError: If the person doesn't exist
        """
        person = self.db.query(Person).filter_by(id=person_id).first()
        if not person:
            raise GmailServiceError(f"Person not found: {person_id}")

        # Build search query
        query = self.build_search_query(person)
        if not query:
            return []

        # Get all active Google accounts
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
        if not accounts:
            return []

        all_threads: list[EmailThread] = []

        # Search each account
        for account in accounts:
            try:
                threads = self._search_account(account, query, max_results)
                all_threads.extend(threads)
            except GmailAuthError:
                # Skip accounts with auth issues
                continue
            except GmailAPIError:
                # Skip accounts with API issues
                continue

        # Filter out ignored emails
        filtered_threads = self._filter_ignored_threads(all_threads)

        # Sort by date (newest first)
        filtered_threads.sort(
            key=lambda t: t.last_message_date or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        return filtered_threads

    def get_thread_details(
        self,
        thread_id: str,
        account_id: UUID,
    ) -> EmailThread | None:
        """
        Get detailed information about a specific email thread.

        Args:
            thread_id: Gmail thread ID
            account_id: UUID of the Google account

        Returns:
            EmailThread with full details, or None if not found
        """
        account = self.db.query(GoogleAccount).filter_by(id=account_id).first()
        if not account:
            return None

        try:
            credentials = self._get_credentials(account)
            service = build("gmail", "v1", credentials=credentials)

            thread = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "To", "Date"],
            ).execute()

            return self._parse_thread(thread, account)

        except HttpError as e:
            raise GmailAPIError(f"Failed to get thread details: {e}")

    def _search_account(
        self,
        account: GoogleAccount,
        query: str,
        max_results: int,
    ) -> list[EmailThread]:
        """Search a single Google account for matching threads."""
        try:
            credentials = self._get_credentials(account)
            service = build("gmail", "v1", credentials=credentials)

            # Search for threads
            response = service.users().threads().list(
                userId="me",
                q=query,
                maxResults=max_results,
            ).execute()

            threads_data = response.get("threads", [])
            if not threads_data:
                return []

            # Get details for each thread
            threads = []
            for thread_data in threads_data:
                thread_id = thread_data["id"]
                try:
                    thread_detail = service.users().threads().get(
                        userId="me",
                        id=thread_id,
                        format="metadata",
                        metadataHeaders=["Subject", "From", "To", "Date"],
                    ).execute()
                    parsed = self._parse_thread(thread_detail, account)
                    if parsed:
                        threads.append(parsed)
                except HttpError:
                    # Skip individual thread errors
                    continue

            return threads

        except HttpError as e:
            raise GmailAPIError(f"Gmail API error: {e}")

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
                scopes=creds_dict.get("scopes", GMAIL_SCOPES),
            )
        except Exception as e:
            raise GmailAuthError(f"Failed to get credentials: {e}")

    def _parse_thread(self, thread_data: dict, account: GoogleAccount) -> EmailThread | None:
        """Parse Gmail API thread response into EmailThread object."""
        messages = thread_data.get("messages", [])
        if not messages:
            return None

        # Get subject from first message
        subject = ""
        participants = set()
        last_date = None

        for msg in messages:
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

            # Get subject from first message
            if not subject and "Subject" in headers:
                subject = headers["Subject"]

            # Collect participants
            for header in ["From", "To"]:
                if header in headers:
                    # Extract email addresses from header
                    emails = self._extract_emails(headers[header])
                    participants.update(emails)

            # Get date from last message
            if "Date" in headers:
                try:
                    last_date = self._parse_email_date(headers["Date"])
                except ValueError:
                    pass

        return EmailThread(
            thread_id=thread_data["id"],
            account_id=account.id,
            account_email=account.email,
            subject=subject,
            snippet=thread_data.get("snippet", ""),
            participants=list(participants),
            last_message_date=last_date,
            message_count=len(messages),
        )

    def _extract_emails(self, header_value: str) -> list[str]:
        """Extract email addresses from a header value."""
        # Match email addresses in various formats:
        # "Name <email@example.com>" or just "email@example.com"
        pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        return re.findall(pattern, header_value.lower())

    def _parse_email_date(self, date_str: str) -> datetime:
        """Parse email date header to datetime."""
        # Common email date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
        ]

        # Clean up timezone abbreviations
        date_str = re.sub(r'\s+\([A-Z]+\)$', '', date_str)

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        raise ValueError(f"Unable to parse date: {date_str}")

    def _get_ignore_patterns(self) -> list[tuple[str, str]]:
        """Get cached ignore patterns from database."""
        if self._ignore_patterns is None:
            patterns = self.db.query(EmailIgnoreList).all()
            self._ignore_patterns = [(p.pattern, p.pattern_type.value) for p in patterns]
        return self._ignore_patterns

    def _filter_ignored_threads(self, threads: list[EmailThread]) -> list[EmailThread]:
        """Filter out threads matching ignore patterns."""
        patterns = self._get_ignore_patterns()
        if not patterns:
            return threads

        filtered = []
        for thread in threads:
            if not self._should_ignore_thread(thread, patterns):
                filtered.append(thread)

        return filtered

    def _should_ignore_thread(
        self,
        thread: EmailThread,
        patterns: list[tuple[str, str]],
    ) -> bool:
        """Check if a thread should be ignored based on participants."""
        for participant in thread.participants:
            participant_lower = participant.lower()

            for pattern, pattern_type in patterns:
                if pattern_type == "domain":
                    # Domain match: check if email ends with @domain
                    if participant_lower.endswith(f"@{pattern.lower()}"):
                        return True
                elif pattern_type == "email":
                    # Email pattern match (supports wildcards with *)
                    if self._matches_email_pattern(participant_lower, pattern.lower()):
                        return True

        return False

    def _matches_email_pattern(self, email: str, pattern: str) -> bool:
        """Check if email matches pattern (supports * wildcards)."""
        if "*" not in pattern:
            return email == pattern

        # Convert pattern to regex
        # e.g., "noreply@*" becomes "noreply@.*"
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
        return bool(re.match(f"^{regex_pattern}$", email))


def get_gmail_service(db: Session) -> GmailService:
    """Get a Gmail service instance.

    Args:
        db: Database session

    Returns:
        GmailService instance
    """
    return GmailService(db)
