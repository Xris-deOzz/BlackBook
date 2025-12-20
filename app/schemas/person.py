"""
Pydantic schemas for Person-related operations.
"""

from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DeleteScope(str, Enum):
    """Scope for delete operations - determines what gets deleted."""
    blackbook_only = "blackbook_only"  # Delete only from BlackBook
    google_only = "google_only"        # Delete only from Google Contacts
    both = "both"                      # Delete from both (default)


class PersonDeleteRequest(BaseModel):
    """Request schema for deleting a person with scope."""
    scope: DeleteScope = Field(
        default=DeleteScope.both,
        description="What to delete: blackbook_only, google_only, or both"
    )


class PersonBulkDeleteRequest(BaseModel):
    """Request schema for bulk deleting persons with scope."""
    ids: List[str] = Field(..., description="List of person UUIDs to delete")
    scope: DeleteScope = Field(
        default=DeleteScope.both,
        description="What to delete: blackbook_only, google_only, or both"
    )


class DeleteResult(BaseModel):
    """Result of a delete operation."""
    success: bool
    person_id: UUID
    person_name: str
    blackbook_deleted: bool = False
    google_deleted: bool = False
    google_resource_name: Optional[str] = None
    error: Optional[str] = None


class BulkDeleteResult(BaseModel):
    """Result of a bulk delete operation."""
    success: bool
    total_requested: int
    blackbook_deleted: int = 0
    google_deleted: int = 0
    failed: int = 0
    errors: List[str] = Field(default_factory=list)
    results: List[DeleteResult] = Field(default_factory=list)
