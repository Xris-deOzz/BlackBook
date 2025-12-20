"""
Pydantic schemas for API request/response validation.
"""

from app.schemas.person_website import (
    PersonWebsiteCreate,
    PersonWebsiteUpdate,
    PersonWebsiteResponse,
)
from app.schemas.person_address import (
    PersonAddressCreate,
    PersonAddressUpdate,
    PersonAddressResponse,
)
from app.schemas.person_education import (
    PersonEducationCreate,
    PersonEducationUpdate,
    PersonEducationResponse,
)
from app.schemas.person_employment import (
    PersonEmploymentCreate,
    PersonEmploymentUpdate,
    PersonEmploymentResponse,
)
from app.schemas.person_relationship import (
    PersonRelationshipCreate,
    PersonRelationshipUpdate,
    PersonRelationshipResponse,
)
from app.schemas.affiliation_type import (
    AffiliationTypeCreate,
    AffiliationTypeResponse,
)
from app.schemas.relationship_type import (
    RelationshipTypeResponse,
)
from app.schemas.organization_office import (
    OrganizationOfficeCreate,
    OrganizationOfficeUpdate,
    OrganizationOfficeResponse,
)
from app.schemas.organization_relationship_status import (
    OrganizationRelationshipStatusCreate,
    OrganizationRelationshipStatusUpdate,
    OrganizationRelationshipStatusResponse,
)
from app.schemas.person import (
    DeleteScope,
    PersonDeleteRequest,
    PersonBulkDeleteRequest,
    DeleteResult,
    BulkDeleteResult,
)

__all__ = [
    # Websites
    "PersonWebsiteCreate",
    "PersonWebsiteUpdate",
    "PersonWebsiteResponse",
    # Addresses
    "PersonAddressCreate",
    "PersonAddressUpdate",
    "PersonAddressResponse",
    # Education
    "PersonEducationCreate",
    "PersonEducationUpdate",
    "PersonEducationResponse",
    # Employment
    "PersonEmploymentCreate",
    "PersonEmploymentUpdate",
    "PersonEmploymentResponse",
    # Relationships
    "PersonRelationshipCreate",
    "PersonRelationshipUpdate",
    "PersonRelationshipResponse",
    # Lookup tables
    "AffiliationTypeCreate",
    "AffiliationTypeResponse",
    "RelationshipTypeResponse",
    # Organization Offices
    "OrganizationOfficeCreate",
    "OrganizationOfficeUpdate",
    "OrganizationOfficeResponse",
    # Organization Relationship Status
    "OrganizationRelationshipStatusCreate",
    "OrganizationRelationshipStatusUpdate",
    "OrganizationRelationshipStatusResponse",
    # Person Delete
    "DeleteScope",
    "PersonDeleteRequest",
    "PersonBulkDeleteRequest",
    "DeleteResult",
    "BulkDeleteResult",
]
