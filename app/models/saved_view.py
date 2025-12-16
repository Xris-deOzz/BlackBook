"""
SavedView and ImportLog models for application state tracking.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, Boolean, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SavedView(Base):
    """Saved view configuration for Airtable-like filtering."""

    __tablename__ = "saved_views"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'person' or 'organization'
    filters: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        default=dict,
    )
    sort_by: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[str] = mapped_column(String(10), default="asc")
    columns: Mapped[list[Any] | None] = mapped_column(
        JSONB,
        default=list,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<SavedView(name={self.name!r}, type={self.entity_type})>"


class ImportLog(Base):
    """Import run tracking for debugging/auditing."""

    __tablename__ = "import_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    import_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    source_file: Mapped[str | None] = mapped_column(String(200))
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_imported: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[Any] | None] = mapped_column(
        JSONB,
        default=list,
    )
    warnings: Mapped[list[Any] | None] = mapped_column(
        JSONB,
        default=list,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<ImportLog(date={self.import_date}, file={self.source_file!r})>"
