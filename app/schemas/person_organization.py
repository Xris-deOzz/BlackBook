"""
Pydantic schemas for PersonOrganization (person-to-organization links).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PersonOrganizationBase(BaseModel):
    """Base schema for PersonOrganization."""
    organization_id: UUID = Field(..., description="ID of the organization to link")
    relationship: str = Field("affiliated_with", description="Relationship type")
    role: Optional[str] = Field(None, max_length=300, description="Role at organization")
    is_current: bool = Field(True, description="Is this a current affiliation?")
    notes: Optional[str] = Field(None, description="Additional notes")


class PersonOrganizationCreate(PersonOrganizationBase):
    """Schema for creating a PersonOrganization."""
    pass


class PersonOrganizationUpdate(BaseModel):
    """Schema for updating a PersonOrganization."""
    relationship: Optional[str] = None
    role: Optional[str] = Field(None, max_length=300)
    is_current: Optional[bool] = None
    notes: Optional[str] = None


class OrganizationInfo(BaseModel):
    """Nested organization info for response."""
    id: UUID
    name: str

    class Config:
        from_attributes = True


class PersonOrganizationResponse(BaseModel):
    """Schema for PersonOrganization response."""
    id: UUID
    person_id: UUID
    organization_id: UUID
    relationship: str
    role: Optional[str]
    is_current: bool
    notes: Optional[str]
    created_at: datetime
    organization: OrganizationInfo

    class Config:
        from_attributes = True
