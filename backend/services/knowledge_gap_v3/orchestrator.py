"""
Knowledge Gap Orchestrator
==========================

Main entry point that coordinates all 6 stages of the knowledge gap detection system.
"""

import os
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# Get model from environment
DEFAULT_MODEL = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-5-chat")

from .deep_extractor import DeepDocumentExtractor, DocumentExtraction
from .knowledge_graph import KnowledgeGraph, Entity, EntityType
from .gap_analyzers import GapAnalyzerEngine, Gap, GapType, GapSeverity
from .question_generator import QuestionGenerator, GeneratedQuestion
from .prioritization import PrioritizationEngine, PrioritizedQuestion
from .feedback_loop import FeedbackLoop, FeedbackType, Answer

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class AnalysisResult:
    """Complete result of knowledge gap analysis"""
    # Metadata
    analysis_id: str
    tenant_id: str
    project_id: Optional[str]
    analyzed_at: str

    # Document stats
    documents_processed: int
    total_entities: int
    total_relationships: int

    # Gap stats
    total_gaps: int
    gaps_by_type: Dict[str, int]
    gaps_by_severity: Dict[str, int]

    # Questions
    total_questions: int
    prioritized_questions: List[Dict]  # Top N questions

    # Raw data (for detailed view)
    extractions: List[Dict] = field(default_factory=list)
    all_gaps: List[Dict] = field(default_factory=list)
    graph_stats: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "analysis_id": self.analysis_id,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "analyzed_at": self.analyzed_at,
            "documents_processed": self.documents_processed,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships,
            "total_gaps": self.total_gaps,
            "gaps_by_type": self.gaps_by_type,
            "gaps_by_severity": self.gaps_by_severity,
            "total_questions": self.total_questions,
            "prioritized_questions": self.prioritized_questions,
            "extractions": self.extractions,
            "all_gaps": self.all_gaps,
            "graph_stats": self.graph_stats
        }


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class KnowledgeGapOrchestrator:
    """
    Main orchestrator for the Knowledge Gap Detection v3.0 system.

    Coordinates:
    - Stage 1: Deep Document Extraction
    - Stage 2: Knowledge Graph Assembly
    - Stage 3: Multi-Analyzer Gap Detection
    - Stage 4: LLM Question Generation
    - Stage 5: Intelligent Prioritization
    - Stage 6: Feedback & Learning Loop
    """

    def __init__(
        self,
        extraction_model: str = None,
        question_model: str = None,
        org_context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the orchestrator.

        Args:
            extraction_model: Model for document extraction (defaults to AZURE_CHAT_DEPLOYMENT)
            question_model: Model for question generation (defaults to AZURE_CHAT_DEPLOYMENT)
            org_context: Optional organizational context (team size, industry, etc.)
        """
        # Use environment variable if not specified
        self.extraction_model = extraction_model or DEFAULT_MODEL
        self.question_model = question_model or DEFAULT_MODEL
        self.org_context = org_context or {}

        # Initialize components
        self.extractor = DeepDocumentExtractor(model=extraction_model)
        self.graph = KnowledgeGraph()
        self.question_generator = QuestionGenerator(self.graph, model=question_model)
        self.prioritization_engine = PrioritizationEngine(self.graph)
        self.feedback_loop = FeedbackLoop(self.prioritization_engine)

        # State
        self.extractions: List[DocumentExtraction] = []
        self.gaps: List[Gap] = []
        self.questions: List[GeneratedQuestion] = []
        self.prioritized: List[PrioritizedQuestion] = []

        self._analysis_counter = 0

        logger.info("[Orchestrator] Initialized Knowledge Gap Detection v3.0")

    def analyze(
        self,
        documents: List[Dict[str, str]],
        tenant_id: str,
        project_id: Optional[str] = None,
        top_n_questions: int = 20
    ) -> AnalysisResult:
        """
        Run complete analysis on documents.

        Args:
            documents: List of {"doc_id", "title", "content"} dicts
            tenant_id: Tenant identifier
            project_id: Optional project identifier
            top_n_questions: Number of top questions to include in result

        Returns:
            AnalysisResult with all findings
        """
        start_time = datetime.utcnow()
        self._analysis_counter += 1
        analysis_id = f"KG3_{tenant_id}_{self._analysis_counter}_{start_time.strftime('%Y%m%d%H%M%S')}"

        logger.info(f"[Orchestrator] Starting analysis {analysis_id} for {len(documents)} documents")

        # Reset state for new analysis
        self.extractions = []
        self.gaps = []
        self.questions = []
        self.prioritized = []
        self.graph = KnowledgeGraph()  # Fresh graph

        # =====================================================================
        # STAGE 1: Deep Document Extraction
        # =====================================================================
        logger.info("[Orchestrator] Stage 1: Deep Document Extraction")

        for doc in documents:
            extraction = self.extractor.extract(
                doc_id=doc.get("doc_id") or doc.get("id"),
                title=doc.get("title", "Untitled"),
                content=doc.get("content", "")
            )
            self.extractions.append(extraction)

        logger.info(f"[Orchestrator] Extracted from {len(self.extractions)} documents")

        # =====================================================================
        # STAGE 2: Knowledge Graph Assembly
        # =====================================================================
        logger.info("[Orchestrator] Stage 2: Knowledge Graph Assembly")

        for extraction in self.extractions:
            self.graph.add_extraction(extraction)

        graph_stats = self.graph.get_stats()
        logger.info(f"[Orchestrator] Graph built: {graph_stats['total_entities']} entities, "
                   f"{graph_stats['total_relationships']} relationships")

        # =====================================================================
        # STAGE 3: Multi-Analyzer Gap Detection
        # =====================================================================
        logger.info("[Orchestrator] Stage 3: Multi-Analyzer Gap Detection")

        analyzer_engine = GapAnalyzerEngine(self.graph, self.extractions)
        self.gaps = analyzer_engine.analyze_all()

        gap_stats = analyzer_engine.get_stats()
        logger.info(f"[Orchestrator] Detected {len(self.gaps)} gaps")

        # =====================================================================
        # STAGE 4: LLM Question Generation
        # =====================================================================
        logger.info("[Orchestrator] Stage 4: LLM Question Generation")

        # Limit gaps for question generation (cost control)
        gaps_for_questions = self.gaps[:50]  # Top 50 gaps

        self.questions = self.question_generator.generate_questions(
            gaps=gaps_for_questions,
            org_context=self.org_context
        )

        logger.info(f"[Orchestrator] Generated {len(self.questions)} questions")

        # =====================================================================
        # STAGE 5: Intelligent Prioritization
        # =====================================================================
        logger.info("[Orchestrator] Stage 5: Intelligent Prioritization")

        # Create gap lookup
        gap_lookup = {g.id: g for g in self.gaps}

        self.prioritized = self.prioritization_engine.prioritize(
            questions=self.questions,
            gaps=gap_lookup
        )

        logger.info(f"[Orchestrator] Prioritized {len(self.prioritized)} questions")

        # =====================================================================
        # BUILD RESULT
        # =====================================================================
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"[Orchestrator] Analysis complete in {elapsed:.1f}s")

        return AnalysisResult(
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            project_id=project_id,
            analyzed_at=start_time.isoformat(),
            documents_processed=len(documents),
            total_entities=graph_stats["total_entities"],
            total_relationships=graph_stats["total_relationships"],
            total_gaps=len(self.gaps),
            gaps_by_type=gap_stats["by_type"],
            gaps_by_severity=gap_stats["by_severity"],
            total_questions=len(self.questions),
            prioritized_questions=[p.to_dict() for p in self.prioritized[:top_n_questions]],
            extractions=[e.to_dict() for e in self.extractions],
            all_gaps=[g.to_dict() for g in self.gaps],
            graph_stats=graph_stats
        )

    def get_questions(
        self,
        limit: int = 20,
        category: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Dict]:
        """
        Get prioritized questions with optional filtering.

        Args:
            limit: Maximum number of questions
            category: Filter by category
            severity: Filter by gap severity

        Returns:
            List of question dicts
        """
        results = []

        for p in self.prioritized:
            # Apply filters
            if category and p.question.category != category:
                continue
            if severity and p.gap.severity.value != severity:
                continue

            results.append(p.to_dict())

            if len(results) >= limit:
                break

        return results

    def submit_feedback(
        self,
        question_id: str,
        feedback_type: str,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit feedback for a question.

        Args:
            question_id: Question ID
            feedback_type: "useful", "not_useful", "already_known", "skipped"
            comment: Optional comment

        Returns:
            Feedback confirmation
        """
        # Find the question and gap
        question = None
        gap = None

        for p in self.prioritized:
            if p.question.id == question_id:
                question = p.question
                gap = p.gap
                break

        if not question or not gap:
            return {"error": f"Question not found: {question_id}"}

        # Record feedback
        feedback = self.feedback_loop.record_feedback(
            question_id=question_id,
            gap_id=gap.id,
            gap_type=GapType(gap.gap_type) if isinstance(gap.gap_type, str) else gap.gap_type,
            category=question.category,
            feedback_type=FeedbackType(feedback_type),
            comment=comment
        )

        return {
            "status": "recorded",
            "feedback": feedback.to_dict()
        }

    def submit_answer(
        self,
        question_id: str,
        answer_text: str,
        respondent: str,
        quality: str = "partial"
    ) -> Dict[str, Any]:
        """
        Submit an answer to a question.

        Args:
            question_id: Question ID
            answer_text: The answer
            respondent: Who answered
            quality: "comprehensive", "partial", "minimal"

        Returns:
            Answer confirmation
        """
        # Find the gap
        gap_id = None
        for p in self.prioritized:
            if p.question.id == question_id:
                gap_id = p.gap.id
                break

        if not gap_id:
            return {"error": f"Question not found: {question_id}"}

        answer = self.feedback_loop.record_answer(
            question_id=question_id,
            gap_id=gap_id,
            answer_text=answer_text,
            respondent=respondent,
            quality=quality
        )

        # Also record as "answered" feedback
        self.submit_feedback(question_id, "answered")

        return {
            "status": "recorded",
            "answer": answer.to_dict()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get overall system statistics"""
        return {
            "extractions": len(self.extractions),
            "graph": self.graph.get_stats() if self.graph else {},
            "gaps": len(self.gaps),
            "questions": len(self.questions),
            "prioritization": self.prioritization_engine.get_stats() if self.prioritization_engine else {},
            "feedback": self.feedback_loop.get_effectiveness_stats() if self.feedback_loop else {}
        }

    def get_graph(self) -> KnowledgeGraph:
        """Get the knowledge graph"""
        return self.graph

    def get_feedback_suggestions(self) -> List[Dict[str, Any]]:
        """Get suggestions for improving the system based on feedback"""
        return self.feedback_loop.get_improvement_suggestions()

    def export_state(self) -> Dict[str, Any]:
        """Export current state for persistence"""
        return {
            "extractions": [e.to_dict() for e in self.extractions],
            "graph": self.graph.to_dict(),
            "gaps": [g.to_dict() for g in self.gaps],
            "questions": [q.to_dict() for q in self.questions],
            "prioritized": [p.to_dict() for p in self.prioritized],
            "feedback": self.feedback_loop.export_learning_data(),
            "prioritization": self.prioritization_engine.get_stats(),
            "org_context": self.org_context,
            "exported_at": datetime.utcnow().isoformat()
        }


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def analyze_documents(
    documents: List[Dict[str, str]],
    tenant_id: str,
    project_id: Optional[str] = None,
    org_context: Optional[Dict[str, Any]] = None,
    top_n_questions: int = 20
) -> Dict[str, Any]:
    """
    Convenience function to run complete analysis.

    Args:
        documents: List of {"doc_id", "title", "content"} dicts
        tenant_id: Tenant identifier
        project_id: Optional project identifier
        org_context: Optional organizational context
        top_n_questions: Number of top questions to return

    Returns:
        Analysis result as dict
    """
    orchestrator = KnowledgeGapOrchestrator(org_context=org_context)
    result = orchestrator.analyze(
        documents=documents,
        tenant_id=tenant_id,
        project_id=project_id,
        top_n_questions=top_n_questions
    )
    return result.to_dict()
