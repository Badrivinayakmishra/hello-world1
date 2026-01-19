"""
Stage 2: Knowledge Graph Assembly
=================================

Builds a rich, queryable knowledge graph from extracted document information.
Supports entity resolution, relationship inference, and graph queries.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum
import hashlib
import json

from .deep_extractor import (
    DocumentExtraction, ExtractedEntity, ExtractedDecision,
    ExtractedProcess, ExtractedDependency, KnowledgeSignal,
    EntityType, SignalType
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class RelationshipType(str, Enum):
    # Ownership/Responsibility
    OWNS = "OWNS"
    MANAGES = "MANAGES"
    MAINTAINS = "MAINTAINS"
    CREATED = "CREATED"

    # Knowledge/Expertise
    KNOWS_ABOUT = "KNOWS_ABOUT"
    EXPERT_IN = "EXPERT_IN"
    TRAINED_ON = "TRAINED_ON"

    # System relationships
    DEPENDS_ON = "DEPENDS_ON"
    USES = "USES"
    CALLS = "CALLS"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"
    INTEGRATES_WITH = "INTEGRATES_WITH"

    # Decision relationships
    DECIDED_BY = "DECIDED_BY"
    APPROVED_BY = "APPROVED_BY"
    IMPACTS = "IMPACTS"
    REPLACED_BY = "REPLACED_BY"

    # Documentation
    DOCUMENTED_IN = "DOCUMENTED_IN"
    MENTIONED_IN = "MENTIONED_IN"

    # Team relationships
    MEMBER_OF = "MEMBER_OF"
    REPORTS_TO = "REPORTS_TO"
    COLLABORATES_WITH = "COLLABORATES_WITH"

    # Process relationships
    EXECUTES = "EXECUTES"
    INPUT_TO = "INPUT_TO"
    OUTPUT_OF = "OUTPUT_OF"


@dataclass
class Entity:
    """A node in the knowledge graph"""
    id: str
    name: str
    canonical_name: str
    entity_type: EntityType
    description: Optional[str] = None
    role: Optional[str] = None
    aliases: Set[str] = field(default_factory=set)
    source_docs: Set[str] = field(default_factory=set)
    mention_count: int = 0
    confidence: float = 0.8
    attributes: Dict[str, Any] = field(default_factory=dict)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type.value if isinstance(self.entity_type, Enum) else self.entity_type,
            "description": self.description,
            "role": self.role,
            "aliases": list(self.aliases),
            "source_docs": list(self.source_docs),
            "mention_count": self.mention_count,
            "confidence": self.confidence,
            "attributes": self.attributes,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen
        }


@dataclass
class Relationship:
    """An edge in the knowledge graph"""
    id: str
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    confidence: float = 0.8
    evidence: List[str] = field(default_factory=list)
    source_docs: Set[str] = field(default_factory=set)
    attributes: Dict[str, Any] = field(default_factory=dict)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type.value if isinstance(self.relationship_type, Enum) else self.relationship_type,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_docs": list(self.source_docs),
            "attributes": self.attributes,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen
        }


# =============================================================================
# ENTITY RESOLVER
# =============================================================================

class EntityResolver:
    """Resolves and merges similar entities"""

    # Common name variations to normalize
    TITLES = {"mr", "ms", "mrs", "dr", "prof", "sir"}
    SUFFIXES = {"jr", "sr", "ii", "iii", "phd", "md"}

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.canonical_map: Dict[str, str] = {}  # normalized -> canonical

    def normalize_name(self, name: str) -> str:
        """Normalize a name for comparison"""
        name = name.lower().strip()

        # Remove titles
        words = name.split()
        words = [w for w in words if w.rstrip('.') not in self.TITLES]

        # Remove suffixes
        words = [w for w in words if w.rstrip('.') not in self.SUFFIXES]

        # Handle email addresses
        if '@' in name:
            local_part = name.split('@')[0]
            # john.smith@company.com -> john smith
            name = local_part.replace('.', ' ').replace('_', ' ')
            words = name.split()

        return ' '.join(words).strip()

    def are_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar enough to be the same entity"""
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)

        # Exact match after normalization
        if norm1 == norm2:
            return True

        # Check if one is abbreviation of other
        if self._is_abbreviation(norm1, norm2) or self._is_abbreviation(norm2, norm1):
            return True

        # Sequence matching
        ratio = SequenceMatcher(None, norm1, norm2).ratio()
        return ratio >= self.similarity_threshold

    def _is_abbreviation(self, short: str, long: str) -> bool:
        """Check if short is an abbreviation of long (e.g., 'J. Smith' for 'John Smith')"""
        short_words = short.split()
        long_words = long.split()

        if len(short_words) != len(long_words):
            return False

        for s, l in zip(short_words, long_words):
            # Allow single letter abbreviation
            if len(s) == 1 and l.startswith(s):
                continue
            # Allow initial with period
            if len(s) == 2 and s.endswith('.') and l.startswith(s[0]):
                continue
            # Must match
            if s != l:
                return False

        return True

    def get_canonical(self, name: str, entity_type: EntityType) -> str:
        """Get or create canonical name for an entity"""
        normalized = self.normalize_name(name)
        key = f"{entity_type.value}:{normalized}"

        if key in self.canonical_map:
            return self.canonical_map[key]

        # Check for similar existing entries
        for existing_key, canonical in self.canonical_map.items():
            if existing_key.startswith(f"{entity_type.value}:"):
                existing_norm = existing_key.split(":", 1)[1]
                if self.are_similar(normalized, existing_norm):
                    self.canonical_map[key] = canonical
                    return canonical

        # Create new canonical entry
        # Use the longest version as canonical (has most info)
        self.canonical_map[key] = name
        return name


# =============================================================================
# KNOWLEDGE GRAPH
# =============================================================================

class KnowledgeGraph:
    """
    A queryable knowledge graph built from document extractions.
    """

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relationships: Dict[str, Relationship] = {}
        self.entity_resolver = EntityResolver()

        # Indexes for fast lookup
        self._entities_by_type: Dict[EntityType, Set[str]] = defaultdict(set)
        self._entities_by_name: Dict[str, Set[str]] = defaultdict(set)
        self._relationships_by_source: Dict[str, Set[str]] = defaultdict(set)
        self._relationships_by_target: Dict[str, Set[str]] = defaultdict(set)
        self._relationships_by_type: Dict[RelationshipType, Set[str]] = defaultdict(set)

        # Document tracking
        self._processed_docs: Set[str] = set()

        logger.info("[KnowledgeGraph] Initialized")

    def add_extraction(self, extraction: DocumentExtraction) -> Dict[str, int]:
        """
        Add a document extraction to the graph.

        Returns:
            Stats about what was added
        """
        doc_id = extraction.doc_id
        timestamp = datetime.utcnow().isoformat()
        stats = {"entities": 0, "relationships": 0, "signals_processed": 0}

        if doc_id in self._processed_docs:
            logger.warning(f"[KnowledgeGraph] Document already processed: {doc_id}")

        self._processed_docs.add(doc_id)

        # Add document as entity
        doc_entity = self._add_entity(
            name=extraction.title,
            entity_type=EntityType.CONCEPT,  # Using CONCEPT for documents
            doc_id=doc_id,
            attributes={"is_document": True, "doc_type": extraction.document_type.value}
        )

        # Process extracted entities
        for ext_entity in extraction.entities:
            entity = self._add_entity(
                name=ext_entity.name,
                entity_type=ext_entity.entity_type,
                doc_id=doc_id,
                description=ext_entity.description,
                role=ext_entity.role,
                aliases=set(ext_entity.aliases),
                confidence=ext_entity.confidence
            )
            stats["entities"] += 1

            # Add MENTIONED_IN relationship
            self._add_relationship(
                source_id=entity.id,
                target_id=doc_entity.id,
                rel_type=RelationshipType.MENTIONED_IN,
                doc_id=doc_id,
                evidence=ext_entity.evidence
            )
            stats["relationships"] += 1

        # Process decisions
        for decision in extraction.decisions:
            decision_entity = self._add_entity(
                name=decision.what[:100],  # Truncate long decisions
                entity_type=EntityType.DECISION,
                doc_id=doc_id,
                description=decision.what,
                attributes={
                    "why": decision.why,
                    "why_quality": decision.why_quality,
                    "when": decision.when,
                    "alternatives": decision.alternatives_considered,
                    "reversibility": decision.reversibility,
                    "status": decision.status
                }
            )
            stats["entities"] += 1

            # Link decision makers
            for who in decision.who:
                person_entity = self._add_entity(
                    name=who,
                    entity_type=EntityType.PERSON,
                    doc_id=doc_id
                )
                self._add_relationship(
                    source_id=decision_entity.id,
                    target_id=person_entity.id,
                    rel_type=RelationshipType.DECIDED_BY,
                    doc_id=doc_id,
                    evidence=decision.evidence
                )
                stats["relationships"] += 1

        # Process processes
        for process in extraction.processes:
            process_entity = self._add_entity(
                name=process.name,
                entity_type=EntityType.PROCESS,
                doc_id=doc_id,
                description=process.description,
                attributes={
                    "frequency": process.frequency,
                    "steps_documented": process.steps_documented,
                    "edge_cases_documented": process.edge_cases_documented,
                    "failure_handling_documented": process.failure_handling_documented,
                    "criticality": process.criticality,
                    "automation_level": process.automation_level
                }
            )
            stats["entities"] += 1

            # Link owner
            if process.owner:
                owner_entity = self._add_entity(
                    name=process.owner,
                    entity_type=EntityType.PERSON,
                    doc_id=doc_id
                )
                self._add_relationship(
                    source_id=owner_entity.id,
                    target_id=process_entity.id,
                    rel_type=RelationshipType.OWNS,
                    doc_id=doc_id,
                    evidence=process.evidence
                )
                stats["relationships"] += 1

            # Link backup owner
            if process.backup_owner:
                backup_entity = self._add_entity(
                    name=process.backup_owner,
                    entity_type=EntityType.PERSON,
                    doc_id=doc_id
                )
                self._add_relationship(
                    source_id=backup_entity.id,
                    target_id=process_entity.id,
                    rel_type=RelationshipType.KNOWS_ABOUT,
                    doc_id=doc_id,
                    attributes={"is_backup": True}
                )
                stats["relationships"] += 1

        # Process dependencies
        for dep in extraction.dependencies:
            source_entity = self._add_entity(
                name=dep.source,
                entity_type=EntityType.SYSTEM,
                doc_id=doc_id
            )
            target_entity = self._add_entity(
                name=dep.target,
                entity_type=EntityType.SYSTEM,
                doc_id=doc_id
            )

            rel_type = self._map_dependency_type(dep.dependency_type)
            self._add_relationship(
                source_id=source_entity.id,
                target_id=target_entity.id,
                rel_type=rel_type,
                doc_id=doc_id,
                evidence=dep.evidence,
                attributes={
                    "criticality": dep.criticality,
                    "documented_impact": dep.documented_impact,
                    "failure_impact": dep.failure_impact
                }
            )
            stats["relationships"] += 1

        # Process knowledge signals
        for signal in extraction.knowledge_signals:
            self._process_knowledge_signal(signal, doc_id)
            stats["signals_processed"] += 1

        logger.info(f"[KnowledgeGraph] Added from {doc_id}: "
                   f"{stats['entities']} entities, {stats['relationships']} relationships")

        return stats

    def _add_entity(
        self,
        name: str,
        entity_type: EntityType,
        doc_id: str,
        description: Optional[str] = None,
        role: Optional[str] = None,
        aliases: Set[str] = None,
        confidence: float = 0.8,
        attributes: Dict[str, Any] = None
    ) -> Entity:
        """Add or update an entity in the graph"""
        # Get canonical name
        canonical = self.entity_resolver.get_canonical(name, entity_type)

        # Create entity ID
        entity_id = self._make_entity_id(canonical, entity_type)

        timestamp = datetime.utcnow().isoformat()

        if entity_id in self.entities:
            # Update existing entity
            entity = self.entities[entity_id]
            entity.source_docs.add(doc_id)
            entity.mention_count += 1
            entity.last_seen = timestamp

            if aliases:
                entity.aliases.update(aliases)
            entity.aliases.add(name)  # Add original name as alias

            if description and not entity.description:
                entity.description = description
            if role and not entity.role:
                entity.role = role
            if attributes:
                entity.attributes.update(attributes)

            # Update confidence (take max)
            entity.confidence = max(entity.confidence, confidence)
        else:
            # Create new entity
            entity = Entity(
                id=entity_id,
                name=name,
                canonical_name=canonical,
                entity_type=entity_type,
                description=description,
                role=role,
                aliases=aliases or {name},
                source_docs={doc_id},
                mention_count=1,
                confidence=confidence,
                attributes=attributes or {},
                first_seen=timestamp,
                last_seen=timestamp
            )
            self.entities[entity_id] = entity

            # Update indexes
            self._entities_by_type[entity_type].add(entity_id)
            self._entities_by_name[canonical.lower()].add(entity_id)

        return entity

    def _add_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelationshipType,
        doc_id: str,
        evidence: List[str] = None,
        confidence: float = 0.8,
        attributes: Dict[str, Any] = None
    ) -> Relationship:
        """Add or update a relationship in the graph"""
        # Create relationship ID
        rel_id = self._make_relationship_id(source_id, target_id, rel_type)

        timestamp = datetime.utcnow().isoformat()

        if rel_id in self.relationships:
            # Update existing relationship
            rel = self.relationships[rel_id]
            rel.source_docs.add(doc_id)
            rel.last_seen = timestamp

            if evidence:
                rel.evidence.extend(evidence)
            if attributes:
                rel.attributes.update(attributes)

            # Update confidence (take max)
            rel.confidence = max(rel.confidence, confidence)
        else:
            # Create new relationship
            rel = Relationship(
                id=rel_id,
                source_id=source_id,
                target_id=target_id,
                relationship_type=rel_type,
                confidence=confidence,
                evidence=evidence or [],
                source_docs={doc_id},
                attributes=attributes or {},
                first_seen=timestamp,
                last_seen=timestamp
            )
            self.relationships[rel_id] = rel

            # Update indexes
            self._relationships_by_source[source_id].add(rel_id)
            self._relationships_by_target[target_id].add(rel_id)
            self._relationships_by_type[rel_type].add(rel_id)

        return rel

    def _process_knowledge_signal(self, signal: KnowledgeSignal, doc_id: str):
        """Process a knowledge signal and add relevant relationships"""
        if signal.signal_type == SignalType.TRIBAL_KNOWLEDGE and signal.referenced_person:
            # Add person with KNOWS_ABOUT relationship to topic
            person = self._add_entity(
                name=signal.referenced_person,
                entity_type=EntityType.PERSON,
                doc_id=doc_id,
                attributes={"tribal_knowledge_holder": True}
            )

            if signal.topic:
                topic = self._add_entity(
                    name=signal.topic,
                    entity_type=EntityType.CONCEPT,
                    doc_id=doc_id
                )
                self._add_relationship(
                    source_id=person.id,
                    target_id=topic.id,
                    rel_type=RelationshipType.KNOWS_ABOUT,
                    doc_id=doc_id,
                    evidence=[signal.text],
                    attributes={
                        "signal_type": signal.signal_type.value,
                        "severity": signal.severity,
                        "is_tribal": True
                    }
                )

    def _map_dependency_type(self, dep_type: str) -> RelationshipType:
        """Map dependency type string to RelationshipType"""
        mapping = {
            "uses": RelationshipType.USES,
            "requires": RelationshipType.DEPENDS_ON,
            "calls": RelationshipType.CALLS,
            "reads_from": RelationshipType.READS_FROM,
            "writes_to": RelationshipType.WRITES_TO
        }
        return mapping.get(dep_type, RelationshipType.DEPENDS_ON)

    def _make_entity_id(self, canonical_name: str, entity_type: EntityType) -> str:
        """Create a stable entity ID"""
        key = f"{entity_type.value}:{canonical_name.lower()}"
        return hashlib.md5(key.encode()).hexdigest()[:16]

    def _make_relationship_id(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelationshipType
    ) -> str:
        """Create a stable relationship ID"""
        key = f"{source_id}:{rel_type.value}:{target_id}"
        return hashlib.md5(key.encode()).hexdigest()[:16]

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID"""
        return self.entities.get(entity_id)

    def find_entity_by_name(self, name: str) -> Optional[Entity]:
        """Find entity by name (fuzzy matching)"""
        normalized = self.entity_resolver.normalize_name(name).lower()

        # Direct match
        if normalized in self._entities_by_name:
            entity_ids = self._entities_by_name[normalized]
            if entity_ids:
                return self.entities.get(list(entity_ids)[0])

        # Fuzzy match
        for entity in self.entities.values():
            if self.entity_resolver.are_similar(name, entity.canonical_name):
                return entity

        return None

    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """Get all entities of a specific type"""
        entity_ids = self._entities_by_type.get(entity_type, set())
        return [self.entities[eid] for eid in entity_ids if eid in self.entities]

    def get_relationships_for_entity(
        self,
        entity_id: str,
        direction: str = "both"
    ) -> List[Relationship]:
        """Get all relationships involving an entity"""
        rels = []

        if direction in ("both", "outgoing"):
            for rel_id in self._relationships_by_source.get(entity_id, []):
                if rel_id in self.relationships:
                    rels.append(self.relationships[rel_id])

        if direction in ("both", "incoming"):
            for rel_id in self._relationships_by_target.get(entity_id, []):
                if rel_id in self.relationships:
                    rels.append(self.relationships[rel_id])

        return rels

    def get_entities_owned_by(self, person_entity_id: str) -> List[Entity]:
        """Get all entities owned/managed by a person"""
        owned = []
        ownership_types = {
            RelationshipType.OWNS,
            RelationshipType.MANAGES,
            RelationshipType.MAINTAINS
        }

        for rel_id in self._relationships_by_source.get(person_entity_id, []):
            rel = self.relationships.get(rel_id)
            if rel and rel.relationship_type in ownership_types:
                entity = self.entities.get(rel.target_id)
                if entity:
                    owned.append(entity)

        return owned

    def get_owners_of(self, entity_id: str) -> List[Entity]:
        """Get all people who own/manage an entity"""
        owners = []
        ownership_types = {
            RelationshipType.OWNS,
            RelationshipType.MANAGES,
            RelationshipType.MAINTAINS
        }

        for rel_id in self._relationships_by_target.get(entity_id, []):
            rel = self.relationships.get(rel_id)
            if rel and rel.relationship_type in ownership_types:
                entity = self.entities.get(rel.source_id)
                if entity and entity.entity_type == EntityType.PERSON:
                    owners.append(entity)

        return owners

    def get_dependencies(self, entity_id: str) -> Dict[str, List[Entity]]:
        """Get upstream and downstream dependencies of an entity"""
        upstream = []  # Things that depend on this entity
        downstream = []  # Things this entity depends on

        dependency_types = {
            RelationshipType.DEPENDS_ON,
            RelationshipType.USES,
            RelationshipType.CALLS,
            RelationshipType.READS_FROM,
            RelationshipType.WRITES_TO
        }

        # Downstream: this entity is the source
        for rel_id in self._relationships_by_source.get(entity_id, []):
            rel = self.relationships.get(rel_id)
            if rel and rel.relationship_type in dependency_types:
                entity = self.entities.get(rel.target_id)
                if entity:
                    downstream.append(entity)

        # Upstream: this entity is the target
        for rel_id in self._relationships_by_target.get(entity_id, []):
            rel = self.relationships.get(rel_id)
            if rel and rel.relationship_type in dependency_types:
                entity = self.entities.get(rel.source_id)
                if entity:
                    upstream.append(entity)

        return {"upstream": upstream, "downstream": downstream}

    def get_people_who_know_about(self, entity_id: str) -> List[Entity]:
        """Get people who know about an entity"""
        people = []
        knowledge_types = {
            RelationshipType.KNOWS_ABOUT,
            RelationshipType.EXPERT_IN,
            RelationshipType.TRAINED_ON,
            RelationshipType.OWNS,
            RelationshipType.MANAGES
        }

        for rel_id in self._relationships_by_target.get(entity_id, []):
            rel = self.relationships.get(rel_id)
            if rel and rel.relationship_type in knowledge_types:
                entity = self.entities.get(rel.source_id)
                if entity and entity.entity_type == EntityType.PERSON:
                    people.append(entity)

        return people

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        entity_counts = defaultdict(int)
        for entity in self.entities.values():
            entity_counts[entity.entity_type.value] += 1

        rel_counts = defaultdict(int)
        for rel in self.relationships.values():
            rel_counts[rel.relationship_type.value] += 1

        return {
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
            "documents_processed": len(self._processed_docs),
            "entities_by_type": dict(entity_counts),
            "relationships_by_type": dict(rel_counts)
        }

    def find_isolated_entities(self) -> List[Entity]:
        """Find entities with no relationships"""
        isolated = []
        for entity_id, entity in self.entities.items():
            incoming = len(self._relationships_by_target.get(entity_id, []))
            outgoing = len(self._relationships_by_source.get(entity_id, []))

            if incoming == 0 and outgoing == 0:
                isolated.append(entity)

        return isolated

    def find_single_source_entities(self) -> List[Entity]:
        """Find entities only mentioned in one document"""
        return [e for e in self.entities.values() if len(e.source_docs) == 1]

    def to_dict(self) -> Dict[str, Any]:
        """Export graph to dictionary"""
        return {
            "entities": {eid: e.to_dict() for eid, e in self.entities.items()},
            "relationships": {rid: r.to_dict() for rid, r in self.relationships.items()},
            "stats": self.get_stats()
        }

    def to_json(self) -> str:
        """Export graph to JSON"""
        return json.dumps(self.to_dict(), indent=2)
