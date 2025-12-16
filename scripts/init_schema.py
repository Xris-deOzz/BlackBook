"""
Initialize database schema from SQLAlchemy models.
Creates all tables defined in the models.

Run with: python scripts/init_schema.py
Or inside Docker: python -c "exec(open('scripts/init_schema.py').read())"
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def init_schema():
    """Create all database tables from SQLAlchemy models."""

    print("\n" + "=" * 50)
    print("  BlackBook Database Schema Initialization")
    print("=" * 50 + "\n")

    try:
        # Import Base and all models (this registers them with Base)
        from app.models.base import Base
        from app.models import *  # noqa: F401, F403 - imports all models
        from app.database import engine

        print("Creating all tables from SQLAlchemy models...")
        print(f"Database: {engine.url}")
        print()

        # Create all tables
        Base.metadata.create_all(bind=engine)

        # List created tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  - {table}")

        print("\n" + "=" * 50)
        print("  Schema initialization complete!")
        print("=" * 50)
        print("\nYou can now import your data.")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    init_schema()
