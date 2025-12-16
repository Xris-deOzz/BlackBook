"""
Pydantic schemas for PersonEducation.
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# Degree type options
DegreeType = Literal["BA", "BS", "MA", "MS", "MBA", "PhD", "JD", "MD", "Other"]


class PersonEducationBase(BaseModel):
    """Base schema for PersonEducation."""
    school_name: str = Field(..., max_length=255, description="Name of the school/university")
    degree_type: Optional[DegreeType] = Field(None, description="Type of degree")
    field_of_study: Optional[str] = Field(None, max_length=255, description="Field of study/major")
    graduation_year: Optional[int] = Field(None, ge=1900, le=2100, description="Year of graduation")


class PersonEducationCreate(PersonEducationBase):
    """Schema for creating a PersonEducation."""
    pass


class PersonEducationUpdate(BaseModel):
    """Schema for updating a PersonEducation."""
    school_name: Optional[str] = Field(None, max_length=255)
    degree_type: Optional[DegreeType] = None
    field_of_study: Optional[str] = Field(None, max_length=255)
    graduation_year: Optional[int] = Field(None, ge=1900, le=2100)


class PersonEducationResponse(PersonEducationBase):
    """Schema for PersonEducation response."""
    id: UUID
    person_id: UUID
    created_at: datetime
    updated_at: datetime
    display_text: str = Field(..., description="Formatted education display text")

    class Config:
        from_attributes = True
