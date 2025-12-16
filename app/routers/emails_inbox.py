"""
Email Inbox routes for Perun's BlackBook.

Handles the Email inbox page with filtering, search, and detail views.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    GoogleAccount,
    EmailMessage,
    EmailPersonLink,
    EmailSyncState,
    Person,
    PersonEmail,
)
from app.services.gmail_sync_service import get_gmail_sync_service, get_gmail_labels

router = APIRouter(prefix="/emails", tags=["emails"])
templates = Jinja2Templates(directory="app/templates")

# Constants
DEFAULT_PAGE_SIZE = 50


@router.get("", response_class=HTMLResponse)
async def email_inbox(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    account_id: Optional[str] = Query(None, description="Filter by Google account"),
    q: Optional[str] = Query(None, description="Search query"),
    folder: str = Query("inbox", description="Folder filter: inbox, sent, all"),
    label: Optional[str] = Query(None, description="Filter by Gmail label"),
    unread_only: bool = Query(False, description="Show only unread emails"),
):
    """
    Email inbox page - list all synced emails with filtering.
    """
    # Get all connected Google accounts
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    # Build email query
    query = db.query(EmailMessage).options(
        joinedload(EmailMessage.person_links).joinedload(EmailPersonLink.person)
    )

    # Filter by account
    if account_id:
        try:
            query = query.filter(EmailMessage.google_account_id == UUID(account_id))
        except ValueError:
            pass

    # Filter by folder
    if folder == "inbox":
        query = query.filter(EmailMessage.labels.contains(["INBOX"]))
    elif folder == "sent":
        query = query.filter(EmailMessage.labels.contains(["SENT"]))
    elif folder == "drafts":
        query = query.filter(EmailMessage.labels.contains(["DRAFT"]))
    elif folder == "spam":
        query = query.filter(EmailMessage.labels.contains(["SPAM"]))
    elif folder == "trash":
        query = query.filter(EmailMessage.labels.contains(["TRASH"]))

    # Filter by Gmail label
    if label:
        query = query.filter(EmailMessage.labels.contains([label]))

    # Filter unread only
    if unread_only:
        query = query.filter(EmailMessage.is_read == False)

    # Search
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                EmailMessage.subject.ilike(search_term),
                EmailMessage.snippet.ilike(search_term),
                EmailMessage.from_email.ilike(search_term),
                EmailMessage.from_name.ilike(search_term),
            )
        )

    # Order by date (newest first)
    query = query.order_by(desc(EmailMessage.internal_date))

    # Get total count
    total_count = query.count()
    total_pages = (total_count + per_page - 1) // per_page

    # Paginate
    offset = (page - 1) * per_page
    emails = query.offset(offset).limit(per_page).all()

    # Get unread counts per folder
    unread_inbox = db.query(func.count(EmailMessage.id)).filter(
        EmailMessage.is_read == False,
        EmailMessage.labels.contains(["INBOX"]),
    ).scalar() or 0

    # Get sync state for each account
    sync_states = {}
    for account in accounts:
        state = db.query(EmailSyncState).filter_by(
            google_account_id=account.id
        ).first()
        sync_states[str(account.id)] = state

    # Get distinct Gmail labels from synced emails
    gmail_labels = _get_gmail_labels(db, account_id)

    # Group emails by date for display
    email_groups = _group_emails_by_date(emails)

    return templates.TemplateResponse(
        "emails/inbox.html",
        {
            "request": request,
            "title": "Email",
            "emails": emails,
            "email_groups": email_groups,
            "accounts": accounts,
            "sync_states": sync_states,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "account_id": account_id or "",
            "q": q or "",
            "folder": folder,
            "label": label or "",
            "unread_only": unread_only,
            "unread_inbox": unread_inbox,
            "gmail_labels": gmail_labels,
        },
    )


@router.get("/table", response_class=HTMLResponse)
async def email_inbox_table(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    account_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    folder: str = Query("inbox"),
    label: Optional[str] = Query(None),
    unread_only: bool = Query(False),
):
    """
    HTMX partial for email list table.
    """
    # Build email query (same as inbox)
    query = db.query(EmailMessage).options(
        joinedload(EmailMessage.person_links).joinedload(EmailPersonLink.person)
    )

    if account_id:
        try:
            query = query.filter(EmailMessage.google_account_id == UUID(account_id))
        except ValueError:
            pass

    if folder == "inbox":
        query = query.filter(EmailMessage.labels.contains(["INBOX"]))
    elif folder == "sent":
        query = query.filter(EmailMessage.labels.contains(["SENT"]))
    elif folder == "drafts":
        query = query.filter(EmailMessage.labels.contains(["DRAFT"]))
    elif folder == "spam":
        query = query.filter(EmailMessage.labels.contains(["SPAM"]))
    elif folder == "trash":
        query = query.filter(EmailMessage.labels.contains(["TRASH"]))

    if label:
        query = query.filter(EmailMessage.labels.contains([label]))

    if unread_only:
        query = query.filter(EmailMessage.is_read == False)

    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                EmailMessage.subject.ilike(search_term),
                EmailMessage.snippet.ilike(search_term),
                EmailMessage.from_email.ilike(search_term),
                EmailMessage.from_name.ilike(search_term),
            )
        )

    query = query.order_by(desc(EmailMessage.internal_date))

    total_count = query.count()
    total_pages = (total_count + per_page - 1) // per_page

    offset = (page - 1) * per_page
    emails = query.offset(offset).limit(per_page).all()

    email_groups = _group_emails_by_date(emails)

    # Get accounts for empty state
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    return templates.TemplateResponse(
        "emails/_email_list.html",
        {
            "request": request,
            "emails": emails,
            "email_groups": email_groups,
            "accounts": accounts,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "account_id": account_id or "",
            "q": q or "",
            "folder": folder,
            "label": label or "",
            "unread_only": unread_only,
        },
    )


@router.get("/{email_id}", response_class=HTMLResponse)
async def email_detail(
    request: Request,
    email_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Email detail view - shows full email with linked contacts.
    """
    email = db.query(EmailMessage).options(
        joinedload(EmailMessage.person_links).joinedload(EmailPersonLink.person),
        joinedload(EmailMessage.google_account),
    ).filter_by(id=email_id).first()

    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Get other emails in the same thread
    thread_emails = db.query(EmailMessage).filter(
        EmailMessage.gmail_thread_id == email.gmail_thread_id,
        EmailMessage.id != email.id,
    ).order_by(EmailMessage.internal_date).all()

    return templates.TemplateResponse(
        "emails/detail.html",
        {
            "request": request,
            "title": email.subject or "(No subject)",
            "email": email,
            "thread_emails": thread_emails,
        },
    )


@router.post("/sync", response_class=HTMLResponse)
async def trigger_sync(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    account_id: Optional[str] = Query(None, description="Sync specific account"),
):
    """
    Trigger email sync (manual sync button).
    """
    sync_service = get_gmail_sync_service(db)

    if account_id:
        try:
            account = db.query(GoogleAccount).filter_by(id=UUID(account_id)).first()
            if account:
                # Run sync in background
                background_tasks.add_task(_run_sync, db, account.id)
        except ValueError:
            pass
    else:
        # Sync all accounts
        accounts = db.query(GoogleAccount).filter_by(is_active=True).all()
        for account in accounts:
            background_tasks.add_task(_run_sync, db, account.id)

    # Return updated sync status partial
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()
    sync_states = {}
    for account in accounts:
        state = db.query(EmailSyncState).filter_by(
            google_account_id=account.id
        ).first()
        sync_states[str(account.id)] = state

    return templates.TemplateResponse(
        "emails/_sync_status.html",
        {
            "request": request,
            "accounts": accounts,
            "sync_states": sync_states,
            "sync_triggered": True,
        },
    )


@router.post("/sync-folder", response_class=HTMLResponse)
async def trigger_folder_sync(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    folder: str = Query(..., description="Folder to sync (inbox, sent, spam, trash, drafts)"),
    label: Optional[str] = Query(None, description="Custom label ID to sync"),
    account_id: Optional[str] = Query(None, description="Sync specific account"),
):
    """
    Trigger sync for a specific folder/label.
    """
    # Map folder names to Gmail label IDs
    folder_to_label = {
        "inbox": "INBOX",
        "sent": "SENT",
        "spam": "SPAM",
        "trash": "TRASH",
        "drafts": "DRAFT",
        "all": None,  # No filter for all
    }

    # Determine which label to sync
    label_id = label if label else folder_to_label.get(folder)

    if not label_id:
        # For "all" folder, do a regular full sync
        if account_id:
            try:
                account = db.query(GoogleAccount).filter_by(id=UUID(account_id)).first()
                if account:
                    background_tasks.add_task(_run_sync, db, account.id)
            except ValueError:
                pass
        else:
            accounts = db.query(GoogleAccount).filter_by(is_active=True).all()
            for account in accounts:
                background_tasks.add_task(_run_sync, db, account.id)
    else:
        # Sync specific folder
        if account_id:
            try:
                account = db.query(GoogleAccount).filter_by(id=UUID(account_id)).first()
                if account:
                    background_tasks.add_task(_run_folder_sync, db, account.id, label_id)
            except ValueError:
                pass
        else:
            accounts = db.query(GoogleAccount).filter_by(is_active=True).all()
            for account in accounts:
                background_tasks.add_task(_run_folder_sync, db, account.id, label_id)

    # Build the refresh URL with current filters
    refresh_url = f"/emails/table?folder={folder}&account_id={account_id or ''}&label={label or ''}"

    # Return response with auto-refresh after delay
    return HTMLResponse(
        content=f"""
        <div class="text-sm text-blue-600 flex items-center"
             hx-get="{refresh_url}"
             hx-target="#email-list"
             hx-trigger="load delay:3s"
             hx-swap="innerHTML">
            <svg class="w-4 h-4 mr-1.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            Syncing... (will refresh in 3s)
        </div>
        <script>
            // Also update sync status after refresh
            setTimeout(function() {{
                document.querySelector('#sync-status').innerHTML = '<div class="text-sm text-green-600 flex items-center"><svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>Sync complete</div>';
            }}, 3500);
        </script>
        """,
        status_code=200,
    )


@router.post("/{email_id}/link-person", response_class=HTMLResponse)
async def link_email_to_person(
    request: Request,
    email_id: UUID,
    person_id: UUID = Query(...),
    link_type: str = Query("mentioned"),
    db: Session = Depends(get_db),
):
    """
    Manually link an email to a CRM contact.
    """
    email = db.query(EmailMessage).filter_by(id=email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check if link already exists
    existing = db.query(EmailPersonLink).filter_by(
        email_message_id=email_id,
        person_id=person_id,
        link_type=link_type,
    ).first()

    if not existing:
        link = EmailPersonLink(
            email_message_id=email_id,
            person_id=person_id,
            link_type=link_type,
            linked_by="manual",
        )
        db.add(link)
        db.commit()

    # Return updated linked contacts partial
    email = db.query(EmailMessage).options(
        joinedload(EmailMessage.person_links).joinedload(EmailPersonLink.person)
    ).filter_by(id=email_id).first()

    return templates.TemplateResponse(
        "emails/_linked_contacts.html",
        {
            "request": request,
            "email": email,
        },
    )


def _run_sync(db: Session, account_id: UUID) -> None:
    """Background task to run email sync."""
    from app.database import SessionLocal

    # Create new session for background task
    with SessionLocal() as session:
        account = session.query(GoogleAccount).filter_by(id=account_id).first()
        if account:
            sync_service = get_gmail_sync_service(session)
            sync_state = session.query(EmailSyncState).filter_by(
                google_account_id=account_id
            ).first()

            if sync_state and not sync_state.needs_full_sync:
                sync_service.incremental_sync(account)
            else:
                sync_service.full_sync(account, max_results=200)


def _run_folder_sync(db: Session, account_id: UUID, label_id: str) -> None:
    """Background task to run folder-specific email sync."""
    from app.database import SessionLocal

    # Create new session for background task
    with SessionLocal() as session:
        account = session.query(GoogleAccount).filter_by(id=account_id).first()
        if account:
            sync_service = get_gmail_sync_service(session)
            sync_service.sync_folder(account, label_id, max_results=200)


def _get_gmail_labels(db: Session, account_id: Optional[str] = None) -> list[dict]:
    """
    Get ALL Gmail labels from the Gmail API.

    Fetches all user labels directly from Gmail API (not limited to synced emails).
    Returns hierarchical label structure (parent labels with children).
    Excludes system labels like UNREAD, CATEGORY_*.
    """
    # System labels to exclude from display (these are internal Gmail labels)
    system_labels = {
        "UNREAD", "STARRED", "IMPORTANT", "CHAT", "SPAM", "TRASH",
        "CATEGORY_PERSONAL", "CATEGORY_SOCIAL", "CATEGORY_PROMOTIONS",
        "CATEGORY_UPDATES", "CATEGORY_FORUMS",
    }

    # Standard folders we already show
    standard_folders = {"INBOX", "SENT", "DRAFT", "DRAFTS"}

    # Additional labels to exclude (system/internal labels by name)
    excluded_label_names = {
        # Star colors (Gmail internal)
        "BLUE_STAR", "GREEN_STAR", "RED_STAR", "YELLOW_STAR", "ORANGE_STAR", "PURPLE_STAR",
        "BLUE_INFO", "GREEN_CHECK", "YELLOW_BANG", "RED_BANG",
        "BLUE_CIRCLE", "GREEN_CIRCLE", "RED_CIRCLE", "YELLOW_CIRCLE", "ORANGE_CIRCLE", "PURPLE_CIRCLE",
        # Other system labels
        "Junk E-mail",
        "Snoozed", "Important",
    }

    # Get ALL labels directly from Gmail API
    label_names = {}  # Maps label_id -> label_name
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    if account_id:
        try:
            account_uuid = UUID(account_id)
            account = db.query(GoogleAccount).filter_by(id=account_uuid).first()
            if account:
                label_names = get_gmail_labels(account)
        except ValueError:
            pass
    else:
        # Get labels from all accounts
        for account in accounts:
            account_labels = get_gmail_labels(account)
            label_names.update(account_labels)

    # Build flat list from ALL Gmail labels (not just synced emails)
    flat_labels = []
    for label_id, display_name in label_names.items():
        # Filter out system labels and standard folders
        if label_id in system_labels:
            continue
        if display_name in standard_folders:
            continue
        if display_name in system_labels:
            continue
        if display_name in excluded_label_names:
            continue
        # Also filter star/circle labels that might have different casing
        if display_name.upper() in excluded_label_names or display_name.replace("_", " ").upper() in {n.replace("_", " ").upper() for n in excluded_label_names}:
            continue

        flat_labels.append({
            "name": label_id,
            "display_name": display_name,
        })

    # Build hierarchical structure
    # Gmail uses "/" to separate parent/child labels (e.g., "News/Bloomberg")
    hierarchy = {}
    standalone = []

    for label in flat_labels:
        display_name = label["display_name"]
        if "/" in display_name:
            # This is a nested label
            parts = display_name.split("/")
            parent_name = parts[0]
            child_name = "/".join(parts[1:])  # Handle deeply nested labels

            if parent_name not in hierarchy:
                hierarchy[parent_name] = {
                    "name": None,  # Parent may not have its own label ID
                    "display_name": parent_name,
                    "children": [],
                }

            hierarchy[parent_name]["children"].append({
                "name": label["name"],
                "display_name": child_name,
            })
        else:
            # Check if this is a parent of nested labels
            is_parent = any(
                l["display_name"].startswith(display_name + "/")
                for l in flat_labels
            )
            if is_parent:
                if display_name not in hierarchy:
                    hierarchy[display_name] = {
                        "name": label["name"],
                        "display_name": display_name,
                        "children": [],
                    }
                else:
                    # Update with actual label ID
                    hierarchy[display_name]["name"] = label["name"]
            else:
                standalone.append(label)

    # Convert hierarchy to sorted list
    result_labels = []

    # Add hierarchical labels (sorted by parent name)
    for parent_name in sorted(hierarchy.keys(), key=str.lower):
        parent = hierarchy[parent_name]
        # Sort children alphabetically
        parent["children"].sort(key=lambda x: x["display_name"].lower())
        result_labels.append(parent)

    # Add standalone labels (sorted alphabetically)
    standalone.sort(key=lambda x: x["display_name"].lower())
    for label in standalone:
        label["children"] = []  # No children
        result_labels.append(label)

    return result_labels


def _group_emails_by_date(emails: list[EmailMessage]) -> list[dict]:
    """Group emails by date for display (Today, Yesterday, This Week, etc.)."""
    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    groups = {
        "Today": [],
        "Yesterday": [],
        "This Week": [],
        "Earlier": [],
    }

    for email in emails:
        if email.internal_date:
            email_date = email.internal_date.date()
            if email_date == today:
                groups["Today"].append(email)
            elif email_date == yesterday:
                groups["Yesterday"].append(email)
            elif email_date > week_ago:
                groups["This Week"].append(email)
            else:
                groups["Earlier"].append(email)
        else:
            groups["Earlier"].append(email)

    # Convert to list format for template
    result = []
    for label, emails_in_group in groups.items():
        if emails_in_group:
            result.append({"label": label, "emails": emails_in_group})

    return result
