"""
Interaction routes for Perun's BlackBook.
Handles interaction listing, searching, filtering, CRUD operations, and HTMX partials.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Interaction, InteractionMedium, Person

router = APIRouter(prefix="/interactions", tags=["interactions"])
templates = Jinja2Templates(directory="app/templates")

# Constants
DEFAULT_PAGE_SIZE = 20


@router.get("", response_class=HTMLResponse)
async def list_interactions(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=250),
    q: Optional[str] = Query(None, description="Search query"),
    medium: Optional[str] = Query(None, description="Filter by interaction medium"),
    sort_by: str = Query("interaction_date", description="Sort column"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """
    Full page interaction list view.
    """
    # Build the query with filters applied
    query_result = _build_interaction_query(
        db=db,
        q=q,
        medium=medium,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count for pagination
    total_count = query_result.count()
    total_pages = (total_count + per_page - 1) // per_page

    # Apply pagination
    offset = (page - 1) * per_page
    interactions = query_result.offset(offset).limit(per_page).all()

    return templates.TemplateResponse(
        "interactions/list.html",
        {
            "request": request,
            "title": "Interactions",
            "interactions": interactions,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "q": q or "",
            "medium": medium or "",
            "sort_by": sort_by,
            "sort_order": sort_order,
            "mediums": [m.value for m in InteractionMedium],
        },
    )


@router.get("/table", response_class=HTMLResponse)
async def list_interactions_table(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=250),
    q: Optional[str] = Query(None, description="Search query"),
    medium: Optional[str] = Query(None, description="Filter by interaction medium"),
    sort_by: str = Query("interaction_date", description="Sort column"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """
    HTMX partial - returns just the table body for dynamic updates.
    """
    # Build the query with filters applied
    query_result = _build_interaction_query(
        db=db,
        q=q,
        medium=medium,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count for pagination
    total_count = query_result.count()
    total_pages = (total_count + per_page - 1) // per_page

    # Apply pagination
    offset = (page - 1) * per_page
    interactions = query_result.offset(offset).limit(per_page).all()

    return templates.TemplateResponse(
        "interactions/_table.html",
        {
            "request": request,
            "interactions": interactions,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "q": q or "",
            "medium": medium or "",
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


def _build_interaction_query(
    db: Session,
    q: Optional[str] = None,
    medium: Optional[str] = None,
    sort_by: str = "interaction_date",
    sort_order: str = "desc",
):
    """
    Build the interaction query with all filters and sorting applied.
    Returns the query object (not executed) for further processing.
    """
    # Start with base query, eager load person relationship
    query = db.query(Interaction).options(
        joinedload(Interaction.person),
    )

    # Apply text search filter
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Interaction.person_name.ilike(search_term),
                Interaction.notes.ilike(search_term),
                Interaction.files_sent.ilike(search_term),
            )
        )

    # Apply medium filter
    if medium:
        try:
            medium_enum = InteractionMedium(medium)
            query = query.filter(Interaction.medium == medium_enum)
        except ValueError:
            pass  # Invalid medium, ignore filter

    # Apply sorting
    sort_column = _get_sort_column(sort_by)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    return query


def _get_sort_column(sort_by: str):
    """Map sort_by parameter to SQLAlchemy column."""
    column_map = {
        "person_name": Interaction.person_name,
        "medium": Interaction.medium,
        "interaction_date": Interaction.interaction_date,
        "created_at": Interaction.created_at,
        "updated_at": Interaction.updated_at,
    }
    return column_map.get(sort_by, Interaction.interaction_date)


@router.get("/new", response_class=HTMLResponse)
async def new_interaction_form(
    request: Request,
    db: Session = Depends(get_db),
    person_id: Optional[str] = Query(None, description="Pre-select a person"),
):
    """
    Display the new interaction form.
    """
    # Get all people for the dropdown
    people = db.query(Person).order_by(Person.full_name).all()

    # Pre-selected person if provided
    selected_person = None
    if person_id:
        try:
            selected_person = db.query(Person).filter(Person.id == UUID(person_id)).first()
        except ValueError:
            pass

    return templates.TemplateResponse(
        "interactions/new.html",
        {
            "request": request,
            "title": "Log Interaction",
            "people": people,
            "selected_person": selected_person,
            "mediums": [m.value for m in InteractionMedium],
            "today": date.today().isoformat(),
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_interaction(
    request: Request,
    db: Session = Depends(get_db),
    person_id: Optional[str] = Form(None),
    medium: str = Form(...),
    interaction_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    files_sent: Optional[str] = Form(None),
):
    """
    Create a new interaction.
    """
    # Validate medium
    try:
        medium_enum = InteractionMedium(medium)
    except ValueError:
        medium_enum = InteractionMedium.other

    # Get person name if person selected
    person_name = None
    person_uuid = None
    if person_id and person_id.strip():
        try:
            person_uuid = UUID(person_id)
            person = db.query(Person).filter(Person.id == person_uuid).first()
            if person:
                person_name = person.full_name
        except ValueError:
            pass

    # Parse date
    parsed_date = None
    if interaction_date:
        try:
            parsed_date = date.fromisoformat(interaction_date)
        except ValueError:
            pass

    # Create interaction
    interaction = Interaction(
        person_id=person_uuid,
        person_name=person_name,
        medium=medium_enum,
        interaction_date=parsed_date,
        notes=notes.strip() if notes else None,
        files_sent=files_sent.strip() if files_sent else None,
    )

    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    # Redirect to the interaction detail or back to person if from person page
    if person_uuid:
        return RedirectResponse(url=f"/people/{person_uuid}", status_code=303)
    return RedirectResponse(url="/interactions", status_code=303)


@router.get("/{interaction_id}", response_class=HTMLResponse)
async def interaction_detail(
    request: Request,
    interaction_id: UUID,
    db: Session = Depends(get_db),
):
    """
    View interaction details.
    """
    interaction = db.query(Interaction).options(
        joinedload(Interaction.person)
    ).filter(Interaction.id == interaction_id).first()

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    return templates.TemplateResponse(
        "interactions/detail.html",
        {
            "request": request,
            "title": f"Interaction - {interaction.medium.value.replace('_', ' ').title()}",
            "interaction": interaction,
        },
    )


@router.get("/{interaction_id}/edit", response_class=HTMLResponse)
async def edit_interaction_form(
    request: Request,
    interaction_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Display the edit interaction form.
    """
    interaction = db.query(Interaction).options(
        joinedload(Interaction.person)
    ).filter(Interaction.id == interaction_id).first()

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    # Get all people for the dropdown
    people = db.query(Person).order_by(Person.full_name).all()

    return templates.TemplateResponse(
        "interactions/edit.html",
        {
            "request": request,
            "title": f"Edit Interaction",
            "interaction": interaction,
            "people": people,
            "mediums": [m.value for m in InteractionMedium],
        },
    )


@router.put("/{interaction_id}", response_class=HTMLResponse)
async def update_interaction(
    request: Request,
    interaction_id: UUID,
    db: Session = Depends(get_db),
    person_id: Optional[str] = Form(None),
    medium: str = Form(...),
    interaction_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    files_sent: Optional[str] = Form(None),
):
    """
    Update an existing interaction.
    """
    interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    # Validate medium
    try:
        medium_enum = InteractionMedium(medium)
    except ValueError:
        medium_enum = InteractionMedium.other

    # Get person name if person selected
    person_name = None
    person_uuid = None
    if person_id and person_id.strip():
        try:
            person_uuid = UUID(person_id)
            person = db.query(Person).filter(Person.id == person_uuid).first()
            if person:
                person_name = person.full_name
        except ValueError:
            pass

    # Parse date
    parsed_date = None
    if interaction_date:
        try:
            parsed_date = date.fromisoformat(interaction_date)
        except ValueError:
            pass

    # Update interaction
    interaction.person_id = person_uuid
    interaction.person_name = person_name
    interaction.medium = medium_enum
    interaction.interaction_date = parsed_date
    interaction.notes = notes.strip() if notes else None
    interaction.files_sent = files_sent.strip() if files_sent else None

    db.commit()
    db.refresh(interaction)

    return RedirectResponse(url=f"/interactions/{interaction_id}", status_code=303)


@router.delete("/{interaction_id}")
async def delete_interaction(
    request: Request,
    interaction_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete an interaction.
    Handles both HTMX/AJAX and regular browser requests.
    """
    interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    # Store person_id before deletion for redirect
    person_id = interaction.person_id

    db.delete(interaction)
    db.commit()

    # Check if this is an HTMX or fetch request
    if request.headers.get("HX-Request") or request.headers.get("Content-Type") == "application/json":
        from fastapi.responses import JSONResponse
        return JSONResponse(content={"success": True, "deleted_id": str(interaction_id)})

    # Regular browser request - redirect
    if person_id:
        return RedirectResponse(url=f"/people/{person_id}", status_code=303)
    return RedirectResponse(url="/interactions", status_code=303)
