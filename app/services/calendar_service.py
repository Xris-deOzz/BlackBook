"""
Calendar service for interacting with Google Calendar API.

Handles fetching events, matching attendees to persons, and syncing calendar data.
Supports timezone-aware date calculations for accurate "today" queries.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.models import (
    GoogleAccount,
    Person,
    PersonEmail,
    CalendarEvent,
    PendingContact,
    PendingContactStatus,
    Interaction,
    InteractionMedium,
    InteractionSource,
)
from app.services.google_auth import CALENDAR_SCOPES


# Google Calendar colorId mapping (from Google Calendar API)
# See: https://developers.google.com/calendar/api/v3/reference/colors
GOOGLE_CALENDAR_COLORS = {
    "tomato": "11",      # Red (#D50000)
    "flamingo": "4",     # Pink (#E67C73)
    "tangerine": "6",    # Orange (#F4511E)
    "banana": "5",       # Yellow (#F6BF26)
    "sage": "2",         # Light green (#33B679)
    "basil": "10",       # Dark green (#0B8043)
    "peacock": "7",      # Cyan (#039BE5)
    "blueberry": "9",    # Blue (#3F51B5)
    "lavender": "1",     # Light purple (#7986CB)
    "grape": "3",        # Purple (#8E24AA)
    "graphite": "8",     # Gray (#616161)
}

# Reverse mapping for syncing from Google to local
GOOGLE_COLOR_ID_TO_NAME = {v: k for k, v in GOOGLE_CALENDAR_COLORS.items()}


class CalendarServiceError(Exception):
    """Base exception for Calendar service errors."""
    pass


class CalendarAuthError(CalendarServiceError):
    """Raised when Calendar authentication fails."""
    pass


class CalendarAPIError(CalendarServiceError):
    """Raised when Calendar API calls fail."""
    pass


class CalendarService:
    """
    Service for interacting with Google Calendar API.

    Handles fetching events, caching them locally, and matching attendees to persons.
    """

    def __init__(self, db: Session):
        """Initialize the Calendar service.

        Args:
            db: Database session for querying accounts and storing events
        """
        self.db = db
        self._email_to_person_cache: dict[str, UUID | None] | None = None

    def fetch_events(
        self,
        account_id: UUID,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 100,
    ) -> list[CalendarEvent]:
        """
        Fetch calendar events from a Google account and cache them locally.

        Args:
            account_id: UUID of the Google account
            time_min: Start of time range (defaults to now)
            time_max: End of time range (defaults to 7 days from now)
            max_results: Maximum number of events to fetch

        Returns:
            List of CalendarEvent objects (newly fetched and cached)

        Raises:
            CalendarServiceError: If account not found
            CalendarAuthError: If authentication fails
            CalendarAPIError: If API call fails
        """
        account = self.db.query(GoogleAccount).filter_by(id=account_id).first()
        if not account:
            raise CalendarServiceError(f"Account not found: {account_id}")

        # Set default time range
        if time_min is None:
            time_min = datetime.now(timezone.utc)
        if time_max is None:
            time_max = time_min + timedelta(days=7)

        try:
            credentials = self._get_credentials(account)
            service = build("calendar", "v3", credentials=credentials)

            events_result = service.events().list(
                calendarId="primary",
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events_data = events_result.get("items", [])

            # Cache events in database
            cached_events = []
            for event_data in events_data:
                cached_event = self._cache_event(account, event_data)
                if cached_event:
                    cached_events.append(cached_event)

            self.db.commit()
            return cached_events

        except HttpError as e:
            raise CalendarAPIError(f"Calendar API error: {e}")

    def get_todays_events(
        self,
        local_tz: ZoneInfo | None = None,
        account_id: UUID | None = None,
    ) -> list[CalendarEvent]:
        """
        Get today's calendar events, optionally filtered by account.

        Args:
            local_tz: Local timezone to determine "today". If None, uses UTC.
            account_id: Optional UUID to filter events to a specific Google account.

        Returns:
            List of CalendarEvent objects for today, sorted by start time
        """
        if local_tz:
            # Calculate today's boundaries in local timezone, then convert to UTC
            now_local = datetime.now(local_tz)
            today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end_local = today_start_local + timedelta(days=1)
            # Convert to UTC for database queries
            today_start = today_start_local.astimezone(timezone.utc)
            today_end = today_end_local.astimezone(timezone.utc)
        else:
            # Fallback to UTC
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

        # Fetch fresh events from accounts
        if account_id:
            # Fetch only from specific account
            account = self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()
            if account:
                try:
                    self.fetch_events(
                        account_id=account.id,
                        time_min=today_start,
                        time_max=today_end,
                    )
                except (CalendarAuthError, CalendarAPIError):
                    pass
        else:
            # Fetch from all active accounts
            accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
            for account in accounts:
                try:
                    self.fetch_events(
                        account_id=account.id,
                        time_min=today_start,
                        time_max=today_end,
                    )
                except (CalendarAuthError, CalendarAPIError):
                    # Continue with other accounts if one fails
                    continue

        # Query cached events for today
        query = (
            self.db.query(CalendarEvent)
            .filter(CalendarEvent.start_time >= today_start)
            .filter(CalendarEvent.start_time < today_end)
        )

        # Filter by account if specified, otherwise filter to active accounts only
        if account_id:
            query = query.filter(CalendarEvent.google_account_id == account_id)
        else:
            # Only show events from active accounts (prevents orphaned events)
            active_account_ids = [a.id for a in self.db.query(GoogleAccount).filter_by(is_active=True).all()]
            if active_account_ids:
                query = query.filter(CalendarEvent.google_account_id.in_(active_account_ids))

        events = query.order_by(CalendarEvent.start_time).all()

        return events

    def get_events_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
        account_id: UUID | None = None,
        fetch_fresh: bool = True,
    ) -> list[CalendarEvent]:
        """
        Get calendar events for a specific date range.

        Args:
            start_date: Start of date range (timezone-aware)
            end_date: End of date range (timezone-aware)
            account_id: Optional UUID to filter events to a specific Google account.
            fetch_fresh: Whether to fetch fresh events from Google API (default True)

        Returns:
            List of CalendarEvent objects, sorted by start time
        """
        # Convert to UTC for database queries (database stores times in UTC)
        if start_date.tzinfo is not None:
            start_utc = start_date.astimezone(timezone.utc)
        else:
            start_utc = start_date.replace(tzinfo=timezone.utc)

        if end_date.tzinfo is not None:
            end_utc = end_date.astimezone(timezone.utc)
        else:
            end_utc = end_date.replace(tzinfo=timezone.utc)

        # Fetch fresh events from accounts if requested
        if fetch_fresh:
            if account_id:
                # Fetch only from specific account
                account = self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()
                if account:
                    try:
                        self.fetch_events(
                            account_id=account.id,
                            time_min=start_utc,
                            time_max=end_utc,
                        )
                    except (CalendarAuthError, CalendarAPIError):
                        pass
            else:
                # Fetch from all active accounts
                accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
                for account in accounts:
                    try:
                        self.fetch_events(
                            account_id=account.id,
                            time_min=start_utc,
                            time_max=end_utc,
                        )
                    except (CalendarAuthError, CalendarAPIError):
                        continue

        # Query cached events for the range (using UTC times)
        query = (
            self.db.query(CalendarEvent)
            .filter(CalendarEvent.start_time >= start_utc)
            .filter(CalendarEvent.start_time < end_utc)
        )

        # Filter by account if specified, otherwise filter to active accounts only
        if account_id:
            query = query.filter(CalendarEvent.google_account_id == account_id)
        else:
            # Only show events from active accounts (prevents orphaned events)
            active_account_ids = [a.id for a in self.db.query(GoogleAccount).filter_by(is_active=True).all()]
            if active_account_ids:
                query = query.filter(CalendarEvent.google_account_id.in_(active_account_ids))

        events = query.order_by(CalendarEvent.start_time).all()

        return events

    def get_upcoming_events(
        self,
        days: int = 7,
        offset: int = 0,
        account_id: UUID | None = None,
    ) -> list[CalendarEvent]:
        """
        Get upcoming calendar events, optionally filtered by account.

        Args:
            days: Number of days to look ahead (default 7)
            offset: Number of days to skip from today (default 0)
            account_id: Optional UUID to filter events to a specific Google account.

        Returns:
            List of CalendarEvent objects, sorted by start time
        """
        now = datetime.now(timezone.utc)
        time_min = now + timedelta(days=offset)
        time_max = time_min + timedelta(days=days)

        # Fetch fresh events from accounts
        if account_id:
            # Fetch only from specific account
            account = self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()
            if account:
                try:
                    self.fetch_events(
                        account_id=account.id,
                        time_min=time_min,
                        time_max=time_max,
                    )
                except (CalendarAuthError, CalendarAPIError):
                    pass
        else:
            # Fetch from all active accounts
            accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
            for account in accounts:
                try:
                    self.fetch_events(
                        account_id=account.id,
                        time_min=time_min,
                        time_max=time_max,
                    )
                except (CalendarAuthError, CalendarAPIError):
                    continue

        # Query cached events
        query = (
            self.db.query(CalendarEvent)
            .filter(CalendarEvent.start_time >= time_min)
            .filter(CalendarEvent.start_time < time_max)
        )

        # Filter by account if specified, otherwise filter to active accounts only
        if account_id:
            query = query.filter(CalendarEvent.google_account_id == account_id)
        else:
            # Only show events from active accounts (prevents orphaned events)
            active_account_ids = [a.id for a in self.db.query(GoogleAccount).filter_by(is_active=True).all()]
            if active_account_ids:
                query = query.filter(CalendarEvent.google_account_id.in_(active_account_ids))

        events = query.order_by(CalendarEvent.start_time).all()

        return events

    def create_event(
        self,
        summary: str,
        start_datetime: datetime,
        end_datetime: datetime | None = None,
        description: str | None = None,
        location: str | None = None,
        attendee_email: str | None = None,
        attendee_emails: list[str] | None = None,
        add_video_conferencing: bool = False,
        notification_minutes: int | None = None,
        account_id: UUID | None = None,
        timezone_str: str | None = None,
        recurrence: str | None = None,
        send_updates: str = "none",
        color: str | None = None,
    ) -> str | None:
        """
        Create a new event in Google Calendar.

        Args:
            summary: Event title
            start_datetime: Start date/time (can be naive or timezone-aware)
            end_datetime: End date/time (default: 1 hour after start)
            description: Event description/notes
            location: Event location (address or place name)
            attendee_email: Optional single email to add as attendee (legacy)
            attendee_emails: Optional list of emails to add as attendees
            add_video_conferencing: Whether to add Google Meet video conferencing
            notification_minutes: Minutes before event to send reminder (e.g., 10, 30, 60)
            account_id: Optional specific Google account to use
            timezone_str: Timezone string (e.g., "America/New_York"). If not provided,
                          uses the datetime's timezone or defaults to "America/New_York"
            recurrence: RRULE string for recurring events (e.g., "RRULE:FREQ=WEEKLY")
            send_updates: Whether to send invite emails ("all", "externalOnly", "none")
            color: Event color name (tomato, flamingo, tangerine, banana, sage, basil, peacock, blueberry, lavender, grape, graphite)

        Returns:
            Google Calendar event ID if successful, None otherwise

        Raises:
            CalendarServiceError: If no active account found
            CalendarAuthError: If authentication fails
            CalendarAPIError: If API call fails
        """
        # Get specific account or first active Google account
        if account_id:
            account = self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()
        else:
            account = self.db.query(GoogleAccount).filter_by(is_active=True).first()
        if not account:
            raise CalendarServiceError("No active Google account found")

        # Default end time to 1 hour after start
        if end_datetime is None:
            end_datetime = start_datetime + timedelta(hours=1)

        # Determine timezone to use
        # Priority: explicit timezone_str > datetime's timezone > default
        if timezone_str:
            tz_to_use = timezone_str
        elif start_datetime.tzinfo is not None:
            tz_to_use = str(start_datetime.tzinfo)
        else:
            # Default timezone - Google Calendar API requires timezone for proper event creation
            tz_to_use = "America/New_York"

        # Build event body - always include timezone for reliability
        # Format datetime without timezone suffix, let timeZone field handle it
        if start_datetime.tzinfo is not None:
            # If datetime has timezone, convert to the target timezone first
            start_str = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            # Naive datetime - use as-is (assumed to be in tz_to_use)
            start_str = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")

        if end_datetime.tzinfo is not None:
            end_str = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            end_str = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")

        start_entry = {
            "dateTime": start_str,
            "timeZone": tz_to_use,
        }
        end_entry = {
            "dateTime": end_str,
            "timeZone": tz_to_use,
        }

        event_body = {
            "summary": summary,
            "start": start_entry,
            "end": end_entry,
        }

        if description:
            event_body["description"] = description

        if location:
            event_body["location"] = location

        # Handle attendees - combine single email and list of emails
        attendees = []
        if attendee_email:
            attendees.append({"email": attendee_email})
        if attendee_emails:
            for email in attendee_emails:
                if email and email.strip():
                    attendees.append({"email": email.strip()})
        if attendees:
            event_body["attendees"] = attendees

        # Add Google Meet video conferencing
        if add_video_conferencing:
            event_body["conferenceData"] = {
                "createRequest": {
                    "requestId": f"meet-{start_datetime.strftime('%Y%m%d%H%M%S')}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }

        # Add notification/reminder
        if notification_minutes is not None and notification_minutes >= 0:
            event_body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": notification_minutes},
                ],
            }

        # Add recurrence rule for recurring events
        if recurrence:
            event_body["recurrence"] = [recurrence]

        # Add event color (using Google Calendar's colorId)
        if color and color in GOOGLE_CALENDAR_COLORS:
            event_body["colorId"] = GOOGLE_CALENDAR_COLORS[color]

        try:
            credentials = self._get_credentials(account)
            service = build("calendar", "v3", credentials=credentials)

            # If adding video conferencing, we need conferenceDataVersion=1
            conference_version = 1 if add_video_conferencing else 0

            created_event = service.events().insert(
                calendarId="primary",
                body=event_body,
                sendUpdates=send_updates,
                conferenceDataVersion=conference_version,
            ).execute()

            # Cache the newly created event locally so it shows up immediately with color
            try:
                self._cache_event(account, created_event)
                self.db.commit()
            except Exception as cache_error:
                logger.warning(f"Failed to cache new event: {cache_error}")

            return created_event.get("id")

        except HttpError as e:
            raise CalendarAPIError(f"Failed to create calendar event: {e}")

    def delete_event(
        self,
        google_event_id: str,
        account_id: UUID,
    ) -> bool:
        """
        Delete an event from Google Calendar.

        Args:
            google_event_id: Google Calendar event ID to delete
            account_id: UUID of the Google account that owns the event

        Returns:
            True if deletion was successful, False otherwise

        Raises:
            CalendarServiceError: If account not found
            CalendarAuthError: If authentication fails
            CalendarAPIError: If API call fails
        """
        account = self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()
        if not account:
            raise CalendarServiceError(f"Account not found: {account_id}")

        try:
            credentials = self._get_credentials(account)
            service = build("calendar", "v3", credentials=credentials)

            service.events().delete(
                calendarId="primary",
                eventId=google_event_id,
                sendUpdates="none",
            ).execute()

            return True

        except HttpError as e:
            if e.resp.status == 404:
                # Event already deleted or doesn't exist - treat as success
                return True
            raise CalendarAPIError(f"Failed to delete calendar event: {e}")

    def update_event(
        self,
        google_event_id: str,
        account_id: UUID,
        summary: str | None = None,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
        description: str | None = None,
        location: str | None = None,
        attendee_emails: list[str] | None = None,
        add_video_conferencing: bool = False,
        timezone_str: str | None = None,
        recurrence: str | None = None,
        send_updates: str = "none",
        color: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Update an existing event in Google Calendar.

        Args:
            google_event_id: Google Calendar event ID to update
            account_id: UUID of the Google account that owns the event
            summary: Event title (optional, keeps existing if not provided)
            start_datetime: Start date/time (optional)
            end_datetime: End date/time (optional)
            description: Event description/notes (optional)
            location: Event location (optional)
            attendee_emails: List of attendee emails (optional, replaces existing)
            add_video_conferencing: Whether to add Google Meet
            timezone_str: Timezone string (e.g., "America/New_York")
            recurrence: RRULE string for recurring events (optional)
            send_updates: Whether to send invite emails ("all", "externalOnly", "none")
            color: Event color name (tomato, flamingo, tangerine, banana, sage, basil, peacock, blueberry, lavender, grape, graphite)

        Returns:
            Updated event data dict if successful, None otherwise

        Raises:
            CalendarServiceError: If account not found
            CalendarAuthError: If authentication fails
            CalendarAPIError: If API call fails
        """
        account = self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()
        if not account:
            raise CalendarServiceError(f"Account not found: {account_id}")

        try:
            credentials = self._get_credentials(account)
            service = build("calendar", "v3", credentials=credentials)

            # First, get the existing event to preserve fields we're not updating
            existing_event = service.events().get(
                calendarId="primary",
                eventId=google_event_id,
            ).execute()

            # Build update body - start with existing event
            event_body = existing_event.copy()

            # Update fields if provided
            if summary is not None:
                event_body["summary"] = summary

            if description is not None:
                event_body["description"] = description

            if location is not None:
                event_body["location"] = location

            # Determine timezone to use
            if timezone_str:
                tz_to_use = timezone_str
            elif start_datetime and start_datetime.tzinfo is not None:
                tz_to_use = str(start_datetime.tzinfo)
            else:
                # Use existing timezone or default
                tz_to_use = existing_event.get("start", {}).get("timeZone", "America/New_York")

            # Update start/end times if provided
            if start_datetime is not None:
                start_str = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
                event_body["start"] = {
                    "dateTime": start_str,
                    "timeZone": tz_to_use,
                }

            if end_datetime is not None:
                end_str = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")
                event_body["end"] = {
                    "dateTime": end_str,
                    "timeZone": tz_to_use,
                }

            # Update attendees if provided
            if attendee_emails is not None:
                attendees = []
                for email in attendee_emails:
                    if email and email.strip():
                        attendees.append({"email": email.strip()})
                event_body["attendees"] = attendees if attendees else []

            # Add Google Meet video conferencing if requested
            if add_video_conferencing and "conferenceData" not in existing_event:
                event_body["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"meet-update-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }

            # Update recurrence if provided
            if recurrence is not None:
                if recurrence:
                    event_body["recurrence"] = [recurrence]
                else:
                    # Clear recurrence
                    event_body.pop("recurrence", None)

            # Update event color if provided
            if color is not None:
                if color and color in GOOGLE_CALENDAR_COLORS:
                    event_body["colorId"] = GOOGLE_CALENDAR_COLORS[color]
                else:
                    # Clear color (use calendar default)
                    event_body.pop("colorId", None)

            # Determine conference version
            conference_version = 1 if add_video_conferencing else 0

            updated_event = service.events().update(
                calendarId="primary",
                eventId=google_event_id,
                body=event_body,
                sendUpdates=send_updates,
                conferenceDataVersion=conference_version,
            ).execute()

            # Also update local cache
            self._cache_event(account, updated_event)
            self.db.commit()

            return updated_event

        except HttpError as e:
            raise CalendarAPIError(f"Failed to update calendar event: {e}")

    def get_event(
        self,
        google_event_id: str,
        account_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Get a single event from Google Calendar.

        Args:
            google_event_id: Google Calendar event ID
            account_id: UUID of the Google account

        Returns:
            Event data dict if found, None otherwise
        """
        account = self.db.query(GoogleAccount).filter_by(id=account_id, is_active=True).first()
        if not account:
            return None

        try:
            credentials = self._get_credentials(account)
            service = build("calendar", "v3", credentials=credentials)

            event = service.events().get(
                calendarId="primary",
                eventId=google_event_id,
            ).execute()

            return event

        except HttpError:
            return None

    def match_attendees_to_persons(
        self,
        event: CalendarEvent,
    ) -> list[dict[str, Any]]:
        """
        Match event attendees to persons in the database.

        Args:
            event: CalendarEvent to match attendees for

        Returns:
            List of attendee dicts with person_id if matched:
            [{"email": str, "name": str, "person_id": UUID|None, "person_name": str|None}]
        """
        if not event.attendees:
            return []

        matched = []
        for attendee in event.attendees:
            email = attendee.get("email", "").lower()
            name = attendee.get("displayName") or attendee.get("name", "")

            person_id = self._find_person_by_email(email)
            person_name = None

            if person_id:
                person = self.db.query(Person).filter_by(id=person_id).first()
                if person:
                    person_name = person.full_name

            matched.append({
                "email": email,
                "name": name,
                "response_status": attendee.get("responseStatus"),
                "person_id": str(person_id) if person_id else None,
                "person_name": person_name,
            })

        return matched

    def sync_past_events(self, days: int = 30) -> dict[str, int]:
        """
        Sync past calendar events for interaction creation.

        Args:
            days: Number of days to look back (default 30)

        Returns:
            Dict with sync statistics: {"events_synced": int, "pending_contacts_created": int}
        """
        now = datetime.now(timezone.utc)
        time_min = now - timedelta(days=days)

        events_synced = 0
        pending_created = 0

        # Fetch past events from all accounts
        accounts = self.db.query(GoogleAccount).filter_by(is_active=True).all()
        for account in accounts:
            try:
                events = self.fetch_events(
                    account_id=account.id,
                    time_min=time_min,
                    time_max=now,
                    max_results=250,
                )
                events_synced += len(events)

                # Process attendees for pending contacts
                for event in events:
                    pending_created += self._process_attendees_for_pending(event)

            except (CalendarAuthError, CalendarAPIError):
                continue

        self.db.commit()
        return {
            "events_synced": events_synced,
            "pending_contacts_created": pending_created,
        }

    def auto_create_interactions(
        self,
        days: int = 30,
        only_past: bool = True,
    ) -> dict[str, int]:
        """
        Automatically create interactions for calendar events with known attendees.

        Args:
            days: Number of days to look back (default 30)
            only_past: Only create interactions for past events (default True)

        Returns:
            Dict with statistics: {"events_processed": int, "interactions_created": int}
        """
        now = datetime.now(timezone.utc)
        time_min = now - timedelta(days=days)

        # Query events that are past and have attendees
        query = (
            self.db.query(CalendarEvent)
            .filter(CalendarEvent.start_time >= time_min)
            .filter(CalendarEvent.attendees.isnot(None))
        )

        if only_past:
            query = query.filter(CalendarEvent.end_time < now)

        events = query.all()

        events_processed = 0
        interactions_created = 0

        for event in events:
            events_processed += 1
            created = self._create_interactions_for_event(event)
            interactions_created += created

        self.db.commit()
        return {
            "events_processed": events_processed,
            "interactions_created": interactions_created,
        }

    def _create_interactions_for_event(self, event: CalendarEvent) -> int:
        """
        Create interactions for all known attendees of an event.

        Args:
            event: CalendarEvent to process

        Returns:
            Number of interactions created
        """
        if not event.attendees:
            return 0

        # Determine interaction medium
        medium = InteractionMedium.video_call if event.is_video_call else InteractionMedium.meeting

        created = 0
        for attendee in event.attendees:
            email = attendee.get("email", "").lower()
            if not email:
                continue

            # Skip self
            if attendee.get("self"):
                continue

            # Find person by email
            person_id = self._find_person_by_email(email)
            if not person_id:
                continue

            # Check if interaction already exists
            existing = (
                self.db.query(Interaction)
                .filter_by(
                    person_id=person_id,
                    calendar_event_id=event.google_event_id,
                )
                .first()
            )
            if existing:
                continue

            # Create interaction
            interaction = Interaction(
                person_id=person_id,
                medium=medium,
                interaction_date=event.start_time,
                notes=f"Calendar: {event.summary or 'Meeting'}",
                calendar_event_id=event.google_event_id,
                source=InteractionSource.calendar,
            )
            self.db.add(interaction)
            created += 1

        return created

    def full_sync(self, days: int = 30) -> dict[str, Any]:
        """
        Perform a full calendar sync: fetch events, create pending contacts,
        and auto-create interactions.

        Args:
            days: Number of days to look back (default 30)

        Returns:
            Dict with full sync statistics
        """
        # First sync past events
        sync_result = self.sync_past_events(days=days)

        # Then auto-create interactions
        interaction_result = self.auto_create_interactions(days=days)

        return {
            "events_synced": sync_result["events_synced"],
            "pending_contacts_created": sync_result["pending_contacts_created"],
            "events_processed": interaction_result["events_processed"],
            "interactions_created": interaction_result["interactions_created"],
        }

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
                scopes=creds_dict.get("scopes", CALENDAR_SCOPES),
            )
        except Exception as e:
            raise CalendarAuthError(f"Failed to get credentials: {e}")

    def _cache_event(
        self,
        account: GoogleAccount,
        event_data: dict[str, Any],
    ) -> CalendarEvent | None:
        """Cache a calendar event in the database (upsert)."""
        google_event_id = event_data.get("id")
        if not google_event_id:
            return None

        # Parse start/end times
        start = event_data.get("start", {})
        end = event_data.get("end", {})

        start_time = self._parse_event_time(start)
        end_time = self._parse_event_time(end)

        if not start_time or not end_time:
            return None

        # Parse attendees
        attendees = []
        for attendee in event_data.get("attendees", []):
            attendees.append({
                "email": attendee.get("email", ""),
                "name": attendee.get("displayName", ""),
                "response_status": attendee.get("responseStatus", ""),
                "self": attendee.get("self", False),
                "organizer": attendee.get("organizer", False),
            })

        # Get organizer email
        organizer = event_data.get("organizer", {})
        organizer_email = organizer.get("email")

        # Check for recurring event
        is_recurring = "recurringEventId" in event_data
        recurring_event_id = event_data.get("recurringEventId")

        # Upsert event
        existing = (
            self.db.query(CalendarEvent)
            .filter_by(
                google_account_id=account.id,
                google_event_id=google_event_id,
            )
            .first()
        )

        # Get the direct link to view in Google Calendar
        html_link = event_data.get("htmlLink")

        # Get event color (convert Google's colorId to our color name)
        color_id = event_data.get("colorId")
        calendar_color = GOOGLE_COLOR_ID_TO_NAME.get(color_id) if color_id else None

        if existing:
            # Update existing event
            existing.summary = event_data.get("summary")
            existing.description = event_data.get("description")
            existing.start_time = start_time
            existing.end_time = end_time
            existing.location = event_data.get("location")
            existing.attendees = attendees if attendees else None
            existing.is_recurring = is_recurring
            existing.recurring_event_id = recurring_event_id
            existing.organizer_email = organizer_email
            existing.html_link = html_link
            existing.calendar_color = calendar_color
            return existing
        else:
            # Create new event
            event = CalendarEvent(
                google_account_id=account.id,
                google_event_id=google_event_id,
                summary=event_data.get("summary"),
                description=event_data.get("description"),
                start_time=start_time,
                end_time=end_time,
                location=event_data.get("location"),
                attendees=attendees if attendees else None,
                is_recurring=is_recurring,
                recurring_event_id=recurring_event_id,
                organizer_email=organizer_email,
                html_link=html_link,
                calendar_color=calendar_color,
            )
            self.db.add(event)
            return event

    def _parse_event_time(self, time_data: dict[str, str]) -> datetime | None:
        """Parse event start/end time from Google Calendar API response."""
        if "dateTime" in time_data:
            # Regular event with specific time
            dt_str = time_data["dateTime"]
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                return None
        elif "date" in time_data:
            # All-day event
            try:
                date = datetime.strptime(time_data["date"], "%Y-%m-%d")
                return date.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    def _find_person_by_email(self, email: str) -> UUID | None:
        """Find a person by email address (cached lookup)."""
        email_lower = email.lower()

        # Build cache on first lookup
        if self._email_to_person_cache is None:
            self._email_to_person_cache = {}
            person_emails = self.db.query(PersonEmail).all()
            for pe in person_emails:
                self._email_to_person_cache[pe.email.lower()] = pe.person_id

            # Also check legacy email field
            persons = self.db.query(Person).filter(Person.email.isnot(None)).all()
            for p in persons:
                if p.email and p.email.lower() not in self._email_to_person_cache:
                    self._email_to_person_cache[p.email.lower()] = p.id

        return self._email_to_person_cache.get(email_lower)

    def _process_attendees_for_pending(self, event: CalendarEvent) -> int:
        """
        Process event attendees and create pending contacts for unknown ones.

        Returns:
            Number of new pending contacts created
        """
        if not event.attendees:
            return 0

        created = 0
        for attendee in event.attendees:
            email = attendee.get("email", "").lower()
            if not email:
                continue

            # Skip self (the calendar owner)
            if attendee.get("self"):
                continue

            # Check if person exists
            person_id = self._find_person_by_email(email)
            if person_id:
                continue

            # Check if already in pending contacts
            existing = (
                self.db.query(PendingContact)
                .filter_by(email=email)
                .first()
            )

            if existing:
                # Increment occurrence count
                existing.increment_occurrence()
            else:
                # Create new pending contact
                pending = PendingContact(
                    email=email,
                    name=attendee.get("name") or attendee.get("displayName"),
                    source_event_id=event.id,
                )
                self.db.add(pending)
                created += 1

        return created


def get_calendar_service(db: Session) -> CalendarService:
    """Get a Calendar service instance.

    Args:
        db: Database session

    Returns:
        CalendarService instance
    """
    return CalendarService(db)
