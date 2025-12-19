"""
Generate complete database schema from SQLAlchemy models.
Run this once to initialize a fresh database.
"""
import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text
from app.models.base import Base
from app.core.config import settings

# Import ALL models to register them with Base.metadata
from app.models.person import Person
from app.models.organization import Organization
from app.models.tag import Tag
from app.models.interaction import Interaction
from app.models.person_email import PersonEmail
from app.models.google_account import GoogleAccount
from app.models.email_ignore import EmailIgnoreList
from app.models.email_cache import EmailCache
from app.models.calendar_event import CalendarEvent
from app.models.calendar_settings import CalendarSettings
from app.models.pending_contact import PendingContact
from app.models.ai_conversation import AIConversation
from app.models.ai_message import AIMessage
from app.models.ai_suggestion import AISuggestion
from app.models.ai_quick_prompt import AIQuickPrompt
from app.models.organization_category import OrganizationCategory
from app.models.organization_type_lookup import OrganizationType
from app.models.relationship_type import RelationshipType
from app.models.setting import Setting
from app.models.saved_view import SavedView
from app.models.import_history import ImportHistory
from app.models.duplicate_exclusion import DuplicateExclusion
from app.models.email_message import EmailMessage
from app.models.email_person_link import EmailPersonLink
from app.models.email_sync_state import EmailSyncState
from app.models.person_address import PersonAddress
from app.models.person_phone import PersonPhone
from app.models.person_employment import PersonEmployment
from app.models.person_education import PersonEducation
from app.models.person_website import PersonWebsite
from app.models.investment_profile_option import InvestmentProfileOption
from app.models.ai_provider import AIProvider
from app.models.ai_api_key import AIApiKey

# Try to import additional models if they exist
try:
    from app.models.person_organization import PersonOrganization
except ImportError:
    pass

try:
    from app.models.organization_person import OrganizationPerson
except ImportError:
    pass

try:
    from app.models.contact_sync_state import ContactSyncState
    from app.models.sync_conflict_log import SyncConflictLog
    from app.models.sync_audit_log import SyncAuditLog
except ImportError:
    pass

def create_schema():
    """Create all tables from SQLAlchemy models."""
    engine = create_engine(settings.database_url, echo=True)
    
    # Create extension first
    with engine.connect() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Schema created successfully!")

if __name__ == "__main__":
    create_schema()
