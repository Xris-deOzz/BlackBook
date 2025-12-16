"""Merge person_organizations and organization_persons tables

Revision ID: l1h89i0j2k34
Revises: k0g78h9i1j23_add_birthday_to_persons
Create Date: 2025-12-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'l1h89i0j2k34'
down_revision: Union[str, None] = 'k0g78h9i1j23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add new values to the relationship_type enum
    # First, we need to add the new enum values
    op.execute("""
        ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'current_employee';
        ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'former_employee';
        ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'board_member';
        ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'advisor';
        ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'investor';
        ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'founder';
    """)

    # Step 2: Add person_name column to person_organizations (for unlinked references)
    op.add_column('person_organizations',
        sa.Column('person_name', sa.Text(), nullable=True)
    )

    # Step 3: Make person_id nullable in person_organizations (to support unlinked references)
    op.alter_column('person_organizations', 'person_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True
    )

    # Step 4: Migrate data from organization_persons to person_organizations
    # We need to handle duplicates carefully
    op.execute("""
        INSERT INTO person_organizations (id, person_id, organization_id, relationship, person_name, notes, created_at, is_current, role)
        SELECT
            gen_random_uuid(),
            op.person_id,
            op.organization_id,
            op.relationship,
            op.person_name,
            op.notes,
            op.created_at,
            true,
            NULL
        FROM organization_persons op
        WHERE NOT EXISTS (
            -- Skip if we already have this exact person-org-relationship combo
            SELECT 1 FROM person_organizations po
            WHERE po.person_id = op.person_id
            AND po.organization_id = op.organization_id
            AND po.relationship = op.relationship
            AND op.person_id IS NOT NULL
        )
    """)

    # Step 5: Drop the organization_persons table
    op.drop_table('organization_persons')


def downgrade() -> None:
    # Step 1: Recreate organization_persons table
    op.create_table('organization_persons',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('person_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('person_name', sa.Text(), nullable=True),
        sa.Column('relationship', postgresql.ENUM('affiliated_with', 'peer_history', 'key_person', 'connection', 'contact_at', 'current_employee', 'former_employee', 'board_member', 'advisor', 'investor', 'founder', name='relationship_type', create_type=False), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Step 2: Migrate data back (only records that look like organization_persons entries)
    op.execute("""
        INSERT INTO organization_persons (id, organization_id, person_id, person_name, relationship, notes, created_at)
        SELECT
            gen_random_uuid(),
            organization_id,
            person_id,
            person_name,
            relationship,
            notes,
            created_at
        FROM person_organizations
        WHERE relationship IN ('key_person', 'connection', 'contact_at')
        OR person_name IS NOT NULL
    """)

    # Step 3: Make person_id NOT NULL again in person_organizations
    # First delete any records with null person_id
    op.execute("""
        DELETE FROM person_organizations WHERE person_id IS NULL
    """)
    op.alter_column('person_organizations', 'person_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False
    )

    # Step 4: Remove person_name column from person_organizations
    op.drop_column('person_organizations', 'person_name')

    # Note: We cannot remove enum values in PostgreSQL easily, so we leave them
