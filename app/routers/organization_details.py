"""
Organization Details API Router.

Handles CRUD operations for organization-related entities:
- Offices
- Relationship Status (your relationship with the org)
- Logo upload/delete
- Aggregated interactions
- Lookup endpoints
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
from app.models import Organization, Person, Interaction
from app.models.organization_office import OrganizationOffice
from app.models.organization_relationship_status import OrganizationRelationshipStatus
from app.models.org_relationship import OrgRelationshipType, OrganizationRelationship
from app.models.person_employment import PersonEmployment

from app.schemas.organization_office import (
    OrganizationOfficeCreate,
    OrganizationOfficeUpdate,
    OrganizationOfficeResponse,
)
from app.schemas.organization_relationship_status import (
    OrganizationRelationshipStatusCreate,
    OrganizationRelationshipStatusUpdate,
    OrganizationRelationshipStatusResponse,
)


router = APIRouter(prefix="/api/organizations", tags=["organization-details"])
templates = Jinja2Templates(directory="app/templates")


# =============================================================================
# Logo Upload Configuration
# =============================================================================

UPLOAD_DIR = Path("app/static/uploads/organization_logos")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


# =============================================================================
# Helper Functions
# =============================================================================


def get_organization_or_404(db: Session, org_id: UUID) -> Organization:
    """Get organization by ID or raise 404."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def delete_logo_file(file_path: str | None) -> None:
    """Delete the logo file from disk if it exists."""
    if file_path:
        full_path = Path(file_path.lstrip("/"))
        if full_path.exists():
            full_path.unlink()


# =============================================================================
# Office Endpoints
# =============================================================================


@router.get("/{org_id}/offices", response_model=List[OrganizationOfficeResponse])
async def list_offices(
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """List all offices for an organization."""
    get_organization_or_404(db, org_id)
    offices = (
        db.query(OrganizationOffice)
        .filter(OrganizationOffice.organization_id == org_id)
        .order_by(OrganizationOffice.is_headquarters.desc(), OrganizationOffice.city)
        .all()
    )
    return offices


@router.post("/{org_id}/offices", response_model=OrganizationOfficeResponse)
async def create_office(
    org_id: UUID,
    office_data: OrganizationOfficeCreate,
    db: Session = Depends(get_db),
):
    """Create a new office for an organization."""
    get_organization_or_404(db, org_id)

    # If this is being set as HQ, clear other HQ flags
    if office_data.is_headquarters:
        db.query(OrganizationOffice).filter(
            OrganizationOffice.organization_id == org_id,
            OrganizationOffice.is_headquarters == True,
        ).update({"is_headquarters": False})

    office = OrganizationOffice(
        organization_id=org_id,
        **office_data.model_dump(),
    )
    db.add(office)
    db.commit()
    db.refresh(office)
    return office


@router.put("/{org_id}/offices/{office_id}", response_model=OrganizationOfficeResponse)
async def update_office(
    org_id: UUID,
    office_id: UUID,
    office_data: OrganizationOfficeUpdate,
    db: Session = Depends(get_db),
):
    """Update an office."""
    office = (
        db.query(OrganizationOffice)
        .filter(
            OrganizationOffice.id == office_id,
            OrganizationOffice.organization_id == org_id,
        )
        .first()
    )
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    # If setting as HQ, clear other HQ flags
    if office_data.is_headquarters:
        db.query(OrganizationOffice).filter(
            OrganizationOffice.organization_id == org_id,
            OrganizationOffice.is_headquarters == True,
            OrganizationOffice.id != office_id,
        ).update({"is_headquarters": False})

    update_data = office_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(office, field, value)

    db.commit()
    db.refresh(office)
    return office


@router.delete("/{org_id}/offices/{office_id}")
async def delete_office(
    org_id: UUID,
    office_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an office."""
    office = (
        db.query(OrganizationOffice)
        .filter(
            OrganizationOffice.id == office_id,
            OrganizationOffice.organization_id == org_id,
        )
        .first()
    )
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    db.delete(office)
    db.commit()
    return {"message": "Office deleted successfully"}


# =============================================================================
# Relationship Status Endpoints
# =============================================================================


@router.get("/{org_id}/relationship-status", response_model=OrganizationRelationshipStatusResponse | None)
async def get_relationship_status(
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get the relationship status for an organization."""
    get_organization_or_404(db, org_id)
    status = (
        db.query(OrganizationRelationshipStatus)
        .options(
            joinedload(OrganizationRelationshipStatus.primary_contact),
            joinedload(OrganizationRelationshipStatus.intro_available_via),
        )
        .filter(OrganizationRelationshipStatus.organization_id == org_id)
        .first()
    )
    return status


@router.put("/{org_id}/relationship-status", response_model=OrganizationRelationshipStatusResponse)
async def update_relationship_status(
    org_id: UUID,
    status_data: OrganizationRelationshipStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update or create relationship status for an organization."""
    get_organization_or_404(db, org_id)

    status = (
        db.query(OrganizationRelationshipStatus)
        .filter(OrganizationRelationshipStatus.organization_id == org_id)
        .first()
    )

    if status:
        # Update existing
        update_data = status_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(status, field, value)
    else:
        # Create new
        status = OrganizationRelationshipStatus(
            organization_id=org_id,
            **status_data.model_dump(exclude_unset=True),
        )
        db.add(status)

    db.commit()
    db.refresh(status)

    # Load relationships for response
    status = (
        db.query(OrganizationRelationshipStatus)
        .options(
            joinedload(OrganizationRelationshipStatus.primary_contact),
            joinedload(OrganizationRelationshipStatus.intro_available_via),
        )
        .filter(OrganizationRelationshipStatus.id == status.id)
        .first()
    )

    return status


# =============================================================================
# Aggregated Interactions Endpoint
# =============================================================================


@router.get("/{org_id}/interactions")
async def get_org_interactions(
    org_id: UUID,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get aggregated interactions for an organization.
    Returns all interactions with any person affiliated with the org.
    """
    get_organization_or_404(db, org_id)

    # Get all person IDs affiliated with this org (via employment)
    person_ids = (
        db.query(PersonEmployment.person_id)
        .filter(PersonEmployment.organization_id == org_id)
        .distinct()
        .all()
    )
    person_id_list = [pid[0] for pid in person_ids]

    if not person_id_list:
        return {
            "interactions": [],
            "total": 0,
            "last_contacted": None,
            "most_frequent_contact": None,
        }

    # Get total count
    total = (
        db.query(Interaction)
        .filter(Interaction.person_id.in_(person_id_list))
        .count()
    )

    # Get interactions with person info
    interactions = (
        db.query(Interaction)
        .options(joinedload(Interaction.person))
        .filter(Interaction.person_id.in_(person_id_list))
        .order_by(Interaction.interaction_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Find last contacted date
    last_interaction = (
        db.query(Interaction)
        .filter(Interaction.person_id.in_(person_id_list))
        .order_by(Interaction.interaction_date.desc())
        .first()
    )

    # Find most frequent contact
    from sqlalchemy import func
    most_frequent = (
        db.query(
            Interaction.person_id,
            func.count(Interaction.id).label("count"),
        )
        .filter(Interaction.person_id.in_(person_id_list))
        .group_by(Interaction.person_id)
        .order_by(func.count(Interaction.id).desc())
        .first()
    )

    most_frequent_person = None
    if most_frequent:
        person = db.query(Person).filter(Person.id == most_frequent[0]).first()
        if person:
            most_frequent_person = {
                "id": str(person.id),
                "full_name": person.full_name,
                "count": most_frequent[1],
            }

    return {
        "interactions": [
            {
                "id": str(i.id),
                "interaction_date": i.interaction_date.isoformat() if i.interaction_date else None,
                "medium": i.medium.value if i.medium else None,
                "notes": i.notes,
                "person_id": str(i.person_id),
                "person_name": i.person.full_name if i.person else None,
            }
            for i in interactions
        ],
        "total": total,
        "last_contacted": last_interaction.interaction_date.isoformat() if last_interaction else None,
        "most_frequent_contact": most_frequent_person,
    }


# =============================================================================
# Logo Upload/Delete Endpoints
# =============================================================================


@router.post("/{org_id}/logo")
async def upload_logo(
    org_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a logo for an organization."""
    org = get_organization_or_404(db, org_id)

    # Validate file extension
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file and check size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB",
        )

    # Create upload directory if it doesn't exist
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Delete old logo if exists
    if org.logo:
        delete_logo_file(org.logo)

    # Save new file
    filename = f"{org_id}{file_ext}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(contents)

    # Update database
    org.logo = f"/static/uploads/organization_logos/{filename}"
    db.commit()

    return {"logo_url": org.logo}


@router.delete("/{org_id}/logo")
async def delete_logo(
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an organization's logo."""
    org = get_organization_or_404(db, org_id)

    if org.logo:
        delete_logo_file(org.logo)
        org.logo = None
        db.commit()

    return {"message": "Logo deleted successfully"}


# =============================================================================
# Lookup Endpoints
# =============================================================================


@router.get("/lookup/relationship-types")
async def get_relationship_types():
    """Get all organization relationship types."""
    results = []
    for rt in OrgRelationshipType:
        inverse = OrganizationRelationship.get_inverse_type(rt)
        results.append({
            "value": rt.value,
            "display": rt.value.replace("_", " ").title(),
            "inverse": inverse.value if inverse else None,
        })
    return results


@router.get("/lookup/investment-stages")
async def get_investment_stages():
    """Get all investment stages."""
    stages = [
        {"value": "pre_seed", "display": "Pre-Seed"},
        {"value": "seed", "display": "Seed"},
        {"value": "series_a", "display": "Series A"},
        {"value": "series_b", "display": "Series B"},
        {"value": "series_c", "display": "Series C"},
        {"value": "series_d", "display": "Series D+"},
        {"value": "growth", "display": "Growth"},
        {"value": "late_stage", "display": "Late Stage"},
        {"value": "buyout", "display": "Buyout"},
        {"value": "secondary", "display": "Secondary"},
    ]
    return stages


@router.get("/lookup/investment-sectors")
async def get_investment_sectors():
    """Get all investment sectors."""
    sectors = [
        {"value": "saas", "display": "SaaS"},
        {"value": "fintech", "display": "Fintech"},
        {"value": "healthcare", "display": "Healthcare"},
        {"value": "consumer", "display": "Consumer"},
        {"value": "enterprise", "display": "Enterprise"},
        {"value": "ai_ml", "display": "AI/ML"},
        {"value": "cybersecurity", "display": "Cybersecurity"},
        {"value": "biotech", "display": "Biotech"},
        {"value": "cleantech", "display": "Cleantech"},
        {"value": "edtech", "display": "EdTech"},
        {"value": "proptech", "display": "PropTech"},
        {"value": "marketplace", "display": "Marketplace"},
        {"value": "hardware", "display": "Hardware"},
        {"value": "crypto_web3", "display": "Crypto/Web3"},
        {"value": "deeptech", "display": "DeepTech"},
        {"value": "other", "display": "Other"},
    ]
    return sectors


@router.get("/lookup/warmth-levels")
async def get_warmth_levels():
    """Get all relationship warmth levels."""
    levels = [
        {"value": "hot", "display": "Hot", "emoji": "🔥", "description": "Active deal/discussion"},
        {"value": "warm", "display": "Warm", "emoji": "🟢", "description": "Regular contact, good relationship"},
        {"value": "met_once", "display": "Met Once", "emoji": "🟡", "description": "Had one meeting/interaction"},
        {"value": "cold", "display": "Cold", "emoji": "🔴", "description": "No recent contact"},
        {"value": "unknown", "display": "Unknown", "emoji": "⚪", "description": "Haven't assessed yet"},
    ]
    return levels
