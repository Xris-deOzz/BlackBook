"""
Organization Section Editing API - Returns HTML partials for inline editing.

Each section can be toggled between view and edit mode via HTMX.
Auto-saves on blur for most fields.
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Organization, Person
from app.models.person import PersonOrganization
from app.models.org_relationship import OrganizationRelationship

router = APIRouter(prefix="/api/organizations", tags=["organization-sections"])
templates = Jinja2Templates(directory="app/templates")


def get_organization_or_404(db: Session, org_id: UUID) -> Organization:
    """Get organization by ID or raise 404."""
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
    return organization


def get_org_relationships_context(db: Session, org_id: UUID) -> dict:
    """Get organization relationships context for templates."""
    # Get outgoing relationships (this org is the "from" org)
    outgoing = (
        db.query(OrganizationRelationship)
        .options(joinedload(OrganizationRelationship.to_organization))
        .filter(OrganizationRelationship.from_organization_id == org_id)
        .all()
    )

    # Get incoming relationships (this org is the "to" org)
    incoming = (
        db.query(OrganizationRelationship)
        .options(joinedload(OrganizationRelationship.from_organization))
        .filter(OrganizationRelationship.to_organization_id == org_id)
        .all()
    )

    # Group by relationship type
    outgoing_by_type = {}
    for rel in outgoing:
        rel_type = rel.relationship_type.value if hasattr(rel.relationship_type, 'value') else rel.relationship_type
        if rel_type not in outgoing_by_type:
            outgoing_by_type[rel_type] = []
        outgoing_by_type[rel_type].append(rel)

    incoming_by_type = {}
    for rel in incoming:
        rel_type = rel.relationship_type.value if hasattr(rel.relationship_type, 'value') else rel.relationship_type
        if rel_type not in incoming_by_type:
            incoming_by_type[rel_type] = []
        incoming_by_type[rel_type].append(rel)

    return {
        "outgoing_relationships": outgoing,
        "incoming_relationships": incoming,
        "outgoing_by_type": outgoing_by_type,
        "incoming_by_type": incoming_by_type,
    }


def get_people_by_type(db: Session, org_id: UUID) -> dict:
    """Get people affiliated with organization grouped by relationship type."""
    organization = get_organization_or_404(db, org_id)

    people_by_type = {}
    for po in organization.affiliated_persons:
        rel_type = po.relationship.value if hasattr(po.relationship, 'value') else str(po.relationship)
        if rel_type not in people_by_type:
            people_by_type[rel_type] = []
        people_by_type[rel_type].append(po)

    return people_by_type


# =============================================================================
# DESCRIPTION SECTION
# =============================================================================

@router.get("/{org_id}/sections/description/edit", response_class=HTMLResponse)
async def get_description_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get description section in edit mode."""
    organization = get_organization_or_404(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_description_edit.html",
        {"request": request, "organization": organization}
    )


@router.get("/{org_id}/sections/description/view", response_class=HTMLResponse)
async def get_description_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get description section in view mode."""
    organization = get_organization_or_404(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_description_view.html",
        {"request": request, "organization": organization}
    )


@router.put("/{org_id}/sections/description", response_class=HTMLResponse)
async def update_description(
    request: Request,
    org_id: UUID,
    description: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update description and return view mode."""
    organization = get_organization_or_404(db, org_id)
    organization.description = description if description else None
    db.commit()
    db.refresh(organization)
    return templates.TemplateResponse(
        "organizations/sections/_description_view.html",
        {"request": request, "organization": organization}
    )


# =============================================================================
# NOTES SECTION
# =============================================================================

@router.get("/{org_id}/sections/notes/edit", response_class=HTMLResponse)
async def get_notes_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get notes section in edit mode."""
    organization = get_organization_or_404(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_notes_edit.html",
        {"request": request, "organization": organization}
    )


@router.get("/{org_id}/sections/notes/view", response_class=HTMLResponse)
async def get_notes_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get notes section in view mode."""
    organization = get_organization_or_404(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_notes_view.html",
        {"request": request, "organization": organization}
    )


@router.put("/{org_id}/sections/notes", response_class=HTMLResponse)
async def update_notes(
    request: Request,
    org_id: UUID,
    notes: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update notes and return view mode."""
    organization = get_organization_or_404(db, org_id)
    organization.notes = notes if notes else None
    db.commit()
    db.refresh(organization)
    return templates.TemplateResponse(
        "organizations/sections/_notes_view.html",
        {"request": request, "organization": organization}
    )


# =============================================================================
# LINKS SECTION
# =============================================================================

@router.get("/{org_id}/sections/links/edit", response_class=HTMLResponse)
async def get_links_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get links section in edit mode."""
    organization = get_organization_or_404(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_links_edit.html",
        {"request": request, "organization": organization}
    )


@router.get("/{org_id}/sections/links/view", response_class=HTMLResponse)
async def get_links_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get links section in view mode."""
    organization = get_organization_or_404(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_links_view.html",
        {"request": request, "organization": organization}
    )


@router.put("/{org_id}/sections/links", response_class=HTMLResponse)
async def update_links(
    request: Request,
    org_id: UUID,
    website: str = Form(None),
    crunchbase: str = Form(None),
    db: Session = Depends(get_db),
):
    """Update links and return view mode."""
    organization = get_organization_or_404(db, org_id)

    # Auto-add https:// if no protocol specified
    if website and website.strip():
        website = website.strip()
        if not website.startswith(('http://', 'https://')):
            website = f'https://{website}'

    if crunchbase and crunchbase.strip():
        crunchbase = crunchbase.strip()
        if not crunchbase.startswith(('http://', 'https://')):
            crunchbase = f'https://{crunchbase}'

    organization.website = website if website else None
    organization.crunchbase = crunchbase if crunchbase else None
    db.commit()
    db.refresh(organization)
    return templates.TemplateResponse(
        "organizations/sections/_links_view.html",
        {"request": request, "organization": organization}
    )


# =============================================================================
# PEOPLE SECTION
# =============================================================================

@router.get("/{org_id}/sections/people/edit", response_class=HTMLResponse)
async def get_people_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get people section in edit mode - uses the existing _people_section.html template."""
    organization = get_organization_or_404(db, org_id)
    all_persons = db.query(Person).order_by(Person.first_name, Person.last_name).all()
    return templates.TemplateResponse(
        "organizations/_people_section.html",
        {"request": request, "organization": organization, "all_persons": all_persons}
    )


@router.get("/{org_id}/sections/people/view", response_class=HTMLResponse)
async def get_people_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get people section in view mode."""
    organization = get_organization_or_404(db, org_id)
    people_by_type = get_people_by_type(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_people_view.html",
        {"request": request, "organization": organization, "people_by_type": people_by_type}
    )


# =============================================================================
# RELATED ORGANIZATIONS SECTION
# =============================================================================

@router.get("/{org_id}/sections/related-orgs/edit", response_class=HTMLResponse)
async def get_related_orgs_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get related organizations section in edit mode - uses existing _org_relationships_section.html."""
    organization = get_organization_or_404(db, org_id)
    all_organizations = db.query(Organization).filter(Organization.id != org_id).order_by(Organization.name).all()

    context = get_org_relationships_context(db, org_id)
    context.update({
        "request": request,
        "organization": organization,
        "all_organizations": all_organizations,
    })

    return templates.TemplateResponse(
        "organizations/_org_relationships_section.html",
        context
    )


@router.get("/{org_id}/sections/related-orgs/view", response_class=HTMLResponse)
async def get_related_orgs_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get related organizations section in view mode."""
    organization = get_organization_or_404(db, org_id)
    context = get_org_relationships_context(db, org_id)
    context.update({
        "request": request,
        "organization": organization,
    })

    return templates.TemplateResponse(
        "organizations/sections/_related_orgs_view.html",
        context
    )


# =============================================================================
# INVESTMENT PROFILE SECTION
# =============================================================================

@router.get("/{org_id}/sections/investment-profile/edit", response_class=HTMLResponse)
async def get_investment_profile_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get investment profile section in edit mode."""
    organization = get_organization_or_404(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_investment_profile_edit.html",
        {"request": request, "organization": organization}
    )


@router.get("/{org_id}/sections/investment-profile/view", response_class=HTMLResponse)
async def get_investment_profile_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get investment profile section in view mode."""
    organization = get_organization_or_404(db, org_id)
    return templates.TemplateResponse(
        "organizations/sections/_investment_profile_view.html",
        {"request": request, "organization": organization}
    )


@router.put("/{org_id}/sections/investment-profile", response_class=HTMLResponse)
async def update_investment_profile(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
    investment_stages: list = Form(None),
    check_size_min: Optional[int] = Form(None),
    check_size_max: Optional[int] = Form(None),
    investment_sectors: list = Form(None),
    geographic_focus: Optional[str] = Form(None),
    fund_size: Optional[int] = Form(None),
    current_fund_name: Optional[str] = Form(None),
    current_fund_year: Optional[int] = Form(None),
):
    """Update investment profile and return view mode."""
    organization = get_organization_or_404(db, org_id)

    # Convert lists to comma-separated strings
    organization.investment_stages = ','.join(investment_stages) if investment_stages else None
    organization.investment_sectors = ','.join(investment_sectors) if investment_sectors else None
    organization.check_size_min = check_size_min if check_size_min else None
    organization.check_size_max = check_size_max if check_size_max else None
    organization.geographic_focus = geographic_focus.strip() if geographic_focus else None
    organization.fund_size = fund_size if fund_size else None
    organization.current_fund_name = current_fund_name.strip() if current_fund_name else None
    organization.current_fund_year = current_fund_year if current_fund_year else None

    db.commit()
    db.refresh(organization)

    return templates.TemplateResponse(
        "organizations/sections/_investment_profile_view.html",
        {"request": request, "organization": organization}
    )


# =============================================================================
# RELATIONSHIP STATUS SECTION
# =============================================================================

@router.get("/{org_id}/sections/relationship-status/edit", response_class=HTMLResponse)
async def get_relationship_status_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get relationship status section in edit mode."""
    from app.models.organization_relationship_status import OrganizationRelationshipStatus

    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.relationship_status).joinedload(OrganizationRelationshipStatus.primary_contact),
            joinedload(Organization.relationship_status).joinedload(OrganizationRelationshipStatus.intro_available_via),
        )
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    all_persons = db.query(Person).order_by(Person.full_name).all()

    return templates.TemplateResponse(
        "organizations/sections/_relationship_status_edit.html",
        {"request": request, "organization": organization, "all_persons": all_persons}
    )


@router.get("/{org_id}/sections/relationship-status/view", response_class=HTMLResponse)
async def get_relationship_status_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get relationship status section in view mode."""
    from app.models.organization_relationship_status import OrganizationRelationshipStatus
    from app.models import Interaction
    from app.models.person_employment import PersonEmployment

    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.relationship_status).joinedload(OrganizationRelationshipStatus.primary_contact),
            joinedload(Organization.relationship_status).joinedload(OrganizationRelationshipStatus.intro_available_via),
        )
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get last contacted date from aggregated interactions
    person_ids = (
        db.query(PersonEmployment.person_id)
        .filter(PersonEmployment.organization_id == org_id)
        .distinct()
        .all()
    )
    person_id_list = [pid[0] for pid in person_ids]

    last_contacted = None
    if person_id_list:
        last_interaction = (
            db.query(Interaction)
            .filter(Interaction.person_id.in_(person_id_list))
            .order_by(Interaction.interaction_date.desc())
            .first()
        )
        if last_interaction:
            last_contacted = last_interaction.interaction_date

    return templates.TemplateResponse(
        "organizations/sections/_relationship_status_view.html",
        {"request": request, "organization": organization, "last_contacted": last_contacted}
    )


@router.put("/{org_id}/sections/relationship-status", response_class=HTMLResponse)
async def update_relationship_status(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
    primary_contact_id: Optional[str] = Form(None),
    relationship_warmth: Optional[str] = Form(None),
    intro_available_via_id: Optional[str] = Form(None),
    next_followup_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
):
    """Update or create relationship status and return view mode."""
    from app.models.organization_relationship_status import OrganizationRelationshipStatus
    from app.models import Interaction
    from app.models.person_employment import PersonEmployment
    from datetime import datetime

    organization = get_organization_or_404(db, org_id)

    # Get or create relationship status
    status = (
        db.query(OrganizationRelationshipStatus)
        .filter(OrganizationRelationshipStatus.organization_id == org_id)
        .first()
    )

    if not status:
        status = OrganizationRelationshipStatus(organization_id=org_id)
        db.add(status)

    # Update fields
    status.primary_contact_id = UUID(primary_contact_id) if primary_contact_id else None
    status.relationship_warmth = relationship_warmth if relationship_warmth else None
    status.intro_available_via_id = UUID(intro_available_via_id) if intro_available_via_id else None
    status.next_followup_date = datetime.strptime(next_followup_date, '%Y-%m-%d').date() if next_followup_date else None
    status.notes = notes.strip() if notes else None

    db.commit()

    # Reload with relationships
    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.relationship_status).joinedload(OrganizationRelationshipStatus.primary_contact),
            joinedload(Organization.relationship_status).joinedload(OrganizationRelationshipStatus.intro_available_via),
        )
        .filter(Organization.id == org_id)
        .first()
    )

    # Get last contacted date
    person_ids = (
        db.query(PersonEmployment.person_id)
        .filter(PersonEmployment.organization_id == org_id)
        .distinct()
        .all()
    )
    person_id_list = [pid[0] for pid in person_ids]

    last_contacted = None
    if person_id_list:
        last_interaction = (
            db.query(Interaction)
            .filter(Interaction.person_id.in_(person_id_list))
            .order_by(Interaction.interaction_date.desc())
            .first()
        )
        if last_interaction:
            last_contacted = last_interaction.interaction_date

    return templates.TemplateResponse(
        "organizations/sections/_relationship_status_view.html",
        {"request": request, "organization": organization, "last_contacted": last_contacted}
    )


# =============================================================================
# OFFICES SECTION
# =============================================================================

@router.get("/{org_id}/sections/offices/edit", response_class=HTMLResponse)
async def get_offices_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get offices section in edit mode."""
    organization = (
        db.query(Organization)
        .options(joinedload(Organization.offices))
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    return templates.TemplateResponse(
        "organizations/sections/_offices_edit.html",
        {"request": request, "organization": organization}
    )


@router.get("/{org_id}/sections/offices/view", response_class=HTMLResponse)
async def get_offices_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get offices section in view mode."""
    organization = (
        db.query(Organization)
        .options(joinedload(Organization.offices))
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    return templates.TemplateResponse(
        "organizations/sections/_offices_view.html",
        {"request": request, "organization": organization}
    )


@router.post("/{org_id}/offices", response_class=HTMLResponse)
async def add_office(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
    city: str = Form(...),
    state: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    office_type: Optional[str] = Form(None),
    is_headquarters: Optional[str] = Form(None),
):
    """Add a new office to the organization."""
    from app.models.organization_office import OrganizationOffice

    organization = get_organization_or_404(db, org_id)

    is_hq = is_headquarters == "true"

    # If setting as HQ, clear other HQ flags
    if is_hq:
        db.query(OrganizationOffice).filter(
            OrganizationOffice.organization_id == org_id,
            OrganizationOffice.is_headquarters == True,
        ).update({"is_headquarters": False})

    office = OrganizationOffice(
        organization_id=org_id,
        city=city.strip(),
        state=state.strip() if state else None,
        country=country.strip() if country else None,
        address=address.strip() if address else None,
        office_type=office_type if office_type else None,
        is_headquarters=is_hq,
    )
    db.add(office)
    db.commit()
    db.refresh(office)

    # Return the new office HTML
    return f"""
    <div class="flex items-start gap-3 p-3 bg-blackbook-50 rounded-lg border border-blackbook-200"
         id="office-{office.id}">
        <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium text-blackbook-900">
                    {office.city}{f', {office.state}' if office.state else ''}
                </span>
                {'<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">HQ</span>' if is_hq else ''}
            </div>
            {f'<p class="text-sm text-blackbook-500">{office.country}</p>' if office.country else ''}
            {f'<p class="text-sm text-blackbook-600 mt-1">{office.address}</p>' if office.address else ''}
        </div>
        <button type="button"
                hx-delete="/api/organizations/{org_id}/offices/{office.id}"
                hx-target="#office-{office.id}"
                hx-swap="outerHTML"
                hx-confirm="Delete this office location?"
                class="p-1 text-blackbook-400 hover:text-red-600"
                title="Delete office">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
        </button>
    </div>
    """


@router.delete("/{org_id}/offices/{office_id}", response_class=HTMLResponse)
async def delete_office(
    org_id: UUID,
    office_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an office from the organization."""
    from app.models.organization_office import OrganizationOffice

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

    # Return empty string to remove the element
    return ""


# =============================================================================
# CLASSIFICATION SECTION (Category/Type)
# =============================================================================

@router.get("/{org_id}/sections/classification/edit", response_class=HTMLResponse)
async def get_classification_edit(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get classification section in edit mode with cascading dropdowns."""
    from app.models import OrganizationCategory, OrganizationType

    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.type_ref),
            joinedload(Organization.category_ref),
        )
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get all categories
    categories = (
        db.query(OrganizationCategory)
        .filter(OrganizationCategory.is_active == True)
        .order_by(OrganizationCategory.sort_order)
        .all()
    )

    # Get all types
    types = (
        db.query(OrganizationType)
        .filter(OrganizationType.is_active == True)
        .order_by(OrganizationType.category_id, OrganizationType.sort_order)
        .all()
    )

    # Build types_by_category dict for JavaScript
    types_by_category = {}
    for t in types:
        if t.category_id not in types_by_category:
            types_by_category[t.category_id] = []
        types_by_category[t.category_id].append({
            "id": t.id,
            "name": t.name,
            "profile_style": t.profile_style
        })

    return templates.TemplateResponse(
        "organizations/sections/_classification_edit.html",
        {
            "request": request,
            "organization": organization,
            "categories": categories,
            "types": types,
            "types_by_category": types_by_category,
        }
    )


@router.get("/{org_id}/sections/classification/view", response_class=HTMLResponse)
async def get_classification_view(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """Get classification section in view mode."""
    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.type_ref),
            joinedload(Organization.category_ref),
        )
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    return templates.TemplateResponse(
        "organizations/sections/_classification_view.html",
        {"request": request, "organization": organization}
    )


@router.put("/{org_id}/sections/classification", response_class=HTMLResponse)
async def update_classification(
    request: Request,
    org_id: UUID,
    db: Session = Depends(get_db),
    category_id: Optional[int] = Form(None),
    type_id: Optional[int] = Form(None),
):
    """Update organization classification (category/type) and return view mode."""
    from app.models import OrganizationType

    organization = (
        db.query(Organization)
        .filter(Organization.id == org_id)
        .first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate type belongs to category if both are provided
    if type_id and category_id:
        org_type = db.query(OrganizationType).filter(OrganizationType.id == type_id).first()
        if org_type and org_type.category_id != category_id:
            raise HTTPException(
                status_code=400,
                detail="Type does not belong to selected category"
            )

    # Update fields
    organization.category_id = category_id if category_id else None
    organization.type_id = type_id if type_id else None

    db.commit()

    # Reload with relationships
    organization = (
        db.query(Organization)
        .options(
            joinedload(Organization.type_ref),
            joinedload(Organization.category_ref),
        )
        .filter(Organization.id == org_id)
        .first()
    )

    return templates.TemplateResponse(
        "organizations/sections/_classification_view.html",
        {"request": request, "organization": organization}
    )
