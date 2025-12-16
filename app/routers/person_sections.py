"""
Person Section Editing API - Returns HTML partials for inline editing.

Each section can be toggled between view and edit mode via HTMX.
Auto-saves on blur for most fields.
# Fixed route conflicts - added /form suffix for HTMX POST endpoints
"""

import os
import uuid as uuid_lib
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Person, PersonOrganization
from app.models.person_email import PersonEmail, EmailLabel
from app.models.person_phone import PersonPhone, PhoneLabel
from app.models.person_website import PersonWebsite
from app.models.person_address import PersonAddress
from app.models.person_employment import PersonEmployment
from app.models.person_education import PersonEducation
from app.models.person_relationship import PersonRelationship
from app.models.affiliation_type import AffiliationType
from app.models.relationship_type import RelationshipType
from app.models.interaction import Interaction, InteractionMedium, InteractionSource
from app.models.google_account import GoogleAccount


router = APIRouter(prefix="/api/people", tags=["person-sections"])
templates = Jinja2Templates(directory="app/templates")


def get_person_or_404(db: Session, person_id: UUID) -> Person:
    """Get person by ID or raise 404."""
    person = (
        db.query(Person)
        .options(
            joinedload(Person.emails),
            joinedload(Person.phones),
            joinedload(Person.websites),
            joinedload(Person.addresses),
            joinedload(Person.education),
            joinedload(Person.employment),
            joinedload(Person.relationships_from),
            joinedload(Person.organizations).joinedload(PersonOrganization.organization),
        )
        .filter(Person.id == person_id)
        .first()
    )
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


# =============================================================================
# NOTES SECTION
# =============================================================================

@router.get("/{person_id}/sections/notes/edit", response_class=HTMLResponse)
async def get_notes_edit(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get notes section in edit mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_notes_edit.html",
        {"request": request, "person": person}
    )


@router.get("/{person_id}/sections/notes/view", response_class=HTMLResponse)
async def get_notes_view(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get notes section in view mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_notes_view.html",
        {"request": request, "person": person}
    )


@router.put("/{person_id}/sections/notes", response_class=HTMLResponse)
async def update_notes(
    request: Request,
    person_id: UUID,
    notes: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update notes and return view mode."""
    person = get_person_or_404(db, person_id)
    person.notes = notes if notes else None
    db.commit()
    db.refresh(person)
    return templates.TemplateResponse(
        "partials/sections/_notes_view.html",
        {"request": request, "person": person}
    )


# =============================================================================
# HEADER (NAME) SECTION
# =============================================================================

@router.get("/{person_id}/sections/header/edit", response_class=HTMLResponse)
async def get_header_edit(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get header/name section in edit mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_header_edit.html",
        {"request": request, "person": person}
    )


@router.get("/{person_id}/sections/header/view", response_class=HTMLResponse)
async def get_header_view(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get header/name section in view mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_header_view.html",
        {"request": request, "person": person}
    )


@router.post("/{person_id}/sections/header/form", response_class=HTMLResponse)
async def update_header_form(
    request: Request,
    person_id: UUID,
    first_name: str = Form(...),
    last_name: str = Form(...),
    middle_name: str = Form(None),
    nickname: str = Form(None),
    title: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update name fields and return view mode."""
    person = get_person_or_404(db, person_id)

    person.first_name = first_name.strip() if first_name else None
    person.middle_name = middle_name.strip() if middle_name else None
    person.last_name = last_name.strip() if last_name else None
    person.nickname = nickname.strip() if nickname else None
    person.title = title.strip() if title else None

    # Rebuild full_name from components
    name_parts = []
    if person.first_name:
        name_parts.append(person.first_name)
    if person.middle_name:
        name_parts.append(person.middle_name)
    if person.last_name:
        name_parts.append(person.last_name)
    person.full_name = " ".join(name_parts) if name_parts else "Unknown"

    db.commit()
    db.refresh(person)

    return templates.TemplateResponse(
        "partials/sections/_header_view.html",
        {"request": request, "person": person}
    )


# =============================================================================
# PROFILE PICTURE UPLOAD
# =============================================================================

UPLOAD_DIR = "app/static/uploads/profile_pictures"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/{person_id}/profile-picture", response_class=HTMLResponse)
async def upload_profile_picture(
    request: Request,
    person_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a profile picture for a person."""
    person = get_person_or_404(db, person_id)

    # Validate file extension
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file and check size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Delete old profile picture if it exists and is a local file
    if person.profile_picture and person.profile_picture.startswith("/static/uploads/"):
        old_path = person.profile_picture.replace("/static/", "app/static/")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass  # Ignore deletion errors

    # Generate unique filename
    unique_filename = f"{person_id}_{uuid_lib.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # Save file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Update person's profile_picture field with URL path
    person.profile_picture = f"/static/uploads/profile_pictures/{unique_filename}"
    db.commit()
    db.refresh(person)

    return templates.TemplateResponse(
        "partials/sections/_profile_picture.html",
        {"request": request, "person": person}
    )


@router.delete("/{person_id}/profile-picture", response_class=HTMLResponse)
async def delete_profile_picture(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a person's profile picture."""
    person = get_person_or_404(db, person_id)

    # Delete file if it's a local upload
    if person.profile_picture and person.profile_picture.startswith("/static/uploads/"):
        old_path = person.profile_picture.replace("/static/", "app/static/")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass  # Ignore deletion errors

    # Clear the profile picture field
    person.profile_picture = None
    db.commit()
    db.refresh(person)

    return templates.TemplateResponse(
        "partials/sections/_profile_picture.html",
        {"request": request, "person": person}
    )


# =============================================================================
# TEMPORARY PROFILE PICTURE UPLOAD (for new person form)
# =============================================================================

from fastapi.responses import JSONResponse


@router.post("/upload/temp-profile-picture", response_class=JSONResponse)
async def upload_temp_profile_picture(
    file: UploadFile = File(...),
):
    """
    Upload a temporary profile picture before person is created.
    Returns the URL path to be used when creating the person.
    """
    # Validate file extension
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file and check size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Generate unique filename with temp prefix
    unique_filename = f"temp_{uuid_lib.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # Save file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Return the URL path
    url = f"/static/uploads/profile_pictures/{unique_filename}"
    return {"url": url, "filename": unique_filename}


# =============================================================================
# SOCIAL PROFILES SECTION
# =============================================================================

@router.get("/{person_id}/sections/social/edit", response_class=HTMLResponse)
async def get_social_edit(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get social profiles section in edit mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_social_edit.html",
        {"request": request, "person": person}
    )


@router.get("/{person_id}/sections/social/view", response_class=HTMLResponse)
async def get_social_view(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get social profiles section in view mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_social_view.html",
        {"request": request, "person": person}
    )


@router.put("/{person_id}/sections/social", response_class=HTMLResponse)
async def update_social(
    request: Request,
    person_id: UUID,
    linkedin: str = Form(None),
    twitter: str = Form(None),
    crunchbase: str = Form(None),
    angellist: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update social profiles and return view mode."""
    person = get_person_or_404(db, person_id)
    person.linkedin = linkedin if linkedin else None
    person.twitter = twitter if twitter else None
    person.crunchbase = crunchbase if crunchbase else None
    person.angellist = angellist if angellist else None
    db.commit()
    db.refresh(person)
    return templates.TemplateResponse(
        "partials/sections/_social_view.html",
        {"request": request, "person": person}
    )


# =============================================================================
# CONTACT INFO SECTION
# =============================================================================

@router.get("/{person_id}/sections/contact/edit", response_class=HTMLResponse)
async def get_contact_edit(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get contact info section in edit mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


@router.get("/{person_id}/sections/contact/view", response_class=HTMLResponse)
async def get_contact_view(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get contact info section in view mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_view.html",
        {"request": request, "person": person}
    )


@router.put("/{person_id}/sections/contact", response_class=HTMLResponse)
async def update_contact(
    request: Request,
    person_id: UUID,
    birthday: str = Form(None),
    location: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update basic contact info (birthday, location) and return view mode."""
    from datetime import datetime

    person = get_person_or_404(db, person_id)

    if birthday:
        try:
            person.birthday = datetime.strptime(birthday, "%Y-%m-%d").date()
        except ValueError:
            pass
    else:
        person.birthday = None

    person.location = location if location else None
    db.commit()
    db.refresh(person)
    return templates.TemplateResponse(
        "partials/sections/_contact_view.html",
        {"request": request, "person": person}
    )


# =============================================================================
# EMAIL CRUD
# =============================================================================

@router.post("/{person_id}/emails", response_class=HTMLResponse)
async def add_email(
    request: Request,
    person_id: UUID,
    email: str = Form(...),
    label: str = Form("work"),
    db: Session = Depends(get_db),
):
    """Add a new email address to a person."""
    person = get_person_or_404(db, person_id)

    # Check limit (max 5)
    if len(person.emails) >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 email addresses allowed")

    # Determine if this should be primary (first email is primary)
    is_primary = len(person.emails) == 0

    new_email = PersonEmail(
        person_id=person_id,
        email=email,
        label=EmailLabel(label) if label else EmailLabel.work,
        is_primary=is_primary,
    )
    db.add(new_email)
    db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


@router.delete("/{person_id}/emails/{email_id}", response_class=HTMLResponse)
async def delete_email(
    request: Request,
    person_id: UUID,
    email_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an email address."""
    email_obj = db.query(PersonEmail).filter(
        PersonEmail.id == email_id,
        PersonEmail.person_id == person_id
    ).first()

    if not email_obj:
        raise HTTPException(status_code=404, detail="Email not found")

    was_primary = email_obj.is_primary
    db.delete(email_obj)
    db.commit()

    # If deleted email was primary, make another one primary
    if was_primary:
        person = get_person_or_404(db, person_id)
        if person.emails:
            person.emails[0].is_primary = True
            db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


# =============================================================================
# PHONE CRUD
# =============================================================================

@router.post("/{person_id}/phones", response_class=HTMLResponse)
async def add_phone(
    request: Request,
    person_id: UUID,
    phone: str = Form(...),
    label: str = Form("mobile"),
    db: Session = Depends(get_db),
):
    """Add a new phone number to a person."""
    person = get_person_or_404(db, person_id)

    # Check limit (max 5)
    if len(person.phones) >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 phone numbers allowed")

    # Determine if this should be primary (first phone is primary)
    is_primary = len(person.phones) == 0

    new_phone = PersonPhone(
        person_id=person_id,
        phone=phone,
        label=PhoneLabel(label) if label else PhoneLabel.mobile,
        is_primary=is_primary,
    )
    db.add(new_phone)
    db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


@router.delete("/{person_id}/phones/{phone_id}", response_class=HTMLResponse)
async def delete_phone(
    request: Request,
    person_id: UUID,
    phone_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a phone number."""
    phone_obj = db.query(PersonPhone).filter(
        PersonPhone.id == phone_id,
        PersonPhone.person_id == person_id
    ).first()

    if not phone_obj:
        raise HTTPException(status_code=404, detail="Phone not found")

    was_primary = phone_obj.is_primary
    db.delete(phone_obj)
    db.commit()

    # If deleted phone was primary, make another one primary
    if was_primary:
        person = get_person_or_404(db, person_id)
        if person.phones:
            person.phones[0].is_primary = True
            db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


# =============================================================================
# WEBSITE CRUD
# =============================================================================

@router.post("/{person_id}/websites/form", response_class=HTMLResponse)
async def add_website_form(
    request: Request,
    person_id: UUID,
    url: str = Form(...),
    label: str = Form(None),
    db: Session = Depends(get_db),
):
    """Add a new website to a person."""
    person = get_person_or_404(db, person_id)

    # Check limit (max 3)
    if len(person.websites) >= 3:
        raise HTTPException(status_code=400, detail="Maximum 3 websites allowed")

    # Auto-add https:// if no protocol specified
    url = url.strip()
    if url and not url.startswith(('http://', 'https://')):
        url = f'https://{url}'

    new_website = PersonWebsite(
        person_id=person_id,
        url=url,
        label=label if label else None,
    )
    db.add(new_website)
    db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


@router.delete("/{person_id}/websites/{website_id}/inline", response_class=HTMLResponse)
async def delete_website_inline(
    request: Request,
    person_id: UUID,
    website_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a website."""
    website = db.query(PersonWebsite).filter(
        PersonWebsite.id == website_id,
        PersonWebsite.person_id == person_id
    ).first()

    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    db.delete(website)
    db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


# =============================================================================
# ADDRESS CRUD
# =============================================================================

@router.post("/{person_id}/addresses/form", response_class=HTMLResponse)
async def add_address_form(
    request: Request,
    person_id: UUID,
    address_type: str = Form(...),
    street: str = Form(None),
    city: str = Form(None),
    state: str = Form(None),
    zip: str = Form(None),
    country: str = Form(None),
    db: Session = Depends(get_db),
):
    """Add a new address to a person."""
    person = get_person_or_404(db, person_id)

    # Check limit (max 2)
    if len(person.addresses) >= 2:
        raise HTTPException(status_code=400, detail="Maximum 2 addresses allowed")

    # Check if address type already exists
    existing = db.query(PersonAddress).filter(
        PersonAddress.person_id == person_id,
        PersonAddress.address_type == address_type
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"{address_type.title()} address already exists")

    new_address = PersonAddress(
        person_id=person_id,
        address_type=address_type,
        street=street if street else None,
        city=city if city else None,
        state=state if state else None,
        zip=zip if zip else None,
        country=country if country else None,
    )
    db.add(new_address)
    db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


@router.delete("/{person_id}/addresses/{address_id}/inline", response_class=HTMLResponse)
async def delete_address_inline(
    request: Request,
    person_id: UUID,
    address_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an address."""
    address = db.query(PersonAddress).filter(
        PersonAddress.id == address_id,
        PersonAddress.person_id == person_id
    ).first()

    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    db.delete(address)
    db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_contact_edit.html",
        {"request": request, "person": person}
    )


# =============================================================================
# INVESTMENT DETAILS SECTION
# =============================================================================

@router.get("/{person_id}/sections/investment/edit", response_class=HTMLResponse)
async def get_investment_edit(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get investment section in edit mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_investment_edit.html",
        {"request": request, "person": person}
    )


@router.get("/{person_id}/sections/investment/view", response_class=HTMLResponse)
async def get_investment_view(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get investment section in view mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_investment_view.html",
        {"request": request, "person": person}
    )


@router.put("/{person_id}/sections/investment", response_class=HTMLResponse)
async def update_investment(
    request: Request,
    person_id: UUID,
    investment_type: str = Form(None),
    amount_funded: str = Form(None),
    potential_intro_vc: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update investment details and return view mode."""
    person = get_person_or_404(db, person_id)
    person.investment_type = investment_type if investment_type else None
    person.amount_funded = amount_funded if amount_funded else None
    person.potential_intro_vc = potential_intro_vc if potential_intro_vc else None
    db.commit()
    db.refresh(person)
    return templates.TemplateResponse(
        "partials/sections/_investment_view.html",
        {"request": request, "person": person}
    )


# =============================================================================
# EMPLOYMENT SECTION
# =============================================================================

def get_affiliation_types(db: Session) -> list:
    """Get all affiliation types for dropdown."""
    return db.query(AffiliationType).order_by(AffiliationType.name).all()


@router.get("/{person_id}/sections/employment/edit", response_class=HTMLResponse)
async def get_employment_edit(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get employment section in edit mode."""
    person = get_person_or_404(db, person_id)
    affiliation_types = get_affiliation_types(db)
    return templates.TemplateResponse(
        "partials/sections/_employment_edit.html",
        {"request": request, "person": person, "affiliation_types": affiliation_types}
    )


@router.get("/{person_id}/sections/employment/view", response_class=HTMLResponse)
async def get_employment_view(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get employment section in view mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_employment_view.html",
        {"request": request, "person": person}
    )


@router.post("/{person_id}/employment/form", response_class=HTMLResponse)
async def add_employment_form(
    request: Request,
    person_id: UUID,
    organization_name: str = Form(...),
    title: str = Form(None),
    affiliation_type_id: str = Form(None),
    is_current: str = Form(None),
    db: Session = Depends(get_db),
):
    """Add new employment entry."""
    person = get_person_or_404(db, person_id)

    # Check limit (max 10)
    if len(person.employment) >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 employment entries allowed")

    employment = PersonEmployment(
        person_id=person_id,
        organization_name=organization_name,
        title=title if title else None,
        affiliation_type_id=UUID(affiliation_type_id) if affiliation_type_id else None,
        is_current=is_current == "true",
    )
    db.add(employment)
    db.commit()

    # Refresh person to get updated list
    person = get_person_or_404(db, person_id)
    affiliation_types = get_affiliation_types(db)
    return templates.TemplateResponse(
        "partials/sections/_employment_edit.html",
        {"request": request, "person": person, "affiliation_types": affiliation_types}
    )


@router.delete("/{person_id}/employment/{employment_id}/inline", response_class=HTMLResponse)
async def delete_employment_inline(
    request: Request,
    person_id: UUID,
    employment_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an employment entry."""
    employment = db.query(PersonEmployment).filter(
        PersonEmployment.id == employment_id,
        PersonEmployment.person_id == person_id
    ).first()

    if not employment:
        raise HTTPException(status_code=404, detail="Employment entry not found")

    db.delete(employment)
    db.commit()

    person = get_person_or_404(db, person_id)
    affiliation_types = get_affiliation_types(db)
    return templates.TemplateResponse(
        "partials/sections/_employment_edit.html",
        {"request": request, "person": person, "affiliation_types": affiliation_types}
    )


# =============================================================================
# EDUCATION SECTION
# =============================================================================

@router.get("/{person_id}/sections/education/edit", response_class=HTMLResponse)
async def get_education_edit(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get education section in edit mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_education_edit.html",
        {"request": request, "person": person}
    )


@router.get("/{person_id}/sections/education/view", response_class=HTMLResponse)
async def get_education_view(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get education section in view mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_education_view.html",
        {"request": request, "person": person}
    )


@router.post("/{person_id}/education/form", response_class=HTMLResponse)
async def add_education_form(
    request: Request,
    person_id: UUID,
    school_name: str = Form(...),
    degree_type: str = Form(None),
    field_of_study: str = Form(None),
    graduation_year: str = Form(None),  # Accept as string to handle empty input
    db: Session = Depends(get_db),
):
    """Add new education entry."""
    person = get_person_or_404(db, person_id)

    # Check limit (max 6)
    if len(person.education) >= 6:
        raise HTTPException(status_code=400, detail="Maximum 6 education entries allowed")

    # Convert graduation_year to int if provided
    grad_year_int = None
    if graduation_year and graduation_year.strip():
        try:
            grad_year_int = int(graduation_year)
        except ValueError:
            pass

    education = PersonEducation(
        person_id=person_id,
        school_name=school_name,
        degree_type=degree_type if degree_type else None,
        field_of_study=field_of_study if field_of_study else None,
        graduation_year=grad_year_int,
    )
    db.add(education)
    db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_education_edit.html",
        {"request": request, "person": person}
    )


@router.delete("/{person_id}/education/{education_id}/inline", response_class=HTMLResponse)
async def delete_education_inline(
    request: Request,
    person_id: UUID,
    education_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an education entry."""
    education = db.query(PersonEducation).filter(
        PersonEducation.id == education_id,
        PersonEducation.person_id == person_id
    ).first()

    if not education:
        raise HTTPException(status_code=404, detail="Education entry not found")

    db.delete(education)
    db.commit()

    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_education_edit.html",
        {"request": request, "person": person}
    )


# =============================================================================
# RELATIONSHIPS SECTION
# =============================================================================

def get_relationship_types(db: Session) -> list:
    """Get all relationship types for dropdown, sorted by display_order then name."""
    return db.query(RelationshipType).order_by(
        RelationshipType.display_order,
        RelationshipType.name
    ).all()


def get_all_persons_for_dropdown(db: Session) -> list:
    """Get all persons for the relationship dropdown."""
    return db.query(Person).order_by(Person.first_name, Person.last_name).all()


@router.get("/{person_id}/sections/relationships/edit", response_class=HTMLResponse)
async def get_relationships_edit(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get relationships section in edit mode."""
    person = get_person_or_404(db, person_id)
    relationship_types = get_relationship_types(db)
    all_persons = get_all_persons_for_dropdown(db)
    return templates.TemplateResponse(
        "partials/sections/_relationships_edit.html",
        {
            "request": request,
            "person": person,
            "relationship_types": relationship_types,
            "all_persons": all_persons,
        }
    )


@router.get("/{person_id}/sections/relationships/view", response_class=HTMLResponse)
async def get_relationships_view(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """Get relationships section in view mode."""
    person = get_person_or_404(db, person_id)
    return templates.TemplateResponse(
        "partials/sections/_relationships_view.html",
        {"request": request, "person": person}
    )


@router.post("/{person_id}/relationships/form", response_class=HTMLResponse)
async def add_relationship_form(
    request: Request,
    person_id: UUID,
    related_person_id: str = Form(...),
    relationship_type_id: str = Form(None),
    context_text: str = Form(None),
    db: Session = Depends(get_db),
):
    """Add new relationship entry with bidirectional inverse creation."""
    person = get_person_or_404(db, person_id)
    related_id = UUID(related_person_id)
    rel_type_id = UUID(relationship_type_id) if relationship_type_id else None

    # Find inverse relationship type if applicable
    inverse_type = None
    if rel_type_id:
        rel_type = db.query(RelationshipType).filter(RelationshipType.id == rel_type_id).first()
        if rel_type and rel_type.inverse_name:
            inverse_type = (
                db.query(RelationshipType)
                .filter(RelationshipType.name == rel_type.inverse_name)
                .first()
            )

    # Create the primary relationship
    relationship = PersonRelationship(
        person_id=person_id,
        related_person_id=related_id,
        relationship_type_id=rel_type_id,
        context_text=context_text if context_text else None,
    )
    db.add(relationship)

    # Create inverse relationship if applicable (bidirectional)
    if inverse_type:
        # Check if inverse already exists
        existing_inverse = (
            db.query(PersonRelationship)
            .filter(
                PersonRelationship.person_id == related_id,
                PersonRelationship.related_person_id == person_id,
                PersonRelationship.relationship_type_id == inverse_type.id,
            )
            .first()
        )
        if not existing_inverse:
            inverse_relationship = PersonRelationship(
                person_id=related_id,
                related_person_id=person_id,
                relationship_type_id=inverse_type.id,
                context_text=context_text if context_text else None,
            )
            db.add(inverse_relationship)

    db.commit()

    person = get_person_or_404(db, person_id)
    relationship_types = get_relationship_types(db)
    all_persons = get_all_persons_for_dropdown(db)
    return templates.TemplateResponse(
        "partials/sections/_relationships_edit.html",
        {
            "request": request,
            "person": person,
            "relationship_types": relationship_types,
            "all_persons": all_persons,
        }
    )


@router.delete("/{person_id}/relationships/{relationship_id}/inline", response_class=HTMLResponse)
async def delete_relationship_inline(
    request: Request,
    person_id: UUID,
    relationship_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a relationship entry and its inverse (bidirectional)."""
    relationship = db.query(PersonRelationship).filter(
        PersonRelationship.id == relationship_id,
        PersonRelationship.person_id == person_id
    ).first()

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Find and delete inverse relationship if exists
    if relationship.relationship_type_id:
        rel_type = db.query(RelationshipType).filter(
            RelationshipType.id == relationship.relationship_type_id
        ).first()
        if rel_type and rel_type.inverse_name:
            inverse_type = db.query(RelationshipType).filter(
                RelationshipType.name == rel_type.inverse_name
            ).first()
            if inverse_type:
                inverse_relationship = db.query(PersonRelationship).filter(
                    PersonRelationship.person_id == relationship.related_person_id,
                    PersonRelationship.related_person_id == person_id,
                    PersonRelationship.relationship_type_id == inverse_type.id,
                ).first()
                if inverse_relationship:
                    db.delete(inverse_relationship)

    db.delete(relationship)
    db.commit()

    person = get_person_or_404(db, person_id)
    relationship_types = get_relationship_types(db)
    all_persons = get_all_persons_for_dropdown(db)
    return templates.TemplateResponse(
        "partials/sections/_relationships_edit.html",
        {
            "request": request,
            "person": person,
            "relationship_types": relationship_types,
            "all_persons": all_persons,
        }
    )


@router.post("/{person_id}/my-relationship", response_class=HTMLResponse)
async def update_my_relationship(
    request: Request,
    person_id: UUID,
    my_relationship_type_id: str = Form(""),
    my_relationship_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    """Update the 'My Relationship' field for a person (how you know them)."""
    person = get_person_or_404(db, person_id)

    # Update my relationship fields
    # Handle empty string from form select
    if my_relationship_type_id and my_relationship_type_id.strip():
        person.my_relationship_type_id = UUID(my_relationship_type_id.strip())
    else:
        person.my_relationship_type_id = None

    person.my_relationship_notes = my_relationship_notes.strip() if my_relationship_notes and my_relationship_notes.strip() else None

    db.commit()
    db.refresh(person)

    # Return the edit view with updated data
    relationship_types = get_relationship_types(db)
    all_persons = get_all_persons_for_dropdown(db)
    return templates.TemplateResponse(
        "partials/sections/_relationships_edit.html",
        {
            "request": request,
            "person": person,
            "relationship_types": relationship_types,
            "all_persons": all_persons,
        }
    )


# =============================================================================
# INTERACTIONS SECTION
# =============================================================================

@router.post("/{person_id}/interactions/form", response_class=HTMLResponse)
async def add_interaction_form(
    request: Request,
    person_id: UUID,
    medium: str = Form(...),
    interaction_date: str = Form(None),
    interaction_time: str = Form(None),
    notes: str = Form(None),
    add_to_calendar: str = Form(None),
    calendar_account_id: str = Form(None),
    append_to_notes: str = Form(None),
    db: Session = Depends(get_db),
):
    """Add new interaction via inline form and return updated interactions card."""
    from datetime import datetime, timezone

    person = get_person_or_404(db, person_id)

    # Parse interaction date
    parsed_date = None
    if interaction_date and interaction_date.strip():
        try:
            parsed_date = datetime.strptime(interaction_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Create new interaction
    interaction = Interaction(
        person_id=person_id,
        person_name=person.full_name,
        medium=InteractionMedium(medium),
        interaction_date=parsed_date,
        notes=notes if notes else None,
        source=InteractionSource.manual,
    )
    db.add(interaction)

    # Append notes to person's Notes section if requested
    if append_to_notes == "true" and notes and notes.strip():
        medium_label = medium.replace('_', ' ').title()
        date_str = parsed_date.strftime('%b %d, %Y') if parsed_date else 'No date'
        time_str = f" at {interaction_time}" if interaction_time else ""

        # Build HTML note entry - notes already contains HTML from Quill, don't wrap in <p>
        note_entry = f'<p><strong>{medium_label}</strong> - {date_str}{time_str}</p>{notes}'

        if person.notes:
            person.notes = f'{person.notes}<p><br></p>{note_entry}'
        else:
            person.notes = note_entry

    # Add to Google Calendar if requested
    if add_to_calendar == "true" and parsed_date:
        try:
            from app.services.calendar_service import CalendarService, CalendarServiceError
            from app.models.calendar_settings import CalendarSettings

            calendar_service = CalendarService(db)
            user_timezone = CalendarSettings.get_timezone(db)

            # Build start datetime - use local time, not UTC
            # Google Calendar API will handle timezone conversion
            if interaction_time:
                start_dt = datetime.strptime(
                    f"{interaction_date} {interaction_time}",
                    "%Y-%m-%d %H:%M"
                )
            else:
                # Default to 9 AM if no time specified
                start_dt = datetime.combine(
                    parsed_date,
                    datetime.strptime("09:00", "%H:%M").time()
                )

            # Create calendar event
            medium_label = medium.replace('_', ' ').title()
            event_summary = f"{medium_label} with {person.full_name}"

            # Get person's primary email for attendee (if available)
            person_email = None
            if person.emails:
                primary_email = next((e for e in person.emails if e.is_primary), None)
                if primary_email:
                    person_email = primary_email.email
                elif person.emails:
                    person_email = person.emails[0].email

            # Parse account ID if provided
            account_id = None
            if calendar_account_id and calendar_account_id.strip():
                try:
                    account_id = UUID(calendar_account_id)
                except ValueError:
                    pass

            # Strip HTML from notes for calendar description
            import re
            plain_notes = None
            if notes:
                plain_notes = re.sub(r'<[^>]+>', '', notes)
                plain_notes = plain_notes.strip() if plain_notes else None

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Creating calendar event: {event_summary} at {start_dt}")

            calendar_event_id = calendar_service.create_event(
                summary=event_summary,
                start_datetime=start_dt,
                description=plain_notes,
                attendee_email=person_email,
                account_id=account_id,
                timezone_str=user_timezone,
            )

            if calendar_event_id:
                interaction.calendar_event_id = calendar_event_id
                logger.info(f"Calendar event created successfully: {calendar_event_id}")
            else:
                logger.warning("Calendar event creation returned None")

        except (CalendarServiceError, Exception) as e:
            # Log error but don't fail the interaction creation
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create calendar event: {e}")
            logger.error(traceback.format_exc())
            print(f"Failed to create calendar event: {e}")
            print(traceback.format_exc())

    db.commit()

    # Get updated interactions list (most recent first)
    interactions = (
        db.query(Interaction)
        .filter(Interaction.person_id == person_id)
        .order_by(Interaction.interaction_date.desc().nullsfirst())
        .all()
    )

    # Get active Google accounts for the template
    google_accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    # Refresh person to get updated notes
    db.refresh(person)

    return templates.TemplateResponse(
        "partials/sections/_interactions_card.html",
        {
            "request": request,
            "person": person,
            "interactions": interactions,
            "google_accounts": google_accounts,
        }
    )
