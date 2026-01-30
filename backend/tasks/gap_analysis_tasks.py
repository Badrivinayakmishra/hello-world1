"""
Knowledge Gap Analysis Tasks
Background tasks for analyzing documents and identifying knowledge gaps.
"""

from celery_app import celery
from database.models import get_db
from services.knowledge_service import KnowledgeService


@celery.task(bind=True, name='tasks.gap_analysis_tasks.analyze_gaps')
def analyze_gaps_task(
    self,
    tenant_id: str,
    project_id: str = None,
    mode: str = 'intelligent',
    force: bool = False
):
    """
    Background task for knowledge gap analysis.

    Args:
        tenant_id: Tenant ID
        project_id: Optional project ID to analyze specific project
        mode: Analysis mode (simple, intelligent, v3, multistage, goalfirst)
        force: Force re-analysis even if recent

    Returns:
        dict: Analysis results with gaps found
    """
    db = next(get_db())

    try:
        # Update initial status
        self.update_progress(0, 100, 'Initializing gap analysis...')

        # Initialize service
        service = KnowledgeService(db)

        # Progress callback
        def on_progress(current, total, message):
            """Progress callback for gap analysis"""
            self.update_progress(current, total, message)

        # Run analysis based on mode
        if mode == 'intelligent':
            self.update_progress(10, 100, 'Running intelligent NLP-based analysis...')
            result = service.analyze_gaps_intelligent(
                tenant_id=tenant_id,
                project_id=project_id,
                max_documents=100,
                force=force
            )

        elif mode == 'v3':
            self.update_progress(10, 100, 'Running 6-stage GPT-4 analysis...')
            result = service.analyze_gaps_v3(
                tenant_id=tenant_id,
                project_id=project_id,
                force=force
            )

        elif mode == 'multistage':
            self.update_progress(10, 100, 'Running multi-stage analysis...')
            result = service.analyze_gaps_multistage(
                tenant_id=tenant_id,
                project_id=project_id,
                force=force
            )

        elif mode == 'goalfirst':
            self.update_progress(10, 100, 'Running goal-first analysis...')
            result = service.analyze_gaps_goalfirst(
                tenant_id=tenant_id,
                project_id=project_id,
                force=force
            )

        else:  # simple
            self.update_progress(10, 100, 'Running simple gap analysis...')
            result = service.analyze_gaps(
                tenant_id=tenant_id,
                project_id=project_id,
                force=force
            )

        # Update final status
        gaps_found = len(result.get('gaps', []))
        self.update_progress(100, 100, f'Analysis complete. Found {gaps_found} knowledge gaps.')

        return {
            'success': True,
            'mode': mode,
            'tenant_id': tenant_id,
            'project_id': project_id,
            'gaps_found': gaps_found,
            'gaps': result.get('gaps', []),
            'categories_found': result.get('categories_found', {}),
            'analysis_stats': result.get('context', {}).get('stats', {})
        }

    except Exception as e:
        print(f"[GapAnalysisTask] Error: {e}", flush=True)

        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'mode': mode,
                'tenant_id': tenant_id
            }
        )

        raise

    finally:
        db.close()


@celery.task(bind=True, name='tasks.gap_analysis_tasks.rebuild_index')
def rebuild_index_task(self, tenant_id: str, force: bool = False):
    """
    Background task for rebuilding the knowledge base index.

    Args:
        tenant_id: Tenant ID
        force: Force rebuild even if index exists

    Returns:
        dict: Rebuild results
    """
    db = next(get_db())

    try:
        self.update_progress(0, 100, 'Starting index rebuild...')

        service = KnowledgeService(db)

        # Progress callback
        def on_progress(current, total, message):
            self.update_progress(current, total, message)

        # Rebuild index
        result = service.rebuild_index(
            tenant_id=tenant_id,
            progress_callback=on_progress,
            force=force
        )

        self.update_progress(100, 100, 'Index rebuild complete')

        return {
            'success': True,
            'tenant_id': tenant_id,
            'documents_indexed': result.get('documents_indexed', 0),
            'chunks_created': result.get('chunks_created', 0),
            'errors': result.get('errors', [])
        }

    except Exception as e:
        print(f"[RebuildIndexTask] Error: {e}", flush=True)

        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'tenant_id': tenant_id
            }
        )

        raise

    finally:
        db.close()
