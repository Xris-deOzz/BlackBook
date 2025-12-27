"""
SQLAlchemy models for Perun's BlackBook.

All models are imported here for easy access and to ensure
they are registered with the declarative base.
"""

from app.models.base import Base
from app.models.tag import Tag, PersonTag, OrganizationTag
from app.models.tag_subcategory import TagSubcategory, DEFAULT_SUBCATEGORY_COLORS
from app.models.organization import Organization, OrgType, RelationshipType
from app.models.person import Person, PersonOrganization
from app.models.interaction import Interaction, InteractionMedium, InteractionSource
from app.models.saved_view import SavedView, ImportLog
from app.models.person_email import PersonEmail, EmailLabel
from app.models.person_phone import PersonPhone, PhoneLabel
from app.models.person_website import PersonWebsite
from app.models.person_address import PersonAddress
from app.models.person_education import PersonEducation
from app.models.person_employment import PersonEmployment
from app.models.person_relationship import PersonRelationship
from app.models.affiliation_type import AffiliationType
from app.models.org_relationship import OrganizationRelationship, OrgRelationshipType
from app.models.organization_office import OrganizationOffice, OfficeType
from app.models.organization_relationship_status import OrganizationRelationshipStatus, RelationshipWarmth
from app.models.organization_category import OrganizationCategory
from app.models.organization_type_lookup import OrganizationType, ProfileStyle
from app.models.investment_profile_option import InvestmentProfileOption, OptionType
from app.models.relationship_type import RelationshipType as PersonRelationshipType
from app.models.google_account import GoogleAccount
from app.models.person_google_link import PersonGoogleLink
from app.models.email_ignore import EmailIgnoreList, IgnorePatternType
from app.models.email_cache import EmailCache
from app.models.calendar_event import CalendarEvent
from app.models.calendar_settings import CalendarSettings, COMMON_TIMEZONES
from app.models.pending_contact import PendingContact, PendingContactStatus
from app.models.import_history import ImportHistory, ImportSource, ImportStatus
from app.models.duplicate_exclusion import DuplicateExclusion

# Tag-Google Label Sync models
from app.models.tag_google_link import TagGoogleLink, SyncDirection
from app.models.tag_sync_log import TagSyncLog

# Phase 5: AI Research Assistant models
from app.models.ai_provider import AIProvider, AIProviderType
from app.models.ai_api_key import AIAPIKey
from app.models.ai_conversation import AIConversation
from app.models.ai_message import AIMessage, AIMessageRole
from app.models.ai_data_access import AIDataAccessSettings
from app.models.ai_suggestion import AISuggestion, AISuggestionStatus
from app.models.ai_quick_prompt import AIQuickPrompt, PromptEntityType
from app.models.record_snapshot import RecordSnapshot, ChangeSource

# Phase 6: Email Inbox Integration models
from app.models.email_message import EmailMessage
from app.models.email_person_link import EmailPersonLink, EmailLinkType, EmailLinkSource
from app.models.email_sync_state import EmailSyncState, SyncStatus

# Settings
from app.models.setting import Setting

__all__ = [
    # Base
    "Base",
    # Core models
    "Person",
    "Organization",
    "Tag",
    "TagSubcategory",
    "DEFAULT_SUBCATEGORY_COLORS",
    "Interaction",
    "SavedView",
    "ImportLog",
    "PersonEmail",
    "PersonPhone",
    "PersonWebsite",
    "PersonAddress",
    "PersonEducation",
    "PersonEmployment",
    "PersonRelationship",
    "AffiliationType",
    "PersonRelationshipType",
    "GoogleAccount",
    "PersonGoogleLink",
    "EmailIgnoreList",
    "EmailCache",
    "CalendarEvent",
    "CalendarSettings",
    "COMMON_TIMEZONES",
    "PendingContact",
    "ImportHistory",
    "DuplicateExclusion",
    # Tag-Google Label Sync
    "TagGoogleLink",
    "SyncDirection",
    "TagSyncLog",
    # Junction tables
    "PersonTag",
    "OrganizationTag",
    "PersonOrganization",
    "OrganizationRelationship",
    "OrganizationOffice",
    "OrganizationRelationshipStatus",
    # Organization type system
    "OrganizationCategory",
    "OrganizationType",
    "InvestmentProfileOption",
    # Enums
    "OrgType",
    "OfficeType",
    "RelationshipWarmth",
    "RelationshipType",
    "InteractionMedium",
    "InteractionSource",
    "EmailLabel",
    "PhoneLabel",
    "IgnorePatternType",
    "PendingContactStatus",
    "ImportSource",
    "ImportStatus",
    "OrgRelationshipType",
    "ProfileStyle",
    "OptionType",
    # Phase 5: AI models
    "AIProvider",
    "AIAPIKey",
    "AIConversation",
    "AIMessage",
    "AIDataAccessSettings",
    "AISuggestion",
    "AIQuickPrompt",
    "RecordSnapshot",
    # Phase 5: AI enums
    "AIProviderType",
    "AIMessageRole",
    "AISuggestionStatus",
    "PromptEntityType",
    "ChangeSource",
    # Phase 6: Email Inbox models
    "EmailMessage",
    "EmailPersonLink",
    "EmailSyncState",
    # Phase 6: Email Inbox enums
    "EmailLinkType",
    "EmailLinkSource",
    "SyncStatus",
    # Settings
    "Setting",
]
