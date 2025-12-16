"""
Organization routes for Perun's BlackBook.
Handles organization listing, searching, filtering, and HTMX partials.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import os
import uuid as uuid_lib
from pathlib import Path
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, or_, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Organization, OrgType, Tag, PersonOrganization
from app.models import OrganizationCategory, OrganizationType
from app.models.tag import OrganizationTag
from app.models.org_relationship import OrganizationRelationship, OrgRelationshipType


class BatchDeleteRequest(BaseModel):
    ids: List[str]

router = APIRouter(prefix="/organizations", tags=["organizations"])
templates = Jinja2Templates(directory="app/templates")

# Constants
DEFAULT_PAGE_SIZE = 20
UPLOAD_DIR = "app/static/uploads/org_logos"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def validate_type_belongs_to_category(db: Session, type_id: int, category_id: int) -> bool:
    """
    Validate that an organization type belongs to the specified category.
    Returns True if valid, False otherwise.
    """
    org_type = db.query(OrganizationType).filter(OrganizationType.id == type_id).first()
    if not org_type:
        return False
    return org_type.category_id == category_id


@router.get("", response_class=HTMLResponse)
async def list_organizations(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=250),
    q: Optional[str] = Query(None, description="Search query"),
    org_type: Optional[str] = Query(None, description="Filter by organization type (legacy)"),
    category_id: Optional[str] = Query(None, description="Filter by organization category"),
    type_id: Optional[str] = Query(None, description="Filter by organization type"),
    tag_id: Optional[str] = Query(None, description="Filter by single tag (legacy)"),
    selected_tags: Optional[str] = Query(None, alias="tag_ids", description="Filter by multiple tags (comma-separated)"),
    tag_logic: str = Query("or", description="Logic for multiple tags: 'and' or 'or'"),
    letter: Optional[str] = Query(None, description="Filter by first letter of name"),
    sort_by: str = Query("name", description="Sort column"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
):
    """
    Full page organization list view.
    Supports both legacy org_type filter and new category_id/type_id filters.
    """
    # Get only tags that are associated with organizations
    all_tags = (
        db.query(Tag)
        .join(OrganizationTag, Tag.id == OrganizationTag.tag_id)
        .distinct()
        .order_by(Tag.name)
        .all()
    )

    # Get all categories for the filter dropdown
    all_categories = (
        db.query(OrganizationCategory)
        .filter(OrganizationCategory.is_active == True)
        .order_by(OrganizationCategory.sort_order)
        .all()
    )

    # Get all types grouped by category for cascading dropdown
    all_types = (
        db.query(OrganizationType)
        .filter(OrganizationType.is_active == True)
        .order_by(OrganizationType.category_id, OrganizationType.sort_order)
        .all()
    )

    # Build types_by_category dict for JavaScript
    types_by_category = {}
    for t in all_types:
        if t.category_id not in types_by_category:
            types_by_category[t.category_id] = []
        types_by_category[t.category_id].append({
            "id": t.id,
            "name": t.name,
            "code": t.code
        })

    # Parse multiple tag IDs (or fall back to single tag_id for backwards compatibility)
    tag_uuids = []
    if selected_tags and selected_tags.strip():
        for tid in selected_tags.split(','):
            tid = tid.strip()
            if tid:
                try:
                    tag_uuids.append(UUID(tid))
                except ValueError:
                    pass
    elif tag_id and tag_id.strip():
        # Backwards compatibility with single tag_id
        try:
            tag_uuids.append(UUID(tag_id))
        except ValueError:
            pass

    # Convert category_id and type_id from string to int (handle empty strings)
    category_id_int = int(category_id) if category_id and category_id.strip() else None
    type_id_int = int(type_id) if type_id and type_id.strip() else None

    # Build the query with filters applied
    query_result = _build_organization_query(
        db=db,
        q=q,
        org_type=org_type,
        category_id=category_id_int,
        type_id=type_id_int,
        tag_ids=tag_uuids,
        tag_logic=tag_logic,
        letter=letter,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count for pagination
    total_count = query_result.count()
    total_pages = (total_count + per_page - 1) // per_page

    # Apply pagination
    offset = (page - 1) * per_page
    organizations = query_result.offset(offset).limit(per_page).all()

    # Build list of selected tag ID strings for template
    selected_tag_ids = [str(tid) for tid in tag_uuids]

    return templates.TemplateResponse(
        "organizations/list.html",
        {
            "request": request,
            "title": "Organizations",
            "organizations": organizations,
            "all_tags": all_tags,
            "all_categories": all_categories,
            "types_by_category": types_by_category,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "q": q or "",
            "org_type": org_type or "",
            "category_id": category_id or "",
            "type_id": type_id or "",
            "selected_tag_ids": selected_tag_ids,
            "tag_logic": tag_logic,
            "letter": letter or "",
            "sort_by": sort_by,
            "sort_order": sort_order,
            "org_types": [t.value for t in OrgType],
        },
    )


@router.get("/table", response_class=HTMLResponse)
async def list_organizations_table(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=250),
    q: Optional[str] = Query(None, description="Search query"),
    org_type: Optional[str] = Query(None, description="Filter by organization type (legacy)"),
    category_id: Optional[str] = Query(None, description="Filter by organization category"),
    type_id: Optional[str] = Query(None, description="Filter by organization type"),
    tag_id: Optional[str] = Query(None, description="Filter by single tag (legacy)"),
    selected_tags: Optional[str] = Query(None, alias="tag_ids", description="Filter by multiple tags (comma-separated)"),
    tag_logic: str = Query("or", description="Logic for multiple tags: 'and' or 'or'"),
    letter: Optional[str] = Query(None, description="Filter by first letter of name"),
    sort_by: str = Query("name", description="Sort column"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
):
    """
    HTMX partial - returns just the table body for dynamic updates.
    Supports both legacy org_type filter and new category_id/type_id filters.
    Multi-tag filter with AND/OR logic.
    """
    # Convert category_id and type_id from string to int (handle empty strings)
    category_id_int = int(category_id) if category_id and category_id.strip() else None
    type_id_int = int(type_id) if type_id and type_id.strip() else None

    # Parse multiple tag IDs (or fall back to single tag_id for backwards compatibility)
    tag_uuids = []
    if selected_tags and selected_tags.strip():
        for tid in selected_tags.split(','):
            tid = tid.strip()
            if tid:
                try:
                    tag_uuids.append(UUID(tid))
                except ValueError:
                    pass
    elif tag_id and tag_id.strip():
        try:
            tag_uuids.append(UUID(tag_id))
        except ValueError:
            pass

    # Build the query with filters applied
    query_result = _build_organization_query(
        db=db,
        q=q,
        org_type=org_type,
        category_id=category_id_int,
        type_id=type_id_int,
        tag_ids=tag_uuids,
        tag_logic=tag_logic,
        letter=letter,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get total count for pagination
    total_count = query_result.count()
    total_pages = (total_count + per_page - 1) // per_page

    # Apply pagination
    offset = (page - 1) * per_page
    organizations = query_result.offset(offset).limit(per_page).all()

    return templates.TemplateResponse(
        "organizations/_table.html",
        {
            "request": request,
            "organizations": organizations,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "q": q or "",
            "org_type": org_type or "",
            "category_id": category_id or "",
            "type_id": type_id or "",
            "tag_id": str(tag_id) if tag_id else "",
            "letter": letter or "",
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


# ===========================
# Batch Operations (must be before /{org_id} routes)
# ===========================


@router.post("/batch/delete", response_class=JSONResponse)
async def batch_delete_organizations(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
):
    """
    Delete multiple organizations at once.
    """
    deleted_count = 0
    for id_str in request.ids:
        try:
            org_id = UUID(id_str)
            organization = db.query(Organization).filter(Organization.id == org_id).first()
            if organization:
                db.delete(organization)
                deleted_count += 1
        except ValueError:
            continue  # Invalid UUID, skip

    db.commit()

    return {"success": True, "deleted_count": deleted_count}


@router.get("/merge", response_class=HTMLResponse)
async def batch_merge_page(
    request: Request,
    ids: str = Query(..., description="Comma-separated list of organization IDs to merge"),
    db: Session = Depends(get_db),
):
    """
    Show the batch merge page for merging multiple selected organizations.
    """
    # Split comma-separated IDs
    id_list = [id_str.strip() for id_str in ids.split(",") if id_str.strip()]

    # Convert string IDs to UUIDs and fetch organizations
    organizations = []
    for id_str in id_list:
        try:
            org_id = UUID(id_str)
            organization = (
                db.query(Organization)
                .options(
                    joinedload(Organization.tags),
                    joinedload(Organization.affiliated_persons).joinedload(PersonOrganization.person),
                )
                .filter(Organization.id == org_id)
                .first()
            )
            if organization:
                organizations.append(organization)
        except ValueError:
            continue

    if len(organizations) < 2:
        raise HTTPException(status_code=400, detail="At least 2 valid organizations required for merge")

    return templates.TemplateResponse(
        "organizations/batch_merge.html",
        {
            "request": request,
            "title": "Merge Organizations",
            "organizations": organizations,
        },
    )


@router.post("/merge/execute", response_class=JSONResponse)
async def execute_batch_merge(
    request: Request,
    keep_id: str = Form(...),
    merge_ids: List[str] = Form(...),
    # Field selections - each field_X contains the org_id whose value should be used
    field_name: Optional[str] = Form(None),
    field_org_type: Optional[str] = Form(None),
    field_category: Optional[str] = Form(None),
    field_logo: Optional[str] = Form(None),
    field_description: Optional[str] = Form(None),
    field_website: Optional[str] = Form(None),
    field_crunchbase: Optional[str] = Form(None),
    field_priority_rank: Optional[str] = Form(None),
    field_notes: Optional[str] = Form(None),
    combine_notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Execute merge of multiple organizations into one with field-level selection.
    """
    try:
        keep_uuid = UUID(keep_id)
        merge_uuids = [UUID(mid) for mid in merge_ids if mid != keep_id]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    if not merge_uuids:
        raise HTTPException(status_code=400, detail="No organizations to merge")

    # Get the keeper organization
    keeper = (
        db.query(Organization)
        .options(
            joinedload(Organization.tags),
            joinedload(Organization.affiliated_persons).joinedload(PersonOrganization.person),
        )
        .filter(Organization.id == keep_uuid)
        .first()
    )
    if not keeper:
        raise HTTPException(status_code=404, detail="Target organization not found")

    # Build field selections dict - maps field name to source org UUID
    field_selections = {}
    field_mapping = {
        "name": field_name,
        "org_type": field_org_type,
        "category": field_category,
        "logo": field_logo,
        "description": field_description,
        "website": field_website,
        "crunchbase": field_crunchbase,
        "priority_rank": field_priority_rank,
        "notes": field_notes,
    }

    for field_name_key, source_id in field_mapping.items():
        if source_id:
            try:
                field_selections[field_name_key] = UUID(source_id)
            except ValueError:
                pass  # Invalid UUID, skip

    # Track stats
    total_stats = {
        "merged_count": 0,
        "tags_transferred": 0,
        "people_transferred": 0,
        "refs_transferred": 0,
    }

    # Merge each organization into the keeper
    for source_id in merge_uuids:
        source = (
            db.query(Organization)
            .options(
                joinedload(Organization.tags),
                joinedload(Organization.affiliated_persons),
            )
            .filter(Organization.id == source_id)
            .first()
        )
        if not source:
            continue

        # Apply field selections - copy values from source if selected
        for field_name_key, selected_org_id in field_selections.items():
            if selected_org_id == source_id:
                if field_name_key == "name":
                    keeper.name = source.name
                elif field_name_key == "org_type":
                    keeper.org_type = source.org_type
                elif field_name_key == "category":
                    keeper.category = source.category
                elif field_name_key == "logo":
                    keeper.logo = source.logo
                elif field_name_key == "description":
                    keeper.description = source.description
                elif field_name_key == "website":
                    keeper.website = source.website
                elif field_name_key == "crunchbase":
                    keeper.crunchbase = source.crunchbase
                elif field_name_key == "priority_rank":
                    keeper.priority_rank = source.priority_rank
                elif field_name_key == "notes":
                    if combine_notes == "true" and keeper.notes and source.notes:
                        keeper.notes = f"{keeper.notes}\n\n---\n\n{source.notes}"
                    else:
                        keeper.notes = source.notes

        # Transfer tags (avoid duplicates)
        keeper_tag_ids = {t.id for t in keeper.tags}
        for tag in source.tags:
            if tag.id not in keeper_tag_ids:
                keeper.tags.append(tag)
                total_stats["tags_transferred"] += 1

        # Transfer affiliated persons (update organization_id)
        for person_org in source.affiliated_persons:
            person_org.organization_id = keeper.id
            total_stats["people_transferred"] += 1

        # Delete the source organization
        db.delete(source)
        total_stats["merged_count"] += 1

    db.commit()

    return {
        "success": True,
        "redirect_url": f"/organizations/{keep_uuid}",
        **total_stats,
    }


def _build_organization_query(
    db: Session,
    q: Optional[str] = None,
    org_type: Optional[str] = None,
    category_id: Optional[int] = None,
    type_id: Optional[int] = None,
    tag_ids: Optional[List[UUID]] = None,
    tag_logic: str = "or",
    letter: Optional[str] = None,
    sort_by: str = "name",
    sort_order: str = "asc",
):
    """
    Build the organization query with all filters and sorting applied.
    Returns the query object (not executed) for further processing.

    Supports both old org_type enum filter and new category_id/type_id lookup filters.
    Multi-tag filter with AND/OR logic.
    """
    # Start with base query, eager load tags and affiliated persons
    query = db.query(Organization).options(
        joinedload(Organization.tags),
        joinedload(Organization.affiliated_persons).joinedload(PersonOrganization.person),
    )

    # Apply text search filter
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Organization.name.ilike(search_term),
                Organization.category.ilike(search_term),
                Organization.description.ilike(search_term),
                Organization.notes.ilike(search_term),
            )
        )

    # Apply org_type filter (legacy enum filter)
    if org_type:
        try:
            type_enum = OrgType(org_type)
            query = query.filter(Organization.org_type == type_enum)
        except ValueError:
            pass  # Invalid type, ignore filter

    # Apply category_id filter (new lookup system)
    if category_id:
        query = query.filter(Organization.category_id == category_id)

    # Apply type_id filter (new lookup system)
    if type_id:
        query = query.filter(Organization.type_id == type_id)

    # Apply multi-tag filter with AND/OR logic
    if tag_ids and len(tag_ids) > 0:
        if tag_logic == "and":
            # AND logic: organization must have ALL selected tags
            for tid in tag_ids:
                query = query.filter(Organization.tags.any(Tag.id == tid))
        else:
            # OR logic (default): organization must have ANY of the selected tags
            tag_conditions = [Organization.tags.any(Tag.id == tid) for tid in tag_ids]
            query = query.filter(or_(*tag_conditions))

    # Apply letter filter (first letter of name)
    if letter and len(letter) == 1 and letter.isalpha():
        letter_upper = letter.upper()
        query = query.filter(func.upper(func.left(Organization.name, 1)) == letter_upper)

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
        "name": Organization.name,
        "org_type": Organization.org_type,
        "category": Organization.category,
        "priority_rank": Organization.priority_rank,
        "created_at": Organization.created_at,
        "updated_at": Organization.updated_at,
    }
    return column_map.get(sort_by, Organization.name)


@router.get("/new", response_class=HTMLResponse)
async def new_organization_form(request: Request, db: Session = Depends(get_db)):
    """
    Display the new organization form.
    """
    # Get categories and types for the dropdown
    categories = (
        db.query(OrganizationCategory)
        .filter(OrganizationCategory.is_active == True)
        .order_by(OrganizationCategory.sort_order)
        .all()
    )

    # Build types grouped by category
    types_by_category = {}
    for cat in categories:
        types_by_category[cat.id] = [
            {"id": t.id, "code": t.code, "name": t.name, "profile_style": t.profile_style}
            for t in cat.types if t.is_active
        ]

    return templates.TemplateResponse(
        "organizations/new.html",
        {
            "request": request,
            "title": "New Organization",
            "organization": None,
            "categories": categories,
            "types_by_category": types_by_category,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_organization(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    org_type: str = Form("other"),
    category: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    type_id: Optional[int] = Form(None),
    priority_rank: int = Form(0),
    website: Optional[str] = Form(None),
    crunchbase: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
):
    """
    Create a new organization.
    Note: Logo is added separately via /logo upload endpoint after creation.

    Supports both old org_type enum and new category_id/type_id lookup system.
    When category_id and type_id are provided, validates that type belongs to category.
    """
    # Validate type belongs to category if both provided
    if category_id and type_id:
        if not validate_type_belongs_to_category(db, type_id, category_id):
            raise HTTPException(
                status_code=400,
                detail="Selected type does not belong to the selected category"
            )

    # Create new organization
    organization = Organization(
        name=name,
        org_type=OrgType(org_type),
        category=category or None,
        category_id=category_id,
        type_id=type_id,
        priority_rank=priority_rank,
        website=website or None,
        crunchbase=crunchbase or None,
        description=description or None,
        notes=notes or None,
    )

    db.add(organization)
    db.commit()
    db.refresh(organization)

    # Redirect to the new organization's detail page
    return RedirectResponse(url=f"/organizations/{organization.id}", status_code=303)


@router.get("/{org_id}/edit", response_class=HTMLResponse)
async def edit_organization_form(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Display the edit organization form.
    """
    from app.models import Person, RelationshipType

    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.affiliated_persons).joinedload(PersonOrganization.person),
            joinedload(Organization.tags),
        )
        .filter(Organization.id == org_id)
        .first()
    )

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get all persons for the dropdown
    all_persons = db.query(Person).order_by(Person.full_name).all()

    # Get relationship types
    relationship_types = [rt for rt in RelationshipType]

    # Get organization tags grouped by category
    # Filter to only tags with Firm Category or Company Category
    org_tags = (
        db.query(Tag)
        .filter(Tag.category.in_(["Firm Category", "Company Category"]))
        .order_by(Tag.name)
        .all()
    )
    current_tag_ids = {t.id for t in organization.tags}
    available_tags = [t for t in org_tags if t.id not in current_tag_ids]

    # Group available tags by category
    firm_category_tags = [t for t in available_tags if t.category == "Firm Category"]
    company_category_tags = [t for t in available_tags if t.category == "Company Category"]

    # Get categories and types for the dropdown
    categories = (
        db.query(OrganizationCategory)
        .filter(OrganizationCategory.is_active == True)
        .order_by(OrganizationCategory.sort_order)
        .all()
    )

    # Build types grouped by category
    types_by_category = {}
    for cat in categories:
        types_by_category[cat.id] = [
            {"id": t.id, "code": t.code, "name": t.name, "profile_style": t.profile_style}
            for t in cat.types if t.is_active
        ]

    return templates.TemplateResponse(
        "organizations/edit.html",
        {
            "request": request,
            "title": f"Edit {organization.name}",
            "organization": organization,
            "all_persons": all_persons,
            "relationship_types": relationship_types,
            "current_tags": organization.tags,
            "categories": categories,
            "types_by_category": types_by_category,
            "firm_category_tags": firm_category_tags,
            "company_category_tags": company_category_tags,
        },
    )


@router.put("/{org_id}", response_class=HTMLResponse)
async def update_organization(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
    name: str = Form(...),
    org_type: str = Form("other"),
    category: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    type_id: Optional[int] = Form(None),
    priority_rank: int = Form(0),
    website: Optional[str] = Form(None),
    crunchbase: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
):
    """
    Update an existing organization.
    Note: Logo is managed separately via /logo upload/delete endpoints.

    Supports both old org_type enum and new category_id/type_id lookup system.
    When category_id and type_id are provided, validates that type belongs to category.
    """
    organization = db.query(Organization).filter(Organization.id == org_id).first()

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate type belongs to category if both provided
    if category_id and type_id:
        if not validate_type_belongs_to_category(db, type_id, category_id):
            raise HTTPException(
                status_code=400,
                detail="Selected type does not belong to the selected category"
            )

    # Update organization fields (logo is managed separately)
    organization.name = name
    organization.org_type = OrgType(org_type)
    organization.category = category or None
    organization.category_id = category_id
    organization.type_id = type_id
    organization.priority_rank = priority_rank
    organization.website = website or None
    organization.crunchbase = crunchbase or None
    organization.description = description or None
    organization.notes = notes or None

    db.commit()
    db.refresh(organization)

    # Redirect to the organization's detail page
    return RedirectResponse(url=f"/organizations/{organization.id}", status_code=303)


@router.delete("/{org_id}", response_class=HTMLResponse)
async def delete_organization(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete an organization.
    """
    organization = db.query(Organization).filter(Organization.id == org_id).first()

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    db.delete(organization)
    db.commit()

    # Return redirect for HTMX or standard redirect
    return RedirectResponse(url="/organizations", status_code=303)


@router.get("/{org_id}", response_class=HTMLResponse)
async def get_organization_detail(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Organization detail page showing all information, related people, and tags.
    """
    from app.models import Interaction, Person
    from app.models.person_employment import PersonEmployment
    from app.models.organization_office import OrganizationOffice
    from app.models.organization_relationship_status import OrganizationRelationshipStatus
    from sqlalchemy import func

    # Query organization with all relationships loaded
    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.tags),
            joinedload(Organization.affiliated_persons).joinedload(PersonOrganization.person),
            joinedload(Organization.offices),
            joinedload(Organization.relationship_status).joinedload(OrganizationRelationshipStatus.primary_contact),
            joinedload(Organization.relationship_status).joinedload(OrganizationRelationshipStatus.intro_available_via),
            joinedload(Organization.type_ref),
            joinedload(Organization.category_ref),
        )
        .filter(Organization.id == org_id)
        .first()
    )

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Group all persons by relationship type for display
    people_by_type = {}
    for po in organization.affiliated_persons:
        rel_type = po.relationship.value
        if rel_type not in people_by_type:
            people_by_type[rel_type] = []
        people_by_type[rel_type].append(po)

    # Get org-to-org relationships context
    org_relationships_context = _get_org_relationships_context(db, organization)

    # Get aggregated interactions for all affiliated people
    # Get person IDs affiliated with this org via employment
    person_ids = (
        db.query(PersonEmployment.person_id)
        .filter(PersonEmployment.organization_id == org_id)
        .distinct()
        .all()
    )
    person_id_list = [pid[0] for pid in person_ids]

    interactions = []
    interaction_count = 0
    last_contacted = None
    most_frequent_contact = None

    if person_id_list:
        # Get interactions with person info
        interactions = (
            db.query(Interaction)
            .options(joinedload(Interaction.person))
            .filter(Interaction.person_id.in_(person_id_list))
            .order_by(Interaction.interaction_date.desc())
            .limit(20)
            .all()
        )

        interaction_count = (
            db.query(Interaction)
            .filter(Interaction.person_id.in_(person_id_list))
            .count()
        )

        # Get last contacted date
        if interactions:
            last_contacted = interactions[0].interaction_date

        # Find most frequent contact
        most_frequent_result = (
            db.query(
                Interaction.person_id,
                func.count(Interaction.id).label("count"),
            )
            .filter(Interaction.person_id.in_(person_id_list))
            .group_by(Interaction.person_id)
            .order_by(func.count(Interaction.id).desc())
            .first()
        )

        if most_frequent_result:
            person = db.query(Person).filter(Person.id == most_frequent_result[0]).first()
            if person:
                most_frequent_contact = person

    return templates.TemplateResponse(
        "organizations/detail.html",
        {
            "request": request,
            "title": organization.name,
            "organization": organization,
            "people_by_type": people_by_type,
            "affiliated_persons": organization.affiliated_persons,
            "interactions": interactions,
            "interaction_count": interaction_count,
            "last_contacted": last_contacted,
            "most_frequent_contact": most_frequent_contact,
            **org_relationships_context,
        },
    )


# ===========================
# Person Affiliation Management
# ===========================


@router.post("/{org_id}/affiliations", response_class=HTMLResponse)
async def add_person_affiliation(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
    person_id: Optional[str] = Form(None),
    person_name: Optional[str] = Form(None),
    relationship: str = Form("contact_at"),
    role: Optional[str] = Form(None),
    is_current: bool = Form(True),
):
    """
    Add a person affiliation to an organization.
    """
    from app.models import Person, RelationshipType

    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate person_id if provided
    person_uuid = None
    if person_id and person_id.strip():
        try:
            person_uuid = UUID(person_id)
            person = db.query(Person).filter(Person.id == person_uuid).first()
            if not person:
                raise HTTPException(status_code=404, detail="Person not found")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid person ID")

    # Either person_id or person_name must be provided
    if not person_uuid and not person_name:
        raise HTTPException(status_code=400, detail="Either person_id or person_name is required")

    # Validate relationship type
    try:
        rel_type = RelationshipType(relationship)
    except ValueError:
        rel_type = RelationshipType.contact_at

    # Check for duplicate (same person + org + relationship)
    existing = (
        db.query(PersonOrganization)
        .filter(
            PersonOrganization.organization_id == org_id,
            PersonOrganization.relationship == rel_type,
        )
    )
    if person_uuid:
        existing = existing.filter(PersonOrganization.person_id == person_uuid)
    else:
        existing = existing.filter(PersonOrganization.person_name == person_name)

    if existing.first():
        raise HTTPException(status_code=400, detail="This affiliation already exists")

    # Create new affiliation
    affiliation = PersonOrganization(
        person_id=person_uuid,
        organization_id=org_id,
        relationship=rel_type,
        person_name=person_name if not person_uuid else None,
        role=role or None,
        is_current=is_current,
    )

    db.add(affiliation)
    db.commit()
    db.refresh(affiliation)

    # Reload organization with affiliations for template
    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.affiliated_persons).joinedload(PersonOrganization.person),
        )
        .filter(Organization.id == org_id)
        .first()
    )

    # Get all persons and relationship types for the template
    all_persons = db.query(Person).order_by(Person.full_name).all()
    relationship_types = [rt for rt in RelationshipType]

    return templates.TemplateResponse(
        "organizations/_people_section.html",
        {
            "request": request,
            "organization": organization,
            "all_persons": all_persons,
            "relationship_types": relationship_types,
        },
    )


@router.put("/{org_id}/affiliations/{affiliation_id}", response_class=HTMLResponse)
async def update_person_affiliation(
    request: Request,
    org_id: UUID,
    affiliation_id: UUID,
    db: Session = Depends(get_db),
    relationship: str = Form("contact_at"),
    role: Optional[str] = Form(None),
    is_current: bool = Form(True),
):
    """
    Update an existing person affiliation.
    """
    from app.models import Person, RelationshipType

    affiliation = (
        db.query(PersonOrganization)
        .filter(
            PersonOrganization.id == affiliation_id,
            PersonOrganization.organization_id == org_id,
        )
        .first()
    )

    if not affiliation:
        raise HTTPException(status_code=404, detail="Affiliation not found")

    # Validate relationship type
    try:
        rel_type = RelationshipType(relationship)
    except ValueError:
        rel_type = RelationshipType.contact_at

    # Update fields
    affiliation.relationship = rel_type
    affiliation.role = role or None
    affiliation.is_current = is_current

    db.commit()

    # Reload organization with affiliations for template
    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.affiliated_persons).joinedload(PersonOrganization.person),
        )
        .filter(Organization.id == org_id)
        .first()
    )

    # Get all persons and relationship types for the template
    all_persons = db.query(Person).order_by(Person.full_name).all()
    relationship_types = [rt for rt in RelationshipType]

    return templates.TemplateResponse(
        "organizations/_people_section.html",
        {
            "request": request,
            "organization": organization,
            "all_persons": all_persons,
            "relationship_types": relationship_types,
        },
    )


@router.delete("/{org_id}/affiliations/{affiliation_id}", response_class=HTMLResponse)
async def delete_person_affiliation(
    request: Request,
    org_id: UUID,
    affiliation_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete a person affiliation from an organization.
    """
    from app.models import Person, RelationshipType

    affiliation = (
        db.query(PersonOrganization)
        .filter(
            PersonOrganization.id == affiliation_id,
            PersonOrganization.organization_id == org_id,
        )
        .first()
    )

    if not affiliation:
        raise HTTPException(status_code=404, detail="Affiliation not found")

    db.delete(affiliation)
    db.commit()

    # Reload organization with affiliations for template
    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.affiliated_persons).joinedload(PersonOrganization.person),
        )
        .filter(Organization.id == org_id)
        .first()
    )

    # Get all persons and relationship types for the template
    all_persons = db.query(Person).order_by(Person.full_name).all()
    relationship_types = [rt for rt in RelationshipType]

    return templates.TemplateResponse(
        "organizations/_people_section.html",
        {
            "request": request,
            "organization": organization,
            "all_persons": all_persons,
            "relationship_types": relationship_types,
        },
    )


# ===========================
# Tag Management
# ===========================


@router.post("/{org_id}/tags/{tag_id}", response_class=HTMLResponse)
async def add_tag_to_organization(
    request: Request,
    org_id: UUID,
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Add a tag to an organization.
    """
    organization = (
        db.query(Organization)
        .options(joinedload(Organization.tags))
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Check if tag is already assigned
    if tag not in organization.tags:
        organization.tags.append(tag)
        db.commit()

    # Get organization tags grouped by category
    org_tags = (
        db.query(Tag)
        .filter(Tag.category.in_(["Firm Category", "Company Category"]))
        .order_by(Tag.name)
        .all()
    )
    current_tag_ids = {t.id for t in organization.tags}
    available_tags = [t for t in org_tags if t.id not in current_tag_ids]

    # Group available tags by category
    firm_category_tags = [t for t in available_tags if t.category == "Firm Category"]
    company_category_tags = [t for t in available_tags if t.category == "Company Category"]

    return templates.TemplateResponse(
        "organizations/_tag_widget.html",
        {
            "request": request,
            "organization": organization,
            "current_tags": organization.tags,
            "firm_category_tags": firm_category_tags,
            "company_category_tags": company_category_tags,
        },
    )


@router.delete("/{org_id}/tags/{tag_id}", response_class=HTMLResponse)
async def remove_tag_from_organization(
    request: Request,
    org_id: UUID,
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Remove a tag from an organization.
    """
    organization = (
        db.query(Organization)
        .options(joinedload(Organization.tags))
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Remove tag if it's assigned
    if tag in organization.tags:
        organization.tags.remove(tag)
        db.commit()

    # Get organization tags grouped by category
    org_tags = (
        db.query(Tag)
        .filter(Tag.category.in_(["Firm Category", "Company Category"]))
        .order_by(Tag.name)
        .all()
    )
    current_tag_ids = {t.id for t in organization.tags}
    available_tags = [t for t in org_tags if t.id not in current_tag_ids]

    # Group available tags by category
    firm_category_tags = [t for t in available_tags if t.category == "Firm Category"]
    company_category_tags = [t for t in available_tags if t.category == "Company Category"]

    return templates.TemplateResponse(
        "organizations/_tag_widget.html",
        {
            "request": request,
            "organization": organization,
            "current_tags": organization.tags,
            "firm_category_tags": firm_category_tags,
            "company_category_tags": company_category_tags,
        },
    )


# ===========================
# Logo Management
# ===========================


@router.post("/{org_id}/logo", response_class=HTMLResponse)
async def upload_organization_logo(
    request: Request,
    org_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a logo for an organization."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

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

    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Delete old logo if it's a local file
    if organization.logo and organization.logo.startswith("/static/uploads/org_logos/"):
        old_path = organization.logo.replace("/static/", "app/static/")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    # Generate unique filename
    unique_filename = f"{uuid_lib.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # Save the file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Update database
    organization.logo = f"/static/uploads/org_logos/{unique_filename}"
    db.commit()
    db.refresh(organization)

    # Return the logo section HTML
    return templates.TemplateResponse(
        "organizations/_logo_section.html",
        {"request": request, "organization": organization}
    )


@router.delete("/{org_id}/logo", response_class=HTMLResponse)
async def delete_organization_logo(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an organization's logo."""
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Delete file if it's a local upload
    if organization.logo and organization.logo.startswith("/static/uploads/org_logos/"):
        old_path = organization.logo.replace("/static/", "app/static/")
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    # Clear the logo field
    organization.logo = None
    db.commit()
    db.refresh(organization)

    return templates.TemplateResponse(
        "organizations/_logo_section.html",
        {"request": request, "organization": organization}
    )


# ===========================
# Organization-to-Organization Relationships
# ===========================


def _get_org_relationships_context(db: Session, organization: Organization):
    """
    Helper to build context for org relationships template.
    Returns both outgoing and incoming relationships grouped by type,
    plus a list of all other organizations for the dropdown.
    """
    # Load relationships with their related organizations
    outgoing = (
        db.query(OrganizationRelationship)
        .options(joinedload(OrganizationRelationship.to_organization))
        .filter(OrganizationRelationship.from_organization_id == organization.id)
        .all()
    )
    incoming = (
        db.query(OrganizationRelationship)
        .options(joinedload(OrganizationRelationship.from_organization))
        .filter(OrganizationRelationship.to_organization_id == organization.id)
        .all()
    )

    # Group by relationship type
    outgoing_by_type = {}
    for rel in outgoing:
        # relationship_type is stored as string in DB
        rel_type = rel.relationship_type.value if hasattr(rel.relationship_type, 'value') else rel.relationship_type
        if rel_type not in outgoing_by_type:
            outgoing_by_type[rel_type] = []
        outgoing_by_type[rel_type].append(rel)

    incoming_by_type = {}
    for rel in incoming:
        # relationship_type is stored as string in DB
        rel_type = rel.relationship_type.value if hasattr(rel.relationship_type, 'value') else rel.relationship_type
        if rel_type not in incoming_by_type:
            incoming_by_type[rel_type] = []
        incoming_by_type[rel_type].append(rel)

    # Get all other organizations for the dropdown
    all_orgs = (
        db.query(Organization)
        .filter(Organization.id != organization.id)
        .order_by(Organization.name)
        .all()
    )

    return {
        "outgoing_relationships": outgoing,
        "incoming_relationships": incoming,
        "outgoing_by_type": outgoing_by_type,
        "incoming_by_type": incoming_by_type,
        "all_organizations": all_orgs,
        "relationship_types": [rt for rt in OrgRelationshipType],
    }


@router.post("/{org_id}/org-relationships", response_class=HTMLResponse)
async def add_org_relationship(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
    target_org_id: str = Form(...),
    relationship_type: str = Form(...),
    year: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
):
    """
    Add a relationship from this organization to another.
    """
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate target organization
    try:
        target_uuid = UUID(target_org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target organization ID")

    target_org = db.query(Organization).filter(Organization.id == target_uuid).first()
    if not target_org:
        raise HTTPException(status_code=404, detail="Target organization not found")

    # Validate relationship type
    try:
        rel_type = OrgRelationshipType(relationship_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid relationship type")

    # Check for duplicate
    existing = (
        db.query(OrganizationRelationship)
        .filter(
            OrganizationRelationship.from_organization_id == org_id,
            OrganizationRelationship.to_organization_id == target_uuid,
            OrganizationRelationship.relationship_type == rel_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="This relationship already exists")

    # Create the relationship
    relationship = OrganizationRelationship(
        from_organization_id=org_id,
        to_organization_id=target_uuid,
        relationship_type=rel_type,
        year=year,
        notes=notes or None,
    )
    db.add(relationship)
    db.commit()

    # Return updated section
    context = _get_org_relationships_context(db, organization)
    return templates.TemplateResponse(
        "organizations/_org_relationships_section.html",
        {"request": request, "organization": organization, **context},
    )


@router.put("/{org_id}/org-relationships/{rel_id}", response_class=HTMLResponse)
async def update_org_relationship(
    request: Request,
    org_id: UUID,
    rel_id: UUID,
    db: Session = Depends(get_db),
    relationship_type: str = Form(...),
    year: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
):
    """
    Update an organization-to-organization relationship.
    """
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    relationship = (
        db.query(OrganizationRelationship)
        .filter(
            OrganizationRelationship.id == rel_id,
            OrganizationRelationship.from_organization_id == org_id,
        )
        .first()
    )
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Validate relationship type
    try:
        rel_type = OrgRelationshipType(relationship_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid relationship type")

    # Update fields
    relationship.relationship_type = rel_type
    relationship.year = year
    relationship.notes = notes or None
    db.commit()

    # Return updated section
    context = _get_org_relationships_context(db, organization)
    return templates.TemplateResponse(
        "organizations/_org_relationships_section.html",
        {"request": request, "organization": organization, **context},
    )


@router.delete("/{org_id}/org-relationships/{rel_id}", response_class=HTMLResponse)
async def delete_org_relationship(
    request: Request,
    org_id: UUID,
    rel_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete an organization-to-organization relationship.
    """
    organization = db.query(Organization).filter(Organization.id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Find relationship (could be outgoing from this org)
    relationship = (
        db.query(OrganizationRelationship)
        .filter(
            OrganizationRelationship.id == rel_id,
            or_(
                OrganizationRelationship.from_organization_id == org_id,
                OrganizationRelationship.to_organization_id == org_id,
            ),
        )
        .first()
    )
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    db.delete(relationship)
    db.commit()

    # Return updated section
    context = _get_org_relationships_context(db, organization)
    return templates.TemplateResponse(
        "organizations/_org_relationships_section.html",
        {"request": request, "organization": organization, **context},
    )
