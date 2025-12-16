"""
Encryption service for secure storage of OAuth credentials.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
"""

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class EncryptionError(Exception):
    """Base exception for encryption errors."""

    pass


class EncryptionKeyError(EncryptionError):
    """Raised when encryption key is invalid or missing."""

    pass


class DecryptionError(EncryptionError):
    """Raised when decryption fails."""

    pass


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.

    Uses Fernet symmetric encryption which provides:
    - AES-128-CBC encryption
    - HMAC-SHA256 authentication
    - Automatic IV generation
    - Timestamp-based token validation
    """

    def __init__(self, encryption_key: str):
        """
        Initialize the encryption service.

        Args:
            encryption_key: Base64-encoded Fernet key (32 bytes when decoded)

        Raises:
            EncryptionKeyError: If the key is invalid or missing
        """
        if not encryption_key:
            raise EncryptionKeyError("Encryption key is required")

        try:
            self._fernet = Fernet(encryption_key.encode())
        except Exception as e:
            raise EncryptionKeyError(f"Invalid encryption key: {e}")

    def encrypt(self, data: str) -> str:
        """
        Encrypt a string.

        Args:
            data: Plain text string to encrypt

        Returns:
            Base64-encoded encrypted string

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            encrypted = self._fernet.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Decrypted plain text string

        Raises:
            DecryptionError: If decryption fails (invalid token, corrupted data, etc.)
        """
        try:
            decrypted = self._fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except InvalidToken:
            raise DecryptionError("Invalid or corrupted encrypted data")
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def encrypt_json(self, data: dict | list) -> str:
        """
        Encrypt a JSON-serializable object.

        Args:
            data: Dictionary or list to encrypt

        Returns:
            Base64-encoded encrypted string

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            json_str = json.dumps(data)
            return self.encrypt(json_str)
        except (TypeError, ValueError) as e:
            raise EncryptionError(f"Failed to serialize data to JSON: {e}")

    def decrypt_json(self, encrypted_data: str) -> dict | list:
        """
        Decrypt to a JSON object.

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Decrypted dictionary or list

        Raises:
            DecryptionError: If decryption or JSON parsing fails
        """
        try:
            json_str = self.decrypt(encrypted_data)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise DecryptionError(f"Failed to parse decrypted data as JSON: {e}")

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded key string suitable for ENCRYPTION_KEY env var
        """
        return Fernet.generate_key().decode()


@lru_cache
def get_encryption_service() -> EncryptionService:
    """
    Get a cached encryption service instance.

    Returns:
        EncryptionService configured with the app's encryption key

    Raises:
        EncryptionKeyError: If encryption is not configured
    """
    settings = get_settings()
    if not settings.encryption_configured:
        raise EncryptionKeyError(
            "Encryption key not configured. Set ENCRYPTION_KEY in .env"
        )
    return EncryptionService(settings.encryption_key)
