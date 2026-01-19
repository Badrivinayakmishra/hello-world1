"""
Stage 6: Feedback & Learning Loop
=================================

Tracks user feedback on questions and learns to improve future prioritization.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict

from .gap_analyzers import GapType
from .question_generator import GeneratedQuestion
from .prioritization import PrioritizationEngine

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class FeedbackType(str, Enum):
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"
    ALREADY_KNOWN = "already_known"
    ANSWERED = "answered"
    SKIPPED = "skipped"


@dataclass
class QuestionFeedback:
    """Feedback on a single question"""
    question_id: str
    gap_id: str
    gap_type: str
    category: str
    feedback_type: FeedbackType
    comment: Optional[str] = None
    answer_text: Optional[str] = None  # If answered
    answer_quality: Optional[str] = None  # If answered: "comprehensive", "partial", "minimal"
    respondent: Optional[str] = None  # Who answered
    time_to_answer: Optional[int] = None  # Minutes
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "question_id": self.question_id,
            "gap_id": self.gap_id,
            "gap_type": self.gap_type,
            "category": self.category,
            "feedback_type": self.feedback_type.value,
            "comment": self.comment,
            "answer_text": self.answer_text,
            "answer_quality": self.answer_quality,
            "respondent": self.respondent,
            "time_to_answer": self.time_to_answer,
            "created_at": self.created_at
        }


@dataclass
class Answer:
    """An answer to a knowledge gap question"""
    id: str
    question_id: str
    gap_id: str
    answer_text: str
    respondent: str
    quality: str  # "comprehensive", "partial", "minimal"
    follow_up_needed: bool = False
    follow_up_questions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "question_id": self.question_id,
            "gap_id": self.gap_id,
            "answer_text": self.answer_text,
            "respondent": self.respondent,
            "quality": self.quality,
            "follow_up_needed": self.follow_up_needed,
            "follow_up_questions": self.follow_up_questions,
            "created_at": self.created_at,
            "verified": self.verified,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at
        }


# =============================================================================
# FEEDBACK LOOP
# =============================================================================

class FeedbackLoop:
    """
    Manages feedback collection and learning for the knowledge gap system.
    """

    def __init__(self, prioritization_engine: Optional[PrioritizationEngine] = None):
        self.prioritization_engine = prioritization_engine
        self.feedback_history: List[QuestionFeedback] = []
        self.answers: Dict[str, Answer] = {}  # question_id -> Answer

        # Aggregated stats
        self._stats_by_gap_type: Dict[str, Dict] = defaultdict(
            lambda: {"useful": 0, "not_useful": 0, "answered": 0, "total": 0}
        )
        self._stats_by_category: Dict[str, Dict] = defaultdict(
            lambda: {"useful": 0, "not_useful": 0, "answered": 0, "total": 0}
        )
        self._answer_counter = 0

        logger.info("[FeedbackLoop] Initialized")

    def record_feedback(
        self,
        question_id: str,
        gap_id: str,
        gap_type: GapType,
        category: str,
        feedback_type: FeedbackType,
        comment: Optional[str] = None
    ) -> QuestionFeedback:
        """
        Record user feedback on a question.

        Args:
            question_id: ID of the question
            gap_id: ID of the associated gap
            gap_type: Type of gap
            category: Question category
            feedback_type: Type of feedback
            comment: Optional comment

        Returns:
            QuestionFeedback object
        """
        feedback = QuestionFeedback(
            question_id=question_id,
            gap_id=gap_id,
            gap_type=gap_type.value,
            category=category,
            feedback_type=feedback_type,
            comment=comment
        )

        self.feedback_history.append(feedback)

        # Update stats
        gap_type_str = gap_type.value
        self._stats_by_gap_type[gap_type_str]["total"] += 1
        self._stats_by_category[category]["total"] += 1

        if feedback_type == FeedbackType.USEFUL:
            self._stats_by_gap_type[gap_type_str]["useful"] += 1
            self._stats_by_category[category]["useful"] += 1
        elif feedback_type == FeedbackType.NOT_USEFUL:
            self._stats_by_gap_type[gap_type_str]["not_useful"] += 1
            self._stats_by_category[category]["not_useful"] += 1
        elif feedback_type == FeedbackType.ANSWERED:
            self._stats_by_gap_type[gap_type_str]["answered"] += 1
            self._stats_by_category[category]["answered"] += 1

        # Update prioritization engine if available
        if self.prioritization_engine:
            is_useful = feedback_type in (FeedbackType.USEFUL, FeedbackType.ANSWERED)
            self.prioritization_engine.update_from_feedback(
                question_id=question_id,
                gap_type=gap_type,
                category=category,
                useful=is_useful
            )

        logger.info(f"[FeedbackLoop] Recorded feedback: {question_id} -> {feedback_type.value}")

        return feedback

    def record_answer(
        self,
        question_id: str,
        gap_id: str,
        answer_text: str,
        respondent: str,
        quality: str = "partial",
        follow_up_needed: bool = False,
        follow_up_questions: Optional[List[str]] = None
    ) -> Answer:
        """
        Record an answer to a question.

        Args:
            question_id: ID of the question being answered
            gap_id: ID of the associated gap
            answer_text: The answer content
            respondent: Who provided the answer
            quality: Answer quality ("comprehensive", "partial", "minimal")
            follow_up_needed: Whether follow-up is needed
            follow_up_questions: Additional questions that arose

        Returns:
            Answer object
        """
        self._answer_counter += 1
        answer_id = f"A_{question_id}_{self._answer_counter}"

        answer = Answer(
            id=answer_id,
            question_id=question_id,
            gap_id=gap_id,
            answer_text=answer_text,
            respondent=respondent,
            quality=quality,
            follow_up_needed=follow_up_needed,
            follow_up_questions=follow_up_questions or []
        )

        self.answers[question_id] = answer

        logger.info(f"[FeedbackLoop] Recorded answer: {answer_id} (quality: {quality})")

        return answer

    def verify_answer(
        self,
        question_id: str,
        verified_by: str
    ) -> Optional[Answer]:
        """Mark an answer as verified"""
        answer = self.answers.get(question_id)
        if answer:
            answer.verified = True
            answer.verified_by = verified_by
            answer.verified_at = datetime.utcnow().isoformat()
            logger.info(f"[FeedbackLoop] Answer verified: {answer.id} by {verified_by}")
        return answer

    def get_answer(self, question_id: str) -> Optional[Answer]:
        """Get answer for a question"""
        return self.answers.get(question_id)

    def get_unanswered_questions(
        self,
        question_ids: List[str]
    ) -> List[str]:
        """Get list of questions that haven't been answered"""
        return [qid for qid in question_ids if qid not in self.answers]

    def get_effectiveness_stats(self) -> Dict[str, Any]:
        """Get effectiveness statistics for the system"""
        total_feedback = len(self.feedback_history)
        total_answers = len(self.answers)

        if total_feedback == 0:
            return {
                "total_feedback": 0,
                "total_answers": 0,
                "useful_rate": 0,
                "answer_rate": 0
            }

        useful_count = sum(
            1 for f in self.feedback_history
            if f.feedback_type in (FeedbackType.USEFUL, FeedbackType.ANSWERED)
        )

        return {
            "total_feedback": total_feedback,
            "total_answers": total_answers,
            "useful_rate": useful_count / total_feedback if total_feedback > 0 else 0,
            "answer_rate": total_answers / total_feedback if total_feedback > 0 else 0,
            "by_gap_type": dict(self._stats_by_gap_type),
            "by_category": dict(self._stats_by_category),
            "comprehensive_answers": sum(1 for a in self.answers.values() if a.quality == "comprehensive"),
            "verified_answers": sum(1 for a in self.answers.values() if a.verified)
        }

    def get_improvement_suggestions(self) -> List[Dict[str, Any]]:
        """
        Analyze feedback to suggest system improvements.
        """
        suggestions = []

        # Check for gap types with low usefulness
        for gap_type, stats in self._stats_by_gap_type.items():
            if stats["total"] >= 5:  # Minimum sample size
                useful_rate = stats["useful"] / stats["total"]
                if useful_rate < 0.3:
                    suggestions.append({
                        "type": "low_usefulness_gap_type",
                        "gap_type": gap_type,
                        "useful_rate": useful_rate,
                        "suggestion": f"Questions for {gap_type} have low usefulness ({useful_rate:.0%}). "
                                     f"Consider refining the question generation for this gap type."
                    })

        # Check for categories with low usefulness
        for category, stats in self._stats_by_category.items():
            if stats["total"] >= 5:
                useful_rate = stats["useful"] / stats["total"]
                if useful_rate < 0.3:
                    suggestions.append({
                        "type": "low_usefulness_category",
                        "category": category,
                        "useful_rate": useful_rate,
                        "suggestion": f"Questions in category '{category}' have low usefulness ({useful_rate:.0%}). "
                                     f"Consider improving question generation for this category."
                    })

        # Check for high "already known" rate
        already_known_count = sum(
            1 for f in self.feedback_history
            if f.feedback_type == FeedbackType.ALREADY_KNOWN
        )
        if len(self.feedback_history) > 10:
            already_known_rate = already_known_count / len(self.feedback_history)
            if already_known_rate > 0.3:
                suggestions.append({
                    "type": "high_redundancy",
                    "already_known_rate": already_known_rate,
                    "suggestion": f"High rate of 'already known' responses ({already_known_rate:.0%}). "
                                 f"Consider improving gap detection to find truly unknown information."
                })

        return suggestions

    def export_learning_data(self) -> Dict[str, Any]:
        """Export all learning data for persistence"""
        return {
            "feedback_history": [f.to_dict() for f in self.feedback_history],
            "answers": {qid: a.to_dict() for qid, a in self.answers.items()},
            "stats_by_gap_type": dict(self._stats_by_gap_type),
            "stats_by_category": dict(self._stats_by_category),
            "exported_at": datetime.utcnow().isoformat()
        }

    def import_learning_data(self, data: Dict[str, Any]):
        """Import previously exported learning data"""
        # Import feedback history
        for f_data in data.get("feedback_history", []):
            feedback = QuestionFeedback(
                question_id=f_data["question_id"],
                gap_id=f_data["gap_id"],
                gap_type=f_data["gap_type"],
                category=f_data["category"],
                feedback_type=FeedbackType(f_data["feedback_type"]),
                comment=f_data.get("comment"),
                answer_text=f_data.get("answer_text"),
                answer_quality=f_data.get("answer_quality"),
                respondent=f_data.get("respondent"),
                time_to_answer=f_data.get("time_to_answer"),
                created_at=f_data.get("created_at", datetime.utcnow().isoformat())
            )
            self.feedback_history.append(feedback)

        # Import answers
        for qid, a_data in data.get("answers", {}).items():
            answer = Answer(
                id=a_data["id"],
                question_id=a_data["question_id"],
                gap_id=a_data["gap_id"],
                answer_text=a_data["answer_text"],
                respondent=a_data["respondent"],
                quality=a_data["quality"],
                follow_up_needed=a_data.get("follow_up_needed", False),
                follow_up_questions=a_data.get("follow_up_questions", []),
                created_at=a_data.get("created_at", datetime.utcnow().isoformat()),
                verified=a_data.get("verified", False),
                verified_by=a_data.get("verified_by"),
                verified_at=a_data.get("verified_at")
            )
            self.answers[qid] = answer

        # Import stats
        for gap_type, stats in data.get("stats_by_gap_type", {}).items():
            self._stats_by_gap_type[gap_type].update(stats)
        for category, stats in data.get("stats_by_category", {}).items():
            self._stats_by_category[category].update(stats)

        logger.info(f"[FeedbackLoop] Imported {len(self.feedback_history)} feedback records, "
                   f"{len(self.answers)} answers")
