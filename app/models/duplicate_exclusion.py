"""
Duplicate exclusion model.

Stores pairs of persons that have been marked as "not duplicates"
so they don't appear in future duplicate detection results.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.base import Base


class DuplicateExclusion(Base):
    """
    Stores pairs of persons that should not be considered duplicates.
    
    The pair is always stored with the smaller UUID as person1_id
    and the larger UUID as person2_id to ensure uniqueness.
    """
    __tablename__ = "duplicate_exclusions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    person1_id = Column(PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    person2_id = Column(PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Ensure the pair is unique regardless of order
    __table_args__ = (
        Index('ix_duplicate_exclusions_pair', 'person1_id', 'person2_id', unique=True),
    )

    @classmethod
    def make_ordered_pair(cls, id1: UUID, id2: UUID) -> tuple[UUID, UUID]:
        """Return the IDs in consistent order (smaller first) for storage."""
        if str(id1) < str(id2):
            return id1, id2
        return id2, id1
