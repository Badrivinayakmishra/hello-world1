"""
Embedding Tasks
Background tasks for generating embeddings and updating vector store.
"""

from celery_app import celery
from database.models import get_db
from services.embedding_service import EmbeddingService


@celery.task(bind=True, name='tasks.embedding_tasks.generate_embeddings')
def generate_embeddings_task(self, tenant_id: str, document_ids: list = None):
    """
    Background task for generating embeddings for documents.

    Args:
        tenant_id: Tenant ID
        document_ids: Optional list of specific document IDs to embed

    Returns:
        dict: Embedding results
    """
    db = next(get_db())

    try:
        self.update_progress(0, 100, 'Starting embedding generation...')

        service = EmbeddingService(db)

        # Progress callback
        def on_progress(current, total, message):
            self.update_progress(current, total, message)

        # Generate embeddings
        if document_ids:
            result = service.generate_embeddings_for_documents(
                document_ids=document_ids,
                tenant_id=tenant_id,
                progress_callback=on_progress
            )
        else:
            result = service.generate_all_embeddings(
                tenant_id=tenant_id,
                progress_callback=on_progress
            )

        self.update_progress(100, 100, 'Embeddings generated successfully')

        return {
            'success': True,
            'tenant_id': tenant_id,
            'documents_embedded': result.get('documents_embedded', 0),
            'chunks_created': result.get('chunks_created', 0),
            'errors': result.get('errors', [])
        }

    except Exception as e:
        print(f"[EmbeddingTask] Error: {e}", flush=True)

        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )

        raise

    finally:
        db.close()
