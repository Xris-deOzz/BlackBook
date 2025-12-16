"""
Saved Views routes for Perun's BlackBook.
Handles creating, listing, and applying saved filter views.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SavedView

router = APIRouter(prefix="/views", tags=["views"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_views(
    request: Request,
    db: Session = Depends(get_db),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
):
    """
    List all saved views, optionally filtered by entity type.
    """
    query = db.query(SavedView).order_by(SavedView.name)

    if entity_type:
        query = query.filter(SavedView.entity_type == entity_type)

    views = query.all()

    # Group views by entity type
    person_views = [v for v in views if v.entity_type == "person"]
    org_views = [v for v in views if v.entity_type == "organization"]

    return templates.TemplateResponse(
        "views/list.html",
        {
            "request": request,
            "title": "Saved Views",
            "views": views,
            "person_views": person_views,
            "org_views": org_views,
            "entity_type": entity_type or "",
        },
    )


@router.get("/sidebar", response_class=HTMLResponse)
async def get_sidebar_views(
    request: Request,
    db: Session = Depends(get_db),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
):
    """
    HTMX partial - returns saved views for sidebar component.
    """
    query = db.query(SavedView).order_by(SavedView.name)

    if entity_type:
        query = query.filter(SavedView.entity_type == entity_type)

    views = query.all()

    return templates.TemplateResponse(
        "views/_sidebar.html",
        {
            "request": request,
            "views": views,
            "entity_type": entity_type or "",
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_view_form(
    request: Request,
    entity_type: str = Query(..., description="Entity type: person or organization"),
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    org_type: Optional[str] = Query(None),
    tag_id: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
):
    """
    Display the new saved view form, pre-populated with current filter state.
    """
    # Build filters dict from query params
    filters = {}
    if q:
        filters["q"] = q
    if status:
        filters["status"] = status
    if org_type:
        filters["org_type"] = org_type
    if tag_id:
        filters["tag_id"] = tag_id

    return templates.TemplateResponse(
        "views/new.html",
        {
            "request": request,
            "title": "Save Current View",
            "entity_type": entity_type,
            "filters": filters,
            "sort_by": sort_by or "",
            "sort_order": sort_order or "asc",
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_view(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    entity_type: str = Form(...),
    filters_q: Optional[str] = Form(None),
    filters_status: Optional[str] = Form(None),
    filters_org_type: Optional[str] = Form(None),
    filters_tag_id: Optional[str] = Form(None),
    sort_by: Optional[str] = Form(None),
    sort_order: str = Form("asc"),
    is_default: Optional[str] = Form(None),
):
    """
    Create a new saved view.
    """
    # Build filters dict
    filters = {}
    if filters_q:
        filters["q"] = filters_q
    if filters_status:
        filters["status"] = filters_status
    if filters_org_type:
        filters["org_type"] = filters_org_type
    if filters_tag_id:
        filters["tag_id"] = filters_tag_id

    # If setting as default, unset any existing defaults for this entity type
    if is_default == "true":
        db.query(SavedView).filter(
            SavedView.entity_type == entity_type,
            SavedView.is_default == True
        ).update({"is_default": False})

    # Create new view
    view = SavedView(
        name=name,
        entity_type=entity_type,
        filters=filters,
        sort_by=sort_by or None,
        sort_order=sort_order,
        is_default=is_default == "true",
    )

    db.add(view)
    db.commit()
    db.refresh(view)

    # Redirect back to the appropriate list page
    if entity_type == "person":
        return RedirectResponse(url="/people", status_code=303)
    else:
        return RedirectResponse(url="/organizations", status_code=303)


@router.get("/{view_id}", response_class=HTMLResponse)
async def apply_view(
    request: Request,
    view_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Apply a saved view by redirecting to the appropriate list with filters.
    """
    view = db.query(SavedView).filter(SavedView.id == view_id).first()

    if not view:
        raise HTTPException(status_code=404, detail="View not found")

    # Build redirect URL with filter params
    base_url = "/people" if view.entity_type == "person" else "/organizations"
    params = []

    # Add filter params
    if view.filters:
        for key, value in view.filters.items():
            if value:
                params.append(f"{key}={value}")

    # Add sort params
    if view.sort_by:
        params.append(f"sort_by={view.sort_by}")
    if view.sort_order:
        params.append(f"sort_order={view.sort_order}")

    url = base_url
    if params:
        url += "?" + "&".join(params)

    return RedirectResponse(url=url, status_code=303)


@router.get("/{view_id}/edit", response_class=HTMLResponse)
async def edit_view_form(
    request: Request,
    view_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Display the edit view form.
    """
    view = db.query(SavedView).filter(SavedView.id == view_id).first()

    if not view:
        raise HTTPException(status_code=404, detail="View not found")

    return templates.TemplateResponse(
        "views/edit.html",
        {
            "request": request,
            "title": f"Edit View: {view.name}",
            "view": view,
        },
    )


@router.put("/{view_id}", response_class=HTMLResponse)
async def update_view(
    request: Request,
    view_id: UUID,
    db: Session = Depends(get_db),
    name: str = Form(...),
    filters_q: Optional[str] = Form(None),
    filters_status: Optional[str] = Form(None),
    filters_org_type: Optional[str] = Form(None),
    filters_tag_id: Optional[str] = Form(None),
    sort_by: Optional[str] = Form(None),
    sort_order: str = Form("asc"),
    is_default: Optional[str] = Form(None),
):
    """
    Update an existing saved view.
    """
    view = db.query(SavedView).filter(SavedView.id == view_id).first()

    if not view:
        raise HTTPException(status_code=404, detail="View not found")

    # Build filters dict
    filters = {}
    if filters_q:
        filters["q"] = filters_q
    if filters_status:
        filters["status"] = filters_status
    if filters_org_type:
        filters["org_type"] = filters_org_type
    if filters_tag_id:
        filters["tag_id"] = filters_tag_id

    # If setting as default, unset any existing defaults for this entity type
    if is_default == "true" and not view.is_default:
        db.query(SavedView).filter(
            SavedView.entity_type == view.entity_type,
            SavedView.is_default == True
        ).update({"is_default": False})

    # Update view
    view.name = name
    view.filters = filters
    view.sort_by = sort_by or None
    view.sort_order = sort_order
    view.is_default = is_default == "true"

    db.commit()
    db.refresh(view)

    return RedirectResponse(url="/views", status_code=303)


@router.delete("/{view_id}", response_class=HTMLResponse)
async def delete_view(
    request: Request,
    view_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete a saved view.
    """
    view = db.query(SavedView).filter(SavedView.id == view_id).first()

    if not view:
        raise HTTPException(status_code=404, detail="View not found")

    db.delete(view)
    db.commit()

    return RedirectResponse(url="/views", status_code=303)


def create_default_views(db: Session):
    """
    Create default views if they don't exist.
    Called during app startup or via management command.
    """
    default_views = [
        {
            "name": "All People",
            "entity_type": "person",
            "filters": {},
            "sort_by": "full_name",
            "sort_order": "asc",
            "is_default": True,
        },
        {
            "name": "VIP People",
            "entity_type": "person",
            "filters": {},  # Will filter by priority >= 1 (needs custom handling)
            "sort_by": "full_name",
            "sort_order": "asc",
            "is_default": False,
        },
        {
            "name": "Active People",
            "entity_type": "person",
            "filters": {"status": "active"},
            "sort_by": "full_name",
            "sort_order": "asc",
            "is_default": False,
        },
        {
            "name": "All Organizations",
            "entity_type": "organization",
            "filters": {},
            "sort_by": "name",
            "sort_order": "asc",
            "is_default": True,
        },
        {
            "name": "Investment Firms",
            "entity_type": "organization",
            "filters": {"org_type": "investment_firm"},
            "sort_by": "name",
            "sort_order": "asc",
            "is_default": False,
        },
        {
            "name": "Companies",
            "entity_type": "organization",
            "filters": {"org_type": "company"},
            "sort_by": "name",
            "sort_order": "asc",
            "is_default": False,
        },
    ]

    for view_data in default_views:
        # Check if view with this name already exists
        existing = db.query(SavedView).filter(SavedView.name == view_data["name"]).first()
        if not existing:
            view = SavedView(**view_data)
            db.add(view)

    db.commit()
