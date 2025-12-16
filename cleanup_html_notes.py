"""
Standalone script to strip HTML from interaction notes.
Run with: python cleanup_html_notes.py
"""

import re
from app.database import engine
from sqlalchemy import text


def strip_html_tags(t):
    """Remove HTML tags from text and clean up whitespace."""
    if not t:
        return t
    t = re.sub(r'<p[^>]*>', '', t)
    t = re.sub(r'</p>', '\n', t)
    t = re.sub(r'<br\s*/?>', '\n', t)
    t = t.replace('&nbsp;', ' ')
    t = t.replace('&amp;', '&')
    t = t.replace('&lt;', '<')
    t = t.replace('&gt;', '>')
    t = t.replace('&quot;', '"')
    t = t.replace('&#39;', "'")
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    lines = [line.strip() for line in t.split('\n')]
    t = '\n'.join(lines)
    return t.strip()


def main():
    print("Cleaning HTML from interaction notes...")
    
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, notes FROM interactions WHERE notes IS NOT NULL AND notes != ''")
        ).fetchall()
        
        count = 0
        for row in rows:
            interaction_id = row[0]
            original_notes = row[1]
            
            if '<' in original_notes or '&' in original_notes:
                cleaned = strip_html_tags(original_notes)
                if cleaned != original_notes:
                    conn.execute(
                        text("UPDATE interactions SET notes = :notes WHERE id = :id"),
                        {"notes": cleaned, "id": interaction_id}
                    )
                    count += 1
        
        conn.commit()
        print(f"Cleaned HTML from {count} interaction notes")


if __name__ == "__main__":
    main()
