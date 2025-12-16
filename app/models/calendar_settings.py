"""
CalendarSettings model for Google Calendar preferences.

This is a singleton table (only one row) that stores global settings
for calendar display and timezone preferences.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.models.base import Base


# Common timezones grouped by region for UI dropdown
COMMON_TIMEZONES = [
    # Americas
    ("America/New_York", "Eastern Time (US & Canada)"),
    ("America/Chicago", "Central Time (US & Canada)"),
    ("America/Denver", "Mountain Time (US & Canada)"),
    ("America/Los_Angeles", "Pacific Time (US & Canada)"),
    ("America/Anchorage", "Alaska"),
    ("Pacific/Honolulu", "Hawaii"),
    ("America/Toronto", "Toronto"),
    ("America/Vancouver", "Vancouver"),
    ("America/Mexico_City", "Mexico City"),
    ("America/Sao_Paulo", "Sao Paulo"),
    ("America/Buenos_Aires", "Buenos Aires"),
    # Europe
    ("Europe/London", "London"),
    ("Europe/Paris", "Paris"),
    ("Europe/Berlin", "Berlin"),
    ("Europe/Amsterdam", "Amsterdam"),
    ("Europe/Warsaw", "Warsaw"),
    ("Europe/Moscow", "Moscow"),
    ("Europe/Istanbul", "Istanbul"),
    # Asia/Pacific
    ("Asia/Dubai", "Dubai"),
    ("Asia/Kolkata", "India (Kolkata)"),
    ("Asia/Singapore", "Singapore"),
    ("Asia/Hong_Kong", "Hong Kong"),
    ("Asia/Shanghai", "Shanghai"),
    ("Asia/Tokyo", "Tokyo"),
    ("Asia/Seoul", "Seoul"),
    ("Australia/Sydney", "Sydney"),
    ("Australia/Melbourne", "Melbourne"),
    ("Pacific/Auckland", "Auckland"),
    # UTC
    ("UTC", "UTC"),
]


class CalendarSettings(Base):
    """
    Global settings for calendar display and timezone.

    This is a singleton table - only one row should exist.
    Use get_settings() class method to retrieve or create the settings.
    """

    __tablename__ = "calendar_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="America/New_York",
        comment="IANA timezone identifier for calendar display",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<CalendarSettings(timezone={self.timezone})>"

    @classmethod
    def get_settings(cls, db: Session) -> "CalendarSettings":
        """
        Get the singleton settings row, creating it if it doesn't exist.

        Args:
            db: Database session

        Returns:
            The CalendarSettings instance (creates with defaults if missing)
        """
        settings = db.query(cls).first()
        if settings is None:
            settings = cls()
            db.add(settings)
            db.flush()
        return settings

    @classmethod
    def get_timezone(cls, db: Session) -> str:
        """
        Convenience method to get just the timezone string.

        Args:
            db: Database session

        Returns:
            The timezone string (e.g., "America/New_York")
        """
        return cls.get_settings(db).timezone

    def get_timezone_display_name(self) -> str:
        """
        Get the human-readable display name for the current timezone.

        Returns:
            Display name or the raw timezone if not found in common list
        """
        for tz_id, display_name in COMMON_TIMEZONES:
            if tz_id == self.timezone:
                return display_name
        return self.timezone
