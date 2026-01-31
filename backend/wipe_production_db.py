#!/usr/bin/env python3
"""
Wipe production database on Render
This script connects to your PostgreSQL database and Pinecone index to wipe all data
while preserving the schema structure.

Usage on Render:
1. Go to your backend service shell
2. Run: python wipe_production_db.py
"""

import os
import sys
from typing import List


def wipe_postgres():
    """Wipe all data from PostgreSQL database"""
    print("\n" + "=" * 60)
    print("WIPING POSTGRESQL DATABASE")
    print("=" * 60)

    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        print("⚠️  psycopg2 not installed - trying psycopg2-binary...")
        try:
            import psycopg2
            from psycopg2 import sql
        except ImportError:
            print("✗ psycopg2 not available - cannot wipe PostgreSQL")
            print("  Install with: pip install psycopg2-binary")
            return

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("✗ DATABASE_URL not set - cannot connect to database")
        return

    print(f"📊 Connecting to database...")

    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # Disable foreign key checks
        cursor.execute("SET session_replication_role = 'replica';")

        # Get all table names
        cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
        """)
        tables = cursor.fetchall()

        print(f"Found {len(tables)} tables")

        # Delete all rows from each table
        total_deleted = 0
        for (table_name,) in tables:
            try:
                cursor.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table_name)))
                deleted = cursor.rowcount
                total_deleted += deleted
                print(f"  ✓ {table_name}: {deleted} rows deleted")
            except Exception as e:
                print(f"  ✗ {table_name}: {e}")

        # Re-enable foreign key checks
        cursor.execute("SET session_replication_role = 'origin';")

        # Commit changes
        conn.commit()
        cursor.close()
        conn.close()

        print(f"\n✅ PostgreSQL wiped: {total_deleted} total rows deleted")

    except Exception as e:
        print(f"✗ Error wiping PostgreSQL: {e}")
        import traceback
        traceback.print_exc()


def wipe_pinecone():
    """Wipe all vectors from Pinecone index"""
    print("\n" + "=" * 60)
    print("WIPING PINECONE VECTOR STORE")
    print("=" * 60)

    try:
        from pinecone import Pinecone
    except ImportError:
        print("⚠️  Pinecone library not installed")
        print("  Install with: pip install pinecone-client")
        return

    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("⚠️  PINECONE_API_KEY not set - skipping Pinecone wipe")
        return

    try:
        pc = Pinecone(api_key=api_key)
        index_name = os.getenv("PINECONE_INDEX_NAME", "2nd-brain-index")

        print(f"📊 Connecting to index: {index_name}")

        # Check if index exists
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]

        if index_name not in index_names:
            print(f"⚠️  Index '{index_name}' does not exist")
            return

        index = pc.Index(index_name)

        # Get stats
        stats = index.describe_index_stats()
        total = stats.total_vector_count

        print(f"Found {total:,} vectors")

        if total == 0:
            print("✅ Pinecone index is already empty")
            return

        # Delete all vectors
        print("🗑️  Deleting all vectors...")

        # Get namespaces
        namespaces = stats.namespaces if hasattr(stats, 'namespaces') else {}

        if not namespaces:
            # No namespaces, delete all in default
            index.delete(delete_all=True)
            print("  ✓ Deleted all vectors in default namespace")
        else:
            # Delete by namespace
            for namespace in namespaces.keys():
                count = namespaces[namespace].vector_count
                print(f"  🗑️  Deleting {count:,} vectors from namespace: {namespace}")
                index.delete(delete_all=True, namespace=namespace)

        # Verify
        stats_after = index.describe_index_stats()
        print(f"\n✅ Pinecone wiped: {total:,} → {stats_after.total_vector_count} vectors")

    except Exception as e:
        print(f"✗ Error wiping Pinecone: {e}")
        import traceback
        traceback.print_exc()


def wipe_redis():
    """Wipe Redis cache if available"""
    print("\n" + "=" * 60)
    print("WIPING REDIS CACHE")
    print("=" * 60)

    try:
        import redis
    except ImportError:
        print("⚠️  Redis library not installed - skipping")
        return

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("⚠️  REDIS_URL not set - skipping")
        return

    try:
        r = redis.from_url(redis_url)
        db_size = r.dbsize()

        if db_size == 0:
            print("✅ Redis is already empty")
            return

        print(f"Found {db_size} keys")
        r.flushdb()

        print(f"✅ Redis wiped: {db_size} keys deleted")

    except Exception as e:
        print(f"⚠️  Could not wipe Redis: {e}")


def main():
    print("=" * 60)
    print("PRODUCTION DATABASE WIPE UTILITY")
    print("=" * 60)
    print("\n⚠️  WARNING: This will DELETE ALL DATA from:")
    print("  - PostgreSQL database (all tables)")
    print("  - Pinecone vector index (all embeddings)")
    print("  - Redis cache (all keys)")
    print("\nThe schema structure will be preserved.")
    print("\nYou will need to:")
    print("  1. Create new user accounts")
    print("  2. Reconnect integrations (Gmail, Slack, Box)")
    print("  3. Re-sync all data")

    response = input("\n⚠️  Type 'WIPE' to confirm deletion: ")

    if response != "WIPE":
        print("\n❌ Cancelled - no data was deleted")
        return

    # Wipe PostgreSQL
    wipe_postgres()

    # Wipe Pinecone
    wipe_pinecone()

    # Wipe Redis
    wipe_redis()

    print("\n" + "=" * 60)
    print("✅ ALL DATABASES WIPED SUCCESSFULLY")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Go to https://twondbrain-frontend.onrender.com")
    print("  2. Sign up with a new account")
    print("  3. Connect your integrations")
    print("  4. Start syncing fresh data")


if __name__ == "__main__":
    main()
