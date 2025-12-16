"""
Pydantic schemas for AffiliationType lookup table.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AffiliationTypeBase(BaseModel):
    """Base schema for AffiliationType."""
    name: str = Field(..., max_length=100, description="Affiliation type name")


class AffiliationTypeCreate(AffiliationTypeBase):
    """Schema for creating a custom AffiliationType."""
    pass


class AffiliationTypeResponse(AffiliationTypeBase):
    """Schema for AffiliationType response."""
    id: UUID
    is_system: bool = Field(..., description="True if system-defined, False if user-created")
    created_at: datetime

    class Config:
        from_attributes = True
