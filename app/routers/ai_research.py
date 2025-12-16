"""
AI Research API endpoints.

Provides endpoints for executing and managing AI-powered research
on people and organizations.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Person, Organization
from app.services.ai.research import (
    PersonResearcher,
    CompanyResearcher,
    ResearchConfig,
    ResearchResult,
)
from app.services.ai.research.workflow import ResearchDepth


router = APIRouter(prefix="/ai/research", tags=["ai-research"])


# Request/Response models
class ResearchRequest(BaseModel):
    """Request to start a research operation."""

    depth: str = "standard"  # quick, standard, deep
    include_news: bool = True
    include_videos: bool = True
    include_podcasts: bool = True
    max_results_per_source: int = 5
    auto_suggest_updates: bool = True
    provider_name: str | None = None

    def to_config(self) -> ResearchConfig:
        """Convert to ResearchConfig."""
        return ResearchConfig(
            depth=ResearchDepth(self.depth),
            include_news=self.include_news,
            include_videos=self.include_videos,
            include_podcasts=self.include_podcasts,
            max_results_per_source=self.max_results_per_source,
            auto_suggest_updates=self.auto_suggest_updates,
            provider_name=self.provider_name,
        )


# In-memory storage for research results (in production, use database)
_research_results: dict[str, ResearchResult] = {}


def _store_result(result: ResearchResult) -> str:
    """Store a research result and return its ID."""
    result_id = f"{result.entity_type}_{result.entity_id}_{result.started_at.timestamp()}"
    _research_results[result_id] = result
    return result_id


def _get_result(result_id: str) -> ResearchResult | None:
    """Get a stored research result."""
    return _research_results.get(result_id)


@router.post("/person/{person_id}")
async def research_person(
    person_id: UUID,
    request: ResearchRequest = ResearchRequest(),
    db: Session = Depends(get_db),
):
    """
    Execute research on a person.

    Searches multiple sources and uses AI to analyze findings.
    Returns research results including sources and suggested updates.
    """
    # Verify person exists
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Execute research
    researcher = PersonResearcher(db)
    result = await researcher.research(person_id, request.to_config())

    # Store result
    result_id = _store_result(result)

    return JSONResponse(
        content={
            "result_id": result_id,
            **result.to_dict(),
        }
    )


@router.post("/person/{person_id}/background")
async def research_person_background(
    person_id: UUID,
    background_tasks: BackgroundTasks,
    request: ResearchRequest = ResearchRequest(),
    db: Session = Depends(get_db),
):
    """
    Start research on a person in the background.

    Returns immediately with a result ID that can be polled
    for completion.
    """
    # Verify person exists
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Generate result ID in advance
    from datetime import datetime

    result_id = f"person_{person_id}_{datetime.utcnow().timestamp()}"

    # Store placeholder
    placeholder = ResearchResult(
        entity_type="person",
        entity_id=person_id,
        entity_name=person.full_name,
        status="pending",
        started_at=datetime.utcnow(),
        config=request.to_config(),
    )
    _research_results[result_id] = placeholder

    # Schedule background task
    async def run_research():
        researcher = PersonResearcher(db)
        result = await researcher.research(person_id, request.to_config())
        _research_results[result_id] = result

    background_tasks.add_task(run_research)

    return JSONResponse(
        content={
            "result_id": result_id,
            "status": "pending",
            "message": "Research started in background",
        }
    )


@router.post("/organization/{org_id}")
async def research_organization(
    org_id: UUID,
    request: ResearchRequest = ResearchRequest(),
    db: Session = Depends(get_db),
):
    """
    Execute research on an organization.

    Searches multiple sources and uses AI to analyze findings.
    Returns research results including sources and suggested updates.
    """
    # Verify organization exists
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Execute research
    researcher = CompanyResearcher(db)
    result = await researcher.research(org_id, request.to_config())

    # Store result
    result_id = _store_result(result)

    return JSONResponse(
        content={
            "result_id": result_id,
            **result.to_dict(),
        }
    )


@router.post("/organization/{org_id}/background")
async def research_organization_background(
    org_id: UUID,
    background_tasks: BackgroundTasks,
    request: ResearchRequest = ResearchRequest(),
    db: Session = Depends(get_db),
):
    """
    Start research on an organization in the background.

    Returns immediately with a result ID that can be polled
    for completion.
    """
    # Verify organization exists
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Generate result ID in advance
    from datetime import datetime

    result_id = f"organization_{org_id}_{datetime.utcnow().timestamp()}"

    # Store placeholder
    placeholder = ResearchResult(
        entity_type="organization",
        entity_id=org_id,
        entity_name=org.name,
        status="pending",
        started_at=datetime.utcnow(),
        config=request.to_config(),
    )
    _research_results[result_id] = placeholder

    # Schedule background task
    async def run_research():
        researcher = CompanyResearcher(db)
        result = await researcher.research(org_id, request.to_config())
        _research_results[result_id] = result

    background_tasks.add_task(run_research)

    return JSONResponse(
        content={
            "result_id": result_id,
            "status": "pending",
            "message": "Research started in background",
        }
    )


@router.get("/result/{result_id}")
async def get_research_result(result_id: str):
    """
    Get the result of a research operation.

    Use this to poll for completion of background research tasks.
    """
    result = _get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Research result not found")

    return JSONResponse(content=result.to_dict())


@router.get("/results")
async def list_research_results(
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    limit: int = 20,
):
    """
    List recent research results.

    Optionally filter by entity type or ID.
    """
    results = list(_research_results.values())

    # Apply filters
    if entity_type:
        results = [r for r in results if r.entity_type == entity_type]
    if entity_id:
        results = [r for r in results if r.entity_id == entity_id]

    # Sort by started_at descending
    results.sort(key=lambda r: r.started_at, reverse=True)

    # Apply limit
    results = results[:limit]

    return JSONResponse(
        content={
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }
    )
