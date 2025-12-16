"""
Google OAuth authentication routes for Perun's BlackBook.

Handles connecting, disconnecting, and managing Google accounts.
"""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GoogleAccount

templates = Jinja2Templates(directory="app/templates")
from app.services.google_auth import (
    GoogleAuthService,
    GoogleAuthConfigError,
    GoogleAuthTokenError,
    get_google_auth_service,
    GMAIL_SCOPES,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Store OAuth states temporarily (in production, use Redis or session store)
# This is simple in-memory storage for development
_oauth_states: dict[str, bool] = {}


def _generate_state() -> str:
    """Generate a secure random state parameter."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = True
    return state


def _verify_state(state: str) -> bool:
    """Verify and consume an OAuth state parameter."""
    if state in _oauth_states:
        del _oauth_states[state]
        return True
    return False


@router.get("/google/connect")
async def connect_google_account(
    request: Request,
    redirect_to: str = Query("/settings", description="URL to redirect after auth"),
):
    """
    Initiate Google OAuth flow.

    Redirects user to Google consent screen.
    """
    try:
        auth_service = get_google_auth_service()
    except GoogleAuthConfigError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Google OAuth not configured: {e}",
        )

    # Generate secure state with redirect URL encoded
    state = _generate_state()

    # Store redirect URL in session (simplified: append to state)
    # In production, store in Redis/session
    _oauth_states[f"{state}_redirect"] = redirect_to

    authorization_url, _ = auth_service.get_authorization_url(state=state)
    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    error: str | None = Query(None, description="Error from Google if auth failed"),
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth callback.

    Exchanges authorization code for tokens and stores the account.
    """
    # Handle errors from Google
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Google OAuth error: {error}",
        )

    # Verify state to prevent CSRF
    if not _verify_state(state):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter. Please try again.",
        )

    # Get redirect URL (default to settings)
    redirect_url = _oauth_states.pop(f"{state}_redirect", "/settings")

    try:
        auth_service = get_google_auth_service()

        # Exchange code for tokens
        credentials = auth_service.exchange_code(code)

        # Get user info (email, name)
        user_info = auth_service.get_user_info(credentials)
        email = user_info.get("email")
        display_name = user_info.get("name")

        if not email:
            raise HTTPException(
                status_code=400,
                detail="Could not retrieve email from Google account",
            )

        # Check if account already exists
        existing = db.query(GoogleAccount).filter_by(email=email).first()

        if existing:
            # Update existing account with new credentials
            existing.set_credentials(credentials)
            existing.display_name = display_name
            existing.scopes = credentials.get("scopes", GMAIL_SCOPES)
            existing.is_active = True
            db.commit()
        else:
            # Create new account
            account = GoogleAccount.create_with_credentials(
                email=email,
                credentials=credentials,
                display_name=display_name,
                scopes=credentials.get("scopes", GMAIL_SCOPES),
            )
            db.add(account)
            db.commit()

        # Redirect to settings with success message
        return RedirectResponse(
            url=f"{redirect_url}?connected={email}",
            status_code=302,
        )

    except GoogleAuthTokenError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to authenticate with Google: {e}",
        )
    except GoogleAuthConfigError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Google OAuth not configured: {e}",
        )


@router.post("/google/disconnect/{account_id}", response_class=HTMLResponse)
async def disconnect_google_account(
    request: Request,
    account_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Disconnect a Google account.

    Revokes OAuth tokens and removes the account from the database.
    Returns HTML partial for HTMX to update the accounts list.
    """
    account = db.query(GoogleAccount).filter_by(id=account_id).first()

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Google account not found",
        )

    # Try to revoke credentials (don't fail if revocation fails)
    try:
        auth_service = get_google_auth_service()
        credentials = account.get_credentials()
        auth_service.revoke_credentials(credentials)
    except Exception:
        # Revocation failed, but we'll still remove the account
        pass

    # Delete the account
    db.delete(account)
    db.commit()

    # Return updated accounts list
    accounts = db.query(GoogleAccount).order_by(GoogleAccount.created_at.desc()).all()
    return templates.TemplateResponse(
        "settings/_accounts_list.html",
        {
            "request": request,
            "google_accounts": accounts,
        },
    )


@router.get("/google/accounts")
async def list_google_accounts(
    db: Session = Depends(get_db),
    active_only: bool = Query(True, description="Only return active accounts"),
):
    """
    List all connected Google accounts.

    Returns account info without sensitive credentials.
    """
    query = db.query(GoogleAccount)

    if active_only:
        query = query.filter_by(is_active=True)

    accounts = query.order_by(GoogleAccount.email).all()

    return [
        {
            "id": str(account.id),
            "email": account.email,
            "display_name": account.display_name,
            "is_active": account.is_active,
            "scopes": account.scopes,
            "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        }
        for account in accounts
    ]


@router.post("/google/refresh/{account_id}")
async def refresh_google_credentials(
    account_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Refresh OAuth credentials for an account.

    Use this if the access token has expired.
    """
    account = db.query(GoogleAccount).filter_by(id=account_id).first()

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Google account not found",
        )

    try:
        auth_service = get_google_auth_service()
        credentials = account.get_credentials()
        refreshed = auth_service.refresh_credentials(credentials)
        account.set_credentials(refreshed)
        db.commit()

        return {
            "success": True,
            "message": f"Refreshed credentials for {account.email}",
        }
    except GoogleAuthTokenError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to refresh credentials: {e}",
        )


@router.get("/google/status/{account_id}")
async def check_google_account_status(
    account_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Check if an account's credentials are valid.
    """
    account = db.query(GoogleAccount).filter_by(id=account_id).first()

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Google account not found",
        )

    try:
        auth_service = get_google_auth_service()
        credentials = account.get_credentials()
        is_valid = auth_service.validate_credentials(credentials)

        return {
            "id": str(account.id),
            "email": account.email,
            "is_valid": is_valid,
            "is_active": account.is_active,
        }
    except Exception as e:
        return {
            "id": str(account.id),
            "email": account.email,
            "is_valid": False,
            "error": str(e),
        }
