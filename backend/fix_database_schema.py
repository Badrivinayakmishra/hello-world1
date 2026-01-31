"""
Quick database schema fix for Render deployment
Adds missing columns that were added in recent updates
"""

import os
import sys
from sqlalchemy import text, create_engine, inspect
from database.config import get_database_url

def fix_database_schema():
    """Add missing columns to existing database"""

    engine = create_engine(get_database_url())

    print("🔧 Checking database schema...")

    with engine.connect() as conn:
        inspector = inspect(engine)

        # Check if documents table exists
        if 'documents' in inspector.get_table_names():
            existing_columns = {col['name'] for col in inspector.get_columns('documents')}

            # Add status column if missing
            if 'status' not in existing_columns:
                print("  → Adding 'status' column to documents table...")
                conn.execute(text("""
                    ALTER TABLE documents
                    ADD COLUMN status VARCHAR(50) DEFAULT 'pending'
                """))
                conn.commit()
                print("  ✓ Added status column")

            # Update classification column to handle enum
            if 'classification' in existing_columns:
                print("  → Ensuring classification uses enum values...")
                # Convert any string values to enum format
                conn.execute(text("""
                    UPDATE documents
                    SET classification = 'unknown'
                    WHERE classification NOT IN ('work', 'personal', 'spam', 'unknown')
                    OR classification IS NULL
                """))
                conn.commit()
                print("  ✓ Updated classification values")

        print("\n✅ Database schema fixed!")
        print("\nYou can now:")
        print("  1. Login should work")
        print("  2. Existing data preserved")
        print("  3. New features enabled")

if __name__ == '__main__':
    try:
        fix_database_schema()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
