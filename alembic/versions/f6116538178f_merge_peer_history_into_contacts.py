"""merge_peer_history_into_contacts

Revision ID: f6116538178f
Revises: l1h89i0j2k34
Create Date: 2025-12-08 17:55:46.711925

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6116538178f'
down_revision: Union[str, Sequence[str], None] = 'l1h89i0j2k34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Merge all peer_history relationships into contact_at relationships.

    Logic:
    1. For each peer_history record, check if a contact_at record already exists
       for the same person_id + organization_id combination
    2. If a contact_at exists with is_current=True, delete the peer_history record
    3. If a contact_at exists with is_current=False but peer_history has is_current=True,
       update the contact_at to is_current=True and delete peer_history
    4. If no contact_at exists, update the peer_history record to contact_at
    5. Handle duplicates by preferring is_current=True records
    """
    conn = op.get_bind()

    # Step 1: Delete peer_history records where a contact_at already exists
    # with is_current=True for the same person/org combo
    conn.execute(sa.text("""
        DELETE FROM person_organizations ph
        WHERE ph.relationship = 'peer_history'
        AND EXISTS (
            SELECT 1 FROM person_organizations ca
            WHERE ca.relationship = 'contact_at'
            AND ca.person_id = ph.person_id
            AND ca.organization_id = ph.organization_id
            AND ca.is_current = TRUE
        )
    """))

    # Step 2: For remaining peer_history where contact_at exists but is_current=False,
    # and peer_history has is_current=True, update contact_at and delete peer_history
    conn.execute(sa.text("""
        UPDATE person_organizations ca
        SET is_current = TRUE
        FROM person_organizations ph
        WHERE ca.relationship = 'contact_at'
        AND ph.relationship = 'peer_history'
        AND ca.person_id = ph.person_id
        AND ca.organization_id = ph.organization_id
        AND ca.is_current = FALSE
        AND ph.is_current = TRUE
    """))

    # Delete those peer_history records we just used to update contact_at
    conn.execute(sa.text("""
        DELETE FROM person_organizations ph
        WHERE ph.relationship = 'peer_history'
        AND EXISTS (
            SELECT 1 FROM person_organizations ca
            WHERE ca.relationship = 'contact_at'
            AND ca.person_id = ph.person_id
            AND ca.organization_id = ph.organization_id
        )
    """))

    # Step 3: For remaining peer_history (no matching contact_at exists),
    # simply convert them to contact_at
    conn.execute(sa.text("""
        UPDATE person_organizations
        SET relationship = 'contact_at'
        WHERE relationship = 'peer_history'
    """))


def downgrade() -> None:
    """
    Cannot reliably downgrade since we lost information about which
    records were originally peer_history vs contact_at.
    """
    pass
