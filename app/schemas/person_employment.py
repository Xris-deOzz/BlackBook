"""
Pydantic schemas for PersonEmployment.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PersonEmploymentBase(BaseModel):
    """Base schema for PersonEmployment."""
    organization_id: Optional[UUID] = Field(None, description="Link to organization if in system")
    organization_name: Optional[str] = Field(None, max_length=255, description="Organization name (fallback)")
    title: Optional[str] = Field(None, max_length=255, description="Job title/role")
    affiliation_type_id: Optional[UUID] = Field(None, description="Type of affiliation")
    is_current: bool = Field(False, description="Is this current employment?")


class PersonEmploymentCreate(PersonEmploymentBase):
    """Schema for creating a PersonEmployment."""
    pass


class PersonEmploymentUpdate(BaseModel):
    """Schema for updating a PersonEmployment."""
    organization_id: Optional[UUID] = None
    organization_name: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    affiliation_type_id: Optional[UUID] = None
    is_current: Optional[bool] = None


class AffiliationTypeInfo(BaseModel):
    """Nested affiliation type info for response."""
    id: UUID
    name: str

    class Config:
        from_attributes = True


class OrganizationInfo(BaseModel):
    """Nested organization info for response."""
    id: UUID
    name: str

    class Config:
        from_attributes = True


class PersonEmploymentResponse(PersonEmploymentBase):
    """Schema for PersonEmployment response."""
    id: UUID
    person_id: UUID
    created_at: datetime
    updated_at: datetime
    display_organization: str = Field(..., description="Organization name for display")
    affiliation_type: Optional[AffiliationTypeInfo] = None
    organization: Optional[OrganizationInfo] = None

    class Config:
        from_attributes = True
