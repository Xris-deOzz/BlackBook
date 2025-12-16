"""
Person Details API Router.

Handles CRUD operations for person-related entities:
- Websites
- Addresses
- Education
- Employment
- Relationships
- Lookup tables (affiliation types, relationship types)
- Profile picture upload/delete
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Person, Organization, PersonOrganization
from app.models.person_website import PersonWebsite
from app.models.person_address import PersonAddress
from app.models.person_education import PersonEducation
from app.models.person_employment import PersonEmployment
from app.models.person_relationship import PersonRelationship
from app.models.affiliation_type import AffiliationType
from app.models.relationship_type import RelationshipType
from app.models.organization import RelationshipType as OrgRelationshipType

from app.schemas.person_website import (
    PersonWebsiteCreate,
    PersonWebsiteUpdate,
    PersonWebsiteResponse,
)
from app.schemas.person_address import (
    PersonAddressCreate,
    PersonAddressUpdate,
    PersonAddressResponse,
)
from app.schemas.person_education import (
    PersonEducationCreate,
    PersonEducationUpdate,
    PersonEducationResponse,
)
from app.schemas.person_employment import (
    PersonEmploymentCreate,
    PersonEmploymentUpdate,
    PersonEmploymentResponse,
)
from app.schemas.person_relationship import (
    PersonRelationshipCreate,
    PersonRelationshipUpdate,
    PersonRelationshipResponse,
)
from app.schemas.affiliation_type import (
    AffiliationTypeCreate,
    AffiliationTypeResponse,
)
from app.schemas.relationship_type import RelationshipTypeResponse
from app.schemas.person_organization import (
    PersonOrganizationCreate,
    PersonOrganizationUpdate,
    PersonOrganizationResponse,
)


router = APIRouter(prefix="/api", tags=["person-details"])
templates = Jinja2Templates(directory="app/templates")


# =============================================================================
# Profile Picture Upload Configuration
# =============================================================================

UPLOAD_DIR = Path("app/static/uploads/profile_pictures")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


# =============================================================================
# Helper Functions
# =============================================================================


def get_person_or_404(db: Session, person_id: UUID) -> Person:
    """Get person by ID or raise 404."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


def delete_profile_picture_file(file_path: str | None) -> None:
    """Delete the profile picture file from disk if it exists."""
    if not file_path:
        return
    # Handle both relative paths (/static/...) and full paths
    if file_path.startswith("/static/"):
        file_path = file_path.replace("/static/", "app/static/")
    full_path = Path(file_path)
    if full_path.exists():
        full_path.unlink()


# =============================================================================
# Profile Picture Upload/Delete
# =============================================================================


@router.post("/people/{person_id}/profile-picture")
async def upload_profile_picture(
    request: Request,
    person_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a profile picture for a person.

    Accepts: jpg, jpeg, png, gif, webp (max 5MB)
    Returns: HTML partial for HTMX, JSON otherwise
    """
    person = get_person_or_404(db, person_id)

    # Validate file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file and validate size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # Delete existing profile picture if any
    delete_profile_picture_file(person.profile_picture)

    # Create filename using person ID to avoid collisions
    filename = f"{person_id}{file_ext}"
    file_path = UPLOAD_DIR / filename

    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Save the file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Update person record with the URL path (not filesystem path)
    url_path = f"/static/uploads/profile_pictures/{filename}"
    person.profile_picture = url_path
    db.commit()
    db.refresh(person)

    # Return HTML for HTMX requests, JSON otherwise
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/sections/_profile_picture.html",
            {"request": request, "person": person}
        )

    return {
        "message": "Profile picture uploaded successfully",
        "profile_picture": url_path
    }


@router.delete("/people/{person_id}/profile-picture")
async def delete_profile_picture(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete the profile picture for a person."""
    person = get_person_or_404(db, person_id)

    if not person.profile_picture:
        raise HTTPException(status_code=404, detail="No profile picture to delete")

    # Delete the file from disk
    delete_profile_picture_file(person.profile_picture)

    # Clear the database field
    person.profile_picture = None
    db.commit()
    db.refresh(person)

    # Return HTML for HTMX requests, 204 No Content otherwise
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/sections/_profile_picture.html",
            {"request": request, "person": person}
        )

    return JSONResponse(status_code=204, content=None)


# =============================================================================
# Person Websites CRUD
# =============================================================================


@router.get("/people/{person_id}/websites", response_model=List[PersonWebsiteResponse])
async def list_person_websites(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all websites for a person."""
    get_person_or_404(db, person_id)
    websites = (
        db.query(PersonWebsite)
        .filter(PersonWebsite.person_id == person_id)
        .order_by(PersonWebsite.created_at)
        .all()
    )
    return websites


@router.post("/people/{person_id}/websites", response_model=PersonWebsiteResponse, status_code=201)
async def create_person_website(
    person_id: UUID,
    data: PersonWebsiteCreate,
    db: Session = Depends(get_db),
):
    """Create a new website for a person (max 3)."""
    get_person_or_404(db, person_id)

    # Check max limit
    count = db.query(PersonWebsite).filter(PersonWebsite.person_id == person_id).count()
    if count >= 3:
        raise HTTPException(status_code=400, detail="Maximum 3 websites allowed per person")

    website = PersonWebsite(
        person_id=person_id,
        url=data.url,
        label=data.label,
    )
    db.add(website)
    db.commit()
    db.refresh(website)
    return website


@router.put("/people/{person_id}/websites/{website_id}", response_model=PersonWebsiteResponse)
async def update_person_website(
    person_id: UUID,
    website_id: UUID,
    data: PersonWebsiteUpdate,
    db: Session = Depends(get_db),
):
    """Update a website."""
    website = (
        db.query(PersonWebsite)
        .filter(PersonWebsite.id == website_id, PersonWebsite.person_id == person_id)
        .first()
    )
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    if data.url is not None:
        website.url = data.url
    if data.label is not None:
        website.label = data.label

    db.commit()
    db.refresh(website)
    return website


@router.delete("/people/{person_id}/websites/{website_id}", status_code=204)
async def delete_person_website(
    person_id: UUID,
    website_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a website."""
    website = (
        db.query(PersonWebsite)
        .filter(PersonWebsite.id == website_id, PersonWebsite.person_id == person_id)
        .first()
    )
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    db.delete(website)
    db.commit()
    return None


# =============================================================================
# Person Addresses CRUD
# =============================================================================


@router.get("/people/{person_id}/addresses", response_model=List[PersonAddressResponse])
async def list_person_addresses(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all addresses for a person."""
    get_person_or_404(db, person_id)
    addresses = (
        db.query(PersonAddress)
        .filter(PersonAddress.person_id == person_id)
        .order_by(PersonAddress.address_type)
        .all()
    )
    return addresses


@router.post("/people/{person_id}/addresses", response_model=PersonAddressResponse, status_code=201)
async def create_person_address(
    person_id: UUID,
    data: PersonAddressCreate,
    db: Session = Depends(get_db),
):
    """Create a new address for a person (max 2: home and work)."""
    get_person_or_404(db, person_id)

    # Check if address type already exists
    existing = (
        db.query(PersonAddress)
        .filter(PersonAddress.person_id == person_id, PersonAddress.address_type == data.address_type)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Address of type '{data.address_type}' already exists for this person"
        )

    # Check max limit
    count = db.query(PersonAddress).filter(PersonAddress.person_id == person_id).count()
    if count >= 2:
        raise HTTPException(status_code=400, detail="Maximum 2 addresses allowed per person")

    address = PersonAddress(
        person_id=person_id,
        address_type=data.address_type,
        street=data.street,
        city=data.city,
        state=data.state,
        zip=data.zip,
        country=data.country,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.put("/people/{person_id}/addresses/{address_id}", response_model=PersonAddressResponse)
async def update_person_address(
    person_id: UUID,
    address_id: UUID,
    data: PersonAddressUpdate,
    db: Session = Depends(get_db),
):
    """Update an address."""
    address = (
        db.query(PersonAddress)
        .filter(PersonAddress.id == address_id, PersonAddress.person_id == person_id)
        .first()
    )
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    # Check for type conflict if changing type
    if data.address_type is not None and data.address_type != address.address_type:
        existing = (
            db.query(PersonAddress)
            .filter(
                PersonAddress.person_id == person_id,
                PersonAddress.address_type == data.address_type,
                PersonAddress.id != address_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Address of type '{data.address_type}' already exists for this person"
            )
        address.address_type = data.address_type

    if data.street is not None:
        address.street = data.street
    if data.city is not None:
        address.city = data.city
    if data.state is not None:
        address.state = data.state
    if data.zip is not None:
        address.zip = data.zip
    if data.country is not None:
        address.country = data.country

    db.commit()
    db.refresh(address)
    return address


@router.delete("/people/{person_id}/addresses/{address_id}", status_code=204)
async def delete_person_address(
    person_id: UUID,
    address_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an address."""
    address = (
        db.query(PersonAddress)
        .filter(PersonAddress.id == address_id, PersonAddress.person_id == person_id)
        .first()
    )
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    db.delete(address)
    db.commit()
    return None


# =============================================================================
# Person Education CRUD
# =============================================================================


@router.get("/people/{person_id}/education", response_model=List[PersonEducationResponse])
async def list_person_education(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all education entries for a person."""
    get_person_or_404(db, person_id)
    education = (
        db.query(PersonEducation)
        .filter(PersonEducation.person_id == person_id)
        .order_by(PersonEducation.graduation_year.desc().nullslast())
        .all()
    )
    return education


@router.post("/people/{person_id}/education", response_model=PersonEducationResponse, status_code=201)
async def create_person_education(
    person_id: UUID,
    data: PersonEducationCreate,
    db: Session = Depends(get_db),
):
    """Create a new education entry for a person (max 6)."""
    get_person_or_404(db, person_id)

    # Check max limit
    count = db.query(PersonEducation).filter(PersonEducation.person_id == person_id).count()
    if count >= 6:
        raise HTTPException(status_code=400, detail="Maximum 6 education entries allowed per person")

    education = PersonEducation(
        person_id=person_id,
        school_name=data.school_name,
        degree_type=data.degree_type,
        field_of_study=data.field_of_study,
        graduation_year=data.graduation_year,
    )
    db.add(education)
    db.commit()
    db.refresh(education)
    return education


@router.put("/people/{person_id}/education/{education_id}", response_model=PersonEducationResponse)
async def update_person_education(
    person_id: UUID,
    education_id: UUID,
    data: PersonEducationUpdate,
    db: Session = Depends(get_db),
):
    """Update an education entry."""
    education = (
        db.query(PersonEducation)
        .filter(PersonEducation.id == education_id, PersonEducation.person_id == person_id)
        .first()
    )
    if not education:
        raise HTTPException(status_code=404, detail="Education entry not found")

    if data.school_name is not None:
        education.school_name = data.school_name
    if data.degree_type is not None:
        education.degree_type = data.degree_type
    if data.field_of_study is not None:
        education.field_of_study = data.field_of_study
    if data.graduation_year is not None:
        education.graduation_year = data.graduation_year

    db.commit()
    db.refresh(education)
    return education


@router.delete("/people/{person_id}/education/{education_id}", status_code=204)
async def delete_person_education(
    person_id: UUID,
    education_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an education entry."""
    education = (
        db.query(PersonEducation)
        .filter(PersonEducation.id == education_id, PersonEducation.person_id == person_id)
        .first()
    )
    if not education:
        raise HTTPException(status_code=404, detail="Education entry not found")

    db.delete(education)
    db.commit()
    return None


# =============================================================================
# Person Employment CRUD
# =============================================================================


@router.get("/people/{person_id}/employment", response_model=List[PersonEmploymentResponse])
async def list_person_employment(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all employment entries for a person."""
    get_person_or_404(db, person_id)
    employment = (
        db.query(PersonEmployment)
        .options(
            joinedload(PersonEmployment.organization),
            joinedload(PersonEmployment.affiliation_type),
        )
        .filter(PersonEmployment.person_id == person_id)
        .order_by(PersonEmployment.is_current.desc(), PersonEmployment.created_at.desc())
        .all()
    )
    return employment


@router.post("/people/{person_id}/employment", response_model=PersonEmploymentResponse, status_code=201)
async def create_person_employment(
    person_id: UUID,
    data: PersonEmploymentCreate,
    db: Session = Depends(get_db),
):
    """Create a new employment entry for a person (max 10)."""
    get_person_or_404(db, person_id)

    # Check max limit
    count = db.query(PersonEmployment).filter(PersonEmployment.person_id == person_id).count()
    if count >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 employment entries allowed per person")

    employment = PersonEmployment(
        person_id=person_id,
        organization_id=data.organization_id,
        organization_name=data.organization_name,
        title=data.title,
        affiliation_type_id=data.affiliation_type_id,
        is_current=data.is_current,
    )
    db.add(employment)
    db.commit()

    # Reload with relationships
    employment = (
        db.query(PersonEmployment)
        .options(
            joinedload(PersonEmployment.organization),
            joinedload(PersonEmployment.affiliation_type),
        )
        .filter(PersonEmployment.id == employment.id)
        .first()
    )
    return employment


@router.put("/people/{person_id}/employment/{employment_id}", response_model=PersonEmploymentResponse)
async def update_person_employment(
    person_id: UUID,
    employment_id: UUID,
    data: PersonEmploymentUpdate,
    db: Session = Depends(get_db),
):
    """Update an employment entry."""
    employment = (
        db.query(PersonEmployment)
        .filter(PersonEmployment.id == employment_id, PersonEmployment.person_id == person_id)
        .first()
    )
    if not employment:
        raise HTTPException(status_code=404, detail="Employment entry not found")

    if data.organization_id is not None:
        employment.organization_id = data.organization_id
    if data.organization_name is not None:
        employment.organization_name = data.organization_name
    if data.title is not None:
        employment.title = data.title
    if data.affiliation_type_id is not None:
        employment.affiliation_type_id = data.affiliation_type_id
    if data.is_current is not None:
        employment.is_current = data.is_current

    db.commit()

    # Reload with relationships
    employment = (
        db.query(PersonEmployment)
        .options(
            joinedload(PersonEmployment.organization),
            joinedload(PersonEmployment.affiliation_type),
        )
        .filter(PersonEmployment.id == employment_id)
        .first()
    )
    return employment


@router.delete("/people/{person_id}/employment/{employment_id}", status_code=204)
async def delete_person_employment(
    person_id: UUID,
    employment_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an employment entry."""
    employment = (
        db.query(PersonEmployment)
        .filter(PersonEmployment.id == employment_id, PersonEmployment.person_id == person_id)
        .first()
    )
    if not employment:
        raise HTTPException(status_code=404, detail="Employment entry not found")

    db.delete(employment)
    db.commit()
    return None


# =============================================================================
# Person Relationships CRUD
# =============================================================================


@router.get("/people/{person_id}/relationships", response_model=List[PersonRelationshipResponse])
async def list_person_relationships(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all relationships for a person (outgoing relationships)."""
    get_person_or_404(db, person_id)
    relationships = (
        db.query(PersonRelationship)
        .options(
            joinedload(PersonRelationship.related_person),
            joinedload(PersonRelationship.relationship_type),
            joinedload(PersonRelationship.context_organization),
        )
        .filter(PersonRelationship.person_id == person_id)
        .order_by(PersonRelationship.created_at.desc())
        .all()
    )
    return relationships


@router.post("/people/{person_id}/relationships", response_model=PersonRelationshipResponse, status_code=201)
async def create_person_relationship(
    person_id: UUID,
    data: PersonRelationshipCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new relationship for a person.

    Also creates the inverse relationship if the relationship type has an inverse.
    """
    person = get_person_or_404(db, person_id)

    # Verify related person exists
    related_person = db.query(Person).filter(Person.id == data.related_person_id).first()
    if not related_person:
        raise HTTPException(status_code=400, detail="Related person not found")

    # Can't create relationship with self
    if person_id == data.related_person_id:
        raise HTTPException(status_code=400, detail="Cannot create relationship with self")

    # Check for existing relationship
    existing = (
        db.query(PersonRelationship)
        .filter(
            PersonRelationship.person_id == person_id,
            PersonRelationship.related_person_id == data.related_person_id,
            PersonRelationship.relationship_type_id == data.relationship_type_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")

    # Get relationship type for inverse handling
    rel_type = None
    inverse_type = None
    if data.relationship_type_id:
        rel_type = db.query(RelationshipType).filter(RelationshipType.id == data.relationship_type_id).first()
        if rel_type and rel_type.inverse_name:
            # Find the inverse relationship type
            inverse_type = (
                db.query(RelationshipType)
                .filter(RelationshipType.name == rel_type.inverse_name)
                .first()
            )

    # Create the primary relationship
    relationship = PersonRelationship(
        person_id=person_id,
        related_person_id=data.related_person_id,
        relationship_type_id=data.relationship_type_id,
        context_organization_id=data.context_organization_id,
        context_text=data.context_text,
    )
    db.add(relationship)

    # Create inverse relationship if applicable
    if inverse_type:
        # Check if inverse already exists
        existing_inverse = (
            db.query(PersonRelationship)
            .filter(
                PersonRelationship.person_id == data.related_person_id,
                PersonRelationship.related_person_id == person_id,
                PersonRelationship.relationship_type_id == inverse_type.id,
            )
            .first()
        )
        if not existing_inverse:
            inverse_relationship = PersonRelationship(
                person_id=data.related_person_id,
                related_person_id=person_id,
                relationship_type_id=inverse_type.id,
                context_organization_id=data.context_organization_id,
                context_text=data.context_text,
            )
            db.add(inverse_relationship)

    db.commit()

    # Reload with relationships
    relationship = (
        db.query(PersonRelationship)
        .options(
            joinedload(PersonRelationship.related_person),
            joinedload(PersonRelationship.relationship_type),
            joinedload(PersonRelationship.context_organization),
        )
        .filter(PersonRelationship.id == relationship.id)
        .first()
    )
    return relationship


@router.put("/people/{person_id}/relationships/{relationship_id}", response_model=PersonRelationshipResponse)
async def update_person_relationship(
    person_id: UUID,
    relationship_id: UUID,
    data: PersonRelationshipUpdate,
    db: Session = Depends(get_db),
):
    """Update a relationship."""
    relationship = (
        db.query(PersonRelationship)
        .filter(PersonRelationship.id == relationship_id, PersonRelationship.person_id == person_id)
        .first()
    )
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    if data.relationship_type_id is not None:
        relationship.relationship_type_id = data.relationship_type_id
    if data.context_organization_id is not None:
        relationship.context_organization_id = data.context_organization_id
    if data.context_text is not None:
        relationship.context_text = data.context_text

    db.commit()

    # Reload with relationships
    relationship = (
        db.query(PersonRelationship)
        .options(
            joinedload(PersonRelationship.related_person),
            joinedload(PersonRelationship.relationship_type),
            joinedload(PersonRelationship.context_organization),
        )
        .filter(PersonRelationship.id == relationship_id)
        .first()
    )
    return relationship


@router.delete("/people/{person_id}/relationships/{relationship_id}", status_code=204)
async def delete_person_relationship(
    person_id: UUID,
    relationship_id: UUID,
    delete_inverse: bool = Query(True, description="Also delete inverse relationship"),
    db: Session = Depends(get_db),
):
    """Delete a relationship (and optionally its inverse)."""
    relationship = (
        db.query(PersonRelationship)
        .options(joinedload(PersonRelationship.relationship_type))
        .filter(PersonRelationship.id == relationship_id, PersonRelationship.person_id == person_id)
        .first()
    )
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Find and delete inverse if requested
    if delete_inverse and relationship.relationship_type and relationship.relationship_type.inverse_name:
        inverse_type = (
            db.query(RelationshipType)
            .filter(RelationshipType.name == relationship.relationship_type.inverse_name)
            .first()
        )
        if inverse_type:
            inverse = (
                db.query(PersonRelationship)
                .filter(
                    PersonRelationship.person_id == relationship.related_person_id,
                    PersonRelationship.related_person_id == relationship.person_id,
                    PersonRelationship.relationship_type_id == inverse_type.id,
                )
                .first()
            )
            if inverse:
                db.delete(inverse)

    db.delete(relationship)
    db.commit()
    return None


# =============================================================================
# Lookup Tables (Affiliation Types, Relationship Types)
# =============================================================================


@router.get("/affiliation-types", response_model=List[AffiliationTypeResponse])
async def list_affiliation_types(
    db: Session = Depends(get_db),
):
    """Get all affiliation types (system + custom)."""
    types = (
        db.query(AffiliationType)
        .order_by(AffiliationType.is_system.desc(), AffiliationType.name)
        .all()
    )
    return types


@router.post("/affiliation-types", response_model=AffiliationTypeResponse, status_code=201)
async def create_affiliation_type(
    data: AffiliationTypeCreate,
    db: Session = Depends(get_db),
):
    """Create a custom affiliation type."""
    # Check for duplicate name
    existing = db.query(AffiliationType).filter(AffiliationType.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Affiliation type with this name already exists")

    affiliation_type = AffiliationType(
        name=data.name,
        is_system=False,
    )
    db.add(affiliation_type)
    db.commit()
    db.refresh(affiliation_type)
    return affiliation_type


@router.get("/relationship-types", response_model=List[RelationshipTypeResponse])
async def list_relationship_types(
    db: Session = Depends(get_db),
):
    """Get all relationship types."""
    types = (
        db.query(RelationshipType)
        .order_by(RelationshipType.name)
        .all()
    )
    return types


# =============================================================================
# Person Organizations CRUD (link person to organization)
# =============================================================================


@router.get("/people/{person_id}/organizations", response_model=List[PersonOrganizationResponse])
async def list_person_organizations(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all organization links for a person."""
    get_person_or_404(db, person_id)
    orgs = (
        db.query(PersonOrganization)
        .options(joinedload(PersonOrganization.organization))
        .filter(PersonOrganization.person_id == person_id)
        .order_by(PersonOrganization.is_current.desc(), PersonOrganization.created_at.desc())
        .all()
    )
    return orgs


@router.post("/people/{person_id}/organizations", response_model=PersonOrganizationResponse, status_code=201)
async def create_person_organization(
    person_id: UUID,
    data: PersonOrganizationCreate,
    db: Session = Depends(get_db),
):
    """Link a person to an organization."""
    get_person_or_404(db, person_id)

    # Verify organization exists
    org = db.query(Organization).filter(Organization.id == data.organization_id).first()
    if not org:
        raise HTTPException(status_code=400, detail="Organization not found")

    # Check for existing link with same relationship type
    existing = (
        db.query(PersonOrganization)
        .filter(
            PersonOrganization.person_id == person_id,
            PersonOrganization.organization_id == data.organization_id,
            PersonOrganization.relationship == OrgRelationshipType(data.relationship),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Person is already linked to this organization with this relationship type")

    person_org = PersonOrganization(
        person_id=person_id,
        organization_id=data.organization_id,
        relationship=OrgRelationshipType(data.relationship),
        role=data.role,
        is_current=data.is_current,
        notes=data.notes,
    )
    db.add(person_org)
    db.commit()

    # Reload with organization
    person_org = (
        db.query(PersonOrganization)
        .options(joinedload(PersonOrganization.organization))
        .filter(PersonOrganization.id == person_org.id)
        .first()
    )
    return person_org


@router.put("/people/{person_id}/organizations/{link_id}", response_model=PersonOrganizationResponse)
async def update_person_organization(
    person_id: UUID,
    link_id: UUID,
    data: PersonOrganizationUpdate,
    db: Session = Depends(get_db),
):
    """Update a person-organization link."""
    person_org = (
        db.query(PersonOrganization)
        .filter(PersonOrganization.id == link_id, PersonOrganization.person_id == person_id)
        .first()
    )
    if not person_org:
        raise HTTPException(status_code=404, detail="Organization link not found")

    if data.relationship is not None:
        person_org.relationship = OrgRelationshipType(data.relationship)
    if data.role is not None:
        person_org.role = data.role
    if data.is_current is not None:
        person_org.is_current = data.is_current
    if data.notes is not None:
        person_org.notes = data.notes

    db.commit()

    # Reload with organization
    person_org = (
        db.query(PersonOrganization)
        .options(joinedload(PersonOrganization.organization))
        .filter(PersonOrganization.id == link_id)
        .first()
    )
    return person_org


@router.delete("/people/{person_id}/organizations/{link_id}", status_code=204)
async def delete_person_organization(
    person_id: UUID,
    link_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove a person-organization link."""
    person_org = (
        db.query(PersonOrganization)
        .filter(PersonOrganization.id == link_id, PersonOrganization.person_id == person_id)
        .first()
    )
    if not person_org:
        raise HTTPException(status_code=404, detail="Organization link not found")

    db.delete(person_org)
    db.commit()
    return None


@router.get("/org-relationship-types")
async def list_org_relationship_types():
    """Get all organization relationship types."""
    return [{"value": rt.value, "label": rt.value.replace("_", " ").title()} for rt in OrgRelationshipType]


@router.get("/organizations/search")
async def search_organizations(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Search organizations by name."""
    from sqlalchemy import or_

    orgs = (
        db.query(Organization)
        .filter(Organization.name.ilike(f"%{q}%"))
        .order_by(Organization.name)
        .limit(limit)
        .all()
    )
    return [{"id": str(org.id), "name": org.name} for org in orgs]


@router.post("/organizations/quick-create")
async def quick_create_organization(
    name: str = Form(...),
    org_type: str = Form("company"),
    db: Session = Depends(get_db),
):
    """
    Quick create an organization with just a name.
    Used when adding related orgs that don't exist yet.
    Returns JSON with the new organization's id and name.
    """
    from app.models import OrgType

    # Check if org already exists (case-insensitive)
    existing = db.query(Organization).filter(Organization.name.ilike(name)).first()
    if existing:
        return {
            "id": str(existing.id),
            "name": existing.name,
            "existing": True
        }

    # Create new organization
    try:
        org_type_enum = OrgType(org_type)
    except ValueError:
        org_type_enum = OrgType.company

    new_org = Organization(
        name=name,
        org_type=org_type_enum,
    )
    db.add(new_org)
    db.commit()
    db.refresh(new_org)

    return {
        "id": str(new_org.id),
        "name": new_org.name,
        "existing": False
    }


@router.post("/persons/quick-create")
async def quick_create_person(
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Quick create a person with just a name.
    Used when adding relationships to people who don't exist yet.
    Returns JSON with the new person's id and name.

    Parses name intelligently:
    - "John" -> first_name="John"
    - "John Smith" -> first_name="John", last_name="Smith"
    - "John David Smith" -> first_name="John", last_name="David Smith"
    """
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    # Parse name into first/last
    parts = name.split(None, 1)  # Split on first whitespace
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else None

    # Check if person with same name already exists (case-insensitive)
    query = db.query(Person).filter(Person.first_name.ilike(first_name))
    if last_name:
        query = query.filter(Person.last_name.ilike(last_name))
    else:
        query = query.filter(Person.last_name.is_(None))

    existing = query.first()
    if existing:
        return {
            "id": str(existing.id),
            "name": existing.full_name,
            "existing": True
        }

    # Create new person
    # Build full_name from parts
    full_name = first_name
    if last_name:
        full_name = f"{first_name} {last_name}"

    new_person = Person(
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
    )
    db.add(new_person)
    db.commit()
    db.refresh(new_person)

    return {
        "id": str(new_person.id),
        "name": new_person.full_name,
        "existing": False
    }
