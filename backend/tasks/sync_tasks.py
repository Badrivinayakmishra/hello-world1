"""
Sync Tasks
Background tasks for syncing data from integrations (Gmail, Slack, Box, GitHub).
"""

from celery_app import celery
from database.models import get_db, Connector
from connectors.gmail_connector import GmailConnector
from connectors.slack_connector import SlackConnector
from connectors.box_connector import BoxConnector
# from connectors.github_connector import GitHubConnector  # Add when implemented


@celery.task(bind=True, name='tasks.sync_tasks.sync_connector')
def sync_connector_task(self, connector_id: str, tenant_id: str, force: bool = False):
    """
    Background task for syncing connector data.

    Args:
        connector_id: Connector ID to sync
        tenant_id: Tenant ID for security
        force: Force re-sync even if recently synced

    Returns:
        dict: Sync results with document count, etc.
    """
    db = next(get_db())

    try:
        # Update initial status
        self.update_progress(0, 100, 'Starting sync...')

        # Get connector
        connector = db.query(Connector).filter(
            Connector.id == connector_id,
            Connector.tenant_id == tenant_id  # Security: ensure tenant owns connector
        ).first()

        if not connector:
            raise ValueError(f"Connector {connector_id} not found for tenant {tenant_id}")

        if not connector.is_active:
            raise ValueError(f"Connector {connector_id} is not active")

        # Initialize appropriate connector service
        connector_type = connector.type.lower()

        if connector_type == 'gmail':
            service = GmailConnector(connector, db)
        elif connector_type == 'slack':
            service = SlackConnector(connector, db)
        elif connector_type == 'box':
            service = BoxConnector(connector, db)
        # elif connector_type == 'github':
        #     service = GitHubConnector(connector, db)
        else:
            raise ValueError(f"Unknown connector type: {connector_type}")

        # Sync with progress callbacks
        documents_synced = 0
        files_found = 0

        def on_progress(current, total, message):
            """Progress callback for sync operations"""
            nonlocal documents_synced, files_found

            if "found" in message.lower():
                files_found = current

            if "processed" in message.lower() or "synced" in message.lower():
                documents_synced = current

            self.update_progress(current, total, message)

        # Execute sync
        result = service.sync(progress_callback=on_progress, force=force)

        # Update final status
        self.update_progress(100, 100, 'Sync completed')

        return {
            'success': True,
            'connector_id': connector_id,
            'connector_type': connector_type,
            'documents_synced': result.get('documents_synced', 0),
            'documents_updated': result.get('documents_updated', 0),
            'documents_skipped': result.get('documents_skipped', 0),
            'files_found': result.get('files_found', 0),
            'total_documents': result.get('total_documents', 0),
            'errors': result.get('errors', [])
        }

    except Exception as e:
        # Log error
        print(f"[SyncTask] Error syncing connector {connector_id}: {e}", flush=True)

        # Update status to failed
        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'connector_id': connector_id
            }
        )

        raise

    finally:
        db.close()


@celery.task(bind=True, name='tasks.sync_tasks.sync_all_connectors')
def sync_all_connectors_task(self, tenant_id: str, force: bool = False):
    """
    Sync all active connectors for a tenant.

    Args:
        tenant_id: Tenant ID
        force: Force re-sync

    Returns:
        dict: Results for all connectors
    """
    db = next(get_db())

    try:
        # Get all active connectors for tenant
        connectors = db.query(Connector).filter(
            Connector.tenant_id == tenant_id,
            Connector.is_active == True
        ).all()

        if not connectors:
            return {
                'success': True,
                'message': 'No active connectors found',
                'results': []
            }

        total = len(connectors)
        results = []

        for index, connector in enumerate(connectors):
            self.update_progress(
                index,
                total,
                f'Syncing {connector.type} ({index + 1}/{total})...'
            )

            # Sync connector (create subtask)
            try:
                result = sync_connector_task(connector.id, tenant_id, force)
                results.append({
                    'connector_id': connector.id,
                    'connector_type': connector.type,
                    'success': True,
                    **result
                })
            except Exception as e:
                results.append({
                    'connector_id': connector.id,
                    'connector_type': connector.type,
                    'success': False,
                    'error': str(e)
                })

        self.update_progress(total, total, 'All connectors synced')

        return {
            'success': True,
            'total_connectors': total,
            'results': results
        }

    except Exception as e:
        print(f"[SyncAllTask] Error: {e}", flush=True)

        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )

        raise

    finally:
        db.close()


@celery.task(bind=True, name='tasks.sync_tasks.incremental_sync')
def incremental_sync_task(self, connector_id: str, tenant_id: str):
    """
    Incremental sync (only new/changed documents).
    More efficient than full sync.

    Args:
        connector_id: Connector ID
        tenant_id: Tenant ID

    Returns:
        dict: Sync results
    """
    # This is the same as sync_connector_task with force=False
    # Connectors should implement incremental logic internally
    return sync_connector_task(connector_id, tenant_id, force=False)
