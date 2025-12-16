"""Person Page Redesign - Phase A Database Schema

Revision ID: o4k12l3m5n67
Revises: n3j01k2l4m56
Create Date: 2025-12-09

Phase A: Database schema changes for Person Page Redesign
- person_websites: Multiple websites per person (max 3)
- person_addresses: Home/Work addresses (max 2)
- person_education: Education history (max 6)
- affiliation_types: Lookup table for employment affiliations
- person_employment: Employment/affiliation history (max 10)
- relationship_types: Lookup table for person relationships
- person_relationships: Person-to-person relationships (bidirectional)
- Drops status and priority columns from persons
- Removes Active/Priority tags
- Migrates existing website data
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'o4k12l3m5n67'
down_revision: Union[str, None] = 'n3j01k2l4m56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create new tables for Person Page Redesign."""

    # ==========================================================
    # 1. Create person_websites table
    # ==========================================================
    op.create_table(
        'person_websites',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_person_websites_person_id', 'person_websites', ['person_id'], unique=False)

    # ==========================================================
    # 2. Create person_addresses table
    # ==========================================================
    op.create_table(
        'person_addresses',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('address_type', sa.String(length=20), nullable=False),
        sa.Column('street', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('zip', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('person_id', 'address_type', name='uq_person_addresses_person_type')
    )
    op.create_index('idx_person_addresses_person_id', 'person_addresses', ['person_id'], unique=False)

    # ==========================================================
    # 3. Create person_education table
    # ==========================================================
    op.create_table(
        'person_education',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('school_name', sa.String(length=255), nullable=False),
        sa.Column('degree_type', sa.String(length=50), nullable=True),
        sa.Column('field_of_study', sa.String(length=255), nullable=True),
        sa.Column('graduation_year', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_person_education_person_id', 'person_education', ['person_id'], unique=False)

    # ==========================================================
    # 4. Create affiliation_types lookup table
    # ==========================================================
    op.create_table(
        'affiliation_types',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_affiliation_types_name')
    )

    # Seed default affiliation types
    op.execute("""
        INSERT INTO affiliation_types (id, name, is_system, created_at) VALUES
            (gen_random_uuid(), 'Employee', true, now()),
            (gen_random_uuid(), 'Former Employee', true, now()),
            (gen_random_uuid(), 'Advisor', true, now()),
            (gen_random_uuid(), 'Investor', true, now()),
            (gen_random_uuid(), 'Board Member', true, now()),
            (gen_random_uuid(), 'Consultant', true, now()),
            (gen_random_uuid(), 'Founder', true, now()),
            (gen_random_uuid(), 'Co-Founder', true, now()),
            (gen_random_uuid(), 'Intern', true, now()),
            (gen_random_uuid(), 'Contractor', true, now())
    """)

    # ==========================================================
    # 5. Create person_employment table
    # ==========================================================
    op.create_table(
        'person_employment',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('organization_name', sa.String(length=255), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('affiliation_type_id', sa.UUID(), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['affiliation_type_id'], ['affiliation_types.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_person_employment_person_id', 'person_employment', ['person_id'], unique=False)
    op.create_index('idx_person_employment_org_id', 'person_employment', ['organization_id'], unique=False)

    # ==========================================================
    # 6. Create relationship_types lookup table
    # ==========================================================
    op.create_table(
        'relationship_types',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('inverse_name', sa.String(length=100), nullable=True),
        sa.Column('requires_organization', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_relationship_types_name')
    )

    # Seed default relationship types
    op.execute("""
        INSERT INTO relationship_types (id, name, inverse_name, requires_organization, is_system, created_at) VALUES
            (gen_random_uuid(), 'Worked Together', 'Worked Together', true, true, now()),
            (gen_random_uuid(), 'Introduced By', 'Introduced To', false, true, now()),
            (gen_random_uuid(), 'Introduced To', 'Introduced By', false, true, now()),
            (gen_random_uuid(), 'Family Member', 'Family Member', false, true, now()),
            (gen_random_uuid(), 'College Classmate', 'College Classmate', false, true, now()),
            (gen_random_uuid(), 'Reports To', 'Manages', false, true, now()),
            (gen_random_uuid(), 'Manages', 'Reports To', false, true, now()),
            (gen_random_uuid(), 'Other', 'Other', false, true, now())
    """)

    # ==========================================================
    # 7. Create person_relationships table
    # ==========================================================
    op.create_table(
        'person_relationships',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('related_person_id', sa.UUID(), nullable=False),
        sa.Column('relationship_type_id', sa.UUID(), nullable=True),
        sa.Column('context_organization_id', sa.UUID(), nullable=True),
        sa.Column('context_text', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['related_person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['relationship_type_id'], ['relationship_types.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['context_organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('person_id', 'related_person_id', 'relationship_type_id', name='uq_person_relationships_unique')
    )
    op.create_index('idx_person_relationships_person_id', 'person_relationships', ['person_id'], unique=False)
    op.create_index('idx_person_relationships_related_id', 'person_relationships', ['related_person_id'], unique=False)

    # ==========================================================
    # 8. Migrate existing website data from persons to person_websites
    # ==========================================================
    # Truncate URLs to 500 chars if needed
    op.execute("""
        INSERT INTO person_websites (id, person_id, url, label, created_at, updated_at)
        SELECT gen_random_uuid(), id, LEFT(website, 500), 'Website', now(), now()
        FROM persons
        WHERE website IS NOT NULL AND website != ''
    """)

    # ==========================================================
    # 9. Remove Active and Priority tags
    # ==========================================================
    # First, remove the associations in person_tags
    op.execute("""
        DELETE FROM person_tags
        WHERE tag_id IN (SELECT id FROM tags WHERE name IN ('Active', 'Priority'))
    """)
    # Then remove the tags themselves
    op.execute("""
        DELETE FROM tags WHERE name IN ('Active', 'Priority')
    """)

    # ==========================================================
    # 10. Drop status and priority columns from persons
    # ==========================================================
    op.drop_column('persons', 'status')
    op.drop_column('persons', 'priority')

    # Drop the person_status enum type
    op.execute("DROP TYPE IF EXISTS person_status")


def downgrade() -> None:
    """Reverse all changes from Person Page Redesign."""

    # Recreate person_status enum
    op.execute("CREATE TYPE person_status AS ENUM ('active', 'inactive', 'archived')")

    # Add back status and priority columns
    op.add_column('persons', sa.Column('priority', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('persons', sa.Column('status', postgresql.ENUM('active', 'inactive', 'archived', name='person_status', create_type=False), nullable=True, server_default='active'))

    # Note: Cannot restore deleted tags or migrated website data

    # Drop tables in reverse order
    op.drop_index('idx_person_relationships_related_id', table_name='person_relationships')
    op.drop_index('idx_person_relationships_person_id', table_name='person_relationships')
    op.drop_table('person_relationships')

    op.drop_table('relationship_types')

    op.drop_index('idx_person_employment_org_id', table_name='person_employment')
    op.drop_index('idx_person_employment_person_id', table_name='person_employment')
    op.drop_table('person_employment')

    op.drop_table('affiliation_types')

    op.drop_index('idx_person_education_person_id', table_name='person_education')
    op.drop_table('person_education')

    op.drop_index('idx_person_addresses_person_id', table_name='person_addresses')
    op.drop_table('person_addresses')

    op.drop_index('idx_person_websites_person_id', table_name='person_websites')
    op.drop_table('person_websites')
