"""
Embedding Service - Centralized Document Embedding for Multi-tenant RAG

Handles:
- Document embedding to Pinecone during sync
- Document embedding during "Complete Process"
- Deduplication (skip already embedded documents)
- Tenant isolation

Updated 2025-12-09:
- Increased chunk size to 2000 chars (better context preservation)
- Increased overlap to 400 chars (better continuity between chunks)
- All document content is now fully embedded (no truncation)
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from database.models import Document, Tenant
from vector_stores.pinecone_store import get_vector_store, PineconeVectorStore

# Chunking configuration - 2000 chars with 400 overlap for optimal RAG
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 400


def utc_now():
    return datetime.now(timezone.utc)


class EmbeddingService:
    """
    Centralized service for embedding documents to Pinecone.

    Features:
    - Automatic chunking and embedding
    - Deduplication (tracks embedded_at timestamp)
    - Multi-tenant isolation via Pinecone namespaces
    - Progress callbacks for UI updates
    """

    def __init__(self, vector_store: Optional[PineconeVectorStore] = None):
        """
        Initialize embedding service.

        Args:
            vector_store: Optional PineconeVectorStore instance (creates one if not provided)
        """
        self._vector_store = vector_store

    @property
    def vector_store(self) -> PineconeVectorStore:
        """Lazy initialization of vector store"""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    def embed_documents(
        self,
        documents: List[Document],
        tenant_id: str,
        db: Session,
        force_reembed: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        Embed documents to Pinecone.

        Args:
            documents: List of Document model instances
            tenant_id: Tenant ID for isolation
            db: Database session for updating embedded_at
            force_reembed: If True, re-embed even if already embedded
            progress_callback: Optional callback(current, total, status) for progress updates

        Returns:
            Dict with embedding stats
        """
        if not documents:
            return {
                'success': True,
                'total': 0,
                'embedded': 0,
                'skipped': 0,
                'errors': []
            }

        # Filter documents that need embedding
        docs_to_embed = []
        skipped = 0
        skipped_no_content = 0
        skipped_already_embedded = 0

        for doc in documents:
            if not doc.content:
                skipped += 1
                skipped_no_content += 1
                print(f"[EmbeddingService] Skipping doc {doc.id} ({doc.title}): No content")
                continue

            if not force_reembed and doc.embedded_at:
                skipped += 1
                skipped_already_embedded += 1
                print(f"[EmbeddingService] Skipping doc {doc.id} ({doc.title}): Already embedded at {doc.embedded_at}")
                continue

            docs_to_embed.append(doc)

        print(f"[EmbeddingService] Filtered: {len(docs_to_embed)} to embed, {skipped_no_content} without content, {skipped_already_embedded} already embedded")

        if not docs_to_embed:
            print(f"[EmbeddingService] No documents to embed after filtering")
            return {
                'success': True,
                'total': len(documents),
                'embedded': 0,
                'skipped': skipped,
                'errors': []
            }

        print(f"[EmbeddingService] Embedding {len(docs_to_embed)} documents for tenant {tenant_id}")

        # Convert to format expected by PineconeVectorStore
        pinecone_docs = []
        for doc in docs_to_embed:
            pinecone_docs.append({
                'id': str(doc.id),
                'content': doc.content,
                'title': doc.title or '',
                'metadata': {
                    'source_type': doc.source_type or '',
                    'external_id': doc.external_id or '',
                    'sender': doc.sender or '',
                    'classification': doc.classification.value if doc.classification else 'unknown',
                    'created_at': doc.source_created_at.isoformat() if doc.source_created_at else ''
                }
            })

        # Embed to Pinecone with explicit chunking params
        try:
            result = self.vector_store.embed_and_upsert_documents(
                documents=pinecone_docs,
                tenant_id=tenant_id,
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                show_progress=True
            )

            # Update embedded_at for successfully embedded documents
            if result.get('success') or result.get('upserted', 0) > 0:
                now = utc_now()
                embedding_model = os.getenv('AZURE_EMBEDDING_DEPLOYMENT', 'text-embedding-3-large')

                for doc in docs_to_embed:
                    doc.embedded_at = now
                    doc.embedding_generated = True
                    doc.embedding_model = embedding_model

                db.commit()
                print(f"[EmbeddingService] Updated embedded_at for {len(docs_to_embed)} documents")

            return {
                'success': result.get('success', False),
                'total': len(documents),
                'embedded': result.get('upserted', 0),
                'chunks': result.get('total_chunks', 0),
                'skipped': skipped,
                'errors': result.get('errors', []),
                'namespace': result.get('namespace', tenant_id)
            }

        except Exception as e:
            print(f"[EmbeddingService] Error embedding documents: {e}")
            return {
                'success': False,
                'total': len(documents),
                'embedded': 0,
                'skipped': skipped,
                'errors': [str(e)]
            }

    def embed_tenant_documents(
        self,
        tenant_id: str,
        db: Session,
        only_confirmed: bool = False,
        force_reembed: bool = False
    ) -> Dict:
        """
        Embed all documents for a tenant.

        Args:
            tenant_id: Tenant ID
            db: Database session
            only_confirmed: If True, only embed user-confirmed documents
            force_reembed: If True, re-embed all documents

        Returns:
            Dict with embedding stats
        """
        # Query documents
        query = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted == False,
            Document.content != None,
            Document.content != ''
        )

        if only_confirmed:
            query = query.filter(Document.user_confirmed == True)

        if not force_reembed:
            query = query.filter(Document.embedded_at == None)

        documents = query.all()

        print(f"[EmbeddingService] Found {len(documents)} documents to embed for tenant {tenant_id}")

        if not documents:
            return {
                'success': True,
                'total': 0,
                'embedded': 0,
                'skipped': 0,
                'errors': [],
                'message': 'No documents to embed'
            }

        return self.embed_documents(
            documents=documents,
            tenant_id=tenant_id,
            db=db,
            force_reembed=force_reembed
        )

    def delete_document_embeddings(
        self,
        document_ids: List[str],
        tenant_id: str,
        db: Session
    ) -> Dict:
        """
        Delete embeddings for specific documents.

        Args:
            document_ids: List of document IDs to delete
            tenant_id: Tenant ID
            db: Database session

        Returns:
            Dict with deletion stats
        """
        try:
            success = self.vector_store.delete_documents(
                doc_ids=document_ids,
                tenant_id=tenant_id
            )

            if success:
                # Update database to clear embedded_at
                db.query(Document).filter(
                    Document.id.in_(document_ids),
                    Document.tenant_id == tenant_id
                ).update({
                    'embedded_at': None,
                    'embedding_generated': False
                }, synchronize_session=False)
                db.commit()

            return {
                'success': success,
                'deleted': len(document_ids) if success else 0
            }

        except Exception as e:
            print(f"[EmbeddingService] Error deleting embeddings: {e}")
            return {
                'success': False,
                'deleted': 0,
                'error': str(e)
            }

    def delete_tenant_embeddings(self, tenant_id: str, db: Session) -> Dict:
        """
        Delete all embeddings for a tenant (for account deletion).

        Args:
            tenant_id: Tenant ID
            db: Database session

        Returns:
            Dict with deletion stats
        """
        try:
            success = self.vector_store.delete_tenant_data(tenant_id)

            if success:
                # Clear embedded_at for all tenant documents
                db.query(Document).filter(
                    Document.tenant_id == tenant_id
                ).update({
                    'embedded_at': None,
                    'embedding_generated': False
                }, synchronize_session=False)
                db.commit()

            return {
                'success': success,
                'tenant_id': tenant_id
            }

        except Exception as e:
            print(f"[EmbeddingService] Error deleting tenant embeddings: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_embedding_stats(self, tenant_id: str, db: Session) -> Dict:
        """
        Get embedding statistics for a tenant.

        Args:
            tenant_id: Tenant ID
            db: Database session

        Returns:
            Dict with stats
        """
        total_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted == False
        ).count()

        embedded_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted == False,
            Document.embedded_at != None
        ).count()

        pinecone_stats = self.vector_store.get_stats(tenant_id)

        return {
            'total_documents': total_docs,
            'embedded_documents': embedded_docs,
            'pending_documents': total_docs - embedded_docs,
            'pinecone_vectors': pinecone_stats.get('vector_count', 0),
            'namespace': tenant_id
        }


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create singleton EmbeddingService instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
