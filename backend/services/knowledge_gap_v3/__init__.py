"""
Knowledge Gap Detection v3.0
============================

A comprehensive, LLM-powered knowledge gap detection system designed
to identify and fill organizational context gaps.

Architecture:
- Stage 1: Deep Document Extraction (GPT-4)
- Stage 2: Knowledge Graph Assembly
- Stage 3: Multi-Analyzer Gap Detection
- Stage 4: LLM Question Generation
- Stage 5: Intelligent Prioritization
- Stage 6: Feedback & Learning Loop

Author: 2nd Brain Team
Version: 3.0.0
"""

from .deep_extractor import DeepDocumentExtractor
from .knowledge_graph import KnowledgeGraph, Entity, Relationship
from .gap_analyzers import GapAnalyzerEngine
from .question_generator import QuestionGenerator
from .prioritization import PrioritizationEngine
from .feedback_loop import FeedbackLoop
from .orchestrator import KnowledgeGapOrchestrator

__version__ = "3.0.0"
__all__ = [
    "DeepDocumentExtractor",
    "KnowledgeGraph",
    "Entity",
    "Relationship",
    "GapAnalyzerEngine",
    "QuestionGenerator",
    "PrioritizationEngine",
    "FeedbackLoop",
    "KnowledgeGapOrchestrator",
]
