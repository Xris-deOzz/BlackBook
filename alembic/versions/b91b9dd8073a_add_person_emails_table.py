"""add_person_emails_table

Revision ID: b91b9dd8073a
Revises:
Create Date: 2025-12-08 07:44:54.412454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b91b9dd8073a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create person_emails table for storing multiple email addresses per person."""
    # Create the email_label enum type first
    op.execute("CREATE TYPE email_label AS ENUM ('work', 'personal', 'other')")

    # Create the person_emails table
    op.create_table('person_emails',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('label', postgresql.ENUM('work', 'personal', 'other', name='email_label', create_type=False), nullable=True, server_default='work'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('person_id', 'email', name='uq_person_emails_person_email')
    )
    op.create_index('idx_person_emails_email', 'person_emails', ['email'], unique=False)
    op.create_index('idx_person_emails_person_id', 'person_emails', ['person_id'], unique=False)


def downgrade() -> None:
    """Drop person_emails table."""
    op.drop_index('idx_person_emails_person_id', table_name='person_emails')
    op.drop_index('idx_person_emails_email', table_name='person_emails')
    op.drop_table('person_emails')

    # Drop the enum type
    op.execute("DROP TYPE email_label")
