#!/usr/bin/env python3
"""
Sync tag subcategories from Synology to local database.

This script connects to both databases and copies subcategory values
from Synology tags to matching local tags (matched by name).

Usage:
    python scripts/sync_tag_subcategories.py

Environment variables needed:
    LOCAL_DB_URL - Local database URL (defaults to docker)
    SYNOLOGY_DB_HOST - Synology database host
    SYNOLOGY_DB_PORT - Synology database port (default 5433)
    SYNOLOGY_DB_USER - Synology database user
    SYNOLOGY_DB_PASSWORD - Synology database password
    SYNOLOGY_DB_NAME - Synology database name
"""

import os
import sys
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor


def get_local_connection():
    """Connect to local Docker PostgreSQL."""
    return psycopg2.connect(
        host=os.getenv("LOCAL_DB_HOST", "localhost"),
        port=os.getenv("LOCAL_DB_PORT", "5432"),
        user=os.getenv("LOCAL_DB_USER", "blackbook"),
        password=os.getenv("LOCAL_DB_PASSWORD", "changeme"),
        database=os.getenv("LOCAL_DB_NAME", "perunsblackbook"),
    )


def get_synology_connection():
    """Connect to Synology PostgreSQL."""
    host = os.getenv("SYNOLOGY_DB_HOST")
    if not host:
        raise ValueError("SYNOLOGY_DB_HOST environment variable required")

    return psycopg2.connect(
        host=host,
        port=os.getenv("SYNOLOGY_DB_PORT", "5433"),
        user=os.getenv("SYNOLOGY_DB_USER", "blackbook"),
        password=os.getenv("SYNOLOGY_DB_PASSWORD"),
        database=os.getenv("SYNOLOGY_DB_NAME", "perunsblackbook"),
    )


def fetch_synology_tags(conn) -> dict:
    """Fetch all tags with subcategories from Synology."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT name, subcategory, category
            FROM tags
            WHERE subcategory IS NOT NULL AND subcategory != ''
        """)
        rows = cur.fetchall()

    # Return as dict: name -> {subcategory, category}
    return {row["name"]: {"subcategory": row["subcategory"], "category": row["category"]} for row in rows}


def update_local_tags(conn, synology_tags: dict) -> tuple[int, int]:
    """Update local tags with subcategories from Synology."""
    updated = 0
    not_found = 0

    with conn.cursor() as cur:
        for tag_name, data in synology_tags.items():
            cur.execute("""
                UPDATE tags
                SET subcategory = %s, category = %s
                WHERE name = %s AND (subcategory IS NULL OR subcategory = '')
            """, (data["subcategory"], data["category"], tag_name))

            if cur.rowcount > 0:
                updated += 1
                print(f"  Updated: {tag_name} -> subcategory='{data['subcategory']}'")
            else:
                # Check if tag exists
                cur.execute("SELECT name FROM tags WHERE name = %s", (tag_name,))
                if cur.fetchone():
                    print(f"  Skipped: {tag_name} (already has subcategory)")
                else:
                    not_found += 1
                    print(f"  Not found locally: {tag_name}")

    conn.commit()
    return updated, not_found


def main():
    print("=" * 60)
    print("Tag Subcategory Sync: Synology -> Local")
    print("=" * 60)

    # Connect to Synology
    print("\n1. Connecting to Synology database...")
    try:
        syn_conn = get_synology_connection()
        print("   Connected!")
    except Exception as e:
        print(f"   ERROR: Could not connect to Synology: {e}")
        print("\n   Make sure these environment variables are set:")
        print("     SYNOLOGY_DB_HOST (required)")
        print("     SYNOLOGY_DB_PASSWORD (required)")
        print("     SYNOLOGY_DB_PORT (default: 5433)")
        print("     SYNOLOGY_DB_USER (default: blackbook)")
        print("     SYNOLOGY_DB_NAME (default: perunsblackbook)")
        sys.exit(1)

    # Connect to local
    print("\n2. Connecting to local database...")
    try:
        local_conn = get_local_connection()
        print("   Connected!")
    except Exception as e:
        print(f"   ERROR: Could not connect to local database: {e}")
        syn_conn.close()
        sys.exit(1)

    # Fetch Synology tags
    print("\n3. Fetching tags with subcategories from Synology...")
    synology_tags = fetch_synology_tags(syn_conn)
    print(f"   Found {len(synology_tags)} tags with subcategories")

    if not synology_tags:
        print("\n   No tags with subcategories found on Synology.")
        syn_conn.close()
        local_conn.close()
        return

    # Update local tags
    print("\n4. Updating local tags...")
    updated, not_found = update_local_tags(local_conn, synology_tags)

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Tags updated: {updated}")
    print(f"  Tags not found locally: {not_found}")
    print(f"  Tags skipped (already had subcategory): {len(synology_tags) - updated - not_found}")
    print("=" * 60)

    # Cleanup
    syn_conn.close()
    local_conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
