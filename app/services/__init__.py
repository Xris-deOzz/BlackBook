"""
Application services for Perun's BlackBook.
"""

from app.services.encryption import EncryptionService, get_encryption_service
from app.services.google_auth import (
    GoogleAuthService,
    GoogleAuthError,
    GoogleAuthConfigError,
    GoogleAuthTokenError,
    get_google_auth_service,
    GMAIL_SCOPES,
)
from app.services.gmail_service import (
    GmailService,
    GmailServiceError,
    GmailAuthError,
    GmailAPIError,
    EmailThread,
    get_gmail_service,
)

__all__ = [
    # Encryption
    "EncryptionService",
    "get_encryption_service",
    # Google Auth
    "GoogleAuthService",
    "GoogleAuthError",
    "GoogleAuthConfigError",
    "GoogleAuthTokenError",
    "get_google_auth_service",
    "GMAIL_SCOPES",
    # Gmail
    "GmailService",
    "GmailServiceError",
    "GmailAuthError",
    "GmailAPIError",
    "EmailThread",
    "get_gmail_service",
]
