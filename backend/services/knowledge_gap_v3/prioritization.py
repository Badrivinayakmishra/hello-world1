"""
Stage 5: Intelligent Prioritization
====================================

Scores and prioritizes gaps/questions based on multiple factors:
- Knowledge risk (bus factor, staleness)
- Business criticality
- Answerability
- User interest (learned from feedback)
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

from .gap_analyzers import Gap, GapType, GapSeverity
from .question_generator import GeneratedQuestion
from .knowledge_graph import KnowledgeGraph, Entity, EntityType

logger = logging.getLogger(__name__)


# =============================================================================
# PRIORITY WEIGHTS (Configurable)
# =============================================================================

DEFAULT_WEIGHTS = {
    "knowledge_risk": 0.30,
    "business_criticality": 0.30,
    "answerability": 0.20,
    "user_interest": 0.20
}

# Gap type base scores (0-1)
GAP_TYPE_RISK_SCORES = {
    GapType.CRITICAL_BUS_FACTOR: 1.0,
    GapType.KNOWLEDGE_CONCENTRATION: 0.8,
    GapType.NO_BACKUP_OWNER: 0.9,
    GapType.MISSING_RATIONALE: 0.6,
    GapType.NO_ALTERNATIVES_DOCUMENTED: 0.4,
    GapType.UNCLEAR_DECISION_MAKER: 0.5,
    GapType.STALE_DECISION: 0.5,
    GapType.HIGH_STAKES_UNDOCUMENTED: 0.9,
    GapType.INCOMPLETE_CRITICAL_PROCESS: 0.8,
    GapType.MISSING_EDGE_CASES: 0.6,
    GapType.MISSING_FAILURE_HANDLING: 0.8,
    GapType.UNVERIFIED_PROCESS: 0.4,
    GapType.UNDOCUMENTED_STEPS: 0.7,
    GapType.KNOWLEDGE_LOCKED_IN_PERSON: 0.9,
    GapType.IMPLICIT_EXPERTISE: 0.6,
    GapType.UNDOCUMENTED_DEPENDENCY: 0.6,
    GapType.UNKNOWN_FAILURE_CASCADE: 0.8,
    GapType.CIRCULAR_DEPENDENCY: 0.5,
    GapType.STALE_DOCUMENTATION: 0.4,
    GapType.VAGUE_FUTURE_REFERENCE: 0.2,
    GapType.UNTRACKED_CHANGE: 0.5,
    GapType.NUMERIC_CONTRADICTION: 0.6,
    GapType.FACTUAL_CONTRADICTION: 0.7,
    GapType.STATUS_CONTRADICTION: 0.6,
    GapType.UNDEFINED_TERM: 0.3,
    GapType.ASSUMED_CONTEXT: 0.4,
    GapType.MISSING_PREREQUISITE: 0.5,
}

# Severity multipliers
SEVERITY_MULTIPLIERS = {
    GapSeverity.LOW: 0.5,
    GapSeverity.MEDIUM: 0.75,
    GapSeverity.HIGH: 1.0,
    GapSeverity.CRITICAL: 1.25
}

# Entity type criticality scores
ENTITY_CRITICALITY = {
    EntityType.DATABASE: 0.9,
    EntityType.SERVICE: 0.8,
    EntityType.SYSTEM: 0.8,
    EntityType.API: 0.7,
    EntityType.PROCESS: 0.6,
    EntityType.DECISION: 0.6,
    EntityType.PERSON: 0.5,
    EntityType.TEAM: 0.5,
    EntityType.TOOL: 0.4,
    EntityType.CONCEPT: 0.3,
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PrioritizedQuestion:
    """A question with priority score and breakdown"""
    question: GeneratedQuestion
    gap: Gap
    priority_score: float
    score_breakdown: Dict[str, float]
    rank: int = 0

    def to_dict(self) -> Dict:
        return {
            "question": self.question.to_dict(),
            "gap": self.gap.to_dict(),
            "priority_score": self.priority_score,
            "score_breakdown": self.score_breakdown,
            "rank": self.rank
        }


# =============================================================================
# PRIORITIZATION ENGINE
# =============================================================================

class PrioritizationEngine:
    """
    Scores and prioritizes questions based on multiple factors.
    """

    def __init__(
        self,
        graph: KnowledgeGraph,
        weights: Optional[Dict[str, float]] = None,
        feedback_history: Optional[Dict[str, Any]] = None
    ):
        self.graph = graph
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self.feedback_history = feedback_history or {}

        # Learned adjustments from feedback
        self.gap_type_adjustments: Dict[GapType, float] = {}
        self.category_adjustments: Dict[str, float] = {}

        logger.info(f"[PrioritizationEngine] Initialized with weights: {self.weights}")

    def prioritize(
        self,
        questions: List[GeneratedQuestion],
        gaps: Dict[str, Gap]
    ) -> List[PrioritizedQuestion]:
        """
        Prioritize questions and return sorted list.

        Args:
            questions: List of generated questions
            gaps: Dict mapping gap_id to Gap

        Returns:
            Sorted list of PrioritizedQuestion objects
        """
        logger.info(f"[PrioritizationEngine] Prioritizing {len(questions)} questions...")

        prioritized = []

        for question in questions:
            gap = gaps.get(question.gap_id)
            if not gap:
                logger.warning(f"Gap not found for question: {question.gap_id}")
                continue

            score, breakdown = self._calculate_score(question, gap)

            prioritized.append(PrioritizedQuestion(
                question=question,
                gap=gap,
                priority_score=score,
                score_breakdown=breakdown
            ))

        # Sort by priority score (descending)
        prioritized.sort(key=lambda x: x.priority_score, reverse=True)

        # Assign ranks
        for i, p in enumerate(prioritized):
            p.rank = i + 1

        logger.info(f"[PrioritizationEngine] Prioritization complete. "
                   f"Top score: {prioritized[0].priority_score:.2f}" if prioritized else "")

        return prioritized

    def _calculate_score(
        self,
        question: GeneratedQuestion,
        gap: Gap
    ) -> tuple[float, Dict[str, float]]:
        """Calculate priority score for a question"""
        breakdown = {}

        # 1. Knowledge Risk Score
        knowledge_risk = self._calculate_knowledge_risk(gap)
        breakdown["knowledge_risk"] = knowledge_risk

        # 2. Business Criticality Score
        business_crit = self._calculate_business_criticality(gap)
        breakdown["business_criticality"] = business_crit

        # 3. Answerability Score
        answerability = self._calculate_answerability(question, gap)
        breakdown["answerability"] = answerability

        # 4. User Interest Score (learned)
        user_interest = self._calculate_user_interest(question, gap)
        breakdown["user_interest"] = user_interest

        # Calculate weighted total
        total = (
            self.weights["knowledge_risk"] * knowledge_risk +
            self.weights["business_criticality"] * business_crit +
            self.weights["answerability"] * answerability +
            self.weights["user_interest"] * user_interest
        )

        return total, breakdown

    def _calculate_knowledge_risk(self, gap: Gap) -> float:
        """Calculate knowledge risk score (0-1)"""
        # Base score from gap type
        base_score = GAP_TYPE_RISK_SCORES.get(gap.gap_type, 0.5)

        # Apply severity multiplier
        severity_mult = SEVERITY_MULTIPLIERS.get(gap.severity, 1.0)
        score = base_score * severity_mult

        # Apply learned adjustment if available
        adjustment = self.gap_type_adjustments.get(gap.gap_type, 0)
        score = max(0, min(1, score + adjustment))

        # Boost for bus factor indicators
        if gap.metadata.get("backup_count", 1) == 0:
            score = min(1, score * 1.2)

        # Boost for single source
        if len(gap.source_docs) == 1:
            score = min(1, score * 1.1)

        return score

    def _calculate_business_criticality(self, gap: Gap) -> float:
        """Calculate business criticality score (0-1)"""
        # Get affected entities
        max_criticality = 0.3  # Base score

        for entity_id in gap.affected_entities:
            entity = self.graph.get_entity(entity_id)
            if entity:
                entity_crit = ENTITY_CRITICALITY.get(entity.entity_type, 0.3)

                # Boost if explicitly marked critical
                if entity.attributes.get("criticality") == "critical":
                    entity_crit = min(1.0, entity_crit * 1.3)
                elif entity.attributes.get("criticality") == "high":
                    entity_crit = min(1.0, entity_crit * 1.15)

                max_criticality = max(max_criticality, entity_crit)

        # Boost for process/system gaps
        if gap.gap_type in (
            GapType.INCOMPLETE_CRITICAL_PROCESS,
            GapType.MISSING_FAILURE_HANDLING,
            GapType.UNKNOWN_FAILURE_CASCADE,
            GapType.CRITICAL_BUS_FACTOR
        ):
            max_criticality = min(1.0, max_criticality * 1.2)

        return max_criticality

    def _calculate_answerability(
        self,
        question: GeneratedQuestion,
        gap: Gap
    ) -> float:
        """Calculate answerability score (0-1)"""
        score = 0.5  # Base score

        # Boost if suggested respondent exists
        if question.suggested_respondent:
            score += 0.2

            # Check if person exists in graph
            person = self.graph.find_entity_by_name(question.suggested_respondent)
            if person:
                score += 0.1

        # Boost if question has clear context
        if question.context_summary and len(question.context_summary) > 50:
            score += 0.1

        # Boost if effort estimate is reasonable
        if question.estimated_effort:
            effort_lower = question.estimated_effort.lower()
            if any(x in effort_lower for x in ["minute", "30", "hour"]):
                score += 0.1

        # Penalty for vague questions
        if question.confidence < 0.5:
            score *= 0.8

        return min(1.0, score)

    def _calculate_user_interest(
        self,
        question: GeneratedQuestion,
        gap: Gap
    ) -> float:
        """Calculate user interest score based on feedback history (0-1)"""
        base_score = 0.5  # Neutral starting point

        # Check category preferences from feedback
        category = question.category
        if category in self.category_adjustments:
            base_score += self.category_adjustments[category]

        # Check gap type preferences
        if gap.gap_type in self.gap_type_adjustments:
            base_score += self.gap_type_adjustments[gap.gap_type]

        # Check for similar questions that were marked useful
        if self.feedback_history:
            useful_rate = self._get_similar_question_feedback(question, gap)
            if useful_rate is not None:
                base_score = base_score * 0.5 + useful_rate * 0.5

        return max(0, min(1, base_score))

    def _get_similar_question_feedback(
        self,
        question: GeneratedQuestion,
        gap: Gap
    ) -> Optional[float]:
        """Get feedback rate for similar questions"""
        # Look for questions with same gap type
        type_feedback = self.feedback_history.get("by_gap_type", {})
        gap_type_str = gap.gap_type.value

        if gap_type_str in type_feedback:
            feedback = type_feedback[gap_type_str]
            if feedback.get("total", 0) > 0:
                return feedback.get("useful", 0) / feedback["total"]

        return None

    def update_from_feedback(
        self,
        question_id: str,
        gap_type: GapType,
        category: str,
        useful: bool
    ):
        """
        Update learned preferences from user feedback.

        Args:
            question_id: ID of the question that received feedback
            gap_type: Type of gap the question addressed
            category: Question category
            useful: Whether user marked it useful
        """
        # Update gap type adjustments
        current = self.gap_type_adjustments.get(gap_type, 0)
        adjustment = 0.05 if useful else -0.05
        self.gap_type_adjustments[gap_type] = max(-0.3, min(0.3, current + adjustment))

        # Update category adjustments
        current = self.category_adjustments.get(category, 0)
        self.category_adjustments[category] = max(-0.3, min(0.3, current + adjustment))

        # Update feedback history
        if "by_gap_type" not in self.feedback_history:
            self.feedback_history["by_gap_type"] = {}

        gap_type_str = gap_type.value
        if gap_type_str not in self.feedback_history["by_gap_type"]:
            self.feedback_history["by_gap_type"][gap_type_str] = {"useful": 0, "not_useful": 0, "total": 0}

        self.feedback_history["by_gap_type"][gap_type_str]["total"] += 1
        if useful:
            self.feedback_history["by_gap_type"][gap_type_str]["useful"] += 1
        else:
            self.feedback_history["by_gap_type"][gap_type_str]["not_useful"] += 1

        logger.info(f"[PrioritizationEngine] Updated from feedback: "
                   f"gap_type={gap_type.value}, useful={useful}")

    def get_weights(self) -> Dict[str, float]:
        """Get current weights"""
        return self.weights.copy()

    def set_weights(self, weights: Dict[str, float]):
        """Set custom weights (must sum to 1.0)"""
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        self.weights = weights.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get prioritization statistics"""
        return {
            "weights": self.weights,
            "gap_type_adjustments": {k.value: v for k, v in self.gap_type_adjustments.items()},
            "category_adjustments": self.category_adjustments,
            "feedback_history": self.feedback_history
        }
