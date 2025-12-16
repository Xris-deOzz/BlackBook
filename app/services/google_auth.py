"""
Google OAuth service for authenticating Gmail accounts.

Handles OAuth flow, token refresh, and credential management.
"""

import json
import os
from typing import Any
from urllib.parse import urlencode

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import get_settings

# Disable OAuthlib's strict scope checking for incremental authorization
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"


class GoogleAuthError(Exception):
    """Base exception for Google Auth errors."""

    pass


class GoogleAuthConfigError(GoogleAuthError):
    """Raised when Google OAuth is not configured."""

    pass


class GoogleAuthTokenError(GoogleAuthError):
    """Raised when token operations fail."""

    pass


# =============================================================================
# OAuth Scopes Configuration (Updated 2025-12-16)
# =============================================================================
# These scopes MUST match what's enabled in Google Cloud Console OAuth consent screen.
# If a scope is requested but not enabled in GCP, you get 403: access_denied
# =============================================================================

# Scopes that ARE enabled in Google Cloud Console (verified 2025-12-16)
ALL_SCOPES = [
    # Gmail
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    
    # Calendar
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
    "https://www.googleapis.com/auth/calendar.calendarlist",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.calendars",
    
    # Contacts
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
    
    # User Info
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",  # Verified enabled in GCP
    
    # People API
    "https://www.googleapis.com/auth/user.organization.read",
    "https://www.googleapis.com/auth/user.phonenumbers.read",
    "https://www.googleapis.com/auth/user.emails.read",
    "https://www.googleapis.com/auth/user.birthday.read",
    "https://www.googleapis.com/auth/profile.emails.read",
    
    # Tasks
    "https://www.googleapis.com/auth/tasks",
]

# Legacy variables for backwards compatibility
GMAIL_SCOPES = ALL_SCOPES
CALENDAR_SCOPES = ALL_SCOPES
CONTACTS_SCOPES = ALL_SCOPES
TASKS_SCOPES = ALL_SCOPES  # Tasks API scope included


class GoogleAuthService:
    """
    Service for managing Google OAuth authentication.

    Handles:
    - OAuth authorization URL generation
    - Callback processing and token exchange
    - Token refresh
    - Credential validation
    """

    def __init__(self):
        """Initialize the Google Auth service."""
        self.settings = get_settings()

        if not self.settings.google_oauth_configured:
            raise GoogleAuthConfigError(
                "Google OAuth not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in .env"
            )

        self._client_config = {
            "web": {
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.settings.google_redirect_uri],
            }
        }

    def get_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """
        Generate the Google OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        flow = Flow.from_client_config(
            self._client_config,
            scopes=ALL_SCOPES,
            redirect_uri=self.settings.google_redirect_uri,
        )

        authorization_url, state = flow.authorization_url(
            access_type="offline",  # Get refresh token
            include_granted_scopes="true",
            prompt="consent",  # Always show consent screen for refresh token
            state=state,
        )

        return authorization_url, state

    def exchange_code(self, code: str) -> dict[str, Any]:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dictionary containing:
            - token: Access token
            - refresh_token: Refresh token (for offline access)
            - token_uri: Token refresh endpoint
            - client_id: OAuth client ID
            - client_secret: OAuth client secret
            - scopes: Granted scopes

        Raises:
            GoogleAuthTokenError: If code exchange fails
        """
        try:
            flow = Flow.from_client_config(
                self._client_config,
                scopes=ALL_SCOPES,
                redirect_uri=self.settings.google_redirect_uri,
            )
            flow.fetch_token(code=code)
            credentials = flow.credentials

            return {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": list(credentials.scopes) if credentials.scopes else [],
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            }
        except Exception as e:
            raise GoogleAuthTokenError(f"Failed to exchange authorization code: {e}")

    def get_user_info(self, credentials_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Get user info (email, name) from Google.

        Args:
            credentials_dict: Credential dictionary from exchange_code

        Returns:
            Dictionary with email, name, picture, etc.

        Raises:
            GoogleAuthTokenError: If fetching user info fails
        """
        try:
            credentials = self._dict_to_credentials(credentials_dict)
            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info
        except Exception as e:
            raise GoogleAuthTokenError(f"Failed to get user info: {e}")

    def refresh_credentials(self, credentials_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Refresh expired credentials.

        Args:
            credentials_dict: Credential dictionary with refresh_token

        Returns:
            Updated credential dictionary with new access token

        Raises:
            GoogleAuthTokenError: If refresh fails
        """
        try:
            credentials = self._dict_to_credentials(credentials_dict)

            if not credentials.refresh_token:
                raise GoogleAuthTokenError("No refresh token available")

            credentials.refresh(Request())

            return {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": list(credentials.scopes) if credentials.scopes else [],
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            }
        except Exception as e:
            raise GoogleAuthTokenError(f"Failed to refresh credentials: {e}")

    def validate_credentials(self, credentials_dict: dict[str, Any]) -> bool:
        """
        Check if credentials are valid (not expired or can be refreshed).

        Args:
            credentials_dict: Credential dictionary to validate

        Returns:
            True if credentials are valid or refreshable
        """
        try:
            credentials = self._dict_to_credentials(credentials_dict)

            if credentials.valid:
                return True

            # Try to refresh if expired
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                return credentials.valid

            return False
        except Exception:
            return False

    def revoke_credentials(self, credentials_dict: dict[str, Any]) -> bool:
        """
        Revoke OAuth credentials (disconnect account).

        Args:
            credentials_dict: Credential dictionary to revoke

        Returns:
            True if revocation succeeded
        """
        import requests

        try:
            token = credentials_dict.get("token") or credentials_dict.get("refresh_token")
            if not token:
                return False

            response = requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            return response.status_code == 200
        except Exception:
            return False

    def _dict_to_credentials(self, credentials_dict: dict[str, Any]) -> Credentials:
        """Convert credential dictionary to google.oauth2.credentials.Credentials object."""
        return Credentials(
            token=credentials_dict.get("token"),
            refresh_token=credentials_dict.get("refresh_token"),
            token_uri=credentials_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=credentials_dict.get("client_id", self.settings.google_client_id),
            client_secret=credentials_dict.get("client_secret", self.settings.google_client_secret),
            scopes=credentials_dict.get("scopes", ALL_SCOPES),
        )

    def credentials_to_dict(self, credentials: Credentials) -> dict[str, Any]:
        """Convert google.oauth2.credentials.Credentials object to dictionary."""
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }


def get_google_auth_service() -> GoogleAuthService:
    """
    Get a Google Auth service instance.

    Returns:
        GoogleAuthService instance

    Raises:
        GoogleAuthConfigError: If Google OAuth is not configured
    """
    return GoogleAuthService()
