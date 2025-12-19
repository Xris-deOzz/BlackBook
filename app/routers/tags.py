"""
Tag management routes for Perun's BlackBook.
Handles creating, listing, editing, and deleting tags.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tag
from app.models.tag import PersonTag, OrganizationTag

router = APIRouter(prefix="/tags", tags=["tags"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_tags(
    request: Request,
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search tag names"),
    sort: Optional[str] = Query("name", description="Sort field: name, color, count"),
    order: Optional[str] = Query("asc", description="Sort order: asc, desc"),
):
    """
    List all tags grouped by People and Organizations.
    """
    # Validate sort parameters
    valid_sorts = {"name", "color", "count"}
    valid_orders = {"asc", "desc"}
    if sort not in valid_sorts:
        sort = "name"
    if order not in valid_orders:
        order = "asc"

    # Query for People tags (tags that have at least one person association)
    usage_count_label = func.count(func.distinct(PersonTag.person_id)).label("usage_count")
    people_tags_query = db.query(
        Tag,
        usage_count_label,
    ).join(
        PersonTag, Tag.id == PersonTag.tag_id
    ).group_by(Tag.id)

    if q:
        people_tags_query = people_tags_query.filter(Tag.name.ilike(f"%{q}%"))

    # Apply sorting for people tags
    if sort == "name":
        sort_col = Tag.name
    elif sort == "color":
        sort_col = Tag.color
    else:  # count
        sort_col = usage_count_label

    if order == "desc":
        people_tags_query = people_tags_query.order_by(desc(sort_col))
    else:
        people_tags_query = people_tags_query.order_by(sort_col)

    people_results = people_tags_query.all()

    people_tags = []
    for tag, usage_count in people_results:
        people_tags.append({
            "tag": tag,
            "usage_count": usage_count,
        })

    # Query for Organization tags (tags that have at least one org association)
    org_usage_count_label = func.count(func.distinct(OrganizationTag.organization_id)).label("usage_count")
    org_tags_query = db.query(
        Tag,
        org_usage_count_label,
    ).join(
        OrganizationTag, Tag.id == OrganizationTag.tag_id
    ).group_by(Tag.id)

    if q:
        org_tags_query = org_tags_query.filter(Tag.name.ilike(f"%{q}%"))

    # Apply sorting for org tags
    if sort == "name":
        org_sort_col = Tag.name
    elif sort == "color":
        org_sort_col = Tag.color
    else:  # count
        org_sort_col = org_usage_count_label

    if order == "desc":
        org_tags_query = org_tags_query.order_by(desc(org_sort_col))
    else:
        org_tags_query = org_tags_query.order_by(org_sort_col)

    org_results = org_tags_query.all()

    org_tags = []
    for tag, usage_count in org_results:
        org_tags.append({
            "tag": tag,
            "usage_count": usage_count,
        })

    return templates.TemplateResponse(
        "tags/list.html",
        {
            "request": request,
            "title": "Tag Management",
            "people_tags": people_tags,
            "org_tags": org_tags,
            "people_count": len(people_tags),
            "org_count": len(org_tags),
            "q": q or "",
            "sort": sort,
            "order": order,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_tag_form(
    request: Request,
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Pre-select category for the tag"),
):
    """
    Display the new tag form.
    """
    # Map category labels to display info
    category_info = {
        "People": {"title": "New People Tag", "description": "Create a new tag for organizing people"},
        "Firm Category": {"title": "New Firm Category Tag", "description": "Create a new tag for Investment Firms (VC, PE, Angels, etc.)"},
        "Company Category": {"title": "New Company Category Tag", "description": "Create a new tag for Companies (Banking, Payments, Insurance, etc.)"},
    }

    info = category_info.get(category, {"title": "New Tag", "description": "Create a new tag to organize people and organizations"})

    # Get existing subcategories for dropdown
    existing_subcategories = db.query(Tag.subcategory).filter(
        Tag.subcategory.isnot(None)
    ).distinct().order_by(Tag.subcategory).all()
    existing_subcategories = [s[0] for s in existing_subcategories]

    return templates.TemplateResponse(
        "tags/new.html",
        {
            "request": request,
            "title": info["title"],
            "description": info["description"],
            "category": category,
            "existing_subcategories": existing_subcategories,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_tag(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    color: str = Form("#6B7280"),
    category: Optional[str] = Form(None),
    subcategory: Optional[str] = Form(None),
):
    """
    Create a new tag.
    """
    # Check if tag with this name already exists
    existing = db.query(Tag).filter(Tag.name == name).first()
    if existing:
        # Map category labels to display info
        category_info = {
            "People": {"title": "New People Tag", "description": "Create a new tag for organizing people"},
            "Firm Category": {"title": "New Firm Category Tag", "description": "Create a new tag for Investment Firms (VC, PE, Angels, etc.)"},
            "Company Category": {"title": "New Company Category Tag", "description": "Create a new tag for Companies (Banking, Payments, Insurance, etc.)"},
        }
        info = category_info.get(category, {"title": "New Tag", "description": "Create a new tag to organize people and organizations"})

        # Get existing subcategories for dropdown
        existing_subcategories = db.query(Tag.subcategory).filter(
            Tag.subcategory.isnot(None)
        ).distinct().order_by(Tag.subcategory).all()
        existing_subcategories = [s[0] for s in existing_subcategories]

        return templates.TemplateResponse(
            "tags/new.html",
            {
                "request": request,
                "title": info["title"],
                "description": info["description"],
                "error": f"A tag with the name '{name}' already exists.",
                "name": name,
                "color": color,
                "category": category,
                "subcategory": subcategory,
                "existing_subcategories": existing_subcategories,
            },
            status_code=400,
        )

    # Clean subcategory - strip whitespace and set to None if empty
    if subcategory:
        subcategory = subcategory.strip() or None

    # Create new tag - only set category for org tags (Firm/Company), not People
    tag = Tag(
        name=name,
        color=color,
        category=category if category in ("Firm Category", "Company Category") else None,
        subcategory=subcategory,
    )

    db.add(tag)
    db.commit()
    db.refresh(tag)

    # Redirect back to settings tags tab
    return RedirectResponse(url="/settings?tab=tags", status_code=303)


@router.get("/{tag_id}", response_class=HTMLResponse)
async def tag_detail(
    request: Request,
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    """
    View tag details with associated people and organizations.
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Get counts
    person_count = db.query(PersonTag).filter(PersonTag.tag_id == tag_id).count()
    org_count = db.query(OrganizationTag).filter(OrganizationTag.tag_id == tag_id).count()

    return templates.TemplateResponse(
        "tags/detail.html",
        {
            "request": request,
            "title": f"Tag: {tag.name}",
            "tag": tag,
            "person_count": person_count,
            "org_count": org_count,
        },
    )


@router.get("/{tag_id}/edit", response_class=HTMLResponse)
async def edit_tag_form(
    request: Request,
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Display the edit tag form.
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Get existing subcategories for dropdown
    existing_subcategories = db.query(Tag.subcategory).filter(
        Tag.subcategory.isnot(None)
    ).distinct().order_by(Tag.subcategory).all()
    existing_subcategories = [s[0] for s in existing_subcategories]

    return templates.TemplateResponse(
        "tags/edit.html",
        {
            "request": request,
            "title": f"Edit Tag: {tag.name}",
            "tag": tag,
            "existing_subcategories": existing_subcategories,
        },
    )


@router.post("/{tag_id}", response_class=HTMLResponse)
async def update_tag(
    request: Request,
    tag_id: UUID,
    db: Session = Depends(get_db),
    name: str = Form(...),
    color: str = Form("#6B7280"),
    subcategory: Optional[str] = Form(None),
):
    """
    Update an existing tag.
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Check if another tag with this name exists
    existing = db.query(Tag).filter(Tag.name == name, Tag.id != tag_id).first()
    if existing:
        # Get existing subcategories for dropdown
        existing_subcategories = db.query(Tag.subcategory).filter(
            Tag.subcategory.isnot(None)
        ).distinct().order_by(Tag.subcategory).all()
        existing_subcategories = [s[0] for s in existing_subcategories]

        return templates.TemplateResponse(
            "tags/edit.html",
            {
                "request": request,
                "title": f"Edit Tag: {tag.name}",
                "tag": tag,
                "error": f"Another tag with the name '{name}' already exists.",
                "existing_subcategories": existing_subcategories,
            },
            status_code=400,
        )

    # Clean subcategory - strip whitespace and set to None if empty
    if subcategory:
        subcategory = subcategory.strip() or None

    # Update tag
    tag.name = name
    tag.color = color
    tag.subcategory = subcategory

    db.commit()
    db.refresh(tag)

    return RedirectResponse(url="/settings?tab=tags", status_code=303)


@router.delete("/{tag_id}", response_class=HTMLResponse)
async def delete_tag(
    request: Request,
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete a tag.
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    db.delete(tag)
    db.commit()

    return RedirectResponse(url="/settings?tab=tags", status_code=303)
