"""migrate_person_emails_data

Revision ID: f5b23c4d6e78
Revises: e4a12b3c5d67
Create Date: 2025-12-08 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5b23c4d6e78'
down_revision: Union[str, Sequence[str], None] = 'e4a12b3c5d67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate existing person.email values to person_emails table.

    This migration:
    1. Copies each person's email to person_emails table
    2. Sets the label to 'work' (most common in professional CRM)
    3. Marks each as primary since they're the only email for that person
    4. Handles multi-value emails separated by commas/semicolons/newlines
    """
    # Execute raw SQL for data migration
    op.execute("""
        WITH split_emails AS (
            SELECT
                p.id AS person_id,
                TRIM(unnest(string_to_array(
                    regexp_replace(p.email, '[;\n\r]+', ',', 'g'),
                    ','
                ))) AS email
            FROM persons p
            WHERE p.email IS NOT NULL
              AND p.email != ''
        ),
        clean_emails AS (
            SELECT
                person_id,
                email
            FROM split_emails
            WHERE email IS NOT NULL
              AND email != ''
              AND email ~ '@'  -- Basic validation: must contain @
        ),
        ranked_emails AS (
            SELECT
                person_id,
                email,
                ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY email) AS rn
            FROM clean_emails
        )
        INSERT INTO person_emails (id, person_id, email, label, is_primary, created_at)
        SELECT
            gen_random_uuid(),
            person_id,
            email,
            'work',
            (rn = 1),  -- First email is primary
            NOW()
        FROM ranked_emails
        ON CONFLICT (person_id, email) DO NOTHING;
    """)


def downgrade() -> None:
    """Remove migrated person_emails entries.

    Note: This only removes entries that were created with 'work' label
    and doesn't restore the original persons.email field.
    """
    # We can't perfectly undo this, but we can clear the table
    # and let the original email field remain as source of truth
    op.execute("""
        DELETE FROM person_emails
        WHERE label = 'work'
          AND is_primary = true;
    """)
