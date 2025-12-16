"""
Suggestion service for AI-generated profile updates.

Parses AI responses for structured suggestions and manages
the suggestion lifecycle (create, accept, reject).
"""

import json
import re
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    AISuggestion,
    AISuggestionStatus,
    AIConversation,
    AIDataAccessSettings,
    Person,
    Organization,
    RecordSnapshot,
    ChangeSource,
)
from app.models.ai_suggestion import (
    PERSON_SUGGESTABLE_FIELDS,
    ORGANIZATION_SUGGESTABLE_FIELDS,
)

logger = logging.getLogger(__name__)


class SuggestionService:
    """
    Service for managing AI-generated profile suggestions.

    Handles parsing AI responses, creating suggestions, and
    applying accepted suggestions to Person/Organization records.
    """

    def __init__(self, db: Session):
        """
        Initialize suggestion service.

        Args:
            db: Database session
        """
        self.db = db
        self._data_access: AIDataAccessSettings | None = None

    @property
    def data_access(self) -> AIDataAccessSettings:
        """Get data access settings (cached)."""
        if self._data_access is None:
            self._data_access = AIDataAccessSettings.get_settings(self.db)
        return self._data_access

    def parse_suggestions_from_response(
        self,
        response_content: str,
        conversation_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> list[AISuggestion]:
        """
        Parse AI response for structured suggestions.

        Looks for JSON blocks with suggestion format:
        ```json
        {
            "suggestions": [
                {
                    "field": "title",
                    "value": "Senior Software Engineer",
                    "confidence": 0.9,
                    "source": "https://linkedin.com/..."
                }
            ]
        }
        ```

        Args:
            response_content: AI response text
            conversation_id: Current conversation UUID
            entity_type: "person" or "organization"
            entity_id: UUID of the entity

        Returns:
            List of created AISuggestion instances (not yet committed)
        """
        suggestions = []

        # Try to find JSON block with suggestions
        json_match = re.search(
            r'```(?:json)?\s*(\{[\s\S]*?"suggestions"[\s\S]*?\})\s*```',
            response_content,
            re.IGNORECASE,
        )

        if json_match:
            try:
                data = json.loads(json_match.group(1))
                raw_suggestions = data.get("suggestions", [])

                for raw in raw_suggestions:
                    suggestion = self._create_suggestion_from_dict(
                        raw,
                        conversation_id,
                        entity_type,
                        entity_id,
                    )
                    if suggestion:
                        suggestions.append(suggestion)

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse suggestion JSON: {e}")

        return suggestions

    def _create_suggestion_from_dict(
        self,
        data: dict[str, Any],
        conversation_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> AISuggestion | None:
        """
        Create a suggestion from parsed dictionary.

        Args:
            data: Dictionary with field, value, confidence, source
            conversation_id: Conversation UUID
            entity_type: "person" or "organization"
            entity_id: Entity UUID

        Returns:
            AISuggestion or None if invalid
        """
        field_name = data.get("field")
        suggested_value = data.get("value")

        if not field_name or not suggested_value:
            return None

        # Validate field is allowed
        allowed_fields = (
            PERSON_SUGGESTABLE_FIELDS
            if entity_type == "person"
            else ORGANIZATION_SUGGESTABLE_FIELDS
        )

        if field_name not in allowed_fields:
            logger.warning(f"Field '{field_name}' not allowed for {entity_type}")
            return None

        # Get current value
        current_value = self._get_current_value(entity_type, entity_id, field_name)

        # Skip if value is unchanged
        if current_value == suggested_value:
            return None

        suggestion = AISuggestion(
            conversation_id=conversation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            current_value=current_value,
            suggested_value=str(suggested_value),
            confidence=data.get("confidence"),
            source_url=data.get("source"),
            status=AISuggestionStatus.pending,
        )

        return suggestion

    def _get_current_value(
        self,
        entity_type: str,
        entity_id: UUID,
        field_name: str,
    ) -> str | None:
        """
        Get current value of a field from the entity.

        Args:
            entity_type: "person" or "organization"
            entity_id: Entity UUID
            field_name: Field to get

        Returns:
            Current value as string or None
        """
        if entity_type == "person":
            entity = self.db.query(Person).filter_by(id=entity_id).first()
        else:
            entity = self.db.query(Organization).filter_by(id=entity_id).first()

        if not entity:
            return None

        value = getattr(entity, field_name, None)
        return str(value) if value is not None else None

    def create_suggestions(
        self,
        suggestions: list[AISuggestion],
    ) -> list[AISuggestion]:
        """
        Save suggestions to database.

        Args:
            suggestions: List of suggestion instances

        Returns:
            Saved suggestions
        """
        for suggestion in suggestions:
            self.db.add(suggestion)

        self.db.flush()
        return suggestions

    def get_pending_suggestions(
        self,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        conversation_id: UUID | None = None,
    ) -> list[AISuggestion]:
        """
        Get pending suggestions, optionally filtered.

        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            conversation_id: Filter by conversation

        Returns:
            List of pending suggestions
        """
        query = self.db.query(AISuggestion).filter(
            AISuggestion.status == AISuggestionStatus.pending
        )

        if entity_type:
            query = query.filter(AISuggestion.entity_type == entity_type)
        if entity_id:
            query = query.filter(AISuggestion.entity_id == entity_id)
        if conversation_id:
            query = query.filter(AISuggestion.conversation_id == conversation_id)

        return query.order_by(AISuggestion.created_at.desc()).all()

    def get_suggestion_by_id(self, suggestion_id: UUID) -> AISuggestion | None:
        """
        Get a specific suggestion by ID.

        Args:
            suggestion_id: Suggestion UUID

        Returns:
            AISuggestion or None
        """
        return self.db.query(AISuggestion).filter_by(id=suggestion_id).first()

    def accept_suggestion(self, suggestion_id: UUID) -> bool:
        """
        Accept a suggestion and apply it to the entity.

        Args:
            suggestion_id: Suggestion UUID

        Returns:
            True if accepted and applied, False otherwise
        """
        suggestion = self.get_suggestion_by_id(suggestion_id)
        if not suggestion or not suggestion.is_pending:
            return False

        # Apply the change
        success = self._apply_suggestion(suggestion)
        if not success:
            return False

        # Mark as accepted
        suggestion.accept()
        self.db.flush()

        return True

    def reject_suggestion(self, suggestion_id: UUID) -> bool:
        """
        Reject a suggestion.

        Args:
            suggestion_id: Suggestion UUID

        Returns:
            True if rejected, False otherwise
        """
        suggestion = self.get_suggestion_by_id(suggestion_id)
        if not suggestion or not suggestion.is_pending:
            return False

        suggestion.reject()
        self.db.flush()

        return True

    def _apply_suggestion(self, suggestion: AISuggestion) -> bool:
        """
        Apply a suggestion to the entity.

        Creates a snapshot before applying the change for undo functionality.

        Args:
            suggestion: The suggestion to apply

        Returns:
            True if applied successfully
        """
        if suggestion.entity_type == "person":
            entity = self.db.query(Person).filter_by(id=suggestion.entity_id).first()
        else:
            entity = self.db.query(Organization).filter_by(id=suggestion.entity_id).first()

        if not entity:
            logger.error(f"Entity not found: {suggestion.entity_type}:{suggestion.entity_id}")
            return False

        # Validate field exists on entity
        if not hasattr(entity, suggestion.field_name):
            logger.error(f"Field '{suggestion.field_name}' not found on {suggestion.entity_type}")
            return False

        # Create snapshot before applying change
        snapshot = self._create_snapshot_for_entity(
            entity,
            suggestion.entity_type,
            f"AI suggestion: {suggestion.field_name} changed from '{suggestion.current_value}' to '{suggestion.suggested_value}'",
        )
        if snapshot:
            self.db.add(snapshot)

        # Apply the change
        setattr(entity, suggestion.field_name, suggestion.suggested_value)

        logger.info(
            f"Applied suggestion: {suggestion.entity_type}.{suggestion.field_name} = "
            f"'{suggestion.suggested_value}' (was: '{suggestion.current_value}')"
        )

        return True

    def _create_snapshot_for_entity(
        self,
        entity: Person | Organization,
        entity_type: str,
        description: str,
    ) -> RecordSnapshot | None:
        """
        Create a snapshot of an entity before modification.

        Args:
            entity: The Person or Organization to snapshot
            entity_type: "person" or "organization"
            description: Description of the change being made

        Returns:
            RecordSnapshot instance or None if creation failed
        """
        try:
            if entity_type == "person":
                return RecordSnapshot.create_for_person(
                    entity,
                    change_source=ChangeSource.ai_suggestion,
                    description=description,
                )
            else:
                return RecordSnapshot.create_for_organization(
                    entity,
                    change_source=ChangeSource.ai_suggestion,
                    description=description,
                )
        except Exception as e:
            logger.error(f"Failed to create snapshot for {entity_type}: {e}")
            return None

    def accept_all_pending(
        self,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
    ) -> int:
        """
        Accept all pending suggestions for an entity.

        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID

        Returns:
            Number of suggestions accepted
        """
        suggestions = self.get_pending_suggestions(entity_type, entity_id)
        accepted_count = 0

        for suggestion in suggestions:
            if self.accept_suggestion(suggestion.id):
                accepted_count += 1

        return accepted_count

    def reject_all_pending(
        self,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
    ) -> int:
        """
        Reject all pending suggestions for an entity.

        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID

        Returns:
            Number of suggestions rejected
        """
        suggestions = self.get_pending_suggestions(entity_type, entity_id)
        rejected_count = 0

        for suggestion in suggestions:
            if self.reject_suggestion(suggestion.id):
                rejected_count += 1

        return rejected_count

    def get_suggestion_stats(
        self,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
    ) -> dict[str, int]:
        """
        Get suggestion statistics.

        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID

        Returns:
            Dictionary with counts by status
        """
        query = self.db.query(AISuggestion)

        if entity_type:
            query = query.filter(AISuggestion.entity_type == entity_type)
        if entity_id:
            query = query.filter(AISuggestion.entity_id == entity_id)

        suggestions = query.all()

        return {
            "pending": sum(1 for s in suggestions if s.is_pending),
            "accepted": sum(1 for s in suggestions if s.is_accepted),
            "rejected": sum(1 for s in suggestions if s.is_rejected),
            "total": len(suggestions),
        }


def get_suggestion_service(db: Session) -> SuggestionService:
    """
    Factory function to get suggestion service instance.

    Args:
        db: Database session

    Returns:
        SuggestionService instance
    """
    return SuggestionService(db)
