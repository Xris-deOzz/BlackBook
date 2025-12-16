"""
RecordSnapshot model for storing point-in-time entity backups.

Before AI modifies any CRM record, a snapshot is created to allow
undo/restore functionality.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    String,
    DateTime,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChangeSource(str, PyEnum):
    """Source of the change that triggered the snapshot."""

    manual = "manual"
    ai_suggestion = "ai_suggestion"
    ai_auto = "ai_auto"
    import_data = "import"


class RecordSnapshot(Base):
    """
    Point-in-time snapshot of a CRM entity.

    Created before any modification to allow restore functionality.
    Stores the complete entity state as JSON.

    Attributes:
        entity_type: "person" or "organization"
        entity_id: UUID of the entity
        snapshot_json: Complete entity state as JSON
        change_source: What triggered the snapshot (manual, ai_suggestion, etc.)
        change_description: Human-readable description of the change
    """

    __tablename__ = "record_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    entity_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Entity type: 'person' or 'organization'",
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="UUID of the entity",
    )
    snapshot_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete entity state as JSON",
    )
    change_source: Mapped[ChangeSource] = mapped_column(
        Enum(ChangeSource, name="change_source_type", create_type=False),
        nullable=False,
        comment="What triggered this snapshot",
    )
    change_description: Mapped[str | None] = mapped_column(
        String(255),
        comment="Human-readable description of the change",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<RecordSnapshot("
            f"entity={self.entity_type}:{self.entity_id}, "
            f"source={self.change_source.value}, "
            f"created_at={self.created_at})>"
        )

    @property
    def is_ai_generated(self) -> bool:
        """Check if this snapshot was created by AI activity."""
        return self.change_source in (ChangeSource.ai_suggestion, ChangeSource.ai_auto)

    @property
    def source_icon(self) -> str:
        """Return an icon representing the change source."""
        icons = {
            ChangeSource.manual: "👤",
            ChangeSource.ai_suggestion: "🤖",
            ChangeSource.ai_auto: "⚡",
            ChangeSource.import_data: "📥",
        }
        return icons.get(self.change_source, "❓")

    def get_field_value(self, field_name: str) -> Any:
        """
        Get a specific field value from the snapshot.

        Args:
            field_name: Name of the field to retrieve

        Returns:
            The field value, or None if not present
        """
        return self.snapshot_json.get(field_name)

    def get_fields(self) -> list[str]:
        """
        Get list of all field names in the snapshot.

        Returns:
            List of field names
        """
        return list(self.snapshot_json.keys())

    def compare_to(self, other: "RecordSnapshot") -> dict[str, tuple[Any, Any]]:
        """
        Compare this snapshot to another and return differences.

        Args:
            other: Another RecordSnapshot to compare against

        Returns:
            Dictionary of {field_name: (this_value, other_value)} for changed fields
        """
        differences = {}
        all_fields = set(self.get_fields()) | set(other.get_fields())

        for field in all_fields:
            this_value = self.get_field_value(field)
            other_value = other.get_field_value(field)
            if this_value != other_value:
                differences[field] = (this_value, other_value)

        return differences

    @classmethod
    def create_for_person(
        cls,
        person: Any,  # Person model, but avoid circular import
        change_source: ChangeSource,
        description: str | None = None,
    ) -> "RecordSnapshot":
        """
        Create a snapshot from a Person entity.

        Args:
            person: Person model instance
            change_source: What triggered this snapshot
            description: Optional description of the change

        Returns:
            New RecordSnapshot instance
        """
        # Build JSON snapshot of person data
        snapshot_data = {
            "id": str(person.id),
            "full_name": person.full_name,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "title": person.title,
            "email": person.email,
            "linkedin_url": person.linkedin_url,
            "twitter_handle": person.twitter_handle,
            "notes": person.notes,
        }

        # Include related data if available
        if hasattr(person, "emails") and person.emails:
            snapshot_data["emails"] = [
                {"email": e.email, "label": e.label.value if e.label else None}
                for e in person.emails
            ]

        if hasattr(person, "phones") and person.phones:
            snapshot_data["phones"] = [
                {"phone": p.phone_number, "label": p.label.value if p.label else None}
                for p in person.phones
            ]

        if hasattr(person, "tags") and person.tags:
            snapshot_data["tag_ids"] = [str(t.id) for t in person.tags]

        return cls(
            entity_type="person",
            entity_id=person.id,
            snapshot_json=snapshot_data,
            change_source=change_source,
            change_description=description,
        )

    @classmethod
    def create_for_organization(
        cls,
        organization: Any,  # Organization model, but avoid circular import
        change_source: ChangeSource,
        description: str | None = None,
    ) -> "RecordSnapshot":
        """
        Create a snapshot from an Organization entity.

        Args:
            organization: Organization model instance
            change_source: What triggered this snapshot
            description: Optional description of the change

        Returns:
            New RecordSnapshot instance
        """
        # Build JSON snapshot of organization data
        snapshot_data = {
            "id": str(organization.id),
            "name": organization.name,
            "website": organization.website,
            "industry": organization.industry,
            "description": organization.description,
            "notes": organization.notes,
            "org_type": organization.org_type.value if organization.org_type else None,
        }

        # Include tags if available
        if hasattr(organization, "tags") and organization.tags:
            snapshot_data["tag_ids"] = [str(t.id) for t in organization.tags]

        return cls(
            entity_type="organization",
            entity_id=organization.id,
            snapshot_json=snapshot_data,
            change_source=change_source,
            change_description=description,
        )
