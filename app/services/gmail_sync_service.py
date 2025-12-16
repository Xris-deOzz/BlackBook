"""
Gmail Sync Service for syncing emails to local database.

Handles full sync and incremental sync using Gmail History API.
"""

import re
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.models import (
    GoogleAccount,
    PersonEmail,
    EmailMessage,
    EmailPersonLink,
    EmailSyncState,
    SyncStatus,
    EmailLinkType,
    EmailLinkSource,
)
from app.services.google_auth import GMAIL_SCOPES


class GmailSyncError(Exception):
    """Base exception for Gmail sync errors."""
    pass


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    messages_synced: int
    errors: list[str]
    history_id: int | None = None


class GmailSyncService:
    """
    Service for syncing Gmail messages to local database.

    Supports:
    - Full sync: Initial sync of all messages (paginated)
    - Incremental sync: Using Gmail History API for changes since last sync
    - Auto-linking: Matches emails to CRM contacts by email address
    """

    def __init__(self, db: Session):
        self.db = db
        # Cache person emails for fast lookup during linking
        self._email_to_person: dict[str, UUID] | None = None

    def full_sync(
        self,
        account: GoogleAccount,
        max_results: int = 500,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """
        Perform full sync of messages from Gmail.

        Called on first sync or to rebuild local cache.
        Uses Gmail messages.list API with pagination.

        Args:
            account: Google account to sync
            max_results: Maximum number of messages to sync
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            SyncResult with sync statistics
        """
        errors = []
        messages_synced = 0
        history_id = None

        # Get or create sync state
        sync_state = self._get_or_create_sync_state(account)
        sync_state.start_sync()
        self.db.commit()

        try:
            credentials = self._get_credentials(account)
            service = build("gmail", "v1", credentials=credentials)

            # Get profile for history ID
            profile = service.users().getProfile(userId="me").execute()
            history_id = int(profile.get("historyId", 0))

            # List messages with pagination
            page_token = None
            total_fetched = 0

            while total_fetched < max_results:
                batch_size = min(100, max_results - total_fetched)  # Gmail API max is 100

                response = service.users().messages().list(
                    userId="me",
                    maxResults=batch_size,
                    pageToken=page_token,
                ).execute()

                messages_data = response.get("messages", [])
                if not messages_data:
                    break

                # Process each message
                for msg_ref in messages_data:
                    try:
                        # Get full message metadata
                        msg = service.users().messages().get(
                            userId="me",
                            id=msg_ref["id"],
                            format="metadata",
                            metadataHeaders=[
                                "Subject", "From", "To", "Cc", "Bcc", "Date"
                            ],
                        ).execute()

                        # Parse and save message
                        email_msg = self._parse_message(msg, account)
                        if email_msg:
                            self._save_message(email_msg)
                            messages_synced += 1

                    except HttpError as e:
                        errors.append(f"Error fetching message {msg_ref['id']}: {e}")
                        continue

                total_fetched += len(messages_data)

                # Progress callback
                if progress_callback:
                    progress_callback(total_fetched, max_results)

                # Get next page
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            # Commit all changes
            self.db.commit()

            # Update sync state
            sync_state.complete_sync(
                history_id=history_id,
                messages_synced=messages_synced,
                is_full_sync=True,
            )
            self.db.commit()

            return SyncResult(
                success=True,
                messages_synced=messages_synced,
                errors=errors,
                history_id=history_id,
            )

        except Exception as e:
            self.db.rollback()
            sync_state.fail_sync(str(e))
            self.db.commit()
            return SyncResult(
                success=False,
                messages_synced=messages_synced,
                errors=[str(e)] + errors,
            )

    def sync_folder(
        self,
        account: GoogleAccount,
        label_id: str,
        max_results: int = 200,
    ) -> SyncResult:
        """
        Sync emails from a specific Gmail label/folder.

        Args:
            account: Google account to sync
            label_id: Gmail label ID (e.g., "SPAM", "TRASH", "DRAFT", or custom label ID)
            max_results: Maximum number of messages to sync

        Returns:
            SyncResult with sync statistics
        """
        errors = []
        messages_synced = 0

        try:
            credentials = self._get_credentials(account)
            service = build("gmail", "v1", credentials=credentials)

            # List messages with label filter
            page_token = None
            total_fetched = 0

            while total_fetched < max_results:
                batch_size = min(100, max_results - total_fetched)

                response = service.users().messages().list(
                    userId="me",
                    labelIds=[label_id],
                    maxResults=batch_size,
                    pageToken=page_token,
                ).execute()

                messages_data = response.get("messages", [])
                if not messages_data:
                    break

                # Process each message
                for msg_ref in messages_data:
                    try:
                        # Get full message metadata
                        msg = service.users().messages().get(
                            userId="me",
                            id=msg_ref["id"],
                            format="metadata",
                            metadataHeaders=[
                                "Subject", "From", "To", "Cc", "Bcc", "Date"
                            ],
                        ).execute()

                        # Parse and save message
                        email_msg = self._parse_message(msg, account)
                        if email_msg:
                            self._save_message(email_msg)
                            messages_synced += 1

                    except HttpError as e:
                        errors.append(f"Error fetching message {msg_ref['id']}: {e}")
                        continue

                total_fetched += len(messages_data)

                # Get next page
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            # Commit all changes
            self.db.commit()

            return SyncResult(
                success=True,
                messages_synced=messages_synced,
                errors=errors,
            )

        except Exception as e:
            self.db.rollback()
            return SyncResult(
                success=False,
                messages_synced=messages_synced,
                errors=[str(e)] + errors,
            )

    def incremental_sync(self, account: GoogleAccount) -> SyncResult:
        """
        Perform incremental sync using Gmail History API.

        Only fetches changes since last sync (new messages, status changes).
        Much faster than full sync for regular updates.

        Args:
            account: Google account to sync

        Returns:
            SyncResult with sync statistics
        """
        errors = []
        messages_synced = 0

        sync_state = self._get_or_create_sync_state(account)

        # If no history ID, need full sync
        if sync_state.needs_full_sync:
            return self.full_sync(account)

        sync_state.start_sync()
        self.db.commit()

        try:
            credentials = self._get_credentials(account)
            service = build("gmail", "v1", credentials=credentials)

            # Get history since last sync
            history_id = sync_state.last_history_id
            new_history_id = history_id

            page_token = None
            while True:
                try:
                    response = service.users().history().list(
                        userId="me",
                        startHistoryId=history_id,
                        pageToken=page_token,
                        historyTypes=["messageAdded", "labelAdded", "labelRemoved"],
                    ).execute()
                except HttpError as e:
                    if e.resp.status == 404:
                        # History ID expired, need full sync
                        sync_state.fail_sync("History expired, full sync required")
                        self.db.commit()
                        return self.full_sync(account)
                    raise

                # Update history ID
                new_history_id = int(response.get("historyId", history_id))

                # Process history records
                for history_record in response.get("history", []):
                    # Handle new messages
                    for msg_added in history_record.get("messagesAdded", []):
                        msg_ref = msg_added.get("message", {})
                        msg_id = msg_ref.get("id")
                        if msg_id:
                            try:
                                msg = service.users().messages().get(
                                    userId="me",
                                    id=msg_id,
                                    format="metadata",
                                    metadataHeaders=[
                                        "Subject", "From", "To", "Cc", "Bcc", "Date"
                                    ],
                                ).execute()

                                email_msg = self._parse_message(msg, account)
                                if email_msg:
                                    self._save_message(email_msg)
                                    messages_synced += 1
                            except HttpError:
                                continue

                    # Handle label changes (update existing messages)
                    for label_change in (
                        history_record.get("labelsAdded", []) +
                        history_record.get("labelsRemoved", [])
                    ):
                        msg_ref = label_change.get("message", {})
                        msg_id = msg_ref.get("id")
                        labels = msg_ref.get("labelIds", [])
                        if msg_id:
                            self._update_message_labels(account.id, msg_id, labels)

                # Get next page
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            self.db.commit()

            sync_state.complete_sync(
                history_id=new_history_id,
                messages_synced=messages_synced,
                is_full_sync=False,
            )
            self.db.commit()

            return SyncResult(
                success=True,
                messages_synced=messages_synced,
                errors=errors,
                history_id=new_history_id,
            )

        except Exception as e:
            self.db.rollback()
            sync_state.fail_sync(str(e))
            self.db.commit()
            return SyncResult(
                success=False,
                messages_synced=messages_synced,
                errors=[str(e)] + errors,
            )

    def sync_all_accounts(self) -> dict[str, SyncResult]:
        """
        Sync all active Google accounts.

        Returns:
            Dictionary mapping account email to SyncResult
        """
        results = {}
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()

        for account in accounts:
            sync_state = self._get_or_create_sync_state(account)

            if sync_state.needs_full_sync:
                results[account.email] = self.full_sync(account)
            else:
                results[account.email] = self.incremental_sync(account)

        return results

    def _get_or_create_sync_state(self, account: GoogleAccount) -> EmailSyncState:
        """Get or create sync state for an account."""
        sync_state = self.db.query(EmailSyncState).filter_by(
            google_account_id=account.id
        ).first()

        if not sync_state:
            sync_state = EmailSyncState(google_account_id=account.id)
            self.db.add(sync_state)
            self.db.flush()

        return sync_state

    def _get_credentials(self, account: GoogleAccount) -> Credentials:
        """Get OAuth credentials for a Google account."""
        creds_dict = account.get_credentials()
        return Credentials(
            token=creds_dict.get("token"),
            refresh_token=creds_dict.get("refresh_token"),
            token_uri=creds_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_dict.get("client_id"),
            client_secret=creds_dict.get("client_secret"),
            scopes=creds_dict.get("scopes", GMAIL_SCOPES),
        )

    def _parse_message(
        self,
        message_data: dict,
        account: GoogleAccount,
    ) -> EmailMessage | None:
        """Parse Gmail API message response into EmailMessage model."""
        msg_id = message_data.get("id")
        thread_id = message_data.get("threadId")

        if not msg_id or not thread_id:
            return None

        # Parse headers
        headers = {}
        for header in message_data.get("payload", {}).get("headers", []):
            headers[header["name"].lower()] = header["value"]

        # Parse from field
        from_header = headers.get("from", "")
        from_email, from_name = self._parse_email_header(from_header)

        # Parse recipients
        to_emails = self._parse_recipient_header(headers.get("to", ""))
        cc_emails = self._parse_recipient_header(headers.get("cc", ""))
        bcc_emails = self._parse_recipient_header(headers.get("bcc", ""))

        # Parse date
        internal_date = None
        if "internaldate" in message_data:
            timestamp_ms = int(message_data["internaldate"])
            internal_date = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        # Parse labels
        labels = message_data.get("labelIds", [])

        # Check for attachments
        has_attachments = False
        attachment_count = 0
        parts = message_data.get("payload", {}).get("parts", [])
        for part in parts:
            if part.get("filename"):
                has_attachments = True
                attachment_count += 1

        return EmailMessage(
            google_account_id=account.id,
            gmail_message_id=msg_id,
            gmail_thread_id=thread_id,
            subject=headers.get("subject", ""),
            snippet=message_data.get("snippet", ""),
            from_email=from_email,
            from_name=from_name,
            to_emails=to_emails,
            cc_emails=cc_emails,
            bcc_emails=bcc_emails,
            is_read="UNREAD" not in labels,
            is_starred="STARRED" in labels,
            is_draft="DRAFT" in labels,
            is_sent="SENT" in labels,
            labels=labels,
            internal_date=internal_date,
            received_at=internal_date,
            has_attachments=has_attachments,
            attachment_count=attachment_count,
            history_id=int(message_data.get("historyId", 0)) or None,
        )

    def _parse_email_header(self, header: str) -> tuple[str | None, str | None]:
        """Parse email header like 'Name <email@example.com>' into (email, name)."""
        if not header:
            return None, None

        # Try to match "Name <email>" format
        match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>$', header.strip())
        if match:
            name = match.group(1).strip() or None
            email = match.group(2).strip().lower()
            return email, name

        # Just an email address
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', header)
        if email_match:
            return email_match.group().lower(), None

        return None, None

    def _parse_recipient_header(self, header: str) -> list[dict]:
        """Parse recipient header into list of {email, name} dicts."""
        if not header:
            return []

        recipients = []
        # Split by comma but not commas inside quotes
        parts = re.split(r',\s*(?=(?:[^"]*"[^"]*")*[^"]*$)', header)

        for part in parts:
            email, name = self._parse_email_header(part.strip())
            if email:
                recipients.append({"email": email, "name": name})

        return recipients

    def _save_message(self, email_msg: EmailMessage) -> None:
        """Save or update an email message and create person links."""
        # Check if message already exists
        existing = self.db.query(EmailMessage).filter_by(
            google_account_id=email_msg.google_account_id,
            gmail_message_id=email_msg.gmail_message_id,
        ).first()

        if existing:
            # Update existing message
            existing.subject = email_msg.subject
            existing.snippet = email_msg.snippet
            existing.is_read = email_msg.is_read
            existing.is_starred = email_msg.is_starred
            existing.labels = email_msg.labels
            existing.synced_at = datetime.now(timezone.utc)
            email_msg = existing
        else:
            # Add new message
            self.db.add(email_msg)
            self.db.flush()  # Get the ID

        # Auto-link to persons
        self._auto_link_to_persons(email_msg)

    def _update_message_labels(
        self,
        account_id: UUID,
        gmail_message_id: str,
        labels: list[str],
    ) -> None:
        """Update labels for an existing message."""
        msg = self.db.query(EmailMessage).filter_by(
            google_account_id=account_id,
            gmail_message_id=gmail_message_id,
        ).first()

        if msg:
            msg.labels = labels
            msg.is_read = "UNREAD" not in labels
            msg.is_starred = "STARRED" in labels

    def _auto_link_to_persons(self, email_msg: EmailMessage) -> None:
        """Auto-link email to CRM persons based on email addresses."""
        # Build email-to-person cache if not exists
        if self._email_to_person is None:
            self._email_to_person = {}
            person_emails = self.db.query(PersonEmail).all()
            for pe in person_emails:
                self._email_to_person[pe.email.lower()] = pe.person_id

        # Collect all email addresses and their link types
        addresses_to_link = []

        if email_msg.from_email:
            addresses_to_link.append((email_msg.from_email, EmailLinkType.FROM.value))

        for recipient in email_msg.to_emails or []:
            if isinstance(recipient, dict) and recipient.get("email"):
                addresses_to_link.append((recipient["email"], EmailLinkType.TO.value))

        for recipient in email_msg.cc_emails or []:
            if isinstance(recipient, dict) and recipient.get("email"):
                addresses_to_link.append((recipient["email"], EmailLinkType.CC.value))

        # Create links for matching persons
        for email_addr, link_type in addresses_to_link:
            person_id = self._email_to_person.get(email_addr.lower())
            if person_id:
                # Check if link already exists
                existing = self.db.query(EmailPersonLink).filter_by(
                    email_message_id=email_msg.id,
                    person_id=person_id,
                    link_type=link_type,
                ).first()

                if not existing:
                    link = EmailPersonLink(
                        email_message_id=email_msg.id,
                        person_id=person_id,
                        link_type=link_type,
                        linked_by=EmailLinkSource.AUTO.value,
                    )
                    self.db.add(link)


def get_gmail_sync_service(db: Session) -> GmailSyncService:
    """Get a Gmail sync service instance."""
    return GmailSyncService(db)


def get_gmail_labels(account: GoogleAccount) -> dict[str, str]:
    """
    Fetch all Gmail labels for an account and return mapping of ID to name.

    Args:
        account: Google account to fetch labels for

    Returns:
        Dictionary mapping label ID to human-readable name
    """
    try:
        creds_dict = account.get_credentials()
        credentials = Credentials(
            token=creds_dict.get("token"),
            refresh_token=creds_dict.get("refresh_token"),
            token_uri=creds_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_dict.get("client_id"),
            client_secret=creds_dict.get("client_secret"),
            scopes=creds_dict.get("scopes", GMAIL_SCOPES),
        )

        service = build("gmail", "v1", credentials=credentials)
        response = service.users().labels().list(userId="me").execute()

        labels = {}
        for label in response.get("labels", []):
            label_id = label.get("id")
            label_name = label.get("name")
            if label_id and label_name:
                labels[label_id] = label_name

        return labels

    except Exception:
        return {}
