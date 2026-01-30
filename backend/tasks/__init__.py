"""
Background Tasks Module
Celery tasks for long-running operations.
"""

from celery_app import celery

__all__ = ['celery']
