"""
Christmas Lists router.

Provides endpoints for managing Christmas email lists (Polish and English).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.christmas_service import (
    ChristmasService,
    SuggestionConfidence,
    get_christmas_service,
)


router = APIRouter(prefix="/christmas-lists", tags=["christmas-lists"])
# Force template reload - v2
templates = Jinja2Templates(directory="app/templates", auto_reload=True)


class AssignRequest(BaseModel):
    """Request model for assigning a person to a list."""
    person_id: str
    list_type: str  # 'polish' or 'english'


class BulkAssignRequest(BaseModel):
    """Request model for bulk assignment."""
    min_confidence: str  # 'high', 'medium', or 'low'


@router.get("", response_class=HTMLResponse)
async def christmas_lists_index(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Main Christmas lists page showing overview of both lists.
    """
    service = get_christmas_service(db)
    counts = service.get_list_counts()

    # Get count of unassigned people with email
    suggestions = service.get_unassigned_suggestions(email_only=True)
    unassigned_count = len(suggestions)

    return templates.TemplateResponse(
        request,
        "christmas_lists/index.html",
        {
            "counts": counts,
            "unassigned_count": unassigned_count,
        },
    )


@router.get("/polish", response_class=HTMLResponse)
async def christmas_list_polish(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    View the Polish Christmas list.
    """
    service = get_christmas_service(db)
    members = service.get_list_members("polish")

    return templates.TemplateResponse(
        request,
        "christmas_lists/list.html",
        {
            "list_type": "polish",
            "list_name": "Polish",
            "members": members,
            "member_count": len(members),
            "email_count": sum(1 for m in members if m["email"]),
        },
    )


@router.get("/english", response_class=HTMLResponse)
async def christmas_list_english(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    View the English Christmas list.
    """
    service = get_christmas_service(db)
    members = service.get_list_members("english")

    return templates.TemplateResponse(
        request,
        "christmas_lists/list.html",
        {
            "list_type": "english",
            "list_name": "English",
            "members": members,
            "member_count": len(members),
            "email_count": sum(1 for m in members if m["email"]),
        },
    )


@router.get("/suggestions", response_class=HTMLResponse)
async def christmas_list_suggestions(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 50,
):
    """
    View unassigned people with suggestions for which list they belong to.
    """
    service = get_christmas_service(db)
    all_suggestions = service.get_unassigned_suggestions(email_only=True)

    # Group by confidence for counts
    high_confidence = [s for s in all_suggestions if s.confidence == SuggestionConfidence.HIGH]
    medium_confidence = [s for s in all_suggestions if s.confidence == SuggestionConfidence.MEDIUM]
    low_confidence = [s for s in all_suggestions if s.confidence == SuggestionConfidence.LOW]

    # Pagination
    total_count = len(all_suggestions)
    total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 1
    page = max(1, min(page, total_pages))  # Clamp page to valid range
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    suggestions = all_suggestions[start_idx:end_idx]

    response = templates.TemplateResponse(
        request,
        "christmas_lists/suggestions.html",
        {
            "suggestions": suggestions,
            "high_count": len(high_confidence),
            "medium_count": len(medium_confidence),
            "low_count": len(low_confidence),
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "start_idx": start_idx + 1,
            "end_idx": min(end_idx, total_count),
        },
    )
    # Prevent browser caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.post("/assign")
async def assign_to_list(
    request_data: AssignRequest,
    db: Session = Depends(get_db),
):
    """
    Assign a person to a Christmas list.
    """
    service = get_christmas_service(db)

    try:
        person_id = UUID(request_data.person_id)
    except ValueError:
        return JSONResponse(
            content={"success": False, "error": "Invalid person ID"},
            status_code=400,
        )

    if request_data.list_type not in ("polish", "english"):
        return JSONResponse(
            content={"success": False, "error": "Invalid list type"},
            status_code=400,
        )

    success = service.assign_to_list(person_id, request_data.list_type)

    if success:
        return JSONResponse(content={"success": True})
    else:
        return JSONResponse(
            content={"success": False, "error": "Person not found"},
            status_code=404,
        )


@router.post("/remove")
async def remove_from_list(
    request_data: AssignRequest,
    db: Session = Depends(get_db),
):
    """
    Remove a person from a Christmas list.
    """
    service = get_christmas_service(db)

    try:
        person_id = UUID(request_data.person_id)
    except ValueError:
        return JSONResponse(
            content={"success": False, "error": "Invalid person ID"},
            status_code=400,
        )

    if request_data.list_type not in ("polish", "english"):
        return JSONResponse(
            content={"success": False, "error": "Invalid list type"},
            status_code=400,
        )

    success = service.remove_from_list(person_id, request_data.list_type)

    if success:
        return JSONResponse(content={"success": True})
    else:
        return JSONResponse(
            content={"success": False, "error": "Person not found"},
            status_code=404,
        )


@router.post("/bulk-assign")
async def bulk_assign(
    request_data: BulkAssignRequest,
    db: Session = Depends(get_db),
):
    """
    Bulk assign people based on suggestions with minimum confidence.
    """
    service = get_christmas_service(db)

    confidence_map = {
        "high": SuggestionConfidence.HIGH,
        "medium": SuggestionConfidence.MEDIUM,
        "low": SuggestionConfidence.LOW,
    }

    if request_data.min_confidence not in confidence_map:
        return JSONResponse(
            content={"success": False, "error": "Invalid confidence level"},
            status_code=400,
        )

    min_confidence = confidence_map[request_data.min_confidence]
    counts = service.bulk_assign_by_confidence(min_confidence)

    return JSONResponse(content={
        "success": True,
        "assigned": counts,
        "total": counts["polish"] + counts["english"],
    })


@router.get("/export/{list_type}")
async def export_list(
    list_type: str,
    db: Session = Depends(get_db),
):
    """
    Export a Christmas list to CSV.
    """
    if list_type not in ("polish", "english"):
        return JSONResponse(
            content={"error": "Invalid list type"},
            status_code=400,
        )

    service = get_christmas_service(db)
    csv_content = service.export_list_csv(list_type)

    filename = f"christmas_{list_type}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/table/{list_type}", response_class=HTMLResponse)
async def get_list_table(
    list_type: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint to refresh just the table content.
    """
    if list_type not in ("polish", "english"):
        return HTMLResponse(content="Invalid list type", status_code=400)

    service = get_christmas_service(db)
    members = service.get_list_members(list_type)

    return templates.TemplateResponse(
        request,
        "christmas_lists/_table.html",
        {
            "list_type": list_type,
            "members": members,
        },
    )


@router.get("/suggestions-table", response_class=HTMLResponse)
async def get_suggestions_table(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    HTMX endpoint to refresh just the suggestions table.
    """
    service = get_christmas_service(db)
    suggestions = service.get_unassigned_suggestions(email_only=True)

    return templates.TemplateResponse(
        request,
        "christmas_lists/_suggestions_table.html",
        {
            "suggestions": suggestions,
        },
    )
