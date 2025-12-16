"""
Pydantic schemas for RelationshipType lookup table.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RelationshipTypeResponse(BaseModel):
    """Schema for RelationshipType response."""
    id: UUID
    name: str = Field(..., description="Relationship type name")
    inverse_name: Optional[str] = Field(None, description="Inverse relationship name")
    requires_organization: bool = Field(False, description="Does this relationship require org context?")
    is_system: bool = Field(True, description="True if system-defined")
    created_at: datetime

    class Config:
        from_attributes = True
