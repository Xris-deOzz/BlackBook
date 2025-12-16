"""seed_email_ignore_patterns

Revision ID: g6c34d5e7f89
Revises: f5b23c4d6e78
Create Date: 2025-12-08 09:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'g6c34d5e7f89'
down_revision: Union[str, Sequence[str], None] = 'f5b23c4d6e78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default ignore patterns as specified in CLAUDE_CODE_CONTEXT.md
DEFAULT_IGNORE_PATTERNS = [
    # Marketing/Newsletter domains
    ("mailchimp.com", "domain"),
    ("sendgrid.net", "domain"),
    ("mailgun.org", "domain"),
    ("amazonses.com", "domain"),
    ("postmarkapp.com", "domain"),
    ("constantcontact.com", "domain"),
    ("hubspot.com", "domain"),
    ("salesforce.com", "domain"),
    ("marketo.com", "domain"),
    # Email patterns (wildcard patterns using * prefix match)
    ("noreply@*", "email"),
    ("no-reply@*", "email"),
    ("donotreply@*", "email"),
    ("notifications@*", "email"),
    ("updates@*", "email"),
    ("newsletter@*", "email"),
    ("mailer-daemon@*", "email"),
]


def upgrade() -> None:
    """Seed default email ignore patterns."""
    # Build values for bulk insert
    for pattern, pattern_type in DEFAULT_IGNORE_PATTERNS:
        op.execute(
            sa.text("""
                INSERT INTO email_ignore_list (id, pattern, pattern_type, created_at)
                VALUES (gen_random_uuid(), :pattern, :pattern_type, NOW())
                ON CONFLICT (pattern) DO NOTHING
            """).bindparams(pattern=pattern, pattern_type=pattern_type)
        )


def downgrade() -> None:
    """Remove seeded default patterns."""
    patterns = [p[0] for p in DEFAULT_IGNORE_PATTERNS]
    op.execute(
        sa.text("""
            DELETE FROM email_ignore_list
            WHERE pattern = ANY(:patterns)
        """).bindparams(patterns=patterns)
    )
