"""
Contact import routes for Perun's BlackBook.

Handles importing contacts from Google Contacts and LinkedIn CSV exports,
including import history tracking.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GoogleAccount, ImportHistory, ImportSource, ImportStatus
from app.services.contacts_service import (
    ContactsService,
    ContactsServiceError,
    ContactsAuthError,
    ContactsAPIError,
    get_contacts_service,
)
from app.services.linkedin_import import (
    LinkedInImportService,
    LinkedInImportError,
    LinkedInParseError,
    get_linkedin_import_service,
)

router = APIRouter(prefix="/import", tags=["import"])
templates = Jinja2Templates(directory="app/templates")

# Directory for storing uploaded import files
IMPORT_FILES_DIR = Path("data/imports")
IMPORT_FILES_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/google", response_class=HTMLResponse)
async def sync_google_contacts(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Sync contacts from all connected Google accounts.

    Fetches contacts from Google People API and imports them into BlackBook,
    matching by email address to existing persons.

    Returns HTML partial for HTMX.
    """
    service = get_contacts_service(db)

    try:
        results = service.sync_all_accounts()

        # Calculate totals
        total_created = 0
        total_updated = 0
        total_matched = 0
        total_fetched = 0
        total_saved = 0
        total_other = 0

        for result in results.values():
            total_created += result.contacts_created
            total_updated += result.contacts_updated
            total_matched += result.contacts_matched
            total_fetched += result.contacts_fetched
            total_saved += result.saved_contacts_fetched
            total_other += result.other_contacts_fetched

        # Build details with source breakdown
        details_parts = [
            f"Created: {total_created}",
            f"Updated: {total_updated}",
            f"Matched: {total_matched}",
        ]
        if total_saved > 0 or total_other > 0:
            details_parts.append(f"Sources: {total_saved} saved + {total_other} other contacts")

        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": True,
                "message": f"Synced {total_fetched} contacts from {len(results)} account(s)",
                "details": ", ".join(details_parts),
            },
        )

    except ContactsServiceError as e:
        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": f"Sync failed: {e}",
            },
        )


@router.post("/google/{account_id}", response_class=HTMLResponse)
async def sync_google_contacts_for_account(
    request: Request,
    account_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Sync contacts from a specific Google account.

    Args:
        account_id: UUID of the Google account to sync

    Returns HTML partial for HTMX.
    """
    # Verify account exists
    account = db.query(GoogleAccount).filter_by(id=account_id).first()
    if not account:
        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": "Google account not found",
            },
        )

    service = get_contacts_service(db)

    try:
        result = service.sync_contacts(account_id)

        # Build details with source breakdown
        details_parts = [
            f"Created: {result.contacts_created}",
            f"Updated: {result.contacts_updated}",
            f"Matched: {result.contacts_matched}",
        ]
        if result.saved_contacts_fetched > 0 or result.other_contacts_fetched > 0:
            details_parts.append(
                f"Sources: {result.saved_contacts_fetched} saved + {result.other_contacts_fetched} other contacts"
            )

        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": True,
                "message": f"Synced {result.contacts_fetched} contacts from {account.email}",
                "details": ", ".join(details_parts),
            },
        )

    except ContactsAuthError as e:
        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": f"Authentication failed for {account.email}. Please reconnect your Google account.",
            },
        )
    except ContactsAPIError as e:
        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": f"Google API error: {e}",
            },
        )
    except ContactsServiceError as e:
        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": f"Sync failed: {e}",
            },
        )


@router.post("/linkedin", response_class=HTMLResponse)
async def import_linkedin_csv(
    request: Request,
    file: UploadFile = File(..., description="LinkedIn Connections.csv file"),
    db: Session = Depends(get_db),
):
    """
    Import contacts from a LinkedIn CSV export.

    Expects a Connections.csv file exported from LinkedIn.
    The file should contain columns: First Name, Last Name, Email Address,
    Company, Position, Connected On.

    Returns HTML partial for HTMX.
    """
    # Validate file type
    if not file.filename:
        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": "No filename provided",
            },
        )

    if not file.filename.endswith(".csv"):
        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": "Invalid file type. Please upload a CSV file.",
            },
        )

    try:
        # Read file content
        content = await file.read()
        file_size = len(content)

        # Generate unique filename for storage
        stored_filename = f"{uuid.uuid4()}.csv"
        stored_path = IMPORT_FILES_DIR / stored_filename

        # Save the file to disk
        with open(stored_path, "wb") as f:
            f.write(content)

        service = get_linkedin_import_service(db)
        result = service.import_from_csv(content)

        # Create import history record
        history = ImportHistory(
            source=ImportSource.linkedin,
            status=ImportStatus.success,
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_size_bytes=file_size,
            records_parsed=result.contacts_parsed,
            records_created=result.contacts_created,
            records_updated=result.contacts_updated,
            records_skipped=result.contacts_matched,
            organizations_created=result.organizations_created,
        )
        db.add(history)
        db.commit()

        details_parts = [
            f"Parsed: {result.contacts_parsed}",
            f"Created: {result.contacts_created}",
            f"Updated: {result.contacts_updated}",
            f"Matched: {result.contacts_matched}",
        ]
        if result.organizations_created > 0:
            details_parts.append(f"Organizations: {result.organizations_created}")

        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": True,
                "message": f"Imported contacts from {file.filename}",
                "details": ", ".join(details_parts),
            },
        )

    except LinkedInParseError as e:
        # Record failed import
        history = ImportHistory(
            source=ImportSource.linkedin,
            status=ImportStatus.failed,
            original_filename=file.filename or "unknown",
            file_size_bytes=len(content) if 'content' in locals() else None,
            error_message=str(e),
        )
        db.add(history)
        db.commit()

        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": f"Failed to parse CSV file: {e}",
            },
        )
    except LinkedInImportError as e:
        # Record failed import
        history = ImportHistory(
            source=ImportSource.linkedin,
            status=ImportStatus.failed,
            original_filename=file.filename or "unknown",
            file_size_bytes=len(content) if 'content' in locals() else None,
            error_message=str(e),
        )
        db.add(history)
        db.commit()

        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": f"Import error: {e}",
            },
        )
    except Exception as e:
        # Record failed import
        history = ImportHistory(
            source=ImportSource.linkedin,
            status=ImportStatus.failed,
            original_filename=file.filename or "unknown",
            file_size_bytes=len(content) if 'content' in locals() else None,
            error_message=str(e),
        )
        db.add(history)
        db.commit()

        return templates.TemplateResponse(
            "settings/_sync_result.html",
            {
                "request": request,
                "success": False,
                "message": f"Import failed: {e}",
            },
        )


@router.get("/status")
async def get_import_status(
    db: Session = Depends(get_db),
):
    """
    Get the status of contact import sources.

    Returns information about connected Google accounts and their
    last sync timestamps.
    """
    accounts = db.query(GoogleAccount).filter_by(is_active=True).all()

    return {
        "google_accounts": [
            {
                "id": str(account.id),
                "email": account.email,
                "display_name": account.display_name,
                "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
                "has_contacts_scope": "contacts.readonly" in (account.scopes or []),
            }
            for account in accounts
        ],
        "linkedin": {
            "available": True,
            "description": "Upload your LinkedIn Connections.csv export",
        },
    }


@router.get("/history", response_class=HTMLResponse)
async def get_import_history(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get import history list as HTML partial for HTMX.
    """
    history = db.query(ImportHistory).order_by(ImportHistory.imported_at.desc()).all()

    return templates.TemplateResponse(
        "settings/_import_history.html",
        {
            "request": request,
            "import_history": history,
        },
    )


@router.get("/history/{history_id}/download")
async def download_import_file(
    history_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Download a previously uploaded import file.
    """
    history = db.query(ImportHistory).filter_by(id=history_id).first()

    if not history:
        raise HTTPException(status_code=404, detail="Import record not found")

    if not history.stored_filename:
        raise HTTPException(status_code=404, detail="File not available for download")

    file_path = IMPORT_FILES_DIR / history.stored_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File no longer exists on disk")

    return FileResponse(
        path=str(file_path),
        filename=history.original_filename,
        media_type="text/csv",
    )


@router.post("/google/push/{person_id}", response_class=HTMLResponse)
async def push_person_to_google(
    request: Request,
    person_id: UUID,
    account_id: UUID = Form(...),
    db: Session = Depends(get_db),
):
    """
    Push a BlackBook person to Google Contacts.

    Creates a new contact in Google Contacts and links it to the person record.

    Args:
        person_id: UUID of the person to push
        account_id: UUID of the Google account to push to

    Returns HTML partial for HTMX.
    """
    service = get_contacts_service(db)

    try:
        result = service.push_to_google(person_id, account_id)

        return templates.TemplateResponse(
            "persons/_google_sync_status.html",
            {
                "request": request,
                "success": True,
                "message": result["message"],
            },
        )

    except ContactsAuthError as e:
        return templates.TemplateResponse(
            "persons/_google_sync_status.html",
            {
                "request": request,
                "success": False,
                "message": "Authentication failed. Please reconnect your Google account.",
            },
        )
    except ContactsAPIError as e:
        return templates.TemplateResponse(
            "persons/_google_sync_status.html",
            {
                "request": request,
                "success": False,
                "message": f"Google API error: {e}",
            },
        )
    except ContactsServiceError as e:
        return templates.TemplateResponse(
            "persons/_google_sync_status.html",
            {
                "request": request,
                "success": False,
                "message": str(e),
            },
        )
