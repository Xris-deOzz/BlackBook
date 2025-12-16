"""
ImportHistory model for tracking file import operations.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ImportSource(str, enum.Enum):
    """Source of the imported data."""

    linkedin = "linkedin"
    google_contacts = "google_contacts"
    csv = "csv"
    other = "other"


class ImportStatus(str, enum.Enum):
    """Status of the import operation."""

    success = "success"
    partial = "partial"
    failed = "failed"


class ImportHistory(Base):
    """
    Records history of file imports (LinkedIn CSV, etc.).

    Tracks upload date, filename, statistics, and optionally stores
    the original file for reference.
    """

    __tablename__ = "import_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source: Mapped[ImportSource] = mapped_column(
        Enum(ImportSource),
        nullable=False,
        comment="Source of the import (linkedin, google_contacts, csv, etc.)",
    )
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus),
        default=ImportStatus.success,
        comment="Status of the import operation",
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original name of the uploaded file",
    )
    stored_filename: Mapped[str | None] = mapped_column(
        String(255),
        comment="Name of the stored file on disk (UUID-based)",
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        comment="Size of the uploaded file in bytes",
    )
    # Import statistics
    records_parsed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of records parsed from the file",
    )
    records_created: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of new records created",
    )
    records_updated: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of existing records updated",
    )
    records_skipped: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of records skipped (duplicates, errors)",
    )
    organizations_created: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of organizations created during import",
    )
    # Error tracking
    error_message: Mapped[str | None] = mapped_column(
        Text,
        comment="Error message if import failed",
    )
    # Timestamps
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        comment="When the import was performed",
    )

    def __repr__(self) -> str:
        return f"<ImportHistory(source={self.source.value}, file={self.original_filename!r}, status={self.status.value})>"

    @property
    def records_matched(self) -> int:
        """Total records that matched existing data (updated + skipped)."""
        return self.records_updated + self.records_skipped

    @property
    def total_processed(self) -> int:
        """Total records processed (created + updated + skipped)."""
        return self.records_created + self.records_updated + self.records_skipped
