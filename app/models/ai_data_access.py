"""
AIDataAccessSettings model for controlling what CRM data AI can access.

This is a singleton table (only one row) that stores global settings
for what data types the AI assistant can read from the CRM.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.models.base import Base


class AIDataAccessSettings(Base):
    """
    Global settings controlling AI access to CRM data.

    This is a singleton table - only one row should exist.
    Use get_settings() class method to retrieve or create the settings.

    Privacy Settings:
        - allow_notes: Include notes field in AI context
        - allow_tags: Include tags in AI context
        - allow_interactions: Include interaction history summaries
        - allow_linkedin: Include LinkedIn URLs in AI context
        - auto_apply_suggestions: Automatically apply AI suggestions without approval

    Note: Email addresses and phone numbers are NEVER sent to external AI
    regardless of these settings. This is enforced in the privacy filter.
    """

    __tablename__ = "ai_data_access_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    allow_notes: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Include notes field in AI context",
    )
    allow_tags: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Include tags in AI context",
    )
    allow_interactions: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Include interaction history summaries",
    )
    allow_linkedin: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Include LinkedIn URLs in AI context",
    )
    auto_apply_suggestions: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Auto-apply AI suggestions without approval (default: require approval)",
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
        return (
            f"<AIDataAccessSettings("
            f"notes={self.allow_notes}, "
            f"tags={self.allow_tags}, "
            f"interactions={self.allow_interactions}, "
            f"linkedin={self.allow_linkedin}, "
            f"auto_apply={self.auto_apply_suggestions})>"
        )

    @classmethod
    def get_settings(cls, db: Session) -> "AIDataAccessSettings":
        """
        Get the singleton settings row, creating it if it doesn't exist.

        Args:
            db: Database session

        Returns:
            The AIDataAccessSettings instance (creates with defaults if missing)
        """
        settings = db.query(cls).first()
        if settings is None:
            settings = cls()
            db.add(settings)
            db.flush()
        return settings

    @classmethod
    def get_or_create_defaults(cls, db: Session) -> "AIDataAccessSettings":
        """
        Alias for get_settings() for clarity.

        Args:
            db: Database session

        Returns:
            The AIDataAccessSettings instance
        """
        return cls.get_settings(db)

    def to_dict(self) -> dict[str, bool]:
        """
        Return settings as a dictionary.

        Returns:
            Dictionary with all boolean settings
        """
        return {
            "allow_notes": self.allow_notes,
            "allow_tags": self.allow_tags,
            "allow_interactions": self.allow_interactions,
            "allow_linkedin": self.allow_linkedin,
            "auto_apply_suggestions": self.auto_apply_suggestions,
        }

    def update_from_dict(self, data: dict[str, bool]) -> None:
        """
        Update settings from a dictionary.

        Args:
            data: Dictionary with setting names as keys and boolean values

        Example:
            settings.update_from_dict({
                "allow_notes": False,
                "auto_apply_suggestions": True,
            })
        """
        if "allow_notes" in data:
            self.allow_notes = bool(data["allow_notes"])
        if "allow_tags" in data:
            self.allow_tags = bool(data["allow_tags"])
        if "allow_interactions" in data:
            self.allow_interactions = bool(data["allow_interactions"])
        if "allow_linkedin" in data:
            self.allow_linkedin = bool(data["allow_linkedin"])
        if "auto_apply_suggestions" in data:
            self.auto_apply_suggestions = bool(data["auto_apply_suggestions"])
