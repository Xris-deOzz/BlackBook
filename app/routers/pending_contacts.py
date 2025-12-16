"""
Pending contacts router for managing unknown meeting attendees.

Provides endpoints for viewing and processing pending contacts discovered from calendar events.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    PendingContact,
    PendingContactStatus,
    Person,
    PersonEmail,
    EmailLabel,
)

router = APIRouter(prefix="/pending-contacts", tags=["pending-contacts"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_pending_contacts(
    request: Request,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """
    List all pending contacts with optional status filter.

    Args:
        status: Filter by status (pending, created, ignored). Default shows pending only.
    """
    query = db.query(PendingContact)

    if status:
        try:
            status_enum = PendingContactStatus(status)
            query = query.filter(PendingContact.status == status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter
    else:
        # Default to showing only pending
        query = query.filter(PendingContact.status == PendingContactStatus.pending)

    contacts = query.order_by(
        PendingContact.occurrence_count.desc(),
        PendingContact.first_seen_at.desc(),
    ).all()

    return templates.TemplateResponse(
        request,
        "pending_contacts/list.html",
        {
            "contacts": contacts,
            "current_status": status or "pending",
        },
    )


@router.get("/api")
async def api_list_pending_contacts(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """
    API endpoint: List pending contacts as JSON.

    Args:
        status: Filter by status (pending, created, ignored)
    """
    query = db.query(PendingContact)

    if status:
        try:
            status_enum = PendingContactStatus(status)
            query = query.filter(PendingContact.status == status_enum)
        except ValueError:
            pass
    else:
        query = query.filter(PendingContact.status == PendingContactStatus.pending)

    contacts = query.order_by(
        PendingContact.occurrence_count.desc(),
        PendingContact.first_seen_at.desc(),
    ).all()

    return {
        "contacts": [
            {
                "id": str(c.id),
                "email": c.email,
                "name": c.name,
                "occurrence_count": c.occurrence_count,
                "status": c.status.value,
                "first_seen_at": c.first_seen_at.isoformat() if c.first_seen_at else None,
                "source_event_id": str(c.source_event_id) if c.source_event_id else None,
                "created_person_id": str(c.created_person_id) if c.created_person_id else None,
            }
            for c in contacts
        ]
    }


@router.get("/widget", response_class=HTMLResponse)
async def pending_contacts_widget(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Dashboard widget showing pending contacts summary.

    Returns HTML partial for dashboard HTMX integration.
    """
    contacts = (
        db.query(PendingContact)
        .filter(PendingContact.status == PendingContactStatus.pending)
        .order_by(
            PendingContact.occurrence_count.desc(),
            PendingContact.first_seen_at.desc(),
        )
        .limit(5)
        .all()
    )

    total_count = (
        db.query(PendingContact)
        .filter(PendingContact.status == PendingContactStatus.pending)
        .count()
    )

    return templates.TemplateResponse(
        request,
        "pending_contacts/_widget.html",
        {
            "contacts": contacts,
            "total_count": total_count,
        },
    )


@router.get("/{contact_id}", response_class=HTMLResponse)
async def get_pending_contact_detail(
    request: Request,
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """Get details for a specific pending contact."""
    contact = db.query(PendingContact).filter_by(id=contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Pending contact not found")

    # Get potential matches from existing persons
    potential_matches = []
    if contact.email:
        # Check for similar emails
        email_domain = contact.email.split("@")[-1] if "@" in contact.email else None
        if email_domain:
            similar = (
                db.query(Person)
                .join(PersonEmail)
                .filter(PersonEmail.email.ilike(f"%@{email_domain}"))
                .limit(5)
                .all()
            )
            potential_matches = similar

    return templates.TemplateResponse(
        request,
        "pending_contacts/detail.html",
        {
            "contact": contact,
            "potential_matches": potential_matches,
        },
    )


@router.post("/{contact_id}/create")
async def create_person_from_pending(
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Create a new person from a pending contact.

    Creates a Person record and links the email, then marks the pending contact as created.
    """
    contact = db.query(PendingContact).filter_by(id=contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Pending contact not found")

    if contact.status != PendingContactStatus.pending:
        raise HTTPException(
            status_code=400,
            detail=f"Contact already processed (status: {contact.status.value})"
        )

    # Parse name into first/last
    first_name = ""
    last_name = ""
    full_name = contact.name or contact.email.split("@")[0]

    if contact.name:
        parts = contact.name.strip().split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    # Create the person
    person = Person(
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        email=contact.email,
    )
    db.add(person)
    db.flush()  # Get the person.id

    # Create PersonEmail record
    person_email = PersonEmail(
        person_id=person.id,
        email=contact.email,
        label=EmailLabel.work,
        is_primary=True,
    )
    db.add(person_email)

    # Update pending contact
    contact.mark_created(person.id)

    db.commit()

    return {
        "success": True,
        "person_id": str(person.id),
        "person_name": full_name,
        "message": f"Created person '{full_name}' from pending contact",
    }


@router.post("/{contact_id}/ignore")
async def ignore_pending_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Mark a pending contact as ignored.

    The contact will no longer appear in the pending list.
    """
    contact = db.query(PendingContact).filter_by(id=contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Pending contact not found")

    if contact.status != PendingContactStatus.pending:
        raise HTTPException(
            status_code=400,
            detail=f"Contact already processed (status: {contact.status.value})"
        )

    contact.mark_ignored()
    db.commit()

    return {
        "success": True,
        "message": f"Ignored pending contact '{contact.email}'",
    }


@router.post("/{contact_id}/merge/{person_id}")
async def merge_pending_with_person(
    contact_id: UUID,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Merge a pending contact with an existing person.

    Adds the pending contact's email to the existing person if not already present.
    """
    contact = db.query(PendingContact).filter_by(id=contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Pending contact not found")

    if contact.status != PendingContactStatus.pending:
        raise HTTPException(
            status_code=400,
            detail=f"Contact already processed (status: {contact.status.value})"
        )

    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check if email already exists for this person
    existing_email = (
        db.query(PersonEmail)
        .filter_by(person_id=person_id, email=contact.email.lower())
        .first()
    )

    if not existing_email:
        # Add the email to the person
        person_email = PersonEmail(
            person_id=person_id,
            email=contact.email.lower(),
            label=EmailLabel.work,
            is_primary=False,  # Existing emails take precedence
        )
        db.add(person_email)

    # Mark pending contact as created
    contact.mark_created(person_id)
    db.commit()

    return {
        "success": True,
        "person_id": str(person_id),
        "person_name": person.full_name,
        "message": f"Merged pending contact with '{person.full_name}'",
        "email_added": existing_email is None,
    }


@router.delete("/{contact_id}")
async def delete_pending_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete a pending contact permanently.

    Use this for spam or clearly invalid contacts.
    """
    contact = db.query(PendingContact).filter_by(id=contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Pending contact not found")

    email = contact.email
    db.delete(contact)
    db.commit()

    return {
        "success": True,
        "message": f"Deleted pending contact '{email}'",
    }
