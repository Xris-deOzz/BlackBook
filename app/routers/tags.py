"""
Tag management routes for Perun's BlackBook.
Handles creating, listing, editing, and deleting tags.
Also handles tag subcategory management with default colors.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tag, TagSubcategory, DEFAULT_SUBCATEGORY_COLORS
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

    # Get subcategories with their colors (ordered by display_order)
    subcategories = TagSubcategory.get_all_ordered(db)
    
    # Also get any subcategories that exist on tags but not in the subcategories table
    existing_tag_subcats = db.query(Tag.subcategory).filter(
        Tag.subcategory.isnot(None)
    ).distinct().all()
    existing_tag_subcats = {s[0] for s in existing_tag_subcats}
    
    subcat_names = {s.name for s in subcategories}
    orphan_subcats = existing_tag_subcats - subcat_names

    return templates.TemplateResponse(
        "tags/new.html",
        {
            "request": request,
            "title": info["title"],
            "description": info["description"],
            "category": category,
            "subcategories": subcategories,
            "orphan_subcategories": sorted(orphan_subcats),
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
    apply_subcategory_color: Optional[str] = Form(None),
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

        # Get subcategories
        subcategories = TagSubcategory.get_all_ordered(db)

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
                "subcategories": subcategories,
                "orphan_subcategories": [],
            },
            status_code=400,
        )

    # Clean subcategory - strip whitespace and set to None if empty
    if subcategory:
        subcategory = subcategory.strip() or None

    # Apply subcategory color if checkbox was checked
    if apply_subcategory_color == "true" and subcategory:
        color = TagSubcategory.get_color_for_subcategory(db, subcategory)

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


@router.post("/apply-taxonomy-mapping", response_class=JSONResponse)
async def apply_taxonomy_mapping(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Apply the master tag taxonomy mapping to all existing tags.
    Also CREATES any missing tags from the taxonomy.
    Updates subcategory assignments and applies the subcategory's default color.
    """
    # Master mapping from Excel: Tag Name -> Subcategory
    TAG_TO_SUBCATEGORY = {
        # Location
        "NYC": "Location",
        "SF": "Location",
        "Boston": "Location",
        "Chicago": "Location",
        "London": "Location",
        "PL": "Location",
        "Georgia": "Location",
        "Moscow": "Location",
        "DC": "Location",
        "Bialystok": "Location",
        
        # Classmates
        "Georgetown": "Classmates",
        
        # Education
        "Goodenough": "Education",
        "Hentz": "Education",
        "LFC": "Education",
        "LSE": "Education",
        "Maine East": "Education",
        "Karski": "Education",
        
        # Holidays
        "Xmas - Holidays": "Holidays",
        "Xmas ENG": "Holidays",
        "Xmas PL": "Holidays",
        "Xmas POL": "Holidays",
        "Happy Easter": "Holidays",
        "Hanukah": "Holidays",
        "Salute": "Holidays",
        
        # Personal
        "Admin": "Personal",
        "Matt": "Personal",
        "Personal": "Personal",
        "Art": "Personal",
        "arts": "Personal",
        
        # Social
        "Nudists": "Social",
        "X-Guys": "Social",
        
        # Professional
        "Entrepreneur | Founder": "Professional",
        "C-Suite": "Professional",
        "Partner": "Professional",
        "Managing Director": "Professional",
        "VP/Director": "Professional",
        "Advisor": "Professional",
        "Lawyer": "Professional",
        "Banker": "Professional",
        "Bankers": "Professional",
        "Accountant/CPA": "Professional",
        "Recruiter/Headhunter": "Professional",
        "Headhunter/Recruiter": "Professional",
        "Headhunters": "Professional",
        "Journalist/Media": "Professional",
        "Academic/Professor": "Professional",
        "Government/Regulator": "Professional",
        "Medical Contacts": "Professional",
        "Actuary": "Professional",
        "Resource: Actuary": "Professional",
        "Creative": "Professional",
        "Referrals | Introductions": "Professional",
        "Tech": "Professional",
        "Resource: Tech": "Professional",
        "FinTech": "Professional",
        "StartOut": "Professional",
        "Operations": "Professional",
        "Resource: Operations": "Professional",
        "Resource: Lawyer": "Professional",
        "Banker | Consultant": "Professional",
        
        # Former Colleagues
        "Credit Suisse": "Former Colleagues",
        "GAFG": "Former Colleagues",
        "Lehman": "Former Colleagues",
        "State Department": "Former Colleagues",
        
        # Investor Type
        "VC - Early Stage": "Investor Type",
        "VC - Growth": "Investor Type",
        "Venture VC": "Investor Type",
        "PE - Buyout": "Investor Type",
        "PE - Growth Equity": "Investor Type",
        "PE / Institutional": "Investor Type",
        "Angel Investor": "Investor Type",
        "Angel": "Investor Type",
        "Family Office": "Investor Type",
        "Hedge Fund - Long/Short": "Investor Type",
        "Hedge Fund  - Long/Short": "Investor Type",
        "Hedge Fund - Market Neutral; Pure Alpha": "Investor Type",
        "Hedge Fund - Risk Arb": "Investor Type",
        "Hedge Fund - Distressed / Special Situations": "Investor Type",
        "Hedge Fund - Activist": "Investor Type",
        "Hedge Fund - Macro (Rates, FX, Com)": "Investor Type",
        "Hedge Fund - Relative Value / Arb": "Investor Type",
        "Hedge Fund - Credit": "Investor Type",
        "Hedge Fund - Quant | HFT": "Investor Type",
        "Hedge Fund": "Investor Type",
        "Private Credit": "Investor Type",
        "LP": "Investor Type",
        "Corporate VC": "Investor Type",
        "Sovereign Wealth": "Investor Type",
        
        # Relationship Origin
        "Family": "Relationship Origin",
        "Friend": "Relationship Origin",
        "Classmate": "Relationship Origin",
        "Former Colleague": "Relationship Origin",
        "Referral": "Relationship Origin",
        "Conference/Event": "Relationship Origin",
        "Cold Outreach": "Relationship Origin",
        "Board Connection": "Relationship Origin",
        "Deal Connection": "Relationship Origin",
        "Social Apps": "Relationship Origin",
    }
    
    # Get all subcategory colors
    subcategories = {s.name: s.default_color for s in db.query(TagSubcategory).all()}
    
    # Track updates
    updated_tags = []
    created_tags = []
    skipped_tags = []
    
    # Get all existing tags (case-insensitive lookup)
    all_tags = db.query(Tag).all()
    existing_tag_names = {tag.name.lower(): tag for tag in all_tags}
    
    # First, update existing tags
    for tag in all_tags:
        # Check if tag name matches any mapping (case-insensitive)
        subcategory = None
        for tag_name, subcat in TAG_TO_SUBCATEGORY.items():
            if tag.name.lower() == tag_name.lower():
                subcategory = subcat
                break
        
        if subcategory:
            # Get color for this subcategory
            color = subcategories.get(subcategory, "#6b7280")
            
            # Update the tag
            tag.subcategory = subcategory
            tag.color = color
            updated_tags.append({"name": tag.name, "subcategory": subcategory, "color": color})
        else:
            skipped_tags.append(tag.name)
    
    # Second, create missing tags from the taxonomy
    for tag_name, subcategory in TAG_TO_SUBCATEGORY.items():
        if tag_name.lower() not in existing_tag_names:
            # Tag doesn't exist, create it
            color = subcategories.get(subcategory, "#6b7280")
            new_tag = Tag(
                name=tag_name,
                color=color,
                subcategory=subcategory,
            )
            db.add(new_tag)
            created_tags.append({"name": tag_name, "subcategory": subcategory, "color": color})
    
    db.commit()
    
    return {
        "success": True,
        "updated_count": len(updated_tags),
        "created_count": len(created_tags),
        "skipped_count": len(skipped_tags),
        "updated_tags": updated_tags,
        "created_tags": created_tags,
        "skipped_tags": skipped_tags,
    }


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

    # Get subcategories with their colors (ordered by display_order)
    subcategories = TagSubcategory.get_all_ordered(db)
    
    # Also get any subcategories that exist on tags but not in the subcategories table
    existing_tag_subcats = db.query(Tag.subcategory).filter(
        Tag.subcategory.isnot(None)
    ).distinct().all()
    existing_tag_subcats = {s[0] for s in existing_tag_subcats}
    
    subcat_names = {s.name for s in subcategories}
    orphan_subcats = existing_tag_subcats - subcat_names

    return templates.TemplateResponse(
        "tags/edit.html",
        {
            "request": request,
            "title": f"Edit Tag: {tag.name}",
            "tag": tag,
            "subcategories": subcategories,
            "orphan_subcategories": sorted(orphan_subcats),
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
    apply_subcategory_color: Optional[str] = Form(None),
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
        # Get subcategories
        subcategories = TagSubcategory.get_all_ordered(db)

        return templates.TemplateResponse(
            "tags/edit.html",
            {
                "request": request,
                "title": f"Edit Tag: {tag.name}",
                "tag": tag,
                "error": f"Another tag with the name '{name}' already exists.",
                "subcategories": subcategories,
                "orphan_subcategories": [],
            },
            status_code=400,
        )

    # Clean subcategory - strip whitespace and set to None if empty
    if subcategory:
        subcategory = subcategory.strip() or None

    # Apply subcategory color if checkbox was checked
    if apply_subcategory_color == "true" and subcategory:
        color = TagSubcategory.get_color_for_subcategory(db, subcategory)

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


# ===========================
# Subcategory Management
# ===========================


@router.get("/subcategories/list", response_class=HTMLResponse)
async def list_subcategories(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get subcategories list as HTML partial for settings page.
    """
    subcategories = TagSubcategory.get_all_ordered(db)
    
    # Get tag counts for each subcategory
    subcat_counts = {}
    for subcat in subcategories:
        count = db.query(Tag).filter(Tag.subcategory == subcat.name).count()
        subcat_counts[subcat.name] = count

    return templates.TemplateResponse(
        "tags/_subcategories_list.html",
        {
            "request": request,
            "subcategories": subcategories,
            "subcat_counts": subcat_counts,
        },
    )


@router.get("/subcategories/json", response_class=JSONResponse)
async def get_subcategories_json(
    db: Session = Depends(get_db),
):
    """
    Get all subcategories as JSON (for JavaScript use).
    """
    subcategories = TagSubcategory.get_all_ordered(db)
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "default_color": s.default_color,
            "display_order": s.display_order,
        }
        for s in subcategories
    ]


@router.post("/subcategories", response_class=JSONResponse)
async def create_subcategory(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    default_color: str = Form("#6b7280"),
):
    """
    Create a new subcategory.
    """
    # Check if subcategory with this name already exists
    existing = db.query(TagSubcategory).filter(TagSubcategory.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Subcategory '{name}' already exists")

    # Get next display order
    max_order = db.query(func.max(TagSubcategory.display_order)).scalar() or 0
    
    subcat = TagSubcategory(
        name=name,
        default_color=default_color,
        display_order=max_order + 1,
    )
    
    db.add(subcat)
    db.commit()
    db.refresh(subcat)

    return {
        "success": True,
        "id": str(subcat.id),
        "name": subcat.name,
        "default_color": subcat.default_color,
    }


@router.put("/subcategories/{subcat_id}", response_class=JSONResponse)
async def update_subcategory(
    subcat_id: UUID,
    db: Session = Depends(get_db),
    name: Optional[str] = Form(None),
    default_color: Optional[str] = Form(None),
    display_order: Optional[int] = Form(None),
):
    """
    Update a subcategory's name, color, or display order.
    """
    subcat = db.query(TagSubcategory).filter(TagSubcategory.id == subcat_id).first()
    if not subcat:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    if name is not None:
        # Check if another subcategory with this name exists
        existing = db.query(TagSubcategory).filter(
            TagSubcategory.name == name,
            TagSubcategory.id != subcat_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Subcategory '{name}' already exists")
        
        # Update tag subcategory references if name changed
        old_name = subcat.name
        if old_name != name:
            db.query(Tag).filter(Tag.subcategory == old_name).update(
                {"subcategory": name},
                synchronize_session=False
            )
        subcat.name = name

    if default_color is not None:
        subcat.default_color = default_color

    if display_order is not None:
        subcat.display_order = display_order

    db.commit()
    db.refresh(subcat)

    return {
        "success": True,
        "id": str(subcat.id),
        "name": subcat.name,
        "default_color": subcat.default_color,
        "display_order": subcat.display_order,
    }


@router.delete("/subcategories/{subcat_id}", response_class=JSONResponse)
async def delete_subcategory(
    subcat_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete a subcategory. Tags using this subcategory will keep their subcategory name.
    """
    subcat = db.query(TagSubcategory).filter(TagSubcategory.id == subcat_id).first()
    if not subcat:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    # Note: We intentionally do NOT update tags - they keep their subcategory string
    # This allows historical data to remain intact

    db.delete(subcat)
    db.commit()

    return {"success": True, "deleted": subcat.name}


@router.post("/subcategories/{subcat_id}/apply-color", response_class=JSONResponse)
async def apply_subcategory_color_to_all_tags(
    subcat_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Apply the subcategory's default color to all tags in that subcategory.
    """
    subcat = db.query(TagSubcategory).filter(TagSubcategory.id == subcat_id).first()
    if not subcat:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    # Update all tags with this subcategory
    updated_count = db.query(Tag).filter(Tag.subcategory == subcat.name).update(
        {"color": subcat.default_color},
        synchronize_session=False
    )
    
    db.commit()

    return {
        "success": True,
        "subcategory": subcat.name,
        "color": subcat.default_color,
        "updated_count": updated_count,
    }


@router.post("/subcategories/reorder", response_class=JSONResponse)
async def reorder_subcategories(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Reorder subcategories based on a list of IDs.
    Expects JSON body: {"order": ["uuid1", "uuid2", ...]}
    """
    data = await request.json()
    order_list = data.get("order", [])
    
    if not order_list:
        raise HTTPException(status_code=400, detail="Order list is required")

    for idx, subcat_id in enumerate(order_list):
        try:
            uuid_id = UUID(subcat_id)
            db.query(TagSubcategory).filter(TagSubcategory.id == uuid_id).update(
                {"display_order": idx + 1},
                synchronize_session=False
            )
        except ValueError:
            continue  # Skip invalid UUIDs

    db.commit()

    return {"success": True, "message": "Subcategories reordered"}


@router.post("/bulk-assign-subcategory", response_class=JSONResponse)
async def bulk_assign_subcategory(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Assign a subcategory to multiple tags at once.
    Expects JSON body: {"tag_ids": ["uuid1", "uuid2", ...], "subcategory": "Subcategory Name"}
    Optionally accepts "apply_color": true to also update tag colors.
    """
    data = await request.json()
    tag_ids = data.get("tag_ids", [])
    subcategory_name = data.get("subcategory", "").strip()
    apply_color = data.get("apply_color", False)
    
    if not tag_ids:
        raise HTTPException(status_code=400, detail="No tags selected")
    
    if not subcategory_name:
        raise HTTPException(status_code=400, detail="Subcategory name is required")
    
    # Get the subcategory color if we need to apply it
    color = None
    if apply_color:
        subcat = db.query(TagSubcategory).filter(TagSubcategory.name == subcategory_name).first()
        if subcat:
            color = subcat.default_color
    
    # Convert string IDs to UUIDs
    valid_ids = []
    for tag_id in tag_ids:
        try:
            valid_ids.append(UUID(tag_id))
        except ValueError:
            continue
    
    if not valid_ids:
        raise HTTPException(status_code=400, detail="No valid tag IDs provided")
    
    # Update the tags
    update_data = {"subcategory": subcategory_name}
    if color:
        update_data["color"] = color
    
    updated_count = db.query(Tag).filter(Tag.id.in_(valid_ids)).update(
        update_data,
        synchronize_session=False
    )
    
    db.commit()
    
    return {
        "success": True,
        "updated_count": updated_count,
        "subcategory": subcategory_name,
        "color": color,
    }


@router.put("/categories", response_class=JSONResponse)
async def update_category(
    db: Session = Depends(get_db),
    old_name: str = Form(...),
    new_name: str = Form(...),
):
    """
    Update a category name across all tags.
    This renames a category (e.g., "Firm Category" -> "Investment Firms").
    """
    old_name = old_name.strip()
    new_name = new_name.strip()

    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Category names cannot be empty")

    if old_name == new_name:
        raise HTTPException(status_code=400, detail="New name must be different from old name")

    # Check if any tags use the old category name
    tags_with_old_name = db.query(Tag).filter(Tag.category == old_name).count()
    if tags_with_old_name == 0:
        raise HTTPException(status_code=404, detail=f"No tags found with category '{old_name}'")

    # Check if the new name conflicts with an existing category
    tags_with_new_name = db.query(Tag).filter(Tag.category == new_name).count()
    if tags_with_new_name > 0:
        raise HTTPException(status_code=400, detail=f"Category '{new_name}' already exists")

    # Update all tags with the old category name
    updated_count = db.query(Tag).filter(Tag.category == old_name).update(
        {"category": new_name},
        synchronize_session=False
    )

    db.commit()

    return {
        "success": True,
        "updated_count": updated_count,
        "old_name": old_name,
        "new_name": new_name,
    }


@router.post("/categories/apply-color", response_class=JSONResponse)
async def apply_category_color(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Apply a color to all tags in a specific category.
    Expects JSON body: {"category": "Firm Category", "color": "#687280"}
    """
    data = await request.json()
    category_name = data.get("category", "").strip()
    color = data.get("color", "").strip()

    if not category_name:
        raise HTTPException(status_code=400, detail="Category name is required")

    if not color:
        raise HTTPException(status_code=400, detail="Color is required")

    # Update all tags in this category
    updated_count = db.query(Tag).filter(Tag.category == category_name).update(
        {"color": color},
        synchronize_session=False
    )

    if updated_count == 0:
        raise HTTPException(status_code=404, detail=f"No tags found in category '{category_name}'")

    db.commit()

    return {
        "success": True,
        "updated_count": updated_count,
        "category": category_name,
        "color": color,
    }


@router.post("/categories/delete", response_class=JSONResponse)
async def delete_category(
    db: Session = Depends(get_db),
    category: str = Form(...),
):
    """
    Delete a category by removing the category field from all tags.
    Tags will remain but have category set to NULL.
    """
    category = category.strip()

    if not category:
        raise HTTPException(status_code=400, detail="Category name is required")

    # Check if any tags use this category
    tags_count = db.query(Tag).filter(Tag.category == category).count()
    if tags_count == 0:
        raise HTTPException(status_code=404, detail=f"No tags found with category '{category}'")

    # Remove category from all tags (set to NULL)
    updated_count = db.query(Tag).filter(Tag.category == category).update(
        {"category": None},
        synchronize_session=False
    )

    db.commit()

    return {
        "success": True,
        "deleted": category,
        "updated_count": updated_count,
    }
