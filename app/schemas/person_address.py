"""
Pydantic schemas for PersonAddress.
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PersonAddressBase(BaseModel):
    """Base schema for PersonAddress."""
    address_type: Literal["home", "work"] = Field(..., description="Address type: home or work")
    street: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    zip: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)


class PersonAddressCreate(PersonAddressBase):
    """Schema for creating a PersonAddress."""
    pass


class PersonAddressUpdate(BaseModel):
    """Schema for updating a PersonAddress."""
    address_type: Optional[Literal["home", "work"]] = None
    street: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    zip: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)


class PersonAddressResponse(PersonAddressBase):
    """Schema for PersonAddress response."""
    id: UUID
    person_id: UUID
    created_at: datetime
    updated_at: datetime
    full_address: str = Field(..., description="Formatted full address")

    class Config:
        from_attributes = True
