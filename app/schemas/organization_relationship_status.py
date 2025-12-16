"""
Pydantic schemas for OrganizationRelationshipStatus.
"""

from datetime import datetime, date
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationRelationshipStatusBase(BaseModel):
    """Base schema for OrganizationRelationshipStatus."""
    primary_contact_id: Optional[UUID] = Field(None, description="ID of primary contact person")
    relationship_warmth: Optional[Literal["hot", "warm", "met_once", "cold", "unknown"]] = Field(
        "unknown", description="Warmth level of the relationship"
    )
    intro_available_via_id: Optional[UUID] = Field(None, description="ID of person who can make intro")
    next_followup_date: Optional[date] = Field(None, description="Next follow-up date")
    notes: Optional[str] = Field(None, description="Notes about the relationship")


class OrganizationRelationshipStatusCreate(OrganizationRelationshipStatusBase):
    """Schema for creating an OrganizationRelationshipStatus."""
    pass


class OrganizationRelationshipStatusUpdate(BaseModel):
    """Schema for updating an OrganizationRelationshipStatus."""
    primary_contact_id: Optional[UUID] = None
    relationship_warmth: Optional[Literal["hot", "warm", "met_once", "cold", "unknown"]] = None
    intro_available_via_id: Optional[UUID] = None
    next_followup_date: Optional[date] = None
    notes: Optional[str] = None


class PersonSummary(BaseModel):
    """Minimal person info for embedding in responses."""
    id: UUID
    full_name: str

    class Config:
        from_attributes = True


class OrganizationRelationshipStatusResponse(OrganizationRelationshipStatusBase):
    """Schema for OrganizationRelationshipStatus response."""
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime
    warmth_display: str = Field(..., description="Human-readable warmth level")
    warmth_emoji: str = Field(..., description="Emoji for warmth level")
    primary_contact: Optional[PersonSummary] = None
    intro_available_via: Optional[PersonSummary] = None

    class Config:
        from_attributes = True
