"""
Pydantic schemas for PersonWebsite.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class PersonWebsiteBase(BaseModel):
    """Base schema for PersonWebsite."""
    url: str = Field(..., max_length=500, description="Website URL")
    label: Optional[str] = Field(None, max_length=50, description="Label (e.g., Blog, Portfolio)")


class PersonWebsiteCreate(PersonWebsiteBase):
    """Schema for creating a PersonWebsite."""
    pass


class PersonWebsiteUpdate(BaseModel):
    """Schema for updating a PersonWebsite."""
    url: Optional[str] = Field(None, max_length=500)
    label: Optional[str] = Field(None, max_length=50)


class PersonWebsiteResponse(PersonWebsiteBase):
    """Schema for PersonWebsite response."""
    id: UUID
    person_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
