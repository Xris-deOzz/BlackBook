"""
AffiliationType model - lookup table for employment/affiliation types.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AffiliationType(Base):
    """
    Lookup table for affiliation types.

    System types: Employee, Former Employee, Advisor, Investor,
    Board Member, Consultant, Founder, Co-Founder, Intern, Contractor

    Users can add custom types (is_system=False).
    """

    __tablename__ = "affiliation_types"
    __table_args__ = (
        UniqueConstraint("name", name="uq_affiliation_types_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<AffiliationType(name={self.name!r}, system={self.is_system})>"
