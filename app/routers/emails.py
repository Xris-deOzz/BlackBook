"""
Email history routes for Perun's BlackBook.

Handles fetching and displaying email history from connected Gmail accounts.
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Person,
    GoogleAccount,
    EmailCache,
    Interaction,
    InteractionMedium,
    InteractionSource,
)
from app.services.gmail_service import (
    GmailService,
    GmailServiceError,
    GmailAuthError,
    GmailAPIError,
    EmailThread,
)

router = APIRouter(prefix="/emails", tags=["emails"])
templates = Jinja2Templates(directory="app/templates")

# Cache TTL in hours
CACHE_TTL_HOURS = 1


def _get_cached_threads(
    db: Session,
    person_id: UUID,
    account_id: UUID | None = None,
) -> list[dict] | None:
    """
    Get cached email threads for a person.

    Returns None if cache is expired or doesn't exist.
    """
    cache_cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)

    query = db.query(EmailCache).filter(
        EmailCache.person_id == person_id,
        EmailCache.cached_at >= cache_cutoff,
    )

    if account_id:
        query = query.filter(EmailCache.google_account_id == account_id)

    cached = query.order_by(EmailCache.last_message_date.desc()).all()

    if not cached:
        return None

    return [
        {
            "thread_id": c.gmail_thread_id,
            "account_id": str(c.google_account_id),
            "account_email": c.google_account.email if c.google_account else "",
            "subject": c.subject,
            "snippet": c.snippet,
            "participants": c.participants or [],
            "last_message_date": c.last_message_date.isoformat() if c.last_message_date else None,
            "message_count": c.message_count,
            "gmail_link": f"https://mail.google.com/mail/u/0/#all/{c.gmail_thread_id}",
            "cached": True,
        }
        for c in cached
    ]


def _cache_threads(
    db: Session,
    person_id: UUID,
    threads: list[EmailThread],
) -> None:
    """Cache email threads for a person."""
    # Delete old cache entries for this person
    db.query(EmailCache).filter(EmailCache.person_id == person_id).delete()

    # Insert new cache entries
    for thread in threads:
        cache_entry = EmailCache(
            person_id=person_id,
            google_account_id=thread.account_id,
            gmail_thread_id=thread.thread_id,
            subject=thread.subject,
            snippet=thread.snippet,
            participants=thread.participants,
            last_message_date=thread.last_message_date,
            message_count=thread.message_count,
        )
        db.add(cache_entry)

    db.commit()


@router.get("/person/{person_id}", response_class=HTMLResponse)
async def get_person_emails(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
    account_id: UUID | None = Query(None, description="Filter by specific Google account"),
    refresh: bool = Query(False, description="Force refresh from Gmail API"),
    max_results: int = Query(50, ge=1, le=100, description="Maximum threads to return"),
):
    """
    Get email history for a person.

    Returns HTML partial for HTMX or JSON if Accept header requests it.
    """
    # Verify person exists
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check if any Google accounts are connected
    has_accounts = db.query(GoogleAccount).filter_by(is_active=True).count() > 0

    threads = []
    from_cache = False

    # Check cache first (unless refresh requested)
    if not refresh:
        cached = _get_cached_threads(db, person_id, account_id)
        if cached is not None:
            threads = cached
            from_cache = True

    # Fetch fresh from Gmail API if needed
    if not threads and not from_cache:
        try:
            gmail_service = GmailService(db)
            email_threads = gmail_service.search_emails_for_person(person_id, max_results)

            # Cache the results
            _cache_threads(db, person_id, email_threads)
            threads = [t.to_dict() for t in email_threads]
            from_cache = False

        except (GmailAuthError, GmailAPIError, GmailServiceError):
            # Silently fail and show empty state for HTMX requests
            threads = []

    # Return HTML partial for HTMX
    return templates.TemplateResponse(
        "persons/_email_list.html",
        {
            "request": request,
            "threads": threads,
            "from_cache": from_cache,
            "person_id": str(person_id),
            "has_accounts": has_accounts,
        },
    )


@router.get("/person/{person_id}/refresh", response_class=HTMLResponse)
async def refresh_person_emails(
    request: Request,
    person_id: UUID,
    db: Session = Depends(get_db),
    max_results: int = Query(50, ge=1, le=100),
):
    """
    Force refresh email history for a person.

    Bypasses cache and fetches fresh data from Gmail API.
    """
    return await get_person_emails(
        request=request,
        person_id=person_id,
        db=db,
        refresh=True,
        max_results=max_results,
    )


@router.get("/thread/{account_id}/{thread_id}")
async def get_thread_details(
    account_id: UUID,
    thread_id: str,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific email thread.
    """
    # Verify account exists
    account = db.query(GoogleAccount).filter_by(id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Google account not found")

    try:
        gmail_service = GmailService(db)
        thread = gmail_service.get_thread_details(thread_id, account_id)

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        return thread.to_dict()

    except GmailAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Gmail authentication error: {e}",
        )
    except GmailAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Gmail API error: {e}",
        )


@router.post("/thread/{account_id}/{thread_id}/log")
async def log_email_as_interaction(
    account_id: UUID,
    thread_id: str,
    person_id: UUID = Query(..., description="Person to log interaction for"),
    db: Session = Depends(get_db),
):
    """
    Create an interaction from an email thread.

    Logs the email thread as an interaction with the specified person.
    """
    # Verify person exists
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check if interaction already exists for this thread
    existing = db.query(Interaction).filter_by(
        gmail_thread_id=thread_id,
        person_id=person_id,
    ).first()

    if existing:
        return {
            "success": False,
            "message": "Interaction already exists for this email thread",
            "interaction_id": str(existing.id),
        }

    # Get thread details
    try:
        gmail_service = GmailService(db)
        thread = gmail_service.get_thread_details(thread_id, account_id)

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Create interaction
        interaction = Interaction(
            person_id=person_id,
            person_name=person.full_name,
            medium=InteractionMedium.email,
            interaction_date=thread.last_message_date.date() if thread.last_message_date else None,
            notes=thread.subject,
            gmail_thread_id=thread_id,
            source=InteractionSource.email,
        )
        db.add(interaction)

        # Update person's last_contacted if this is more recent
        if thread.last_message_date:
            thread_date = thread.last_message_date.date()
            if not person.contacted or person.contacted is False:
                person.contacted = True

        db.commit()

        return {
            "success": True,
            "message": f"Logged email as interaction with {person.full_name}",
            "interaction_id": str(interaction.id),
            "subject": thread.subject,
        }

    except GmailAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Gmail authentication error: {e}",
        )
    except GmailAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Gmail API error: {e}",
        )


@router.get("/accounts")
async def list_email_accounts(
    db: Session = Depends(get_db),
):
    """
    List all connected Google accounts available for email search.
    """
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    return [
        {
            "id": str(account.id),
            "email": account.email,
            "display_name": account.display_name,
            "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
        }
        for account in accounts
    ]


@router.delete("/cache/person/{person_id}")
async def clear_person_email_cache(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Clear cached email data for a person.
    """
    deleted = db.query(EmailCache).filter(EmailCache.person_id == person_id).delete()
    db.commit()

    return {
        "success": True,
        "message": f"Cleared {deleted} cached email entries",
    }


@router.delete("/cache/expired")
async def clear_expired_cache(
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, description="Delete cache entries older than this many hours"),
):
    """
    Clear expired email cache entries.

    By default, removes entries older than 24 hours.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    deleted = db.query(EmailCache).filter(EmailCache.cached_at < cutoff).delete()
    db.commit()

    return {
        "success": True,
        "message": f"Cleared {deleted} expired cache entries",
    }
