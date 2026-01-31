#!/usr/bin/env python3
"""
Simple database wipe - delete all rows while preserving schema
"""

import os
import sqlite3
import sys


def wipe_sqlite_db(db_path):
    """Wipe all data from SQLite database"""
    if not os.path.exists(db_path):
        print(f"⚠️  Database not found: {db_path}")
        return

    print(f"\n📂 Wiping: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Disable foreign keys temporarily
        cursor.execute("PRAGMA foreign_keys = OFF")

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()

        print(f"Found {len(tables)} tables")

        # Delete all rows from each table
        for (table_name,) in tables:
            try:
                cursor.execute(f"DELETE FROM {table_name}")
                deleted_count = cursor.rowcount
                print(f"  ✓ {table_name}: {deleted_count} rows deleted")
            except Exception as e:
                print(f"  ✗ {table_name}: {e}")

        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Commit changes
        conn.commit()
        conn.close()

        print(f"✅ Successfully wiped: {db_path}")

    except Exception as e:
        print(f"✗ Error: {e}")


def wipe_pinecone():
    """Wipe Pinecone index"""
    print("\n🔍 Checking Pinecone...")

    try:
        from pinecone import Pinecone

        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            print("⚠️  PINECONE_API_KEY not set - skipping")
            return

        pc = Pinecone(api_key=api_key)
        index_name = os.getenv("PINECONE_INDEX_NAME", "2nd-brain-index")

        # Check if index exists
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]

        if index_name not in index_names:
            print(f"⚠️  Index '{index_name}' does not exist")
            return

        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        total = stats.total_vector_count

        print(f"📊 Found {total:,} vectors")

        if total == 0:
            print("✅ Already empty")
            return

        # Delete all
        print("🗑️  Deleting all vectors...")
        index.delete(delete_all=True)

        # Check again
        stats_after = index.describe_index_stats()
        print(f"✅ Wiped: {total:,} → {stats_after.total_vector_count} vectors")

    except ImportError:
        print("⚠️  Pinecone not installed - skipping")
    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    print("=" * 60)
    print("DATABASE WIPE UTILITY")
    print("=" * 60)
    print("\n⚠️  WARNING: This will DELETE ALL DATA")
    print()

    response = input("Type 'YES' to confirm: ")

    if response != "YES":
        print("\n❌ Cancelled")
        return

    # Find and wipe all .db files in backend
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    db_files = [
        os.path.join(backend_dir, "2nd_brain.db"),
        os.path.join(backend_dir, "knowledge_vault.db"),
        os.path.join(backend_dir, "data", "secondbrain.db")
    ]

    for db_path in db_files:
        wipe_sqlite_db(db_path)

    # Wipe Pinecone
    wipe_pinecone()

    print("\n" + "=" * 60)
    print("✅ WIPE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
