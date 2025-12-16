"""
Pydantic schemas for OrganizationOffice.
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationOfficeBase(BaseModel):
    """Base schema for OrganizationOffice."""
    office_type: Literal["headquarters", "regional", "satellite", "branch"] = Field(
        "regional", description="Type of office location"
    )
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    is_headquarters: bool = Field(False, description="Is this the headquarters")


class OrganizationOfficeCreate(OrganizationOfficeBase):
    """Schema for creating an OrganizationOffice."""
    pass


class OrganizationOfficeUpdate(BaseModel):
    """Schema for updating an OrganizationOffice."""
    office_type: Optional[Literal["headquarters", "regional", "satellite", "branch"]] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    is_headquarters: Optional[bool] = None


class OrganizationOfficeResponse(OrganizationOfficeBase):
    """Schema for OrganizationOffice response."""
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime
    display_location: str = Field(..., description="Formatted location string")

    class Config:
        from_attributes = True
