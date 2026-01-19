#!/usr/bin/env python3
"""
Cleanup Script for Orphaned Pinecone Embeddings

This script identifies and removes embeddings from Pinecone that no longer
have corresponding documents in the database. This can happen when:
1. Documents were deleted before the Pinecone cascade was implemented
2. Database operations failed after Pinecone upsert
3. Manual database cleanup was performed

Usage:
    python scripts/cleanup_orphaned_embeddings.py [--tenant-id TENANT_ID] [--dry-run]

Options:
    --tenant-id     Clean up specific tenant (default: all tenants)
    --dry-run       Report orphans without deleting
"""

import os
import sys
import argparse
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, Document, Tenant, DeletedDocument
from vector_stores.pinecone_store import get_vector_store
from services.embedding_service import get_embedding_service


def utc_now():
    return datetime.now(timezone.utc)


def get_all_tenants(db):
    """Get all active tenants"""
    return db.query(Tenant).filter(Tenant.is_active == True).all()


def get_embedded_document_ids(db, tenant_id: str):
    """Get all document IDs that are currently embedded (should exist in Pinecone)"""
    docs = db.query(Document.id).filter(
        Document.tenant_id == tenant_id,
        Document.embedded_at != None,
        Document.is_deleted == False
    ).all()
    return set(d[0] for d in docs)


def get_deleted_document_ids(db, tenant_id: str):
    """Get all document IDs that were deleted (should NOT exist in Pinecone)"""
    # From deleted_documents tracking table
    deleted = db.query(DeletedDocument).filter(
        DeletedDocument.tenant_id == tenant_id
    ).all()

    # Also check for soft-deleted documents that still have embedded_at set
    soft_deleted = db.query(Document.id).filter(
        Document.tenant_id == tenant_id,
        Document.is_deleted == True,
        Document.embedded_at != None
    ).all()

    deleted_ids = set()

    # Note: deleted_documents tracks external_ids, not internal doc IDs
    # We need to find any documents marked as embedded but now deleted
    for doc in soft_deleted:
        deleted_ids.add(doc[0])

    return deleted_ids


def get_all_embedded_including_deleted(db, tenant_id: str):
    """Get document IDs that were embedded (regardless of deletion status)"""
    # This finds documents that have embedded_at set but are now deleted
    # These are the orphans we need to clean up
    docs = db.query(Document.id).filter(
        Document.tenant_id == tenant_id,
        Document.embedded_at != None
    ).all()
    return set(d[0] for d in docs)


def cleanup_tenant(db, vector_store, tenant_id: str, dry_run: bool = False):
    """Clean up orphaned embeddings for a single tenant"""
    print(f"\n{'='*60}")
    print(f"Processing tenant: {tenant_id}")
    print(f"{'='*60}")

    # Get current Pinecone stats for tenant
    try:
        stats = vector_store.get_stats(tenant_id)
        print(f"Pinecone vectors in namespace: {stats.get('vector_count', 'N/A')}")
    except Exception as e:
        print(f"Warning: Could not get Pinecone stats: {e}")

    # Strategy 1: Find soft-deleted documents that still have embeddings
    soft_deleted_with_embeddings = db.query(Document).filter(
        Document.tenant_id == tenant_id,
        Document.is_deleted == True,
        Document.embedded_at != None
    ).all()

    orphan_doc_ids = [doc.id for doc in soft_deleted_with_embeddings]

    print(f"\nOrphaned embeddings found: {len(orphan_doc_ids)}")

    if orphan_doc_ids:
        print("\nOrphaned documents:")
        for i, doc in enumerate(soft_deleted_with_embeddings[:10]):
            print(f"  {i+1}. {doc.id[:8]}... - {doc.title or 'Untitled'} (deleted at: {doc.deleted_at})")
        if len(soft_deleted_with_embeddings) > 10:
            print(f"  ... and {len(soft_deleted_with_embeddings) - 10} more")

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(orphan_doc_ids)} document embeddings from Pinecone")
        return {"tenant_id": tenant_id, "orphans_found": len(orphan_doc_ids), "deleted": 0}

    # Delete orphaned embeddings from Pinecone
    deleted_count = 0
    if orphan_doc_ids:
        try:
            success = vector_store.delete_documents(
                doc_ids=orphan_doc_ids,
                tenant_id=tenant_id
            )
            if success:
                deleted_count = len(orphan_doc_ids)
                print(f"\n✓ Deleted {deleted_count} orphaned embeddings from Pinecone")

                # Clear the embedded_at flag since embeddings are now deleted
                for doc in soft_deleted_with_embeddings:
                    doc.embedded_at = None
                    doc.embedding_generated = False
                db.commit()
                print(f"✓ Updated database records")
            else:
                print(f"\n✗ Failed to delete embeddings from Pinecone")
        except Exception as e:
            print(f"\n✗ Error deleting embeddings: {e}")

    return {
        "tenant_id": tenant_id,
        "orphans_found": len(orphan_doc_ids),
        "deleted": deleted_count
    }


def main():
    parser = argparse.ArgumentParser(
        description="Clean up orphaned Pinecone embeddings"
    )
    parser.add_argument(
        "--tenant-id",
        help="Clean up specific tenant (default: all tenants)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report orphans without deleting"
    )
    args = parser.parse_args()

    print("="*60)
    print("Pinecone Orphan Embedding Cleanup")
    print(f"Started: {utc_now().isoformat()}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("="*60)

    # Initialize services
    db = SessionLocal()
    try:
        vector_store = get_vector_store()
    except Exception as e:
        print(f"Error initializing Pinecone: {e}")
        print("Make sure PINECONE_API_KEY is set")
        return 1

    results = []

    try:
        if args.tenant_id:
            # Process single tenant
            result = cleanup_tenant(db, vector_store, args.tenant_id, args.dry_run)
            results.append(result)
        else:
            # Process all tenants
            tenants = get_all_tenants(db)
            print(f"\nFound {len(tenants)} active tenants")

            for tenant in tenants:
                result = cleanup_tenant(db, vector_store, tenant.id, args.dry_run)
                results.append(result)

    finally:
        db.close()

    # Summary
    print("\n" + "="*60)
    print("CLEANUP SUMMARY")
    print("="*60)

    total_orphans = sum(r["orphans_found"] for r in results)
    total_deleted = sum(r["deleted"] for r in results)

    print(f"Tenants processed: {len(results)}")
    print(f"Total orphans found: {total_orphans}")
    print(f"Total deleted: {total_deleted}")

    if args.dry_run and total_orphans > 0:
        print(f"\nRun without --dry-run to delete orphaned embeddings")

    print(f"\nCompleted: {utc_now().isoformat()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
