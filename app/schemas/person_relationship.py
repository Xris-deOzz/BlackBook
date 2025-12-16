"""
Pydantic schemas for PersonRelationship.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PersonRelationshipBase(BaseModel):
    """Base schema for PersonRelationship."""
    related_person_id: UUID = Field(..., description="ID of the related person")
    relationship_type_id: Optional[UUID] = Field(None, description="Type of relationship")
    context_organization_id: Optional[UUID] = Field(None, description="Context organization (for 'Worked Together')")
    context_text: Optional[str] = Field(None, max_length=255, description="Additional context")


class PersonRelationshipCreate(PersonRelationshipBase):
    """Schema for creating a PersonRelationship."""
    pass


class PersonRelationshipUpdate(BaseModel):
    """Schema for updating a PersonRelationship."""
    relationship_type_id: Optional[UUID] = None
    context_organization_id: Optional[UUID] = None
    context_text: Optional[str] = Field(None, max_length=255)


class RelationshipTypeInfo(BaseModel):
    """Nested relationship type info for response."""
    id: UUID
    name: str
    inverse_name: Optional[str] = None
    requires_organization: bool = False

    class Config:
        from_attributes = True


class PersonInfo(BaseModel):
    """Nested person info for response."""
    id: UUID
    full_name: str
    title: Optional[str] = None
    profile_picture: Optional[str] = None

    class Config:
        from_attributes = True


class OrganizationContextInfo(BaseModel):
    """Nested organization info for relationship context."""
    id: UUID
    name: str

    class Config:
        from_attributes = True


class PersonRelationshipResponse(BaseModel):
    """Schema for PersonRelationship response."""
    id: UUID
    person_id: UUID
    related_person_id: UUID
    context_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    relationship_type: Optional[RelationshipTypeInfo] = None
    related_person: PersonInfo
    context_organization: Optional[OrganizationContextInfo] = None

    class Config:
        from_attributes = True
