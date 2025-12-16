"""
Social Graph routes for Perun's BlackBook.
Provides network visualization of person-organization relationships.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Person, Organization
from app.models.person import PersonOrganization
from app.models.organization import RelationshipType
from app.models.org_relationship import OrganizationRelationship, OrgRelationshipType

router = APIRouter(prefix="/graph", tags=["graph"])
templates = Jinja2Templates(directory="app/templates")

# Color scheme for node types
NODE_COLORS = {
    "person": "#3B82F6",  # Blue
    "organization": "#10B981",  # Green
}

# Color scheme for relationship types (person-org)
EDGE_COLORS = {
    "affiliated_with": "#6B7280",  # Gray
    "peer_history": "#8B5CF6",  # Purple
    "key_person": "#EF4444",  # Red
    "connection": "#F59E0B",  # Amber
    "contact_at": "#06B6D4",  # Cyan
}

# Color scheme for org-to-org relationship types
ORG_EDGE_COLORS = {
    "invested_in": "#F59E0B",  # Gold - Investment relationships
    "subsidiary_of": "#8B5CF6",  # Purple
    "parent_company": "#8B5CF6",  # Purple
    "partner": "#14B8A6",  # Teal
    "acquired": "#EF4444",  # Red
    "acquired_by": "#EF4444",  # Red
    "spun_off_from": "#EC4899",  # Pink
}


@router.get("", response_class=HTMLResponse)
async def graph_view(
    request: Request,
    db: Session = Depends(get_db),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    focus_person: Optional[str] = Query(None, description="Focus on a specific person"),
    focus_org: Optional[str] = Query(None, description="Focus on a specific organization"),
):
    """
    Display the social graph visualization page.
    """
    # Get all relationship types for filter dropdown
    relationship_types = [r.value for r in RelationshipType]

    return templates.TemplateResponse(
        "graph/index.html",
        {
            "request": request,
            "title": "Social Graph",
            "relationship_types": relationship_types,
            "selected_relationship": relationship_type or "",
            "focus_person": focus_person or "",
            "focus_org": focus_org or "",
        },
    )


@router.get("/data", response_class=JSONResponse)
async def get_graph_data(
    db: Session = Depends(get_db),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    focus_person: Optional[str] = Query(None, description="Focus on a specific person (UUID)"),
    focus_org: Optional[str] = Query(None, description="Focus on a specific organization (UUID)"),
    limit: int = Query(500, ge=1, le=2000, description="Max number of nodes"),
):
    """
    Return graph data in vis.js format.
    Returns nodes (persons and organizations) and edges (relationships).
    """
    nodes = []
    edges = []
    seen_persons = set()
    seen_orgs = set()

    # Build relationship type filter
    rel_filter = None
    if relationship_type:
        try:
            rel_filter = RelationshipType(relationship_type)
        except ValueError:
            pass

    # Focus mode: show only connections for specific entity
    focus_person_uuid = None
    focus_org_uuid = None

    if focus_person:
        try:
            focus_person_uuid = UUID(focus_person)
        except ValueError:
            pass

    if focus_org:
        try:
            focus_org_uuid = UUID(focus_org)
        except ValueError:
            pass

    # Query PersonOrganization relationships (person -> org)
    po_query = db.query(PersonOrganization)

    if rel_filter:
        po_query = po_query.filter(PersonOrganization.relationship == rel_filter)

    if focus_person_uuid:
        po_query = po_query.filter(PersonOrganization.person_id == focus_person_uuid)

    if focus_org_uuid:
        po_query = po_query.filter(PersonOrganization.organization_id == focus_org_uuid)

    person_org_links = po_query.limit(limit).all()

    # Process PersonOrganization links (unified table)
    for link in person_org_links:
        person_id = str(link.person_id)
        org_id = str(link.organization_id)

        if person_id not in seen_persons:
            person = db.query(Person).filter(Person.id == link.person_id).first()
            if person:
                seen_persons.add(person_id)
                nodes.append({
                    "id": f"person_{person_id}",
                    "label": person.full_name,
                    "group": "person",
                    "title": f"{person.full_name}\n{person.title or ''}\nClick to view profile",
                    "shape": "dot",
                    "size": 15,
                    "color": {
                        "background": NODE_COLORS["person"],
                        "border": "#1E40AF",
                        "highlight": {"background": "#60A5FA", "border": "#1E40AF"},
                    },
                    "font": {"color": "#1F2937"},
                    "url": f"/people/{person_id}",
                })

        if org_id not in seen_orgs:
            org = db.query(Organization).filter(Organization.id == link.organization_id).first()
            if org:
                seen_orgs.add(org_id)
                nodes.append({
                    "id": f"org_{org_id}",
                    "label": org.name,
                    "group": "organization",
                    "title": f"{org.name}\n{org.org_type.value.replace('_', ' ').title()}\nClick to view profile",
                    "shape": "square",
                    "size": 20,
                    "color": {
                        "background": NODE_COLORS["organization"],
                        "border": "#065F46",
                        "highlight": {"background": "#34D399", "border": "#065F46"},
                    },
                    "font": {"color": "#1F2937"},
                    "url": f"/organizations/{org_id}",
                })

        # Add edge
        edge_color = EDGE_COLORS.get(link.relationship.value, "#6B7280")
        edge_label = link.relationship.value.replace("_", " ").title()
        if link.role:
            edge_label = f"{edge_label} ({link.role})"

        edges.append({
            "from": f"person_{person_id}",
            "to": f"org_{org_id}",
            "label": edge_label,
            "color": {"color": edge_color, "highlight": edge_color},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
            "smooth": {"type": "curvedCW", "roundness": 0.1},
            "title": f"{link.relationship.value.replace('_', ' ').title()}" +
                     (f"\nRole: {link.role}" if link.role else "") +
                     (f"\n{'Current' if link.is_current else 'Past'}" if hasattr(link, 'is_current') else ""),
        })

    # Query Organization-to-Organization relationships
    org_rel_query = db.query(OrganizationRelationship)

    if focus_org_uuid:
        from sqlalchemy import or_
        org_rel_query = org_rel_query.filter(
            or_(
                OrganizationRelationship.from_organization_id == focus_org_uuid,
                OrganizationRelationship.to_organization_id == focus_org_uuid,
            )
        )

    org_relationships = org_rel_query.limit(limit).all()

    # Process Org-to-Org links
    for org_rel in org_relationships:
        from_org_id = str(org_rel.from_organization_id)
        to_org_id = str(org_rel.to_organization_id)

        # Add "from" org node if not seen
        if from_org_id not in seen_orgs:
            from_org = db.query(Organization).filter(Organization.id == org_rel.from_organization_id).first()
            if from_org:
                seen_orgs.add(from_org_id)
                nodes.append({
                    "id": f"org_{from_org_id}",
                    "label": from_org.name,
                    "group": "organization",
                    "title": f"{from_org.name}\n{from_org.org_type.value.replace('_', ' ').title()}\nClick to view profile",
                    "shape": "square",
                    "size": 20,
                    "color": {
                        "background": NODE_COLORS["organization"],
                        "border": "#065F46",
                        "highlight": {"background": "#34D399", "border": "#065F46"},
                    },
                    "font": {"color": "#1F2937"},
                    "url": f"/organizations/{from_org_id}",
                })

        # Add "to" org node if not seen
        if to_org_id not in seen_orgs:
            to_org = db.query(Organization).filter(Organization.id == org_rel.to_organization_id).first()
            if to_org:
                seen_orgs.add(to_org_id)
                nodes.append({
                    "id": f"org_{to_org_id}",
                    "label": to_org.name,
                    "group": "organization",
                    "title": f"{to_org.name}\n{to_org.org_type.value.replace('_', ' ').title()}\nClick to view profile",
                    "shape": "square",
                    "size": 20,
                    "color": {
                        "background": NODE_COLORS["organization"],
                        "border": "#065F46",
                        "highlight": {"background": "#34D399", "border": "#065F46"},
                    },
                    "font": {"color": "#1F2937"},
                    "url": f"/organizations/{to_org_id}",
                })

        # Add org-to-org edge
        # relationship_type is stored as string in DB
        rel_type_str = org_rel.relationship_type.value if hasattr(org_rel.relationship_type, 'value') else org_rel.relationship_type
        org_edge_color = ORG_EDGE_COLORS.get(rel_type_str, "#6B7280")
        org_edge_label = rel_type_str.replace("_", " ").title()
        if org_rel.year:
            org_edge_label = f"{org_edge_label} ({org_rel.year})"

        edges.append({
            "from": f"org_{from_org_id}",
            "to": f"org_{to_org_id}",
            "label": org_edge_label,
            "color": {"color": org_edge_color, "highlight": org_edge_color},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.5}},
            "smooth": {"type": "curvedCW", "roundness": 0.2},
            "width": 2,
            "dashes": False,
            "title": f"{rel_type_str.replace('_', ' ').title()}" +
                     (f"\nYear: {org_rel.year}" if org_rel.year else "") +
                     (f"\nNotes: {org_rel.notes}" if org_rel.notes else ""),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "person_count": len(seen_persons),
            "org_count": len(seen_orgs),
            "edge_count": len(edges),
        },
    }
