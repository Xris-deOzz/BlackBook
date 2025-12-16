"""Strip HTML from interaction notes

Revision ID: z5v23w4x6y78
Revises: y4u12v3w5x67
Create Date: 2025-12-16
Description: Cleans up HTML tags (like <p>, </p>, etc.) from interaction notes field.
             This is a data migration - no schema changes.
"""

import re
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'z5v23w4x6y78'
down_revision = 'y4u12v3w5x67'
branch_labels = None
depends_on = None


def strip_html_tags(text: str) -> str:
    """
    Remove HTML tags from text and clean up whitespace.
    
    Handles:
    - <p> and </p> tags (convert to line breaks)
    - <br> and <br/> tags (convert to line breaks)
    - <strong>, <em>, <b>, <i> tags (strip but keep content)
    - &nbsp; entities (convert to spaces)
    - Other HTML entities
    - Multiple consecutive newlines (collapse to max 2)
    """
    if not text:
        return text
    
    # Replace <p> tags with newlines
    text = re.sub(r'<p[^>]*>', '', text)
    text = re.sub(r'</p>', '\n', text)
    
    # Replace <br> tags with newlines
    text = re.sub(r'<br\s*/?>', '\n', text)
    
    # Replace common HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    
    # Strip remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Collapse multiple newlines to max 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Strip leading/trailing whitespace from each line, then overall
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    text = text.strip()
    
    return text


def upgrade() -> None:
    """Clean HTML from all interaction notes."""
    # Get database connection
    conn = op.get_bind()
    
    # Fetch all interactions with notes
    result = conn.execute(
        sa.text("SELECT id, notes FROM interactions WHERE notes IS NOT NULL AND notes != ''")
    )
    rows = result.fetchall()
    
    updated_count = 0
    for row in rows:
        interaction_id = row[0]
        original_notes = row[1]
        
        # Check if notes contain HTML
        if '<' in original_notes or '&' in original_notes:
            cleaned_notes = strip_html_tags(original_notes)
            
            # Only update if actually changed
            if cleaned_notes != original_notes:
                conn.execute(
                    sa.text("UPDATE interactions SET notes = :notes WHERE id = :id"),
                    {"notes": cleaned_notes, "id": interaction_id}
                )
                updated_count += 1
    
    print(f"Cleaned HTML from {updated_count} interaction notes")


def downgrade() -> None:
    """
    No downgrade - this is a data cleanup migration.
    The original HTML content cannot be restored.
    """
    pass
