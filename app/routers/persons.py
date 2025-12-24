"""
Person routes for Perun's BlackBook.
Handles person listing, searching, filtering, and HTMX partials.
"""

from datetime import date
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, or_, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Person, Tag, PersonOrganization, Interaction, PersonEmail, GoogleAccount
from app.models.tag import PersonTag
from app.models.person_email import EmailLabel
from app.models.person_website import PersonWebsite
from app.models.person_address import PersonAddress
from app.models.person_education import PersonEducation
from app.models.person_employment import PersonEmployment
from app.models.person_relationship import PersonRelationship
from app.models.affiliation_type import AffiliationType
from app.models.relationship_type import RelationshipType
from app.services.person_merge import (
    merge_persons,
    find_potential_duplicates,
    PersonMergeError,
    PersonNotFoundError,
    SamePersonError,
)
from app.utils.gmail_compose import build_gmail_compose_url_with_chooser

router = APIRouter(prefix="/people", tags=["people"])
templates = Jinja2Templates(directory="app/templates")

# Constants
DEFAULT_PAGE_SIZE = 20


@router.get("", response_class=HTMLResponse)
async def list_people(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=250),
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tag_id: Optional[str] = Query(None, description="Filter by single tag (legacy)"),
    selected_tags: Optional[str] = Query(None, alias="tag_ids", description="Filter by multiple tags (comma-separated)"),
    tag_logic: str = Query("or", description="Logic for multiple tags: 'and' or 'or'"),
    letter: Optional[str] = Query(None, description="Filter by first letter of last name"),
    sort_by: str = Query("full_name", description="Sort column"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
):
    """
    Full page person list view.
    Supports multi-tag filter with AND/OR logic.
    """
    # Get all "People Tags" - tags without a category (org tags have categories like "Firm Category")
    # This includes newly created tags with 0 people associations
    all_tags = (
        db.query(Tag)
        .filter(Tag.category.is_(None))
        .order_by(Tag.name)
        .all()
    )

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

    # Build the query with filters applied
    query_result = _build_person_query(
        db=db,
        q=q,
        status=status,
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
    persons = query_result.offset(offset).limit(per_page).all()

    # Build list of selected tag ID strings for template
    selected_tag_ids = [str(tid) for tid in tag_uuids]

    return templates.TemplateResponse(
        "persons/list.html",
        {
            "request": request,
            "title": "People",
            "persons": persons,
            "all_tags": all_tags,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "q": q or "",
            "status": status or "",
            "tag_id": str(tag_id) if tag_id else "",
            "selected_tag_ids": selected_tag_ids,
            "tag_logic": tag_logic,
            "letter": letter or "",
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


@router.get("/table", response_class=HTMLResponse)
async def list_people_table(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=250),
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tag_id: Optional[str] = Query(None, description="Filter by single tag (legacy)"),
    selected_tags: Optional[str] = Query(None, alias="tag_ids", description="Filter by multiple tags (comma-separated)"),
    tag_logic: str = Query("or", description="Logic for multiple tags: 'and' or 'or'"),
    letter: Optional[str] = Query(None, description="Filter by first letter of last name"),
    sort_by: str = Query("full_name", description="Sort column"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
):
    """
    HTMX partial - returns just the table body for dynamic updates.
    Supports multi-tag filter with AND/OR logic.
    """
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
    query_result = _build_person_query(
        db=db,
        q=q,
        status=status,
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
    persons = query_result.offset(offset).limit(per_page).all()

    return templates.TemplateResponse(
        "persons/_table.html",
        {
            "request": request,
            "persons": persons,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "q": q or "",
            "status": status or "",
            "tag_id": str(tag_id) if tag_id else "",
            "tag_logic": tag_logic,
            "letter": letter or "",
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


def _build_person_query(
    db: Session,
    q: Optional[str] = None,
    status: Optional[str] = None,
    tag_ids: Optional[List[UUID]] = None,
    tag_logic: str = "or",
    letter: Optional[str] = None,
    sort_by: str = "full_name",
    sort_order: str = "asc",
):
    """
    Build the person query with all filters and sorting applied.
    Returns the query object (not executed) for further processing.
    Supports multi-tag filter with AND/OR logic.
    """
    # Start with base query, eager load tags, organizations, and interactions
    query = db.query(Person).options(
        joinedload(Person.tags),
        joinedload(Person.organizations).joinedload(PersonOrganization.organization),
        joinedload(Person.interactions),
    )

    # Apply text search filter
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Person.full_name.ilike(search_term),
                Person.first_name.ilike(search_term),
                Person.last_name.ilike(search_term),
                Person.title.ilike(search_term),
                Person.email.ilike(search_term),
                Person.notes.ilike(search_term),
            )
        )

    # Status filter removed - status column no longer exists

    # Apply tag filter (multi-tag with AND/OR logic)
    if tag_ids and len(tag_ids) > 0:
        if tag_logic.lower() == "and":
            # AND logic: person must have ALL selected tags
            for tid in tag_ids:
                query = query.filter(Person.tags.any(Tag.id == tid))
        else:
            # OR logic: person must have ANY of the selected tags
            tag_conditions = [Person.tags.any(Tag.id == tid) for tid in tag_ids]
            query = query.filter(or_(*tag_conditions))

    # Apply letter filter (first letter of last_name, fallback to full_name)
    if letter and len(letter) == 1 and letter.isalpha():
        letter_upper = letter.upper()
        # Filter by last_name if available, otherwise by full_name
        query = query.filter(
            or_(
                func.upper(func.left(Person.last_name, 1)) == letter_upper,
                # If last_name is null, check full_name
                (Person.last_name.is_(None)) & (func.upper(func.left(Person.full_name, 1)) == letter_upper),
            )
        )

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
        "full_name": Person.full_name,
        "first_name": Person.first_name,
        "last_name": Person.last_name,
        "title": Person.title,
        "created_at": Person.created_at,
        "updated_at": Person.updated_at,
    }
    return column_map.get(sort_by, Person.full_name)


@router.get("/new", response_class=HTMLResponse)
async def new_person_form(request: Request, db: Session = Depends(get_db)):
    """
    Display the new person form.
    """
    from app.models.relationship_type import RelationshipType

    # Get all tags for the form
    all_tags = db.query(Tag).order_by(Tag.name).all()

    # Get all persons for relationship dropdown
    all_persons = db.query(Person).order_by(Person.full_name).all()

    # Get relationship types for dropdown
    relationship_types = db.query(RelationshipType).order_by(RelationshipType.name).all()

    return templates.TemplateResponse(
        "persons/new.html",
        {
            "request": request,
            "title": "New Person",
            "person": None,
            "all_tags": all_tags,
            "person_tag_ids": set(),
            "all_persons": all_persons,
            "relationship_types": relationship_types,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_person(
    request: Request,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    first_name: Optional[str] = Form(None),
    middle_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    nickname: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    contacted: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    birthday: Optional[date] = Form(None),
    linkedin: Optional[str] = Form(None),
    twitter: Optional[str] = Form(None),
    website: Optional[str] = Form(None),
    crunchbase: Optional[str] = Form(None),
    angellist: Optional[str] = Form(None),
    investment_type: Optional[str] = Form(None),
    amount_funded: Optional[str] = Form(None),
    potential_intro_vc: Optional[str] = Form(None),
    profile_picture: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    tag_ids: Optional[List[str]] = Form(None),
    company_name: Optional[str] = Form(None),
):
    """
    Create a new person.
    """
    # Create new person
    person = Person(
        full_name=full_name,
        first_name=first_name or None,
        middle_name=middle_name or None,
        last_name=last_name or None,
        nickname=nickname or None,
        title=title or None,
        contacted=contacted == "true",
        email=email or None,
        phone=phone or None,
        location=location or None,
        birthday=birthday,
        linkedin=linkedin or None,
        twitter=twitter or None,
        website=website or None,
        crunchbase=crunchbase or None,
        angellist=angellist or None,
        investment_type=investment_type or None,
        amount_funded=amount_funded or None,
        potential_intro_vc=potential_intro_vc or None,
        profile_picture=profile_picture or None,
        notes=notes or None,
    )

    db.add(person)
    db.commit()
    db.refresh(person)

    # Add tags if provided
    if tag_ids:
        for tag_id in tag_ids:
            try:
                tag_uuid = UUID(tag_id)
                tag = db.query(Tag).filter(Tag.id == tag_uuid).first()
                if tag:
                    person.tags.append(tag)
            except ValueError:
                pass  # Invalid UUID, skip
        db.commit()

    # Create employment record if company_name is provided
    if company_name:
        # Try to find the "Employee" affiliation type
        affiliation = db.query(AffiliationType).filter(AffiliationType.name == "Employee").first()

        employment = PersonEmployment(
            person_id=person.id,
            organization_name=company_name,
            title=title or None,
            affiliation_type_id=affiliation.id if affiliation else None,
            is_current=True
        )
        db.add(employment)
        db.commit()

    # Redirect to the new person's detail page
    return RedirectResponse(url=f"/people/{person.id}", status_code=303)


# ===========================
# Batch Operations
# ===========================
# NOTE: These routes MUST come before /{person_id} routes to avoid path conflicts


class BatchDeleteRequest(BaseModel):
    ids: List[str]
    scope: str = "both"  # "blackbook_only", "google_only", or "both"


class BatchAddTagsRequest(BaseModel):
    person_ids: List[str]
    tag_ids: List[str]


@router.get("/batch/tags/modal", response_class=HTMLResponse)
async def get_batch_tags_modal(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get the modal for batch adding tags to selected persons.
    """
    # Get all "People Tags" - tags without a category (includes newly created tags with 0 associations)
    all_tags = (
        db.query(Tag)
        .filter(Tag.category.is_(None))
        .order_by(Tag.name)
        .all()
    )
    return templates.TemplateResponse(
        "persons/_batch_tags_modal.html",
        {
            "request": request,
            "all_tags": all_tags,
        },
    )


@router.post("/batch/tags", response_class=JSONResponse)
async def batch_add_tags(
    request: BatchAddTagsRequest,
    db: Session = Depends(get_db),
):
    """
    Add tags to multiple persons at once.
    """
    added_count = 0
    for person_id_str in request.person_ids:
        try:
            person_id = UUID(person_id_str)
            # Verify person exists
            person = db.query(Person).filter(Person.id == person_id).first()
            if not person:
                continue

            for tag_id_str in request.tag_ids:
                try:
                    tag_id = UUID(tag_id_str)
                    # Check if already exists
                    existing = db.query(PersonTag).filter_by(
                        person_id=person_id, tag_id=tag_id
                    ).first()
                    if not existing:
                        new_pt = PersonTag(person_id=person_id, tag_id=tag_id)
                        db.add(new_pt)
                        added_count += 1
                except ValueError:
                    continue
        except ValueError:
            continue

    db.commit()
    return {"success": True, "added_count": added_count}


@router.post("/batch/delete/modal", response_class=HTMLResponse)
async def get_batch_delete_modal(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Return the batch delete confirmation modal.
    Accepts POST with JSON body containing ids to check Google link status.
    """
    # Try to get IDs from JSON body
    try:
        body = await request.json()
        ids = body.get("ids", [])
    except Exception:
        ids = []

    total_count = len(ids)
    google_linked_count = 0

    # Count how many persons have google_resource_name
    for id_str in ids:
        try:
            person_id = UUID(id_str)
            person = db.query(Person).filter(Person.id == person_id).first()
            if person and person.google_resource_name:
                google_linked_count += 1
        except ValueError:
            continue

    return templates.TemplateResponse(
        "persons/_batch_delete_modal.html",
        {
            "request": request,
            "total_count": total_count,
            "google_linked_count": google_linked_count,
        },
    )


@router.get("/batch/delete/modal", response_class=HTMLResponse)
async def get_batch_delete_modal_simple(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Return the batch delete confirmation modal (GET version).
    The count will be updated by JavaScript after loading.
    """
    return templates.TemplateResponse(
        "persons/_batch_delete_modal.html",
        {
            "request": request,
            "total_count": 0,  # Will be updated by JS
            "google_linked_count": 0,  # Will be updated by JS
        },
    )


@router.post("/batch/delete", response_class=JSONResponse)
async def batch_delete_persons(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
):
    """
    Delete multiple persons at once with optional Google Contacts sync.

    Supports scope parameter:
    - "blackbook_only": Delete from BlackBook only, keep in Google
    - "google_only": Delete from Google only, keep in BlackBook
    - "both": Delete from both BlackBook and Google (default)
    """
    from app.services.contacts_service import ContactsService

    # Validate scope
    if request.scope not in ("blackbook_only", "google_only", "both"):
        raise HTTPException(status_code=400, detail="Invalid scope")

    # Convert string IDs to UUIDs
    person_ids = []
    for id_str in request.ids:
        try:
            person_ids.append(UUID(id_str))
        except ValueError:
            continue  # Invalid UUID, skip

    if not person_ids:
        return {"success": True, "deleted_count": 0, "blackbook_deleted": 0, "google_deleted": 0}

    # Use ContactsService for scope-aware bulk deletion
    contacts_service = ContactsService(db)
    result = contacts_service.delete_persons_bulk_with_scope(person_ids, request.scope)

    return {
        "success": result["success"],
        "deleted_count": result["blackbook_deleted"],
        "blackbook_deleted": result["blackbook_deleted"],
        "google_deleted": result["google_deleted"],
        "failed": result["failed"],
        "errors": result.get("errors", []),
    }


@router.get("/merge", response_class=HTMLResponse)
async def batch_merge_page(
    request: Request,
    ids: List[str] = Query(..., description="List of person IDs to merge"),
    db: Session = Depends(get_db),
):
    """
    Show the batch merge page for merging multiple selected persons.
    """
    # Convert string IDs to UUIDs and fetch persons
    persons = []
    for id_str in ids:
        try:
            person_id = UUID(id_str)
            person = (
                db.query(Person)
                .options(
                    joinedload(Person.tags),
                    joinedload(Person.organizations).joinedload(PersonOrganization.organization),
                    joinedload(Person.emails),
                    joinedload(Person.phones),
                    joinedload(Person.websites),
                    joinedload(Person.addresses),
                    joinedload(Person.education),
                    joinedload(Person.employment).joinedload(PersonEmployment.organization),
                    joinedload(Person.relationships_from).joinedload(PersonRelationship.related_person),
                    joinedload(Person.interactions),
                )
                .filter(Person.id == person_id)
                .first()
            )
            if person:
                persons.append(person)
        except ValueError:
            continue

    if len(persons) < 2:
        raise HTTPException(status_code=400, detail="At least 2 valid persons required for merge")

    return templates.TemplateResponse(
        "persons/batch_merge.html",
        {
            "request": request,
            "title": "Merge People",
            "persons": persons,
        },
    )


@router.post("/merge/execute", response_class=JSONResponse)
async def execute_batch_merge(
    request: Request,
    keep_id: str = Form(...),
    merge_ids: List[str] = Form(...),
    # Field selections - each field_X contains the person_id whose value should be used
    field_full_name: Optional[str] = Form(None),
    field_first_name: Optional[str] = Form(None),
    field_last_name: Optional[str] = Form(None),
    field_title: Optional[str] = Form(None),
    field_profile_picture: Optional[str] = Form(None),
    field_birthday: Optional[str] = Form(None),
    field_location: Optional[str] = Form(None),
    field_phone: Optional[str] = Form(None),
    field_linkedin: Optional[str] = Form(None),
    field_twitter: Optional[str] = Form(None),
    field_website: Optional[str] = Form(None),
    field_crunchbase: Optional[str] = Form(None),
    field_angellist: Optional[str] = Form(None),
    field_investment_type: Optional[str] = Form(None),
    field_amount_funded: Optional[str] = Form(None),
    field_potential_intro_vc: Optional[str] = Form(None),
    field_notes: Optional[str] = Form(None),
    field_priority: Optional[str] = Form(None),
    field_status: Optional[str] = Form(None),
    field_contacted: Optional[str] = Form(None),
    combine_notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Execute merge of multiple persons into one with field-level selection.
    """
    try:
        keep_uuid = UUID(keep_id)
        merge_uuids = [UUID(mid) for mid in merge_ids if mid != keep_id]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    if not merge_uuids:
        raise HTTPException(status_code=400, detail="No persons to merge")

    # Build field selections dict - maps field name to source person UUID
    field_selections = {}
    field_mapping = {
        "full_name": field_full_name,
        "first_name": field_first_name,
        "last_name": field_last_name,
        "title": field_title,
        "profile_picture": field_profile_picture,
        "birthday": field_birthday,
        "location": field_location,
        "phone": field_phone,
        "linkedin": field_linkedin,
        "twitter": field_twitter,
        "website": field_website,
        "crunchbase": field_crunchbase,
        "angellist": field_angellist,
        "investment_type": field_investment_type,
        "amount_funded": field_amount_funded,
        "potential_intro_vc": field_potential_intro_vc,
        "notes": field_notes,
        "priority": field_priority,
        "status": field_status,
        "contacted": field_contacted,
    }

    for field_name, source_id in field_mapping.items():
        if source_id:
            try:
                field_selections[field_name] = UUID(source_id)
            except ValueError:
                pass  # Invalid UUID, skip

    # Merge each person into the keeper
    total_stats = {
        "merged_count": 0,
        "emails_transferred": 0,
        "phones_transferred": 0,
        "tags_transferred": 0,
        "interactions_transferred": 0,
        "organizations_transferred": 0,
    }

    try:
        for source_id in merge_uuids:
            try:
                stats = merge_persons(
                    db,
                    source_id=source_id,
                    target_id=keep_uuid,
                    field_selections=field_selections,
                    combine_notes=(combine_notes == "true"),
                )
                total_stats["merged_count"] += 1
                total_stats["emails_transferred"] += stats.get("emails_transferred", 0)
                total_stats["phones_transferred"] += stats.get("phones_transferred", 0)
                total_stats["tags_transferred"] += stats.get("tags_transferred", 0)
                total_stats["interactions_transferred"] += stats.get("interactions_transferred", 0)
                total_stats["organizations_transferred"] += stats.get("organizations_transferred", 0)
            except (PersonNotFoundError, SamePersonError, PersonMergeError) as e:
                print(f"Merge warning for {source_id}: {e}")
                continue  # Skip problematic merges

        db.commit()

        return {
            "success": True,
            "redirect_url": f"/people/{keep_uuid}",
            **total_stats,
        }
    except Exception as e:
        db.rollback()
        print(f"Merge error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")


# ===========================
# Person CRUD (with {person_id} in path)
# ===========================


@router.get("/{person_id}/edit", response_class=HTMLResponse)
async def edit_person_form(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Display the edit person form.
    """
    person = (
        db.query(Person)
        .options(
            joinedload(Person.tags),
            joinedload(Person.emails),
            joinedload(Person.phones),
            joinedload(Person.websites),
            joinedload(Person.addresses),
            joinedload(Person.education),
            joinedload(Person.employment).joinedload(PersonEmployment.organization),
            joinedload(Person.employment).joinedload(PersonEmployment.affiliation_type),
            joinedload(Person.relationships_from).joinedload(PersonRelationship.related_person),
            joinedload(Person.relationships_from).joinedload(PersonRelationship.relationship_type),
            joinedload(Person.relationships_from).joinedload(PersonRelationship.context_organization),
        )
        .filter(Person.id == person_id)
        .first()
    )

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Get all "People Tags" - tags without a category (includes newly created tags with 0 associations)
    all_tags = (
        db.query(Tag)
        .filter(Tag.category.is_(None))
        .order_by(Tag.name)
        .all()
    )
    # Get IDs of tags already assigned to this person
    person_tag_ids = {t.id for t in person.tags}

    # Get lookup values for employment and relationships
    affiliation_types = db.query(AffiliationType).order_by(AffiliationType.name).all()
    relationship_types = db.query(RelationshipType).order_by(RelationshipType.name).all()

    return templates.TemplateResponse(
        "persons/edit.html",
        {
            "request": request,
            "title": f"Edit {person.full_name}",
            "person": person,
            "all_tags": all_tags,
            "person_tag_ids": person_tag_ids,
            "affiliation_types": affiliation_types,
            "relationship_types": relationship_types,
        },
    )


@router.put("/{person_id}", response_class=HTMLResponse)
async def update_person(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    contacted: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    birthday: Optional[date] = Form(None),
    linkedin: Optional[str] = Form(None),
    twitter: Optional[str] = Form(None),
    website: Optional[str] = Form(None),
    crunchbase: Optional[str] = Form(None),
    angellist: Optional[str] = Form(None),
    investment_type: Optional[str] = Form(None),
    amount_funded: Optional[str] = Form(None),
    potential_intro_vc: Optional[str] = Form(None),
    profile_picture: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    tag_ids: List[str] = Form(default=[]),
):
    """
    Update an existing person.
    """
    person = db.query(Person).filter(Person.id == person_id).first()

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Update person fields
    person.full_name = full_name
    person.first_name = first_name or None
    person.last_name = last_name or None
    person.title = title or None
    person.contacted = contacted == "true"
    person.email = email or None
    person.phone = phone or None
    person.location = location or None
    person.birthday = birthday
    person.linkedin = linkedin or None
    person.twitter = twitter or None
    person.website = website or None
    person.crunchbase = crunchbase or None
    person.angellist = angellist or None
    person.investment_type = investment_type or None
    person.amount_funded = amount_funded or None
    person.potential_intro_vc = potential_intro_vc or None
    person.profile_picture = profile_picture or None
    person.notes = notes or None

    # Update tags - remove all existing, add new ones
    db.query(PersonTag).filter_by(person_id=person_id).delete()
    for tag_id_str in tag_ids:
        try:
            tag_uuid = UUID(tag_id_str)
            # Verify tag exists
            tag = db.query(Tag).filter_by(id=tag_uuid).first()
            if tag:
                new_pt = PersonTag(person_id=person_id, tag_id=tag_uuid)
                db.add(new_pt)
        except ValueError:
            continue  # Invalid UUID, skip

    db.commit()
    db.refresh(person)

    # Redirect to the person's detail page
    return RedirectResponse(url=f"/people/{person.id}", status_code=303)


@router.get("/{person_id}/delete/modal", response_class=HTMLResponse)
async def get_delete_modal(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Return the delete confirmation modal for a person.
    Shows Google sync options if person is linked to Google Contacts.
    """
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    return templates.TemplateResponse(
        "persons/_delete_modal.html",
        {
            "request": request,
            "person": person,
            "has_google_link": bool(person.google_resource_name),
        },
    )


@router.delete("/{person_id}", response_class=JSONResponse)
async def delete_person(
    request: Request,
    person_id: UUID,
    scope: str = Query("both", regex="^(blackbook_only|google_only|both)$"),
    db: Session = Depends(get_db),
):
    """
    Delete a person with optional Google Contacts sync.

    Args:
        person_id: UUID of the person to delete
        scope: Delete scope - "blackbook_only", "google_only", or "both" (default)

    Returns:
        JSON response with success status and redirect URL
    """
    from app.services.contacts_service import ContactsService, ContactsServiceError

    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Use ContactsService for scope-aware deletion
    contacts_service = ContactsService(db)

    try:
        result = contacts_service.delete_person_with_scope(person_id, scope)

        if result["success"]:
            return {
                "success": True,
                "redirect_url": "/people",
                "blackbook_deleted": result["blackbook_deleted"],
                "google_deleted": result["google_deleted"],
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to delete contact")
            )
    except ContactsServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{person_id}", response_class=HTMLResponse)
async def get_person_detail(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Person detail page showing all information, organizations, tags, and interactions.
    """
    # Query person with all relationships loaded
    person = (
        db.query(Person)
        .options(
            joinedload(Person.tags),
            joinedload(Person.organizations).joinedload(PersonOrganization.organization),
            joinedload(Person.interactions),
            joinedload(Person.emails),
            joinedload(Person.phones),
            joinedload(Person.websites),
            joinedload(Person.addresses),
            joinedload(Person.education),
            joinedload(Person.employment).joinedload(PersonEmployment.organization),
            joinedload(Person.employment).joinedload(PersonEmployment.affiliation_type),
            joinedload(Person.relationships_from).joinedload(PersonRelationship.related_person),
            joinedload(Person.relationships_from).joinedload(PersonRelationship.relationship_type),
            joinedload(Person.relationships_from).joinedload(PersonRelationship.context_organization),
        )
        .filter(Person.id == person_id)
        .first()
    )

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Sort interactions by date descending (most recent first)
    interactions_sorted = sorted(
        person.interactions,
        key=lambda x: x.interaction_date or x.created_at,
        reverse=True,
    )

    # Build Gmail compose URL with account chooser (allows user to select Gmail account)
    email_compose_url = None
    if person.primary_email:
        email_compose_url = build_gmail_compose_url_with_chooser(to=person.primary_email)

    # Get active Google accounts for calendar selection
    google_accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    return templates.TemplateResponse(
        "persons/detail.html",
        {
            "request": request,
            "title": person.full_name,
            "person": person,
            "interactions": interactions_sorted,
            "email_compose_url": email_compose_url,
            "google_accounts": google_accounts,
        },
    )


# ===========================
# Person Email Management
# ===========================


@router.get("/{person_id}/emails/manage", response_class=HTMLResponse)
async def get_email_manage_modal(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get the email management modal for a person.
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    emails = db.query(PersonEmail).filter_by(person_id=person_id).order_by(
        PersonEmail.is_primary.desc(),
        PersonEmail.created_at.asc(),
    ).all()

    return templates.TemplateResponse(
        "persons/_email_manage.html",
        {
            "request": request,
            "person_id": str(person_id),
            "emails": emails,
        },
    )


@router.post("/{person_id}/emails", response_class=HTMLResponse)
async def add_person_email(
    request: Request,
    person_id: UUID,
    email: str = Form(...),
    label: str = Form("work"),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
):
    """
    Add a new email address to a person.
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check for duplicate
    existing = db.query(PersonEmail).filter_by(
        person_id=person_id,
        email=email.lower().strip(),
    ).first()

    if existing:
        # Just refresh the modal without adding
        emails = db.query(PersonEmail).filter_by(person_id=person_id).order_by(
            PersonEmail.is_primary.desc(),
            PersonEmail.created_at.asc(),
        ).all()
        return templates.TemplateResponse(
            "persons/_email_manage.html",
            {
                "request": request,
                "person_id": str(person_id),
                "emails": emails,
            },
        )

    # If setting as primary, unset others
    if is_primary:
        db.query(PersonEmail).filter_by(person_id=person_id).update({"is_primary": False})

    # Create new email
    new_email = PersonEmail(
        person_id=person_id,
        email=email.lower().strip(),
        label=EmailLabel(label),
        is_primary=is_primary,
    )
    db.add(new_email)
    db.commit()

    # Return updated modal
    emails = db.query(PersonEmail).filter_by(person_id=person_id).order_by(
        PersonEmail.is_primary.desc(),
        PersonEmail.created_at.asc(),
    ).all()

    return templates.TemplateResponse(
        "persons/_email_manage.html",
        {
            "request": request,
            "person_id": str(person_id),
            "emails": emails,
        },
    )


@router.delete("/{person_id}/emails/{email_id}", response_class=HTMLResponse)
async def delete_person_email(
    request: Request,
    person_id: UUID,
    email_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Delete an email address from a person.
    """
    email = db.query(PersonEmail).filter_by(id=email_id, person_id=person_id).first()
    if email:
        was_primary = email.is_primary
        db.delete(email)
        db.commit()

        # If deleted was primary, set another as primary
        if was_primary:
            remaining = db.query(PersonEmail).filter_by(person_id=person_id).first()
            if remaining:
                remaining.is_primary = True
                db.commit()

    # Return updated modal
    emails = db.query(PersonEmail).filter_by(person_id=person_id).order_by(
        PersonEmail.is_primary.desc(),
        PersonEmail.created_at.asc(),
    ).all()

    return templates.TemplateResponse(
        "persons/_email_manage.html",
        {
            "request": request,
            "person_id": str(person_id),
            "emails": emails,
        },
    )


@router.post("/{person_id}/emails/{email_id}/primary", response_class=HTMLResponse)
async def set_primary_email(
    request: Request,
    person_id: UUID,
    email_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Set an email as the primary email for a person.
    """
    email = db.query(PersonEmail).filter_by(id=email_id, person_id=person_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Unset all others as primary
    db.query(PersonEmail).filter_by(person_id=person_id).update({"is_primary": False})

    # Set this one as primary
    email.is_primary = True
    db.commit()

    # Return updated modal
    emails = db.query(PersonEmail).filter_by(person_id=person_id).order_by(
        PersonEmail.is_primary.desc(),
        PersonEmail.created_at.asc(),
    ).all()

    return templates.TemplateResponse(
        "persons/_email_manage.html",
        {
            "request": request,
            "person_id": str(person_id),
            "emails": emails,
        },
    )


# ===========================
# Person Merge Feature
# ===========================


@router.get("/{person_id}/merge", response_class=HTMLResponse)
async def get_merge_page(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Show the merge page for finding and selecting duplicate persons.
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Find potential duplicates
    duplicates = find_potential_duplicates(db, person_id)

    return templates.TemplateResponse(
        "persons/merge.html",
        {
            "request": request,
            "title": f"Merge {person.full_name}",
            "person": person,
            "duplicates": duplicates,
        },
    )


@router.get("/{person_id}/merge/search", response_class=HTMLResponse)
async def search_persons_for_merge(
    request: Request,
    person_id: UUID,
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    """
    Search for persons to merge with (HTMX partial).
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Search for matching persons (excluding self)
    search_term = f"%{q}%"
    results = (
        db.query(Person)
        .filter(Person.id != person_id)
        .filter(
            or_(
                Person.full_name.ilike(search_term),
                Person.first_name.ilike(search_term),
                Person.last_name.ilike(search_term),
                Person.email.ilike(search_term),
            )
        )
        .limit(10)
        .all()
    )

    return templates.TemplateResponse(
        "persons/_merge_search_results.html",
        {
            "request": request,
            "source_person": person,
            "results": results,
        },
    )


@router.post("/{person_id}/merge/{target_id}")
async def perform_merge(
    person_id: UUID,
    target_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Merge person_id (source) into target_id.

    The source person will be deleted and all their data
    transferred to the target person.

    Returns JSON with merge statistics.
    """
    try:
        stats = merge_persons(db, source_id=person_id, target_id=target_id)
        db.commit()
        return {
            "success": True,
            "message": f"Merged '{stats['source_name']}' into '{stats['target_name']}'",
            "redirect_url": f"/people/{target_id}",
            **stats,
        }
    except SamePersonError:
        raise HTTPException(
            status_code=400,
            detail="Cannot merge a person with themselves",
        )
    except PersonNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PersonMergeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{person_id}/duplicates", response_class=HTMLResponse)
async def get_duplicates_widget(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get potential duplicates widget for person detail page.
    """
    duplicates = find_potential_duplicates(db, person_id, limit=5)

    return templates.TemplateResponse(
        "persons/_duplicates_widget.html",
        {
            "request": request,
            "person_id": str(person_id),
            "duplicates": duplicates,
        },
    )


# ===========================
# Person Tag Management
# ===========================


@router.get("/{person_id}/tags/manage", response_class=HTMLResponse)
async def get_tag_manage_widget(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get the tag management widget for a person.
    Returns the current tags and available tags to add.
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Get person's current tags
    current_tag_ids = {t.id for t in person.tags}

    # Get all "People Tags" - tags without a category (includes newly created tags with 0 associations)
    people_tags = (
        db.query(Tag)
        .filter(Tag.category.is_(None))
        .order_by(Tag.name)
        .all()
    )
    available_tags = [t for t in people_tags if t.id not in current_tag_ids]

    # Group available tags by subcategory
    available_tags_by_subcategory = {}
    for tag in available_tags:
        subcat = tag.subcategory or "Other"
        if subcat not in available_tags_by_subcategory:
            available_tags_by_subcategory[subcat] = []
        available_tags_by_subcategory[subcat].append(tag)

    # Define preferred order for subcategories
    preferred_order = ["Investor Type", "Role/Industry", "Location", "Classmates",
                       "Former Colleague", "Professional Services", "Relationship", "Other"]
    available_subcategories = [s for s in preferred_order if s in available_tags_by_subcategory]
    # Add any subcategories not in preferred order
    for subcat in available_tags_by_subcategory:
        if subcat not in available_subcategories:
            available_subcategories.append(subcat)

    return templates.TemplateResponse(
        "persons/_tag_manage.html",
        {
            "request": request,
            "person_id": str(person_id),
            "current_tags": person.tags,
            "available_tags": available_tags,
            "available_tags_by_subcategory": available_tags_by_subcategory,
            "available_subcategories": available_subcategories,
        },
    )


@router.post("/{person_id}/tags/{tag_id}", response_class=HTMLResponse)
async def add_tag_to_person(
    request: Request,
    person_id: UUID,
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Add a tag to a person.
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Check if already exists
    existing = db.query(PersonTag).filter_by(person_id=person_id, tag_id=tag_id).first()
    if not existing:
        new_pt = PersonTag(person_id=person_id, tag_id=tag_id)
        db.add(new_pt)
        db.commit()

    # Return updated widget
    db.refresh(person)
    current_tag_ids = {t.id for t in person.tags}
    # Get all "People Tags" - tags without a category (includes newly created tags with 0 associations)
    people_tags = (
        db.query(Tag)
        .filter(Tag.category.is_(None))
        .order_by(Tag.name)
        .all()
    )
    available_tags = [t for t in people_tags if t.id not in current_tag_ids]

    # Group available tags by subcategory
    available_tags_by_subcategory = {}
    for tag in available_tags:
        subcat = tag.subcategory or "Other"
        if subcat not in available_tags_by_subcategory:
            available_tags_by_subcategory[subcat] = []
        available_tags_by_subcategory[subcat].append(tag)

    # Define preferred order for subcategories
    preferred_order = ["Investor Type", "Role/Industry", "Location", "Classmates",
                       "Former Colleague", "Professional Services", "Relationship", "Other"]
    available_subcategories = [s for s in preferred_order if s in available_tags_by_subcategory]
    for subcat in available_tags_by_subcategory:
        if subcat not in available_subcategories:
            available_subcategories.append(subcat)

    return templates.TemplateResponse(
        "persons/_tag_manage.html",
        {
            "request": request,
            "person_id": str(person_id),
            "current_tags": person.tags,
            "available_tags": available_tags,
            "available_tags_by_subcategory": available_tags_by_subcategory,
            "available_subcategories": available_subcategories,
        },
    )


@router.delete("/{person_id}/tags/{tag_id}", response_class=HTMLResponse)
async def remove_tag_from_person(
    request: Request,
    person_id: UUID,
    tag_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Remove a tag from a person.
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Find and delete the association
    pt = db.query(PersonTag).filter_by(person_id=person_id, tag_id=tag_id).first()
    if pt:
        db.delete(pt)
        db.commit()

    # Return updated widget
    db.refresh(person)
    current_tag_ids = {t.id for t in person.tags}
    # Get all "People Tags" - tags without a category (includes newly created tags with 0 associations)
    people_tags = (
        db.query(Tag)
        .filter(Tag.category.is_(None))
        .order_by(Tag.name)
        .all()
    )
    available_tags = [t for t in people_tags if t.id not in current_tag_ids]

    # Group available tags by subcategory
    available_tags_by_subcategory = {}
    for tag in available_tags:
        subcat = tag.subcategory or "Other"
        if subcat not in available_tags_by_subcategory:
            available_tags_by_subcategory[subcat] = []
        available_tags_by_subcategory[subcat].append(tag)

    # Define preferred order for subcategories
    preferred_order = ["Investor Type", "Role/Industry", "Location", "Classmates",
                       "Former Colleague", "Professional Services", "Relationship", "Other"]
    available_subcategories = [s for s in preferred_order if s in available_tags_by_subcategory]
    for subcat in available_tags_by_subcategory:
        if subcat not in available_subcategories:
            available_subcategories.append(subcat)

    return templates.TemplateResponse(
        "persons/_tag_manage.html",
        {
            "request": request,
            "person_id": str(person_id),
            "current_tags": person.tags,
            "available_tags": available_tags,
            "available_tags_by_subcategory": available_tags_by_subcategory,
            "available_subcategories": available_subcategories,
        },
    )


@router.get("/{person_id}/interactions/modal", response_class=HTMLResponse)
async def get_interactions_modal(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get the interactions modal content for a person.
    """
    person = (
        db.query(Person)
        .options(joinedload(Person.interactions))
        .filter(Person.id == person_id)
        .first()
    )
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Sort interactions by date descending
    interactions_sorted = sorted(
        person.interactions,
        key=lambda x: x.interaction_date or x.created_at,
        reverse=True,
    )

    return templates.TemplateResponse(
        "persons/_interactions_modal.html",
        {
            "request": request,
            "person": person,
            "interactions": interactions_sorted,
        },
    )
