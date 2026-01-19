"""
Stage 3: Multi-Analyzer Gap Detection
=====================================

8 specialized analyzers that examine the knowledge graph to detect gaps:
1. Bus Factor Analyzer - Single points of failure
2. Decision Archaeology Analyzer - Missing decision context
3. Process Completeness Analyzer - Underdocumented processes
4. Tribal Knowledge Analyzer - Knowledge locked in individuals
5. Dependency Risk Analyzer - Hidden/undocumented dependencies
6. Temporal Staleness Analyzer - Outdated documentation
7. Contradiction Detector - Conflicting information
8. Onboarding Barrier Analyzer - Assumed context/undefined terms
"""

import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict

from .knowledge_graph import (
    KnowledgeGraph, Entity, Relationship,
    EntityType, RelationshipType
)
from .deep_extractor import (
    DocumentExtraction, KnowledgeSignal, SignalType
)

logger = logging.getLogger(__name__)


# =============================================================================
# GAP DATA STRUCTURES
# =============================================================================

class GapType(str, Enum):
    # Bus Factor
    CRITICAL_BUS_FACTOR = "CRITICAL_BUS_FACTOR"
    KNOWLEDGE_CONCENTRATION = "KNOWLEDGE_CONCENTRATION"
    NO_BACKUP_OWNER = "NO_BACKUP_OWNER"

    # Decision Archaeology
    MISSING_RATIONALE = "MISSING_RATIONALE"
    NO_ALTERNATIVES_DOCUMENTED = "NO_ALTERNATIVES_DOCUMENTED"
    UNCLEAR_DECISION_MAKER = "UNCLEAR_DECISION_MAKER"
    STALE_DECISION = "STALE_DECISION"
    HIGH_STAKES_UNDOCUMENTED = "HIGH_STAKES_UNDOCUMENTED"

    # Process Completeness
    INCOMPLETE_CRITICAL_PROCESS = "INCOMPLETE_CRITICAL_PROCESS"
    MISSING_EDGE_CASES = "MISSING_EDGE_CASES"
    MISSING_FAILURE_HANDLING = "MISSING_FAILURE_HANDLING"
    UNVERIFIED_PROCESS = "UNVERIFIED_PROCESS"
    UNDOCUMENTED_STEPS = "UNDOCUMENTED_STEPS"

    # Tribal Knowledge
    KNOWLEDGE_LOCKED_IN_PERSON = "KNOWLEDGE_LOCKED_IN_PERSON"
    IMPLICIT_EXPERTISE = "IMPLICIT_EXPERTISE"

    # Dependencies
    UNDOCUMENTED_DEPENDENCY = "UNDOCUMENTED_DEPENDENCY"
    UNKNOWN_FAILURE_CASCADE = "UNKNOWN_FAILURE_CASCADE"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"

    # Temporal
    STALE_DOCUMENTATION = "STALE_DOCUMENTATION"
    VAGUE_FUTURE_REFERENCE = "VAGUE_FUTURE_REFERENCE"
    UNTRACKED_CHANGE = "UNTRACKED_CHANGE"

    # Contradictions
    NUMERIC_CONTRADICTION = "NUMERIC_CONTRADICTION"
    FACTUAL_CONTRADICTION = "FACTUAL_CONTRADICTION"
    STATUS_CONTRADICTION = "STATUS_CONTRADICTION"

    # Onboarding
    UNDEFINED_TERM = "UNDEFINED_TERM"
    ASSUMED_CONTEXT = "ASSUMED_CONTEXT"
    MISSING_PREREQUISITE = "MISSING_PREREQUISITE"


class GapSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Gap:
    """A detected knowledge gap"""
    id: str
    gap_type: GapType
    severity: GapSeverity
    title: str
    description: str
    evidence: List[str] = field(default_factory=list)
    affected_entities: List[str] = field(default_factory=list)  # Entity IDs
    source_docs: List[str] = field(default_factory=list)  # Doc IDs
    suggested_respondent: Optional[str] = None
    related_gaps: List[str] = field(default_factory=list)
    confidence: float = 0.8
    metadata: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "gap_type": self.gap_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "affected_entities": self.affected_entities,
            "source_docs": self.source_docs,
            "suggested_respondent": self.suggested_respondent,
            "related_gaps": self.related_gaps,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "detected_at": self.detected_at
        }


# =============================================================================
# BASE ANALYZER
# =============================================================================

class BaseAnalyzer:
    """Base class for gap analyzers"""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.gaps: List[Gap] = []
        self._gap_counter = 0

    def analyze(self) -> List[Gap]:
        """Run analysis and return detected gaps"""
        raise NotImplementedError

    def _create_gap(
        self,
        gap_type: GapType,
        severity: GapSeverity,
        title: str,
        description: str,
        **kwargs
    ) -> Gap:
        """Helper to create a gap with auto-generated ID"""
        self._gap_counter += 1
        gap_id = f"{self.__class__.__name__}_{gap_type.value}_{self._gap_counter}"

        return Gap(
            id=gap_id,
            gap_type=gap_type,
            severity=severity,
            title=title,
            description=description,
            **kwargs
        )


# =============================================================================
# ANALYZER 1: BUS FACTOR
# =============================================================================

class BusFactorAnalyzer(BaseAnalyzer):
    """
    Detects single points of failure where knowledge/ownership
    is concentrated in one person.
    """

    # Criticality thresholds
    CRITICAL_OWNERSHIP_THRESHOLD = 3  # If person owns 3+ critical items
    HIGH_TENURE_YEARS = 3  # Long tenure increases bus factor risk

    def analyze(self) -> List[Gap]:
        logger.info("[BusFactorAnalyzer] Running analysis...")
        self.gaps = []

        # Get all people
        people = self.graph.get_entities_by_type(EntityType.PERSON)

        for person in people:
            owned_items = self.graph.get_entities_owned_by(person.id)

            if not owned_items:
                continue

            # Check for critical systems/processes with single owner
            critical_owned = [
                item for item in owned_items
                if item.attributes.get("criticality") in ("high", "critical")
                or item.entity_type in (EntityType.SYSTEM, EntityType.DATABASE, EntityType.SERVICE)
            ]

            for item in critical_owned:
                # Check if there's a backup owner
                all_owners = self.graph.get_owners_of(item.id)
                knowledgeable_people = self.graph.get_people_who_know_about(item.id)

                unique_people = set(o.id for o in all_owners) | set(k.id for k in knowledgeable_people)
                unique_people.discard(person.id)  # Exclude the primary owner

                if len(unique_people) == 0:
                    # Critical bus factor - no backup
                    self.gaps.append(self._create_gap(
                        gap_type=GapType.CRITICAL_BUS_FACTOR,
                        severity=GapSeverity.CRITICAL,
                        title=f"Single point of failure: {person.name} → {item.name}",
                        description=(
                            f"{person.name} is the only person with ownership/knowledge of {item.name}. "
                            f"If {person.name} becomes unavailable, there is no documented backup."
                        ),
                        evidence=[f"Mentioned in: {', '.join(item.source_docs)}"],
                        affected_entities=[person.id, item.id],
                        source_docs=list(item.source_docs),
                        suggested_respondent=person.name,
                        metadata={
                            "owner": person.name,
                            "owned_item": item.name,
                            "item_type": item.entity_type.value,
                            "backup_count": 0
                        }
                    ))

            # Check for knowledge concentration
            if len(owned_items) >= self.CRITICAL_OWNERSHIP_THRESHOLD:
                self.gaps.append(self._create_gap(
                    gap_type=GapType.KNOWLEDGE_CONCENTRATION,
                    severity=GapSeverity.HIGH,
                    title=f"Knowledge concentration: {person.name} owns {len(owned_items)} items",
                    description=(
                        f"{person.name} is responsible for {len(owned_items)} different systems/processes: "
                        f"{', '.join(item.name for item in owned_items[:5])}{'...' if len(owned_items) > 5 else ''}. "
                        f"This concentration increases organizational risk."
                    ),
                    evidence=[f"{item.name} ({item.entity_type.value})" for item in owned_items],
                    affected_entities=[person.id] + [item.id for item in owned_items],
                    suggested_respondent=person.name,
                    metadata={
                        "owner": person.name,
                        "owned_count": len(owned_items),
                        "owned_items": [item.name for item in owned_items]
                    }
                ))

        logger.info(f"[BusFactorAnalyzer] Found {len(self.gaps)} gaps")
        return self.gaps


# =============================================================================
# ANALYZER 2: DECISION ARCHAEOLOGY
# =============================================================================

class DecisionArchaeologyAnalyzer(BaseAnalyzer):
    """
    Analyzes decisions for missing context:
    - Missing rationale (why)
    - Missing alternatives considered
    - Unclear decision makers
    - Stale decisions that should be revisited
    """

    def analyze(self) -> List[Gap]:
        logger.info("[DecisionArchaeologyAnalyzer] Running analysis...")
        self.gaps = []

        # Get all decisions
        decisions = self.graph.get_entities_by_type(EntityType.DECISION)

        for decision in decisions:
            attrs = decision.attributes

            # Check for missing rationale
            why_quality = attrs.get("why_quality", "missing")
            if why_quality in ("missing", "vague"):
                self.gaps.append(self._create_gap(
                    gap_type=GapType.MISSING_RATIONALE,
                    severity=GapSeverity.HIGH if why_quality == "missing" else GapSeverity.MEDIUM,
                    title=f"Missing rationale: {decision.name[:50]}...",
                    description=(
                        f"The decision '{decision.description or decision.name}' lacks clear documentation "
                        f"of WHY it was made. Understanding the rationale is critical for future decision-making."
                    ),
                    affected_entities=[decision.id],
                    source_docs=list(decision.source_docs),
                    metadata={
                        "decision": decision.name,
                        "why_quality": why_quality,
                        "current_why": attrs.get("why")
                    }
                ))

            # Check for missing alternatives
            alternatives = attrs.get("alternatives", [])
            alt_quality = attrs.get("alternatives_quality", "missing")
            if alt_quality == "missing" or not alternatives:
                self.gaps.append(self._create_gap(
                    gap_type=GapType.NO_ALTERNATIVES_DOCUMENTED,
                    severity=GapSeverity.MEDIUM,
                    title=f"No alternatives documented: {decision.name[:50]}...",
                    description=(
                        f"The decision '{decision.description or decision.name}' doesn't document "
                        f"what alternatives were considered. This context is valuable for understanding "
                        f"trade-offs and revisiting decisions."
                    ),
                    affected_entities=[decision.id],
                    source_docs=list(decision.source_docs),
                    metadata={
                        "decision": decision.name,
                        "alternatives_quality": alt_quality
                    }
                ))

            # Check for unclear decision maker
            # Look for DECIDED_BY relationships
            decision_makers = []
            for rel in self.graph.get_relationships_for_entity(decision.id, "incoming"):
                if rel.relationship_type == RelationshipType.DECIDED_BY:
                    maker = self.graph.get_entity(rel.target_id)
                    if maker:
                        decision_makers.append(maker)

            if not decision_makers:
                self.gaps.append(self._create_gap(
                    gap_type=GapType.UNCLEAR_DECISION_MAKER,
                    severity=GapSeverity.MEDIUM,
                    title=f"Unclear decision maker: {decision.name[:50]}...",
                    description=(
                        f"The decision '{decision.description or decision.name}' doesn't clearly document "
                        f"who made the decision. This makes it unclear who to consult for context."
                    ),
                    affected_entities=[decision.id],
                    source_docs=list(decision.source_docs),
                    metadata={
                        "decision": decision.name
                    }
                ))

            # Check for high-stakes undocumented decisions
            reversibility = attrs.get("reversibility", "unknown")
            if reversibility == "low" and why_quality in ("missing", "vague"):
                self.gaps.append(self._create_gap(
                    gap_type=GapType.HIGH_STAKES_UNDOCUMENTED,
                    severity=GapSeverity.CRITICAL,
                    title=f"High-stakes decision poorly documented: {decision.name[:50]}...",
                    description=(
                        f"The decision '{decision.description or decision.name}' is marked as "
                        f"low reversibility (hard to undo) but lacks proper documentation of rationale "
                        f"and alternatives. This is a critical documentation gap."
                    ),
                    affected_entities=[decision.id],
                    source_docs=list(decision.source_docs),
                    metadata={
                        "decision": decision.name,
                        "reversibility": reversibility,
                        "why_quality": why_quality
                    }
                ))

        logger.info(f"[DecisionArchaeologyAnalyzer] Found {len(self.gaps)} gaps")
        return self.gaps


# =============================================================================
# ANALYZER 3: PROCESS COMPLETENESS
# =============================================================================

class ProcessCompletenessAnalyzer(BaseAnalyzer):
    """
    Analyzes processes for documentation completeness:
    - Missing steps
    - Missing edge cases
    - Missing failure handling
    - Unverified processes
    """

    def analyze(self) -> List[Gap]:
        logger.info("[ProcessCompletenessAnalyzer] Running analysis...")
        self.gaps = []

        # Get all processes
        processes = self.graph.get_entities_by_type(EntityType.PROCESS)

        for process in processes:
            attrs = process.attributes
            criticality = attrs.get("criticality", "medium")

            # Calculate completeness score
            completeness = 0
            total_aspects = 4

            steps_documented = attrs.get("steps_documented", False)
            edge_cases_documented = attrs.get("edge_cases_documented", False)
            failure_handling_documented = attrs.get("failure_handling_documented", False)

            if steps_documented:
                completeness += 1
            if edge_cases_documented:
                completeness += 1
            if failure_handling_documented:
                completeness += 1

            # Check for backup owner
            owners = self.graph.get_owners_of(process.id)
            has_backup = len(owners) > 1
            if has_backup:
                completeness += 1

            completeness_score = completeness / total_aspects

            # Determine severity based on criticality and completeness
            if criticality in ("critical", "high") and completeness_score < 0.5:
                severity = GapSeverity.CRITICAL
            elif criticality in ("critical", "high") and completeness_score < 0.75:
                severity = GapSeverity.HIGH
            elif completeness_score < 0.5:
                severity = GapSeverity.MEDIUM
            else:
                severity = GapSeverity.LOW

            # Report incomplete critical processes
            if completeness_score < 1.0 and criticality in ("critical", "high"):
                missing = []
                if not steps_documented:
                    missing.append("steps")
                if not edge_cases_documented:
                    missing.append("edge cases")
                if not failure_handling_documented:
                    missing.append("failure handling")
                if not has_backup:
                    missing.append("backup owner")

                self.gaps.append(self._create_gap(
                    gap_type=GapType.INCOMPLETE_CRITICAL_PROCESS,
                    severity=severity,
                    title=f"Incomplete {criticality} process: {process.name}",
                    description=(
                        f"The {criticality}-criticality process '{process.name}' is only "
                        f"{completeness_score*100:.0f}% documented. Missing: {', '.join(missing)}."
                    ),
                    affected_entities=[process.id],
                    source_docs=list(process.source_docs),
                    suggested_respondent=owners[0].name if owners else None,
                    metadata={
                        "process": process.name,
                        "criticality": criticality,
                        "completeness_score": completeness_score,
                        "missing": missing,
                        "owner": owners[0].name if owners else None
                    }
                ))

            # Specific gaps for missing components
            if not steps_documented:
                self.gaps.append(self._create_gap(
                    gap_type=GapType.UNDOCUMENTED_STEPS,
                    severity=GapSeverity.HIGH if criticality in ("critical", "high") else GapSeverity.MEDIUM,
                    title=f"Process steps not documented: {process.name}",
                    description=(
                        f"The process '{process.name}' does not have documented steps. "
                        f"New team members cannot follow this process without verbal guidance."
                    ),
                    affected_entities=[process.id],
                    source_docs=list(process.source_docs),
                    suggested_respondent=owners[0].name if owners else None,
                    metadata={"process": process.name, "criticality": criticality}
                ))

            if not edge_cases_documented and criticality in ("critical", "high"):
                self.gaps.append(self._create_gap(
                    gap_type=GapType.MISSING_EDGE_CASES,
                    severity=GapSeverity.HIGH,
                    title=f"Edge cases not documented: {process.name}",
                    description=(
                        f"The {criticality} process '{process.name}' does not document edge cases. "
                        f"When unusual situations arise, there's no guidance on how to handle them."
                    ),
                    affected_entities=[process.id],
                    source_docs=list(process.source_docs),
                    suggested_respondent=owners[0].name if owners else None,
                    metadata={"process": process.name, "criticality": criticality}
                ))

            if not failure_handling_documented and criticality in ("critical", "high"):
                self.gaps.append(self._create_gap(
                    gap_type=GapType.MISSING_FAILURE_HANDLING,
                    severity=GapSeverity.CRITICAL if criticality == "critical" else GapSeverity.HIGH,
                    title=f"Failure handling not documented: {process.name}",
                    description=(
                        f"The {criticality} process '{process.name}' does not document what to do "
                        f"when things go wrong. This is dangerous for critical processes."
                    ),
                    affected_entities=[process.id],
                    source_docs=list(process.source_docs),
                    suggested_respondent=owners[0].name if owners else None,
                    metadata={"process": process.name, "criticality": criticality}
                ))

        logger.info(f"[ProcessCompletenessAnalyzer] Found {len(self.gaps)} gaps")
        return self.gaps


# =============================================================================
# ANALYZER 4: TRIBAL KNOWLEDGE
# =============================================================================

class TribalKnowledgeAnalyzer(BaseAnalyzer):
    """
    Detects knowledge that is locked in individuals' heads
    based on knowledge signals like "ask John" or "as everyone knows".
    """

    def __init__(self, graph: KnowledgeGraph, extractions: List[DocumentExtraction]):
        super().__init__(graph)
        self.extractions = extractions

    def analyze(self) -> List[Gap]:
        logger.info("[TribalKnowledgeAnalyzer] Running analysis...")
        self.gaps = []

        # Collect all knowledge signals from extractions
        tribal_signals: Dict[str, List[KnowledgeSignal]] = defaultdict(list)

        for extraction in self.extractions:
            for signal in extraction.knowledge_signals:
                if signal.signal_type == SignalType.TRIBAL_KNOWLEDGE:
                    if signal.referenced_person:
                        tribal_signals[signal.referenced_person].append(signal)

        # Create gaps for tribal knowledge
        for person_name, signals in tribal_signals.items():
            topics = set(s.topic for s in signals if s.topic)
            evidence = [s.text for s in signals]

            # Find the person in the graph
            person_entity = self.graph.find_entity_by_name(person_name)

            self.gaps.append(self._create_gap(
                gap_type=GapType.KNOWLEDGE_LOCKED_IN_PERSON,
                severity=GapSeverity.HIGH if len(signals) > 1 else GapSeverity.MEDIUM,
                title=f"Knowledge locked in {person_name}'s head",
                description=(
                    f"Documents reference {person_name} as the go-to person for: "
                    f"{', '.join(topics) if topics else 'unspecified topics'}. "
                    f"This knowledge needs to be documented."
                ),
                evidence=evidence[:5],  # Limit evidence
                affected_entities=[person_entity.id] if person_entity else [],
                suggested_respondent=person_name,
                metadata={
                    "person": person_name,
                    "topics": list(topics),
                    "signal_count": len(signals)
                }
            ))

        # Check for ASSUMED_CONTEXT signals
        for extraction in self.extractions:
            for signal in extraction.knowledge_signals:
                if signal.signal_type == SignalType.ASSUMED_CONTEXT:
                    self.gaps.append(self._create_gap(
                        gap_type=GapType.ASSUMED_CONTEXT,
                        severity=GapSeverity.MEDIUM,
                        title=f"Assumed context: {signal.topic or 'unspecified'}",
                        description=(
                            f"Document assumes knowledge: '{signal.text}'. "
                            f"This creates an onboarding barrier for new team members."
                        ),
                        evidence=[signal.text],
                        source_docs=[extraction.doc_id],
                        metadata={
                            "topic": signal.topic,
                            "doc_id": extraction.doc_id
                        }
                    ))

        logger.info(f"[TribalKnowledgeAnalyzer] Found {len(self.gaps)} gaps")
        return self.gaps


# =============================================================================
# ANALYZER 5: DEPENDENCY RISK
# =============================================================================

class DependencyRiskAnalyzer(BaseAnalyzer):
    """
    Analyzes system dependencies for risks:
    - Undocumented dependencies
    - Unknown failure cascades
    - Circular dependencies
    """

    def analyze(self) -> List[Gap]:
        logger.info("[DependencyRiskAnalyzer] Running analysis...")
        self.gaps = []

        # Get all systems
        systems = self.graph.get_entities_by_type(EntityType.SYSTEM)
        systems.extend(self.graph.get_entities_by_type(EntityType.SERVICE))
        systems.extend(self.graph.get_entities_by_type(EntityType.DATABASE))

        for system in systems:
            deps = self.graph.get_dependencies(system.id)

            # Check downstream dependencies
            for dep in deps["downstream"]:
                # Find the relationship
                for rel in self.graph.get_relationships_for_entity(system.id, "outgoing"):
                    if rel.target_id == dep.id:
                        if not rel.attributes.get("documented_impact", False):
                            self.gaps.append(self._create_gap(
                                gap_type=GapType.UNDOCUMENTED_DEPENDENCY,
                                severity=GapSeverity.MEDIUM,
                                title=f"Undocumented dependency impact: {system.name} → {dep.name}",
                                description=(
                                    f"{system.name} depends on {dep.name}, but the impact of this "
                                    f"dependency is not documented. What happens if {dep.name} fails?"
                                ),
                                affected_entities=[system.id, dep.id],
                                source_docs=list(rel.source_docs),
                                metadata={
                                    "source": system.name,
                                    "target": dep.name,
                                    "relationship": rel.relationship_type.value
                                }
                            ))

                        failure_impact = rel.attributes.get("failure_impact")
                        if not failure_impact:
                            self.gaps.append(self._create_gap(
                                gap_type=GapType.UNKNOWN_FAILURE_CASCADE,
                                severity=GapSeverity.HIGH,
                                title=f"Unknown failure cascade: {system.name} → {dep.name}",
                                description=(
                                    f"If {dep.name} fails, it's unclear what happens to {system.name}. "
                                    f"Document the failure mode and recovery procedure."
                                ),
                                affected_entities=[system.id, dep.id],
                                source_docs=list(rel.source_docs),
                                metadata={
                                    "source": system.name,
                                    "target": dep.name
                                }
                            ))

        # Check for circular dependencies (simplified)
        self._detect_circular_dependencies(systems)

        logger.info(f"[DependencyRiskAnalyzer] Found {len(self.gaps)} gaps")
        return self.gaps

    def _detect_circular_dependencies(self, systems: List[Entity]):
        """Detect circular dependency chains"""
        # Build adjacency list
        adj: Dict[str, Set[str]] = defaultdict(set)

        for system in systems:
            deps = self.graph.get_dependencies(system.id)
            for dep in deps["downstream"]:
                adj[system.id].add(dep.id)

        # DFS to find cycles
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    result = dfs(neighbor, path)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

            path.pop()
            rec_stack.remove(node)
            return None

        for system in systems:
            if system.id not in visited:
                cycle = dfs(system.id, [])
                if cycle:
                    cycle_names = [self.graph.get_entity(eid).name for eid in cycle if self.graph.get_entity(eid)]
                    self.gaps.append(self._create_gap(
                        gap_type=GapType.CIRCULAR_DEPENDENCY,
                        severity=GapSeverity.HIGH,
                        title=f"Circular dependency detected",
                        description=(
                            f"Circular dependency chain: {' → '.join(cycle_names)}. "
                            f"This can cause cascading failures and makes the system fragile."
                        ),
                        affected_entities=cycle,
                        metadata={"cycle": cycle_names}
                    ))


# =============================================================================
# ANALYZER 6: TEMPORAL STALENESS
# =============================================================================

class TemporalStalenessAnalyzer(BaseAnalyzer):
    """
    Detects potentially stale or outdated documentation.
    """

    def __init__(self, graph: KnowledgeGraph, extractions: List[DocumentExtraction]):
        super().__init__(graph)
        self.extractions = extractions

    def analyze(self) -> List[Gap]:
        logger.info("[TemporalStalenessAnalyzer] Running analysis...")
        self.gaps = []

        for extraction in self.extractions:
            health = extraction.document_health
            staleness = health.staleness_risk

            if staleness in ("high", "critical"):
                self.gaps.append(self._create_gap(
                    gap_type=GapType.STALE_DOCUMENTATION,
                    severity=GapSeverity.HIGH if staleness == "critical" else GapSeverity.MEDIUM,
                    title=f"Potentially stale documentation: {extraction.title}",
                    description=(
                        f"The document '{extraction.title}' appears to be outdated "
                        f"(staleness risk: {staleness}). Last updated: {health.last_updated or 'unknown'}. "
                        f"Review and update if necessary."
                    ),
                    source_docs=[extraction.doc_id],
                    metadata={
                        "doc_title": extraction.title,
                        "staleness_risk": staleness,
                        "last_updated": health.last_updated
                    }
                ))

            # Check for vague future references
            for marker in extraction.temporal_markers:
                if marker.marker_type == "future_plan" and not marker.approximate_date:
                    self.gaps.append(self._create_gap(
                        gap_type=GapType.VAGUE_FUTURE_REFERENCE,
                        severity=GapSeverity.LOW,
                        title=f"Vague future reference: {marker.what_changed or 'unspecified'}",
                        description=(
                            f"Document mentions a future plan without timeline: '{marker.text}'. "
                            f"Consider adding specific dates or milestones."
                        ),
                        evidence=[marker.text],
                        source_docs=[extraction.doc_id],
                        metadata={
                            "what": marker.what_changed,
                            "doc_id": extraction.doc_id
                        }
                    ))

        logger.info(f"[TemporalStalenessAnalyzer] Found {len(self.gaps)} gaps")
        return self.gaps


# =============================================================================
# ANALYZER 7: CONTRADICTION DETECTOR
# =============================================================================

class ContradictionDetector(BaseAnalyzer):
    """
    Detects contradictions across documents.
    """

    def __init__(self, graph: KnowledgeGraph, extractions: List[DocumentExtraction]):
        super().__init__(graph)
        self.extractions = extractions

    def analyze(self) -> List[Gap]:
        logger.info("[ContradictionDetector] Running analysis...")
        self.gaps = []

        # Collect facts by entity
        facts_by_entity: Dict[str, List[Dict]] = defaultdict(list)

        for extraction in self.extractions:
            for entity in extraction.entities:
                if entity.description:
                    facts_by_entity[entity.name.lower()].append({
                        "doc_id": extraction.doc_id,
                        "doc_title": extraction.title,
                        "description": entity.description,
                        "role": entity.role
                    })

        # Look for contradictions (simplified - just check different descriptions)
        for entity_name, facts in facts_by_entity.items():
            if len(facts) < 2:
                continue

            descriptions = set()
            for fact in facts:
                if fact["description"]:
                    descriptions.add(fact["description"])

            # If very different descriptions exist, flag as potential contradiction
            if len(descriptions) > 1:
                # Check if descriptions are significantly different
                desc_list = list(descriptions)
                for i in range(len(desc_list)):
                    for j in range(i + 1, len(desc_list)):
                        # Simple heuristic: if descriptions share few words, might be contradiction
                        words1 = set(desc_list[i].lower().split())
                        words2 = set(desc_list[j].lower().split())
                        overlap = len(words1 & words2) / max(len(words1 | words2), 1)

                        if overlap < 0.3:  # Less than 30% word overlap
                            relevant_facts = [f for f in facts if f["description"] in (desc_list[i], desc_list[j])]

                            self.gaps.append(self._create_gap(
                                gap_type=GapType.FACTUAL_CONTRADICTION,
                                severity=GapSeverity.MEDIUM,
                                title=f"Potential contradiction: {entity_name}",
                                description=(
                                    f"Different documents describe '{entity_name}' differently:\n"
                                    f"- Doc '{relevant_facts[0]['doc_title']}': {desc_list[i][:100]}...\n"
                                    f"- Doc '{relevant_facts[1]['doc_title']}': {desc_list[j][:100]}..."
                                ),
                                evidence=[desc_list[i], desc_list[j]],
                                source_docs=[f["doc_id"] for f in relevant_facts],
                                metadata={
                                    "entity": entity_name,
                                    "descriptions": [desc_list[i], desc_list[j]]
                                }
                            ))

        logger.info(f"[ContradictionDetector] Found {len(self.gaps)} gaps")
        return self.gaps


# =============================================================================
# ANALYZER 8: ONBOARDING BARRIER
# =============================================================================

class OnboardingBarrierAnalyzer(BaseAnalyzer):
    """
    Detects barriers to onboarding:
    - Undefined terms
    - Assumed context
    - Missing prerequisites
    """

    def __init__(self, graph: KnowledgeGraph, extractions: List[DocumentExtraction]):
        super().__init__(graph)
        self.extractions = extractions

    def analyze(self) -> List[Gap]:
        logger.info("[OnboardingBarrierAnalyzer] Running analysis...")
        self.gaps = []

        # Collect all defined concepts
        defined_concepts = set()
        for entity in self.graph.get_entities_by_type(EntityType.CONCEPT):
            defined_concepts.add(entity.name.lower())
            for alias in entity.aliases:
                defined_concepts.add(alias.lower())

        # Look for assumed context signals
        for extraction in self.extractions:
            for signal in extraction.knowledge_signals:
                if signal.signal_type == SignalType.ASSUMED_CONTEXT:
                    self.gaps.append(self._create_gap(
                        gap_type=GapType.ASSUMED_CONTEXT,
                        severity=GapSeverity.MEDIUM,
                        title=f"Assumed context in {extraction.title}",
                        description=(
                            f"Document assumes reader knowledge: '{signal.text}'. "
                            f"New team members may not understand this context."
                        ),
                        evidence=[signal.text],
                        source_docs=[extraction.doc_id],
                        metadata={
                            "topic": signal.topic,
                            "doc_title": extraction.title
                        }
                    ))

                if signal.signal_type == SignalType.UNDOCUMENTED_PROCESS:
                    self.gaps.append(self._create_gap(
                        gap_type=GapType.MISSING_PREREQUISITE,
                        severity=GapSeverity.MEDIUM,
                        title=f"Undocumented prerequisite: {signal.topic or 'process'}",
                        description=(
                            f"Document references an undocumented process: '{signal.text}'. "
                            f"This should be documented for newcomers."
                        ),
                        evidence=[signal.text],
                        source_docs=[extraction.doc_id],
                        metadata={
                            "topic": signal.topic,
                            "doc_title": extraction.title
                        }
                    ))

        logger.info(f"[OnboardingBarrierAnalyzer] Found {len(self.gaps)} gaps")
        return self.gaps


# =============================================================================
# GAP ANALYZER ENGINE
# =============================================================================

class GapAnalyzerEngine:
    """
    Orchestrates all gap analyzers and returns consolidated results.
    """

    def __init__(self, graph: KnowledgeGraph, extractions: List[DocumentExtraction]):
        self.graph = graph
        self.extractions = extractions
        self.all_gaps: List[Gap] = []

    def analyze_all(self) -> List[Gap]:
        """Run all analyzers and return all detected gaps"""
        logger.info("[GapAnalyzerEngine] Running all analyzers...")

        analyzers = [
            BusFactorAnalyzer(self.graph),
            DecisionArchaeologyAnalyzer(self.graph),
            ProcessCompletenessAnalyzer(self.graph),
            TribalKnowledgeAnalyzer(self.graph, self.extractions),
            DependencyRiskAnalyzer(self.graph),
            TemporalStalenessAnalyzer(self.graph, self.extractions),
            ContradictionDetector(self.graph, self.extractions),
            OnboardingBarrierAnalyzer(self.graph, self.extractions),
        ]

        self.all_gaps = []
        for analyzer in analyzers:
            gaps = analyzer.analyze()
            self.all_gaps.extend(gaps)

        # Deduplicate similar gaps
        self.all_gaps = self._deduplicate_gaps(self.all_gaps)

        logger.info(f"[GapAnalyzerEngine] Total gaps detected: {len(self.all_gaps)}")
        return self.all_gaps

    def _deduplicate_gaps(self, gaps: List[Gap]) -> List[Gap]:
        """Remove duplicate or very similar gaps"""
        seen_titles = set()
        unique_gaps = []

        for gap in gaps:
            # Simple dedup by title similarity
            title_key = gap.title.lower()[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_gaps.append(gap)

        return unique_gaps

    def get_gaps_by_type(self, gap_type: GapType) -> List[Gap]:
        """Get gaps filtered by type"""
        return [g for g in self.all_gaps if g.gap_type == gap_type]

    def get_gaps_by_severity(self, severity: GapSeverity) -> List[Gap]:
        """Get gaps filtered by severity"""
        return [g for g in self.all_gaps if g.severity == severity]

    def get_stats(self) -> Dict[str, Any]:
        """Get analysis statistics"""
        by_type = defaultdict(int)
        by_severity = defaultdict(int)

        for gap in self.all_gaps:
            by_type[gap.gap_type.value] += 1
            by_severity[gap.severity.value] += 1

        return {
            "total_gaps": len(self.all_gaps),
            "by_type": dict(by_type),
            "by_severity": dict(by_severity)
        }
