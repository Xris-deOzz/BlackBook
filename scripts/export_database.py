"""
Export BlackBook PostgreSQL database for migration to Synology.
Uses Python/SQLAlchemy - no pg_dump needed.

Run with: python scripts/export_database.py
"""

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_database_url():
    """Build database URL from environment variables."""
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "perunsblackbook")
    user = os.getenv("DB_USER", "blackbook")
    password = os.getenv("DB_PASSWORD", "")

    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def format_pg_value(val):
    """Format a Python value for PostgreSQL INSERT statement."""
    if val is None:
        return "NULL"
    elif isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, UUID):
        return f"'{val}'"
    elif isinstance(val, (datetime, date)):
        return f"'{val.isoformat()}'"
    elif isinstance(val, (dict, list)):
        # JSON/JSONB fields - use proper JSON format
        json_str = json.dumps(val).replace("'", "''")
        return f"'{json_str}'"
    else:
        # String - escape single quotes and handle special chars
        str_val = str(val).replace("'", "''")
        return f"'{str_val}'"


# Tables in dependency order (parent tables first, children last)
# This ensures TRUNCATE CASCADE doesn't wipe out data we need
TABLE_ORDER = [
    # Lookup/reference tables first (no foreign keys to other tables)
    "settings",
    "tags",
    "affiliation_types",
    "relationship_types",
    "organization_categories",
    "organization_types",
    "ai_providers",
    "email_ignore_list",

    # Core entity tables
    "organizations",
    "persons",
    "google_accounts",

    # Junction and dependent tables
    "organization_tags",
    "organization_offices",
    "organization_relationships",
    "organization_relationship_status",
    "person_tags",
    "person_emails",
    "person_phones",
    "person_websites",
    "person_addresses",
    "person_education",
    "person_employment",
    "person_organizations",
    "person_relationships",
    "interactions",
    "saved_views",
    "import_logs",
    "import_history",
    "duplicate_exclusions",
    "pending_contacts",

    # AI tables
    "ai_api_keys",
    "ai_conversations",
    "ai_messages",
    "ai_data_access_settings",
    "ai_suggestions",
    "ai_quick_prompts",
    "record_snapshots",

    # Email/Calendar tables
    "email_cache",
    "email_sync_state",
    "email_messages",
    "email_person_links",
    "calendar_settings",
    "calendar_events",
    "investment_profile_options",
]


def export_database():
    """Export database to SQL file."""

    print("\n" + "=" * 50)
    print("  BlackBook Database Export (Python)")
    print("=" * 50 + "\n")

    # Create backup directory
    backup_dir = Path(__file__).parent.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"blackbook_export_{timestamp}.sql"

    print("Connecting to database...")

    try:
        engine = create_engine(get_database_url())

        with engine.connect() as conn:
            # Test connection
            conn.execute(text("SELECT 1"))
            print("Connected successfully!\n")

            # Get all table names from database
            inspector = inspect(engine)
            db_tables = set(inspector.get_table_names())

            # Skip alembic_version - not needed for fresh install
            db_tables.discard("alembic_version")

            # Order tables: known order first, then any unknown tables
            tables = [t for t in TABLE_ORDER if t in db_tables]
            unknown_tables = db_tables - set(TABLE_ORDER)
            if unknown_tables:
                print(f"Note: Found tables not in ORDER list: {unknown_tables}")
                tables.extend(sorted(unknown_tables))

            print(f"Found {len(tables)} tables to export:")
            for t in tables:
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                print(f"  - {t}: {count} rows")

            print(f"\nExporting to: {backup_file}\n")

            with open(backup_file, 'w', encoding='utf-8') as f:
                # Write header
                f.write(f"-- BlackBook Database Export\n")
                f.write(f"-- Exported: {datetime.now().isoformat()}\n")
                f.write(f"-- Tables: {len(tables)}\n")
                f.write("-- \n\n")

                # Disable foreign key checks during import
                f.write("SET session_replication_role = 'replica';\n\n")

                # First, TRUNCATE all tables in REVERSE order (children first)
                f.write("-- Truncate tables in reverse dependency order\n")
                for table in reversed(tables):
                    f.write(f'TRUNCATE TABLE "{table}" CASCADE;\n')
                f.write("\n")

                # Then INSERT data in forward order (parents first)
                for table in tables:
                    print(f"Exporting {table}...")

                    # Get column info
                    columns = inspector.get_columns(table)
                    col_names = [c['name'] for c in columns]
                    col_names_quoted = [f'"{c}"' for c in col_names]

                    f.write(f'-- Table: {table}\n')

                    # Get all rows
                    result = conn.execute(text(f'SELECT * FROM "{table}"'))
                    rows = result.fetchall()

                    if rows:
                        f.write(f'INSERT INTO "{table}" ({", ".join(col_names_quoted)}) VALUES\n')

                        values_list = []
                        for row in rows:
                            values = [format_pg_value(val) for val in row]
                            values_list.append(f"({', '.join(values)})")

                        f.write(',\n'.join(values_list))
                        f.write(';\n')

                    f.write('\n')

                # Re-enable foreign key checks
                f.write("SET session_replication_role = 'origin';\n")

            print("\n" + "=" * 50)
            print("  Export Complete!")
            print("=" * 50)
            print(f"\nBackup file: {backup_file}")
            print(f"File size: {backup_file.stat().st_size / 1024:.1f} KB")
            print("\nNext steps:")
            print("1. Copy this file to your Synology NAS")
            print("2. Place it in /volume1/docker/blackbook/backups/")
            print("3. Run: sudo docker exec -i blackbook-db psql -U blackbook -d perunsblackbook < backups/your_export.sql")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        print("\nMake sure:")
        print("1. PostgreSQL is running")
        print("2. Your .env file has correct database credentials")
        sys.exit(1)


if __name__ == "__main__":
    export_database()
