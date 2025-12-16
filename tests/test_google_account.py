"""
Tests for GoogleAccount model CRUD operations.

Tests include verifying that the encrypted credentials field works correctly.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from app.models import GoogleAccount


class TestGoogleAccountCreate:
    """Test GoogleAccount creation."""

    def test_create_google_account(self, db_session):
        """Test creating a basic Google account."""
        account = GoogleAccount(
            email="test@gmail.com",
            display_name="Test User",
            credentials_encrypted="encrypted_token_data_here",
            scopes=["gmail.readonly", "calendar.readonly"],
        )
        db_session.add(account)
        db_session.flush()

        assert account.id is not None
        assert account.email == "test@gmail.com"
        assert account.display_name == "Test User"
        assert account.credentials_encrypted == "encrypted_token_data_here"
        assert account.scopes == ["gmail.readonly", "calendar.readonly"]
        assert account.is_active is True  # Default
        assert account.created_at is not None
        assert account.updated_at is not None

    def test_create_google_account_minimal(self, db_session):
        """Test creating account with only required fields."""
        account = GoogleAccount(
            email="minimal@gmail.com",
            credentials_encrypted="some_encrypted_data",
        )
        db_session.add(account)
        db_session.flush()

        assert account.id is not None
        assert account.email == "minimal@gmail.com"
        assert account.display_name is None
        assert account.scopes is None
        assert account.is_active is True
        assert account.last_sync_at is None

    def test_unique_email_constraint(self, db_session):
        """Test that email must be unique."""
        account1 = GoogleAccount(
            email="unique@gmail.com",
            credentials_encrypted="token1",
        )
        db_session.add(account1)
        db_session.flush()

        account2 = GoogleAccount(
            email="unique@gmail.com",
            credentials_encrypted="token2",
        )
        db_session.add(account2)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_credentials_encrypted_required(self, db_session):
        """Test that credentials_encrypted is required."""
        account = GoogleAccount(
            email="nocreds@gmail.com",
            # Missing credentials_encrypted
        )
        db_session.add(account)

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestGoogleAccountRead:
    """Test GoogleAccount read operations."""

    def test_read_by_email(self, db_session):
        """Test finding account by email."""
        account = GoogleAccount(
            email="findme@gmail.com",
            credentials_encrypted="encrypted_data",
        )
        db_session.add(account)
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(email="findme@gmail.com").first()

        assert found is not None
        assert found.id == account.id

    def test_read_active_accounts(self, db_session):
        """Test filtering by active status."""
        active = GoogleAccount(
            email="active@gmail.com",
            credentials_encrypted="token",
            is_active=True,
        )
        inactive = GoogleAccount(
            email="inactive@gmail.com",
            credentials_encrypted="token",
            is_active=False,
        )
        db_session.add_all([active, inactive])
        db_session.flush()

        active_accounts = db_session.query(GoogleAccount).filter_by(is_active=True).all()
        # May include other test accounts, so check our specific one is included
        emails = [a.email for a in active_accounts]
        assert "active@gmail.com" in emails
        assert "inactive@gmail.com" not in emails


class TestGoogleAccountUpdate:
    """Test GoogleAccount update operations."""

    def test_update_credentials(self, db_session):
        """Test updating encrypted credentials."""
        account = GoogleAccount(
            email="update@gmail.com",
            credentials_encrypted="old_token",
        )
        db_session.add(account)
        db_session.flush()

        # Update credentials
        account.credentials_encrypted = "new_refreshed_token"
        db_session.flush()

        # Verify update
        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert found.credentials_encrypted == "new_refreshed_token"

    def test_update_last_sync_at(self, db_session):
        """Test updating last sync timestamp."""
        account = GoogleAccount(
            email="sync@gmail.com",
            credentials_encrypted="token",
        )
        db_session.add(account)
        db_session.flush()

        assert account.last_sync_at is None

        # Update sync time
        sync_time = datetime.now(timezone.utc)
        account.last_sync_at = sync_time
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert found.last_sync_at is not None

    def test_deactivate_account(self, db_session):
        """Test deactivating an account."""
        account = GoogleAccount(
            email="deactivate@gmail.com",
            credentials_encrypted="token",
            is_active=True,
        )
        db_session.add(account)
        db_session.flush()

        # Deactivate
        account.is_active = False
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert found.is_active is False

    def test_update_scopes(self, db_session):
        """Test updating OAuth scopes."""
        account = GoogleAccount(
            email="scopes@gmail.com",
            credentials_encrypted="token",
            scopes=["gmail.readonly"],
        )
        db_session.add(account)
        db_session.flush()

        # Add calendar scope
        account.scopes = ["gmail.readonly", "calendar.readonly"]
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert "calendar.readonly" in found.scopes
        assert len(found.scopes) == 2


class TestGoogleAccountDelete:
    """Test GoogleAccount delete operations."""

    def test_delete_account(self, db_session):
        """Test deleting a Google account."""
        account = GoogleAccount(
            email="delete@gmail.com",
            credentials_encrypted="token",
        )
        db_session.add(account)
        db_session.flush()
        account_id = account.id

        # Delete
        db_session.delete(account)
        db_session.flush()

        # Verify deletion
        found = db_session.query(GoogleAccount).filter_by(id=account_id).first()
        assert found is None


class TestEncryptedCredentialsField:
    """Test the encrypted credentials field behavior.

    These tests verify that the credentials_encrypted field can store
    and retrieve encrypted data correctly. The actual encryption/decryption
    will be handled by the EncryptionService (Task 3A.1.2).
    """

    def test_store_long_encrypted_data(self, db_session):
        """Test storing long encrypted data (tokens can be lengthy)."""
        # Simulate a long encrypted token (Fernet produces ~200+ char output)
        long_encrypted_data = "gAAAAAB" + "x" * 500  # Simulated Fernet output

        account = GoogleAccount(
            email="longdata@gmail.com",
            credentials_encrypted=long_encrypted_data,
        )
        db_session.add(account)
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert found.credentials_encrypted == long_encrypted_data
        assert len(found.credentials_encrypted) == 507

    def test_store_base64_like_data(self, db_session):
        """Test storing base64-encoded encrypted data (Fernet format)."""
        # Fernet tokens are base64 encoded
        base64_data = "gAAAAABh7Xt_N8K2L3M4O5P6Q7R8S9T0U1V2W3X4Y5Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2A3B4C5D6E7F8G9H0I1J2K3L4M5N6O7P8Q9R0S1T2U3V4W5X6Y7Z8"

        account = GoogleAccount(
            email="base64@gmail.com",
            credentials_encrypted=base64_data,
        )
        db_session.add(account)
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert found.credentials_encrypted == base64_data

    def test_credentials_roundtrip_simulation(self, db_session):
        """Test simulating encrypt/decrypt roundtrip for credentials.

        This simulates what will happen when EncryptionService is used:
        1. Plain credentials come in
        2. They get encrypted before storage
        3. On read, they get decrypted
        """
        # Simulate encryption (in real code, EncryptionService.encrypt() does this)
        original_token = '{"access_token": "ya29.xxx", "refresh_token": "1//xxx"}'
        encrypted_token = f"ENCRYPTED:{original_token}:ENCRYPTED"  # Simplified simulation

        account = GoogleAccount(
            email="roundtrip@gmail.com",
            credentials_encrypted=encrypted_token,
        )
        db_session.add(account)
        db_session.flush()

        # Read back
        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()

        # Simulate decryption (in real code, EncryptionService.decrypt() does this)
        decrypted = found.credentials_encrypted.replace("ENCRYPTED:", "").replace(":ENCRYPTED", "")

        assert decrypted == original_token

    def test_special_characters_in_encrypted_data(self, db_session):
        """Test that special characters are preserved in encrypted field."""
        # Encrypted data might contain various characters
        special_data = "abc123!@#$%^&*()_+-=[]{}|;':\",./<>?"

        account = GoogleAccount(
            email="special@gmail.com",
            credentials_encrypted=special_data,
        )
        db_session.add(account)
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert found.credentials_encrypted == special_data


class TestScopesArrayField:
    """Test the PostgreSQL ARRAY field for scopes."""

    def test_empty_scopes(self, db_session):
        """Test account with empty scopes array."""
        account = GoogleAccount(
            email="empty_scopes@gmail.com",
            credentials_encrypted="token",
            scopes=[],
        )
        db_session.add(account)
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert found.scopes == []

    def test_multiple_scopes(self, db_session):
        """Test account with multiple scopes."""
        scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
        ]
        account = GoogleAccount(
            email="multi_scopes@gmail.com",
            credentials_encrypted="token",
            scopes=scopes,
        )
        db_session.add(account)
        db_session.flush()

        found = db_session.query(GoogleAccount).filter_by(id=account.id).first()
        assert len(found.scopes) == 3
        assert "https://www.googleapis.com/auth/gmail.readonly" in found.scopes


class TestCredentialsEncryptionIntegration:
    """Test GoogleAccount encryption helper methods.

    These tests verify the set_credentials(), get_credentials(), and
    create_with_credentials() methods work correctly with real encryption.
    """

    def test_set_credentials_encrypts_data(self, db_session):
        """Test that set_credentials encrypts the data."""
        account = GoogleAccount(
            email="encrypt_set@gmail.com",
            credentials_encrypted="placeholder",  # Will be replaced
        )
        db_session.add(account)
        db_session.flush()

        credentials = {
            "access_token": "ya29.test_token",
            "refresh_token": "1//test_refresh",
        }
        account.set_credentials(credentials)

        # The stored data should be encrypted (not plaintext)
        assert "ya29.test_token" not in account.credentials_encrypted
        assert "refresh_token" not in account.credentials_encrypted

    def test_get_credentials_decrypts_data(self, db_session):
        """Test that get_credentials returns decrypted data."""
        account = GoogleAccount(
            email="encrypt_get@gmail.com",
            credentials_encrypted="placeholder",
        )
        db_session.add(account)
        db_session.flush()

        original_credentials = {
            "access_token": "ya29.test_token",
            "refresh_token": "1//test_refresh",
            "scopes": ["gmail.readonly"],
        }
        account.set_credentials(original_credentials)

        # Get credentials should return the original data
        retrieved = account.get_credentials()
        assert retrieved == original_credentials
        assert retrieved["access_token"] == "ya29.test_token"
        assert retrieved["refresh_token"] == "1//test_refresh"

    def test_credentials_roundtrip_with_db(self, db_session):
        """Test full roundtrip: encrypt, save to DB, load, decrypt."""
        credentials = {
            "access_token": "ya29.roundtrip_token",
            "refresh_token": "1//roundtrip_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
        }

        # Create and save
        account = GoogleAccount(
            email="roundtrip_db@gmail.com",
            credentials_encrypted="placeholder",
        )
        account.set_credentials(credentials)
        db_session.add(account)
        db_session.flush()
        account_id = account.id

        # Load from DB (fresh query)
        db_session.expire(account)
        loaded = db_session.query(GoogleAccount).filter_by(id=account_id).first()

        # Decrypt and verify
        decrypted = loaded.get_credentials()
        assert decrypted == credentials

    def test_create_with_credentials_factory(self, db_session):
        """Test the create_with_credentials factory method."""
        credentials = {
            "access_token": "ya29.factory_token",
            "refresh_token": "1//factory_refresh",
        }

        account = GoogleAccount.create_with_credentials(
            email="factory@gmail.com",
            credentials=credentials,
            display_name="Factory Test",
            scopes=["gmail.readonly", "calendar.readonly"],
        )
        db_session.add(account)
        db_session.flush()

        # Verify the account was created correctly
        assert account.email == "factory@gmail.com"
        assert account.display_name == "Factory Test"
        assert account.scopes == ["gmail.readonly", "calendar.readonly"]

        # Verify credentials can be decrypted
        decrypted = account.get_credentials()
        assert decrypted == credentials

    def test_create_with_credentials_minimal(self, db_session):
        """Test create_with_credentials with minimal arguments."""
        credentials = {"refresh_token": "1//minimal"}

        account = GoogleAccount.create_with_credentials(
            email="minimal_factory@gmail.com",
            credentials=credentials,
        )
        db_session.add(account)
        db_session.flush()

        assert account.display_name is None
        assert account.scopes is None
        assert account.get_credentials() == credentials

    def test_update_credentials_re_encrypts(self, db_session):
        """Test that updating credentials re-encrypts properly."""
        original = {"refresh_token": "original_token"}
        updated = {"refresh_token": "updated_token", "new_field": "value"}

        account = GoogleAccount.create_with_credentials(
            email="update_creds@gmail.com",
            credentials=original,
        )
        db_session.add(account)
        db_session.flush()

        # Update credentials
        account.set_credentials(updated)
        db_session.flush()

        # Verify new credentials
        decrypted = account.get_credentials()
        assert decrypted == updated
        assert decrypted["refresh_token"] == "updated_token"
        assert decrypted["new_field"] == "value"

    def test_complex_credentials_structure(self, db_session):
        """Test with realistic Google OAuth credential structure."""
        credentials = {
            "token": "ya29.a0AfB_byC1234567890",
            "refresh_token": "1//0g1234567890-abcdefg",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "123456789.apps.googleusercontent.com",
            "client_secret": "GOCSPX-abcdefg123456",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/calendar.readonly",
            ],
            "expiry": "2024-12-08T12:00:00.000000Z",
            "universe_domain": "googleapis.com",
        }

        account = GoogleAccount.create_with_credentials(
            email="complex@gmail.com",
            credentials=credentials,
        )
        db_session.add(account)
        db_session.flush()

        # Verify all fields preserved
        decrypted = account.get_credentials()
        assert decrypted["token"] == credentials["token"]
        assert decrypted["refresh_token"] == credentials["refresh_token"]
        assert decrypted["scopes"] == credentials["scopes"]
        assert decrypted["expiry"] == credentials["expiry"]
