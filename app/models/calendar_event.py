"""
CalendarEvent model for storing Google Calendar events.
"""

import base64
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.google_account import GoogleAccount


class CalendarEvent(Base):
    """
    Cached calendar event data from Google Calendar API.

    Stores calendar events for display and attendee matching.
    Events are fetched on-demand and cached for quick access.
    """

    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint(
            "google_account_id", "google_event_id",
            name="uq_calendar_events_account_event"
        ),
        Index("idx_calendar_events_start", "start_time"),
        Index("idx_calendar_events_account", "google_account_id"),
        Index("idx_calendar_events_end", "end_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    google_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("google_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    google_event_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Google Calendar event ID",
    )
    summary: Mapped[str | None] = mapped_column(
        String(500),
        comment="Event title/summary",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        comment="Event description",
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Event start time",
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Event end time",
    )
    location: Mapped[str | None] = mapped_column(
        String(500),
        comment="Event location or video call link",
    )
    attendees: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="List of attendees [{email, name, response_status}]",
    )
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether this is part of a recurring event",
    )
    recurring_event_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="ID of the recurring event series",
    )
    organizer_email: Mapped[str | None] = mapped_column(
        String(255),
        comment="Email of the event organizer",
    )
    html_link: Mapped[str | None] = mapped_column(
        String(500),
        comment="Direct link to view event in Google Calendar",
    )
    calendar_color: Mapped[str | None] = mapped_column(
        String(32),
        comment="Event color (tomato, flamingo, tangerine, banana, sage, basil, peacock, blueberry, lavender, grape, graphite)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    google_account: Mapped["GoogleAccount"] = orm_relationship(
        "GoogleAccount",
        back_populates="calendar_events",
    )

    def __repr__(self) -> str:
        return f"<CalendarEvent(summary={self.summary!r}, start={self.start_time})>"

    @property
    def duration_minutes(self) -> int:
        """Get the duration of the event in minutes."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def is_all_day(self) -> bool:
        """Check if this is an all-day event (duration >= 24 hours)."""
        return self.duration_minutes >= 24 * 60

    @property
    def is_past(self) -> bool:
        """Check if the event has already ended."""
        if self.end_time is None:
            return False
        end = self.end_time
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > end

    @property
    def is_upcoming(self) -> bool:
        """Check if the event hasn't started yet."""
        if self.start_time is None:
            return False
        start = self.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < start

    @property
    def is_happening_now(self) -> bool:
        """Check if the event is currently happening."""
        return not self.is_past and not self.is_upcoming

    @property
    def attendee_emails(self) -> list[str]:
        """Get list of attendee email addresses."""
        if not self.attendees:
            return []
        if isinstance(self.attendees, list):
            return [a.get("email", "").lower() for a in self.attendees if a.get("email")]
        return []

    @property
    def attendee_count(self) -> int:
        """Get the number of attendees."""
        return len(self.attendee_emails)

    @property
    def is_video_call(self) -> bool:
        """Check if this event appears to be a video call."""
        if not self.location:
            return False
        location_lower = self.location.lower()
        video_indicators = [
            "zoom.us",
            "meet.google.com",
            "teams.microsoft.com",
            "webex.com",
            "gotomeeting.com",
            "hangouts.google.com",
        ]
        return any(indicator in location_lower for indicator in video_indicators)

    @property
    def google_calendar_url(self) -> str:
        """Get URL to view this event in Google Calendar.

        Uses the html_link from Google API if available (most reliable),
        otherwise falls back to constructing the URL.
        """
        # Use stored html_link from Google API if available
        if self.html_link:
            return self.html_link

        # Fallback: construct URL using base64 encoding
        # Format: base64(event_id + ' ' + calendar_email)
        calendar_email = ""
        if self.google_account and self.google_account.email:
            calendar_email = self.google_account.email

        eid_source = f"{self.google_event_id} {calendar_email}"
        eid_encoded = base64.b64encode(eid_source.encode()).decode()

        return f"https://calendar.google.com/calendar/event?eid={eid_encoded}"

    def get_attendee_by_email(self, email: str) -> dict[str, Any] | None:
        """
        Get attendee info by email address.

        Args:
            email: Email address to search for

        Returns:
            Attendee dict or None if not found
        """
        if not self.attendees:
            return None
        email_lower = email.lower()
        if isinstance(self.attendees, list):
            for attendee in self.attendees:
                if attendee.get("email", "").lower() == email_lower:
                    return attendee
        return None
