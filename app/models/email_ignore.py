"""
EmailIgnoreList model for filtering out unwanted email addresses and domains.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    String,
    DateTime,
    Enum,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IgnorePatternType(str, PyEnum):
    """Type of ignore pattern."""

    email = "email"    # Full email address or pattern like "noreply@*"
    domain = "domain"  # Domain name like "mailchimp.com"


class EmailIgnoreList(Base):
    """
    Email/domain ignore list for filtering Gmail search results.

    Patterns can be:
    - Full email addresses: "newsletter@company.com"
    - Email patterns with wildcard: "noreply@*"
    - Domain names: "mailchimp.com"
    """

    __tablename__ = "email_ignore_list"
    __table_args__ = (
        CheckConstraint(
            "pattern_type IN ('email', 'domain')",
            name="ck_email_ignore_list_pattern_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    pattern: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    pattern_type: Mapped[IgnorePatternType] = mapped_column(
        Enum(IgnorePatternType, name="ignore_pattern_type", create_type=False),
        nullable=False,
    )  # Enum created in migration
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<EmailIgnoreList(pattern={self.pattern!r}, type={self.pattern_type.value})>"

    def matches(self, email: str) -> bool:
        """
        Check if an email address matches this ignore pattern.

        Args:
            email: The email address to check

        Returns:
            True if the email should be ignored
        """
        email_lower = email.lower()

        if self.pattern_type == IgnorePatternType.domain:
            # Domain match: check if email ends with @domain
            return email_lower.endswith(f"@{self.pattern.lower()}")

        elif self.pattern_type == IgnorePatternType.email:
            pattern_lower = self.pattern.lower()
            if "*" in pattern_lower:
                # Wildcard pattern like "noreply@*"
                # Split on * and check prefix
                prefix = pattern_lower.split("*")[0]
                return email_lower.startswith(prefix)
            else:
                # Exact email match
                return email_lower == pattern_lower

        return False
