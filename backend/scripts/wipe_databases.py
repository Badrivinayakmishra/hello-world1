#!/usr/bin/env python3
"""
Wipe all databases (SQLite + Pinecone) while preserving schema
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from database.config import get_database_url
from database.models import Base, engine
from vector_stores.pinecone_store import PineconeVectorStore
from pinecone import Pinecone


def wipe_sqlite():
    """Delete all rows from all tables but preserve schema"""
    print("\n=== Wiping SQLite Database ===")
    print(f"Database URL: {get_database_url()}")

    # Get all table names
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"Found {len(tables)} tables: {tables}")

    with engine.connect() as conn:
        # Disable foreign key constraints temporarily
        conn.execute(text("PRAGMA foreign_keys = OFF;"))
        conn.commit()

        # Delete all rows from each table
        for table in tables:
            try:
                result = conn.execute(text(f"DELETE FROM {table};"))
                conn.commit()
                print(f"  ✓ Wiped table: {table} ({result.rowcount} rows deleted)")
            except Exception as e:
                print(f"  ✗ Error wiping {table}: {e}")

        # Re-enable foreign key constraints
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        conn.commit()

    print("✅ SQLite database wiped successfully")


def wipe_pinecone():
    """Delete all vectors from Pinecone index"""
    print("\n=== Wiping Pinecone Vector Store ===")

    try:
        # Get Pinecone API key from environment
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            print("⚠️  PINECONE_API_KEY not set - skipping Pinecone wipe")
            return

        # Initialize Pinecone
        pc = Pinecone(api_key=api_key)

        # Get index name from environment or use default
        index_name = os.getenv("PINECONE_INDEX_NAME", "2nd-brain-index")

        print(f"Index name: {index_name}")

        # Check if index exists
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]

        if index_name not in index_names:
            print(f"⚠️  Index '{index_name}' does not exist - nothing to wipe")
            return

        # Get index
        index = pc.Index(index_name)

        # Get stats before deletion
        stats = index.describe_index_stats()
        total_vectors = stats.total_vector_count

        print(f"Found {total_vectors:,} vectors in index")

        if total_vectors == 0:
            print("✅ Pinecone index is already empty")
            return

        # Delete all vectors by namespace
        namespaces = stats.namespaces

        if not namespaces:
            # If no namespaces, delete all in default namespace
            print("  Deleting all vectors in default namespace...")
            index.delete(delete_all=True)
        else:
            # Delete by namespace
            for namespace in namespaces.keys():
                vector_count = namespaces[namespace].vector_count
                print(f"  Deleting {vector_count:,} vectors from namespace: {namespace}")
                index.delete(delete_all=True, namespace=namespace)

        # Verify deletion
        stats_after = index.describe_index_stats()
        print(f"✅ Pinecone wiped: {total_vectors:,} → {stats_after.total_vector_count} vectors")

    except Exception as e:
        print(f"✗ Error wiping Pinecone: {e}")
        print(f"  Error type: {type(e).__name__}")


def main():
    print("=" * 60)
    print("DATABASE WIPE UTILITY")
    print("=" * 60)
    print("\n⚠️  WARNING: This will DELETE ALL DATA from:")
    print("  - SQLite database (all tables)")
    print("  - Pinecone vector index (all embeddings)")
    print("\nThe schema structure will be preserved.")

    response = input("\nAre you sure you want to continue? (type 'YES' to confirm): ")

    if response != "YES":
        print("\n❌ Cancelled - no data was deleted")
        return

    # Wipe SQLite
    wipe_sqlite()

    # Wipe Pinecone
    wipe_pinecone()

    print("\n" + "=" * 60)
    print("✅ ALL DATABASES WIPED SUCCESSFULLY")
    print("=" * 60)
    print("\nYou can now:")
    print("  1. Create a new user account")
    print("  2. Connect integrations")
    print("  3. Sync fresh data")


if __name__ == "__main__":
    main()
