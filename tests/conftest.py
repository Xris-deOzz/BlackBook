"""
Pytest configuration and fixtures for Perun's BlackBook tests.
"""

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base


# Configure pytest-asyncio to use auto mode for async tests
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def engine():
    """Create database engine for testing.

    Uses the real database connection since tests will use transactions
    that are rolled back after each test.
    """
    settings = get_settings()
    engine = create_engine(settings.database_url)
    return engine


@pytest.fixture(scope="function")
def db_session(engine) -> Session:
    """Provide a database session for tests.

    Each test runs in its own transaction that is rolled back after the test,
    ensuring test isolation without affecting real data.
    """
    connection = engine.connect()
    transaction = connection.begin()

    # Create a session bound to the connection
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    # Cleanup: rollback transaction and close
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_person(db_session):
    """Create a sample person for testing relationships."""
    from app.models import Person, PersonStatus

    person = Person(
        full_name="Test Person",
        first_name="Test",
        last_name="Person",
        status=PersonStatus.active,
    )
    db_session.add(person)
    db_session.flush()  # Get the ID without committing
    return person


@pytest.fixture
def sample_google_account(db_session):
    """Create a sample Google account for testing relationships."""
    from app.models import GoogleAccount

    account = GoogleAccount(
        email="test@gmail.com",
        display_name="Test Gmail",
        credentials_encrypted="encrypted_test_token",
        scopes=["gmail.readonly"],
    )
    db_session.add(account)
    db_session.flush()
    return account
