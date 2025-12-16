"""
Perun's BlackBook - FastAPI Application Entry Point
# reload trigger v2
"""

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, SessionLocal
from app.routers import persons, organizations, interactions, views, tags, graph, auth, emails, calendar, pending_contacts
from app.routers import emails_inbox
from app.routers import settings as settings_router
from app.routers import import_contacts
from app.routers import ai_chat, ai_research
from app.routers import person_details
from app.routers import person_sections
from app.routers import organization_sections
from app.routers import organization_details
from app.routers import lookups
from app.routers import lookups_admin
from app.routers import dashboard
from app.routers import tasks
from app.routers import christmas_lists
from app.routers.views import create_default_views

# Initialize FastAPI app
settings = get_settings()

app = FastAPI(
    title="Perun's BlackBook",
    description="Personal CRM for managing professional relationships",
    version="0.1.0",
    debug=settings.debug,
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(persons.router)
app.include_router(organizations.router)
app.include_router(interactions.router)
app.include_router(views.router)
app.include_router(tags.router)
app.include_router(graph.router)
app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(emails_inbox.router)
app.include_router(settings_router.router)
app.include_router(calendar.router)
app.include_router(pending_contacts.router)
app.include_router(import_contacts.router)
app.include_router(ai_chat.router)
app.include_router(ai_research.router)
app.include_router(person_details.router)
app.include_router(person_sections.router)
app.include_router(organization_sections.router)
app.include_router(organization_details.router)
app.include_router(lookups.router)
app.include_router(lookups_admin.router)
app.include_router(dashboard.router)
app.include_router(tasks.router)
app.include_router(christmas_lists.router)


@app.on_event("startup")
async def startup_event():
    """Initialize default views and start background tasks on application startup."""
    # Create default views and Christmas tags
    db = SessionLocal()
    try:
        create_default_views(db)
        # Ensure Christmas tags exist
        from app.services.christmas_service import get_christmas_service
        christmas_svc = get_christmas_service(db)
        christmas_svc.get_or_create_christmas_tags()
    finally:
        db.close()

    # Start email sync scheduler
    try:
        from app.tasks.email_sync import start_scheduler
        start_scheduler()
    except ImportError:
        # APScheduler not installed yet
        pass


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background tasks on application shutdown."""
    try:
        from app.tasks.email_sync import stop_scheduler
        stop_scheduler()
    except ImportError:
        pass


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with dashboard."""
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Dashboard - Perun's BlackBook",
        },
    )


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint that also verifies database connection.
    """
    try:
        # Test database connection
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status,
        "debug": settings.debug,
    }


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Get database statistics.
    Verifies database connection by querying actual data.
    """
    stats = {}

    # Query counts from each table
    tables = ["persons", "organizations", "tags", "interactions"]

    for table in tables:
        result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
        count = result.scalar()
        stats[table] = count

    return stats
# trigger reload v9 - auto_reload templates
