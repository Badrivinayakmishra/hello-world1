"""
Intelligent Gap Detection System v2.0
=====================================

Advanced multi-layer gap detection using NLP techniques beyond simple GPT prompting.

Architecture:
- Layer 1: Frame-Based Extraction (DECISION, PROCESS, DEFINITION frames)
- Layer 2: Semantic Role Labeling (missing agents, causes, manners)
- Layer 3: Discourse Analysis (claims without evidence)
- Layer 4: Knowledge Graph (missing entity relations)
- Layer 5: Cross-Document Verification
- Layer 6: Grounded Question Generation

v2.0 Improvements:
- 150+ trigger patterns (up from 50)
- Entity normalization (John = John Smith = J. Smith)
- Rule-based coreference resolution
- Negation handling
- Improved contradiction detection
- Gap deduplication
- Quality scoring

Research foundations:
- Argument Mining (Stab & Gurevych, 2017)
- Frame Semantics (FrameNet, Baker et al.)
- Semantic Role Labeling (AllenNLP)
- Rhetorical Structure Theory (Mann & Thompson)
- Knowledge Graph Completion (TransE/RotatE)
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any
from collections import defaultdict
from datetime import datetime
import hashlib
from difflib import SequenceMatcher

# spaCy is required for NLP processing
import spacy

logger = logging.getLogger(__name__)

# Load spaCy model at module level for efficiency
try:
    NLP = spacy.load("en_core_web_sm")
    logger.info("[IntelligentGapDetector] spaCy en_core_web_sm model loaded")
except OSError:
    raise ImportError(
        "spaCy model 'en_core_web_sm' not found. "
        "Install it with: python -m spacy download en_core_web_sm"
    )


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class FrameSlot:
    """A slot in a frame that may be filled or missing"""
    name: str
    value: Optional[str] = None
    required: bool = True
    source_doc_id: Optional[str] = None
    source_sentence: Optional[str] = None
    confidence: float = 1.0


@dataclass
class Frame:
    """A structured frame representing a concept (decision, process, etc.)"""
    frame_type: str  # DECISION, PROCESS, DEFINITION, EVENT, CONSTRAINT
    trigger: str  # The word/phrase that triggered this frame
    slots: Dict[str, FrameSlot] = field(default_factory=dict)
    source_doc_id: str = ""
    source_sentence: str = ""
    missing_slots: List[str] = field(default_factory=list)
    is_negated: bool = False  # NEW: Track if this is negated


@dataclass
class Entity:
    """An entity in the knowledge graph"""
    id: str
    name: str
    canonical_name: str  # NEW: Normalized name
    entity_type: str  # PERSON, SYSTEM, ORG, CONCEPT, PROCESS, DECISION
    mentions: List[str] = field(default_factory=list)
    documents: Set[str] = field(default_factory=set)
    attributes: Dict[str, Any] = field(default_factory=dict)
    aliases: Set[str] = field(default_factory=set)  # NEW: All name variations


@dataclass
class Relation:
    """A relation between entities"""
    source_entity: str
    target_entity: str
    relation_type: str  # OWNS, MANAGES, USES, DEPENDS_ON, CREATED, DECIDED_BY
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    source_doc_id: Optional[str] = None


@dataclass
class Gap:
    """An identified knowledge gap"""
    gap_type: str  # MISSING_RATIONALE, MISSING_AGENT, MISSING_EVIDENCE, etc.
    description: str
    evidence: List[str]  # Sentences that reveal this gap
    related_entities: List[str]
    confidence: float
    grounded_questions: List[str]
    priority: int  # 1-5
    category: str  # decision, technical, process, context, etc.
    source_pattern: str  # Which detection pattern found this
    quality_score: float = 0.0  # NEW: Quality score 0-1
    fingerprint: str = ""  # NEW: For deduplication


@dataclass
class DiscourseUnit:
    """A unit of discourse (claim, evidence, result, etc.)"""
    text: str
    unit_type: str  # CLAIM, EVIDENCE, RESULT, CAUSE, CONDITION
    doc_id: str
    has_support: bool = False
    supporting_units: List[str] = field(default_factory=list)


@dataclass
class CoreferenceChain:
    """A chain of coreferent mentions"""
    mentions: List[str]  # ["he", "John", "the manager"]
    canonical: str  # "John Smith"
    entity_type: str  # PERSON, ORG, etc.


# =============================================================================
# EXPANDED FRAME DEFINITIONS (150+ triggers)
# =============================================================================

FRAME_TEMPLATES = {
    "DECISION": {
        "required": ["what", "who_decided"],
        "optional": ["why", "alternatives", "when", "impact", "constraints"],
        "triggers": [
            # Original triggers
            r"decided to", r"chose to", r"selected", r"went with", r"opted for",
            r"picked", r"determination was", r"conclusion was", r"we'll use",
            r"we will use", r"using", r"adopted", r"implemented", r"switched to",
            r"moved to", r"migrated to",
            # NEW: Additional decision triggers (50+)
            r"settled on", r"concluded that", r"finalized", r"committed to",
            r"agreed on", r"agreed to", r"approved", r"authorized", r"endorsed",
            r"ratified", r"confirmed", r"validated", r"selected for", r"chosen for",
            r"preference for", r"preferred", r"prioritized", r"favored",
            r"determined that", r"resolved to", r"made the call", r"pulled the trigger",
            r"green-?lit", r"gave the go-?ahead", r"signed off on", r"blessed",
            r"rubber-?stamped", r"going forward with", r"proceeding with",
            r"moving forward with", r"sticking with", r"staying with",
            r"pivoted to", r"transitioned to", r"converted to", r"upgraded to",
            r"downgraded to", r"replaced with", r"substituted", r"swapped",
            r"traded .+ for", r"exchanged .+ for", r"went live with",
            r"rolled out", r"deployed", r"launched", r"shipped",
            r"will be using", r"plan to use", r"intend to use", r"going to use",
            r"standardized on", r"consolidated on", r"unified on",
            r"bet on", r"invested in", r"doubled down on"
        ]
    },
    "PROCESS": {
        "required": ["what", "steps"],
        "optional": ["owner", "frequency", "inputs", "outputs", "exceptions", "tools"],
        "triggers": [
            # Original triggers
            r"process for", r"how to", r"procedure", r"workflow", r"steps to",
            r"method for", r"approach to", r"way to",
            # NEW: Additional process triggers (30+)
            r"protocol for", r"guidelines for", r"instructions for",
            r"checklist for", r"runbook for", r"playbook for",
            r"standard operating procedure", r"SOP for", r"best practice",
            r"recommended approach", r"typical flow", r"normal flow",
            r"usual process", r"standard process", r"default process",
            r"here's how", r"this is how", r"the way we",
            r"to accomplish", r"to achieve", r"to complete",
            r"sequence of", r"series of steps", r"chain of",
            r"pipeline for", r"routine for", r"ritual for",
            r"ceremony for", r"cadence for", r"cycle of",
            r"lifecycle of", r"journey of", r"path to"
        ]
    },
    "DEFINITION": {
        "required": ["term", "meaning"],
        "optional": ["context", "examples", "related_terms", "source"],
        "triggers": [
            # Original triggers
            r"means", r"refers to", r"defined as", r"is when", r"is a",
            r"stands for", r"also known as", r"called",
            # NEW: Additional definition triggers (20+)
            r"denotes", r"signifies", r"represents", r"indicates",
            r"describes", r"characterizes", r"constitutes",
            r"encompasses", r"comprises", r"consists of",
            r"in this context means", r"we use .+ to mean",
            r"by .+ we mean", r"when we say", r"what we call",
            r"our term for", r"our name for", r"internally called",
            r"abbreviated as", r"shortened to", r"aka"
        ]
    },
    "EVENT": {
        "required": ["what_happened", "when"],
        "optional": ["who_involved", "why", "outcome", "location"],
        "triggers": [
            # Original triggers
            r"happened", r"occurred", r"took place", r"launched",
            r"completed", r"started", r"finished", r"announced",
            # NEW: Additional event triggers (25+)
            r"transpired", r"unfolded", r"emerged", r"arose",
            r"surfaced", r"materialized", r"developed", r"evolved",
            r"kicked off", r"wrapped up", r"concluded", r"terminated",
            r"initiated", r"commenced", r"began", r"ended",
            r"went live", r"went down", r"crashed", r"failed",
            r"succeeded", r"passed", r"shipped", r"released",
            r"deployed", r"rolled back", r"reverted"
        ]
    },
    "CONSTRAINT": {
        "required": ["what", "why"],
        "optional": ["source", "impact", "workarounds", "duration"],
        "triggers": [
            # Original triggers
            r"must", r"required", r"cannot", r"prohibited", r"mandatory",
            r"limited to", r"restricted", r"compliance",
            # NEW: Additional constraint triggers (25+)
            r"shall", r"shall not", r"must not", r"may not",
            r"forbidden", r"not allowed", r"not permitted", r"banned",
            r"blocked", r"prevented", r"constrained by", r"bound by",
            r"obligated to", r"compelled to", r"forced to",
            r"have to", r"need to", r"ought to", r"should",
            r"regulatory requirement", r"legal requirement",
            r"contractual obligation", r"SLA requires",
            r"policy states", r"rule is", r"guideline requires"
        ]
    },
    "METRIC": {
        "required": ["what", "value"],
        "optional": ["target", "trend", "owner", "calculation", "frequency"],
        "triggers": [
            # Original triggers
            r"\d+%", r"\$[\d,]+", r"increased by", r"decreased by",
            r"target of", r"goal of", r"KPI", r"metric",
            # NEW: Additional metric triggers (20+)
            r"benchmark", r"baseline", r"threshold", r"limit",
            r"quota", r"cap", r"floor", r"ceiling",
            r"SLA of", r"SLO of", r"uptime of", r"latency of",
            r"throughput of", r"capacity of", r"utilization of",
            r"conversion rate", r"success rate", r"failure rate",
            r"growth rate", r"churn rate", r"retention rate"
        ]
    },
    # NEW FRAME TYPES
    "PROBLEM": {
        "required": ["what", "impact"],
        "optional": ["cause", "solution", "owner", "status"],
        "triggers": [
            r"issue with", r"problem with", r"bug in", r"error in",
            r"failure of", r"outage of", r"incident", r"defect",
            r"broken", r"not working", r"malfunctioning", r"degraded",
            r"struggling with", r"challenge with", r"difficulty with",
            r"pain point", r"bottleneck", r"blocker", r"impediment"
        ]
    },
    "OWNERSHIP": {
        "required": ["what", "who"],
        "optional": ["since", "scope", "backup"],
        "triggers": [
            r"owned by", r"managed by", r"maintained by", r"run by",
            r"responsible for", r"in charge of", r"accountable for",
            r"leads", r"heads", r"oversees", r"supervises",
            r"point of contact", r"POC for", r"go-to person",
            r"subject matter expert", r"SME for", r"domain expert"
        ]
    }
}

# Patterns that indicate missing information
MISSING_PATTERNS = {
    "MISSING_RATIONALE": [
        r"we decided to (.+?)(?:\.|$)",
        r"switched to (.+?) (?:because|due to|for)",
        r"using (.+?)(?:\.|$)",
        # NEW patterns
        r"went with (.+?)(?:\.|$)",
        r"chose (.+?)(?:\.|$)",
        r"selected (.+?)(?:\.|$)",
        r"adopted (.+?)(?:\.|$)",
    ],
    "MISSING_AGENT": [
        r"it was decided",
        r"the decision was made",
        r"they said",
        r"someone mentioned",
        r"was approved",
        r"was rejected",
        # NEW patterns
        r"it was agreed",
        r"it was determined",
        r"there was consensus",
        r"the team decided",  # Vague team
        r"management decided",  # Vague management
        r"leadership approved",
    ],
    "MISSING_TIMELINE": [
        r"eventually",
        r"soon",
        r"later",
        r"in the future",
        r"at some point",
        r"when ready",
        # NEW patterns
        r"down the road",
        r"in due time",
        r"when we get to it",
        r"TBD",
        r"to be determined",
        r"pending",
    ],
    "UNDEFINED_MODIFIER": [
        r"the (?:new|old|current|previous|updated) (.+)",
        r"significantly",
        r"substantially",
        r"major",
        r"minor",
        r"several",
        r"few",
        r"many",
        # NEW patterns
        r"some",
        r"various",
        r"multiple",
        r"numerous",
        r"a lot of",
        r"quite a few",
        r"fairly",
        r"pretty much",
        r"more or less",
    ],
    "PERSON_AS_KNOWLEDGE": [
        r"ask (\w+)",
        r"(\w+) knows",
        r"check with (\w+)",
        r"(\w+) handles that",
        r"(\w+) is the expert",
        r"only (\w+) knows",
        # NEW patterns
        r"talk to (\w+)",
        r"(\w+) can help",
        r"(\w+) deals with",
        r"(\w+) takes care of",
        r"ping (\w+)",
        r"reach out to (\w+)",
        r"(\w+) is the go-to",
    ],
    "IMPLICIT_PROCESS": [
        r"the usual way",
        r"as always",
        r"the standard process",
        r"you know how",
        r"like we always do",
        # NEW patterns
        r"the normal way",
        r"how we usually",
        r"standard procedure",
        r"same as before",
        r"nothing new",
        r"business as usual",
    ],
    "MISSING_EVIDENCE": [
        r"obviously",
        r"clearly",
        r"everyone knows",
        r"it's well known",
        r"common knowledge",
        # NEW patterns
        r"of course",
        r"naturally",
        r"needless to say",
        r"goes without saying",
        r"self-evident",
        r"no-brainer",
    ],
    "ASSUMED_CONTEXT": [
        r"as you know",
        r"remember when",
        r"like last time",
        r"the usual",
        r"that thing",
        # NEW patterns
        r"you remember",
        r"we discussed",
        r"as mentioned",
        r"per our conversation",
        r"as agreed",
        r"the incident",
        r"that issue",
    ],
    "TEMPORAL_REFERENCE": [
        r"before (\w+) left",
        r"when (\w+) was here",
        r"back when",
        r"in the old system",
        # NEW patterns
        r"in the old days",
        r"pre-(\w+)",
        r"post-(\w+)",
        r"after the reorg",
        r"before the migration",
        r"legacy",
    ],
    "EXTERNAL_DEPENDENCY": [
        r"depends on (\w+)",
        r"waiting for",
        r"blocked by",
        r"needs (\w+) approval",
        # NEW patterns
        r"contingent on",
        r"subject to",
        r"requires sign-off",
        r"pending review",
        r"awaiting",
        r"on hold until",
    ]
}

# Negation patterns
NEGATION_PATTERNS = [
    r"\b(not|n't|never|no|none|neither|nor|nobody|nothing|nowhere|without)\b",
    r"\b(didn't|doesn't|don't|won't|wouldn't|couldn't|shouldn't|can't|cannot)\b",
    r"\b(refused|rejected|declined|denied|vetoed|blocked|prevented)\b"
]


# =============================================================================
# ENTITY NORMALIZATION
# =============================================================================

class EntityNormalizer:
    """
    Normalizes entity names to canonical forms.
    Handles: John = John Smith = J. Smith = john.smith@company.com
    """

    # Common title prefixes to strip
    TITLES = {"mr", "ms", "mrs", "dr", "prof", "sir", "dame"}

    # Common suffixes to strip
    SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "esq"}

    def __init__(self):
        self.canonical_map: Dict[str, str] = {}  # alias -> canonical
        self.entity_clusters: Dict[str, Set[str]] = {}  # canonical -> aliases

    def normalize(self, name: str) -> str:
        """Normalize a name to canonical form"""
        if not name:
            return ""

        # Check cache first
        name_lower = name.lower().strip()
        if name_lower in self.canonical_map:
            return self.canonical_map[name_lower]

        # Clean the name
        cleaned = self._clean_name(name)
        return cleaned

    def _clean_name(self, name: str) -> str:
        """Clean and normalize a name"""
        # Remove titles and suffixes
        words = name.lower().strip().split()
        words = [w for w in words if w.rstrip('.') not in self.TITLES]
        words = [w for w in words if w.rstrip('.') not in self.SUFFIXES]

        # Handle email format
        if '@' in name:
            # Extract name from email
            email_name = name.split('@')[0]
            # Handle john.smith format
            if '.' in email_name:
                parts = email_name.split('.')
                return ' '.join(p.title() for p in parts)
            return email_name.title()

        # Handle initials (J. Smith -> J Smith)
        words = [w.rstrip('.') for w in words]

        # Capitalize properly
        return ' '.join(w.title() for w in words if w)

    def add_alias(self, alias: str, canonical: str):
        """Add an alias mapping"""
        alias_lower = alias.lower().strip()
        canonical_clean = self._clean_name(canonical)

        self.canonical_map[alias_lower] = canonical_clean

        if canonical_clean not in self.entity_clusters:
            self.entity_clusters[canonical_clean] = set()
        self.entity_clusters[canonical_clean].add(alias)

    def find_similar(self, name: str, threshold: float = 0.8) -> Optional[str]:
        """Find a similar canonical name if exists"""
        name_clean = self._clean_name(name)

        for canonical in self.entity_clusters.keys():
            similarity = SequenceMatcher(None, name_clean.lower(), canonical.lower()).ratio()
            if similarity >= threshold:
                return canonical

        return None

    def merge_if_similar(self, name: str) -> str:
        """Normalize and merge with existing if similar"""
        # Check exact match first
        normalized = self.normalize(name)

        # Check for similar existing entity
        similar = self.find_similar(normalized)
        if similar:
            self.add_alias(name, similar)
            return similar

        # Register as new canonical
        self.add_alias(name, normalized)
        return normalized


# =============================================================================
# COREFERENCE RESOLUTION (Rule-based)
# =============================================================================

class CoreferenceResolver:
    """
    Rule-based coreference resolution.
    Resolves: "he", "she", "they", "it", "the team", "the company" etc.
    """

    # Pronouns and their likely referent types
    PRONOUN_MAP = {
        # Person pronouns
        "he": "PERSON",
        "him": "PERSON",
        "his": "PERSON",
        "she": "PERSON",
        "her": "PERSON",
        "hers": "PERSON",
        "they": "PERSON",  # Can also be ORG
        "them": "PERSON",
        "their": "PERSON",

        # Organization/team pronouns
        "it": "SYSTEM",  # Usually refers to system/product
        "its": "SYSTEM",
        "we": "ORG",
        "us": "ORG",
        "our": "ORG",
    }

    # Definite descriptions
    DEFINITE_DESCRIPTIONS = {
        "the team": "ORG",
        "the company": "ORG",
        "the organization": "ORG",
        "the department": "ORG",
        "the group": "ORG",
        "the system": "SYSTEM",
        "the platform": "SYSTEM",
        "the service": "SYSTEM",
        "the application": "SYSTEM",
        "the app": "SYSTEM",
        "the database": "SYSTEM",
        "the tool": "SYSTEM",
        "the manager": "PERSON",
        "the lead": "PERSON",
        "the owner": "PERSON",
        "the engineer": "PERSON",
        "the developer": "PERSON",
    }

    def __init__(self):
        self.entity_mentions: List[Dict] = []  # Track entity mentions in order
        self.chains: List[CoreferenceChain] = []

    def add_mention(self, text: str, entity_type: str, position: int):
        """Add an entity mention"""
        self.entity_mentions.append({
            "text": text,
            "type": entity_type,
            "position": position
        })

    def resolve(self, text: str, doc_entities: List[Entity]) -> Dict[str, str]:
        """
        Resolve pronouns and definite descriptions in text.
        Returns mapping of pronoun/description -> resolved entity name
        """
        resolutions = {}
        words = text.lower().split()

        # Build recent entity list by type
        recent_by_type: Dict[str, List[str]] = defaultdict(list)
        for entity in doc_entities:
            recent_by_type[entity.entity_type].append(entity.canonical_name)

        # Resolve pronouns
        for word in words:
            if word in self.PRONOUN_MAP:
                expected_type = self.PRONOUN_MAP[word]
                if recent_by_type.get(expected_type):
                    # Use most recent entity of matching type
                    resolutions[word] = recent_by_type[expected_type][-1]

        # Resolve definite descriptions
        text_lower = text.lower()
        for desc, expected_type in self.DEFINITE_DESCRIPTIONS.items():
            if desc in text_lower:
                if recent_by_type.get(expected_type):
                    resolutions[desc] = recent_by_type[expected_type][-1]

        return resolutions

    def expand_sentence(self, sentence: str, resolutions: Dict[str, str]) -> str:
        """Expand pronouns in a sentence with resolved entities"""
        expanded = sentence
        for pronoun, entity in resolutions.items():
            # Replace pronoun with entity name (case-insensitive)
            pattern = r'\b' + re.escape(pronoun) + r'\b'
            expanded = re.sub(pattern, f"{entity} ({pronoun})", expanded, flags=re.IGNORECASE)
        return expanded


# =============================================================================
# LAYER 1: FRAME-BASED EXTRACTION (Enhanced)
# =============================================================================

class FrameExtractor:
    """
    Extracts structured frames from text with negation handling.
    Uses spaCy for NLP processing.
    """

    def __init__(self):
        self.nlp = NLP  # Use global spaCy model

    def extract_frames(self, text: str, doc_id: str = "") -> List[Frame]:
        """Extract all frames from text"""
        frames = []
        sentences = self._split_sentences(text)

        for sentence in sentences:
            # Check for negation
            is_negated = self._is_negated(sentence)

            for frame_type, template in FRAME_TEMPLATES.items():
                for trigger_pattern in template["triggers"]:
                    if re.search(trigger_pattern, sentence, re.IGNORECASE):
                        frame = self._build_frame(
                            sentence=sentence,
                            frame_type=frame_type,
                            template=template,
                            trigger=trigger_pattern,
                            doc_id=doc_id,
                            is_negated=is_negated
                        )
                        if frame and not is_negated:  # Skip negated frames
                            frames.append(frame)
                        break

        return frames

    def _is_negated(self, sentence: str) -> bool:
        """Check if sentence contains negation before the trigger"""
        for pattern in NEGATION_PATTERNS:
            if re.search(pattern, sentence, re.IGNORECASE):
                return True
        return False

    def _build_frame(
        self,
        sentence: str,
        frame_type: str,
        template: Dict,
        trigger: str,
        doc_id: str,
        is_negated: bool = False
    ) -> Optional[Frame]:
        """Build a frame from a sentence"""
        frame = Frame(
            frame_type=frame_type,
            trigger=trigger,
            source_doc_id=doc_id,
            source_sentence=sentence,
            is_negated=is_negated
        )

        # Extract slot values
        slots = self._extract_slots(sentence, frame_type, template)

        for slot_name, slot_value in slots.items():
            is_required = slot_name in template["required"]
            frame.slots[slot_name] = FrameSlot(
                name=slot_name,
                value=slot_value,
                required=is_required,
                source_doc_id=doc_id,
                source_sentence=sentence
            )

        # Identify missing required slots
        for required_slot in template["required"]:
            if required_slot not in frame.slots or not frame.slots[required_slot].value:
                frame.missing_slots.append(required_slot)

        return frame

    def _extract_slots(self, sentence: str, frame_type: str, template: Dict) -> Dict[str, str]:
        """Extract slot values from sentence"""
        slots = {}

        if self.nlp:
            try:
                doc = self.nlp(sentence)
                slots = self._extract_slots_spacy(doc, sentence, frame_type)
            except Exception:
                slots = self._extract_slots_regex(sentence, frame_type)
        else:
            slots = self._extract_slots_regex(sentence, frame_type)

        return slots

    def _extract_slots_spacy(self, doc, sentence: str, frame_type: str) -> Dict[str, str]:
        """Extract slots using spaCy"""
        slots = {}

        if frame_type == "DECISION":
            # Find decision verb and its arguments
            for token in doc:
                if token.lemma_ in ["decide", "choose", "select", "opt", "pick", "use", "adopt", "go", "switch"]:
                    for child in token.children:
                        if child.dep_ in ["dobj", "xcomp", "ccomp", "pobj"]:
                            what = " ".join([t.text for t in child.subtree])
                            slots["what"] = what[:200]
                        if child.dep_ in ["nsubj", "nsubjpass"]:
                            slots["who_decided"] = child.text

            # Look for rationale
            if "because" in sentence.lower():
                match = re.search(r"because (.+?)(?:\.|$)", sentence, re.IGNORECASE)
                if match:
                    slots["why"] = match.group(1)[:200]

            # Fallback for who_decided
            if "who_decided" not in slots:
                for ent in doc.ents:
                    if ent.label_ in ["PERSON", "ORG"]:
                        slots["who_decided"] = ent.text
                        break

        elif frame_type == "PROCESS":
            what_match = re.search(r"(?:process|procedure|workflow|method) (?:for|to) (.+?)(?:\.|,|$)", sentence, re.IGNORECASE)
            if what_match:
                slots["what"] = what_match.group(1)[:200]

            steps_match = re.findall(r"(?:\d+[\.\)]\s*|\-\s*)(.+?)(?:,|;|$)", sentence)
            if steps_match:
                slots["steps"] = "; ".join(steps_match[:10])

        elif frame_type == "OWNERSHIP":
            # Extract owner and what they own
            for token in doc:
                if token.lemma_ in ["own", "manage", "maintain", "run", "lead", "head"]:
                    for child in token.children:
                        if child.dep_ == "nsubj":
                            slots["who"] = child.text
                        if child.dep_ == "dobj":
                            slots["what"] = child.text

        return slots

    def _extract_slots_regex(self, sentence: str, frame_type: str) -> Dict[str, str]:
        """Regex-based slot extraction fallback"""
        slots = {}

        if frame_type == "DECISION":
            # Extract what was decided
            patterns = [
                r"decided to (.+?)(?:\.|,|$)",
                r"chose (?:to )?(.+?)(?:\.|,|$)",
                r"selected (.+?)(?:\.|,|$)",
                r"went with (.+?)(?:\.|,|$)",
                r"using (.+?)(?:\.|,|$)",
                r"adopted (.+?)(?:\.|,|$)",
                r"switched to (.+?)(?:\.|,|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, sentence, re.IGNORECASE)
                if match:
                    slots["what"] = match.group(1)[:200]
                    break

            # Extract who decided
            who_patterns = [
                r"(\w+(?:\s+\w+)?)\s+decided",
                r"(\w+(?:\s+\w+)?)\s+chose",
                r"(\w+(?:\s+\w+)?)\s+selected",
            ]
            for pattern in who_patterns:
                match = re.search(pattern, sentence, re.IGNORECASE)
                if match:
                    slots["who_decided"] = match.group(1)
                    break

            # Extract rationale
            why_match = re.search(r"because (.+?)(?:\.|$)", sentence, re.IGNORECASE)
            if why_match:
                slots["why"] = why_match.group(1)[:200]

        elif frame_type == "PROCESS":
            what_match = re.search(r"(?:process|procedure) (?:for|to) (.+?)(?:\.|,|$)", sentence, re.IGNORECASE)
            if what_match:
                slots["what"] = what_match.group(1)[:200]

        elif frame_type == "PROBLEM":
            problem_match = re.search(r"(?:issue|problem|bug|error) (?:with|in) (.+?)(?:\.|,|$)", sentence, re.IGNORECASE)
            if problem_match:
                slots["what"] = problem_match.group(1)[:200]

        elif frame_type == "OWNERSHIP":
            owner_match = re.search(r"(?:owned|managed|maintained|run) by (\w+(?:\s+\w+)?)", sentence, re.IGNORECASE)
            if owner_match:
                slots["who"] = owner_match.group(1)

        return slots

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences using spaCy"""
        doc = self.nlp(text[:100000])  # Limit to avoid memory issues
        return [sent.text.strip() for sent in doc.sents]


# =============================================================================
# LAYER 2: SEMANTIC ROLE LABELING (Enhanced)
# =============================================================================

class SemanticRoleAnalyzer:
    """
    Analyzes sentences for missing semantic roles with improved detection.
    """

    ROLE_QUESTIONS = {
        "ARG0": "Who {action}?",
        "ARG1": "What was {action}?",
        "ARGM-CAU": "Why was this {action}?",
        "ARGM-MNR": "How was this {action}?",
        "ARGM-TMP": "When was this {action}?",
        "ARGM-LOC": "Where was this {action}?",
        "ARGM-PRP": "What was the purpose of {action}?"
    }

    # Expanded verb lists
    DECISION_VERBS = [
        "decided", "chose", "selected", "implemented", "changed", "removed", "added",
        "adopted", "approved", "rejected", "canceled", "postponed", "prioritized",
        "committed", "agreed", "settled", "concluded", "determined", "resolved"
    ]

    EVENT_VERBS = [
        "launched", "released", "completed", "started", "finished", "happened",
        "occurred", "began", "ended", "deployed", "shipped", "rolled out",
        "went live", "crashed", "failed", "succeeded"
    ]

    def __init__(self):
        self.nlp = NLP  # Use global spaCy model

    def analyze_missing_roles(self, sentences: List[str], doc_id: str = "") -> List[Dict]:
        """Identify sentences with missing semantic roles"""
        missing_roles = []

        for sentence in sentences:
            if len(sentence) < 20:
                continue

            roles = self._extract_roles(sentence)
            missing = self._identify_missing_roles(sentence, roles)

            if missing:
                missing_roles.append({
                    "sentence": sentence,
                    "doc_id": doc_id,
                    "roles_found": roles,
                    "roles_missing": missing,
                    "questions": [
                        self.ROLE_QUESTIONS.get(role, f"What about {role}?").format(
                            action=self._get_main_action(sentence)
                        )
                        for role in missing
                    ]
                })

        return missing_roles

    def _extract_roles(self, sentence: str) -> Dict[str, str]:
        """Extract semantic roles from sentence"""
        roles = {}

        # Pattern-based extraction (works without spaCy)

        # Agent (subject) patterns
        agent_patterns = [
            r"^(\w+(?:\s+\w+)?)\s+(?:decided|chose|selected|approved)",
            r"^(We|They|The team|The company)\s+",
            r"(\w+)\s+(?:is|was)\s+responsible",
        ]
        for pattern in agent_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                roles["ARG0"] = match.group(1)
                break

        # Temporal patterns
        temporal_patterns = [
            r"(?:on|in|at|during|since|before|after)\s+(\w+\s+\d+|\d{4}|\w+day|\w+\s+\d{1,2})",
            r"(yesterday|today|tomorrow|last\s+\w+|next\s+\w+|this\s+\w+)",
            r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})",
        ]
        for pattern in temporal_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                roles["ARGM-TMP"] = match.group(1)
                break

        # Causal patterns
        causal_patterns = [
            r"because (.+?)(?:\.|,|$)",
            r"due to (.+?)(?:\.|,|$)",
            r"since (.+?)(?:\.|,|$)",
            r"as a result of (.+?)(?:\.|,|$)",
        ]
        for pattern in causal_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                roles["ARGM-CAU"] = match.group(1)[:100]
                break

        # Manner patterns
        manner_patterns = [
            r"by (?:using |)(.+?)(?:\.|,|$)",
            r"via (.+?)(?:\.|,|$)",
            r"through (.+?)(?:\.|,|$)",
        ]
        for pattern in manner_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                roles["ARGM-MNR"] = match.group(1)[:100]
                break

        return roles

    def _identify_missing_roles(self, sentence: str, roles: Dict[str, str]) -> List[str]:
        """Identify which important roles are missing"""
        missing = []
        sentence_lower = sentence.lower()

        # Check for passive voice without agent
        if re.search(r"\b(was|were|been|being)\s+\w+ed\b", sentence) and "ARG0" not in roles:
            missing.append("ARG0")

        # Check for decisions without cause
        if any(v in sentence_lower for v in self.DECISION_VERBS) and "ARGM-CAU" not in roles:
            missing.append("ARGM-CAU")

        # Check for events without time
        if any(v in sentence_lower for v in self.EVENT_VERBS) and "ARGM-TMP" not in roles:
            missing.append("ARGM-TMP")

        return missing

    def _get_main_action(self, sentence: str) -> str:
        """Extract the main action from a sentence"""
        # Look for common verbs
        all_verbs = self.DECISION_VERBS + self.EVENT_VERBS
        sentence_lower = sentence.lower()

        for verb in all_verbs:
            if verb in sentence_lower:
                return verb

        # Fallback
        return "done"


# =============================================================================
# LAYER 3: DISCOURSE ANALYSIS (Enhanced)
# =============================================================================

class DiscourseAnalyzer:
    """
    Analyzes discourse structure with improved claim detection.
    """

    MARKERS = {
        "CAUSE": ["because", "since", "due to", "as a result of", "caused by", "owing to", "thanks to", "given that"],
        "RESULT": ["therefore", "thus", "so", "consequently", "as a result", "hence", "leading to", "which means", "resulting in"],
        "CONTRAST": ["however", "but", "although", "despite", "nevertheless", "on the other hand", "yet", "still", "though"],
        "EVIDENCE": ["for example", "such as", "specifically", "in particular", "demonstrated by", "shown by", "according to", "based on"],
        "CONCESSION": ["although", "even though", "despite", "while", "granted", "admittedly"],
        "CONDITION": ["if", "unless", "provided that", "in case", "when", "assuming"],
        "TEMPORAL": ["before", "after", "when", "while", "during", "following", "prior to", "subsequently"]
    }

    CLAIM_INDICATORS = [
        r"should", r"must", r"need to", r"is better", r"is worse",
        r"will result in", r"is important", r"is critical", r"is essential",
        r"is the best", r"is necessary", r"is recommended", r"is required",
        r"is preferred", r"is optimal", r"is ideal", r"is superior",
        r"is inferior", r"outperforms", r"underperforms"
    ]

    def __init__(self):
        pass

    def analyze_discourse(self, text: str, doc_id: str = "") -> List[DiscourseUnit]:
        """Analyze discourse structure"""
        units = []
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for i, sentence in enumerate(sentences):
            unit_type = self._classify_unit(sentence)
            unit = DiscourseUnit(
                text=sentence,
                unit_type=unit_type,
                doc_id=doc_id,
                has_support=False
            )

            if unit_type == "CLAIM":
                unit.has_support = self._check_support(sentence, sentences, i)

            units.append(unit)

        return units

    def find_unsupported_claims(self, units: List[DiscourseUnit]) -> List[Dict]:
        """Find claims that lack evidence"""
        unsupported = []

        for unit in units:
            if unit.unit_type == "CLAIM" and not unit.has_support:
                unsupported.append({
                    "claim": unit.text,
                    "doc_id": unit.doc_id,
                    "gap_type": "UNSUPPORTED_CLAIM",
                    "question": self._generate_support_question(unit.text)
                })

        return unsupported

    def find_results_without_causes(self, units: List[DiscourseUnit]) -> List[Dict]:
        """Find results without causes"""
        gaps = []

        for i, unit in enumerate(units):
            if unit.unit_type == "RESULT":
                has_cause = False
                context_range = range(max(0, i-3), min(len(units), i+2))
                for j in context_range:
                    if units[j].unit_type == "CAUSE":
                        has_cause = True
                        break

                if not has_cause:
                    gaps.append({
                        "result": unit.text,
                        "doc_id": unit.doc_id,
                        "gap_type": "RESULT_WITHOUT_CAUSE",
                        "question": f"What caused: {unit.text[:100]}...?"
                    })

        return gaps

    def _classify_unit(self, sentence: str) -> str:
        """Classify sentence into discourse unit type"""
        sentence_lower = sentence.lower()

        for pattern in self.CLAIM_INDICATORS:
            if re.search(pattern, sentence_lower):
                return "CLAIM"

        for unit_type, markers in self.MARKERS.items():
            for marker in markers:
                if marker in sentence_lower:
                    return unit_type

        return "STATEMENT"

    def _check_support(self, claim: str, sentences: List[str], claim_index: int) -> bool:
        """Check if claim has support nearby"""
        context_range = range(max(0, claim_index-2), min(len(sentences), claim_index+3))

        for i in context_range:
            if i == claim_index:
                continue

            sentence = sentences[i].lower()

            for marker in self.MARKERS["EVIDENCE"]:
                if marker in sentence:
                    return True

            if re.search(r"\d+%|\d+\s+\w+|study|research|data|survey|according to", sentence):
                return True

        return False

    def _generate_support_question(self, claim: str) -> str:
        """Generate question for unsupported claim"""
        claim_short = claim[:100] + "..." if len(claim) > 100 else claim

        if "should" in claim.lower():
            return f"Why should this be done? What evidence supports: '{claim_short}'"
        elif "must" in claim.lower():
            return f"What requirement mandates: '{claim_short}'"
        elif "better" in claim.lower() or "worse" in claim.lower():
            return f"What comparison supports: '{claim_short}'"
        else:
            return f"What evidence supports: '{claim_short}'"


# =============================================================================
# LAYER 4: KNOWLEDGE GRAPH BUILDER (Enhanced)
# =============================================================================

class KnowledgeGraphBuilder:
    """
    Builds knowledge graph with entity normalization.
    """

    EXPECTED_RELATIONS = {
        ("PERSON", "SYSTEM"): ["OWNS", "USES", "MANAGES", "CREATED"],
        ("PERSON", "PROCESS"): ["OWNS", "EXECUTES", "DESIGNED"],
        ("PERSON", "DECISION"): ["MADE", "APPROVED", "OPPOSED"],
        ("SYSTEM", "SYSTEM"): ["DEPENDS_ON", "INTEGRATES_WITH", "REPLACED_BY"],
        ("PROCESS", "SYSTEM"): ["USES", "INPUTS", "OUTPUTS"],
        ("ORG", "SYSTEM"): ["OWNS", "USES", "PROVIDES"],
        ("DECISION", "SYSTEM"): ["IMPACTS", "CREATED", "DEPRECATED"]
    }

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []
        self.normalizer = EntityNormalizer()
        self.nlp = NLP  # Use global spaCy model

    def add_document(self, text: str, doc_id: str):
        """Extract entities and relations from document"""
        entities = self._extract_entities(text, doc_id)

        for entity in entities:
            if entity.id not in self.entities:
                self.entities[entity.id] = entity
            else:
                self.entities[entity.id].mentions.extend(entity.mentions)
                self.entities[entity.id].documents.update(entity.documents)
                self.entities[entity.id].aliases.update(entity.aliases)

        relations = self._extract_relations(text, doc_id, entities)
        self.relations.extend(relations)

    def find_missing_relations(self) -> List[Dict]:
        """Find expected relations that are missing"""
        missing = []

        entities_by_type = defaultdict(list)
        for entity in self.entities.values():
            entities_by_type[entity.entity_type].append(entity)

        for (type1, type2), expected_rels in self.EXPECTED_RELATIONS.items():
            for e1 in entities_by_type.get(type1, []):
                for e2 in entities_by_type.get(type2, []):
                    if e1.id == e2.id:
                        continue

                    shared_docs = e1.documents.intersection(e2.documents)
                    if shared_docs:
                        existing = self._get_relations(e1.id, e2.id)
                        existing_types = set(r.relation_type for r in existing)

                        for rel_type in expected_rels:
                            if rel_type not in existing_types:
                                missing.append({
                                    "source": e1.canonical_name,
                                    "source_type": e1.entity_type,
                                    "target": e2.canonical_name,
                                    "target_type": e2.entity_type,
                                    "expected_relation": rel_type,
                                    "shared_documents": list(shared_docs)[:3],
                                    "question": self._generate_relation_question(e1, e2, rel_type)
                                })

        return missing

    def find_bus_factor_risks(self, threshold: int = 3) -> List[Dict]:
        """Find knowledge concentrated in single individuals"""
        risks = []

        person_entities = [e for e in self.entities.values() if e.entity_type == "PERSON"]

        for person in person_entities:
            owned = []
            for rel in self.relations:
                if rel.source_entity == person.id and rel.relation_type in ["OWNS", "MANAGES", "CREATED"]:
                    target = self.entities.get(rel.target_entity)
                    if target:
                        owned.append(target.canonical_name)

            if len(owned) >= threshold:
                risks.append({
                    "person": person.canonical_name,
                    "owns_count": len(owned),
                    "owns": owned[:5],
                    "risk_level": "HIGH" if len(owned) >= 5 else "MEDIUM",
                    "question": f"Who else understands {', '.join(owned[:3])} besides {person.canonical_name}? What's the backup plan if {person.canonical_name} is unavailable?"
                })

        return risks

    def find_isolated_entities(self) -> List[Dict]:
        """Find entities with no relations"""
        isolated = []

        for entity in self.entities.values():
            relation_count = sum(
                1 for r in self.relations
                if r.source_entity == entity.id or r.target_entity == entity.id
            )

            if relation_count == 0 and len(entity.documents) > 1:
                isolated.append({
                    "entity": entity.canonical_name,
                    "entity_type": entity.entity_type,
                    "documents": list(entity.documents)[:3],
                    "question": f"What is the relationship between {entity.canonical_name} and other systems/people?"
                })

        return isolated

    def _extract_entities(self, text: str, doc_id: str) -> List[Entity]:
        """Extract entities from text"""
        entities = []

        # Regex-based extraction (works without spaCy)

        # Person patterns (names with capital letters)
        person_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
        for match in re.finditer(person_pattern, text):
            name = match.group(1)
            # Filter out common non-names
            if name.lower() not in ["the team", "the company", "the system"]:
                canonical = self.normalizer.merge_if_similar(name)
                entity_id = self._generate_entity_id(canonical, "PERSON")
                entities.append(Entity(
                    id=entity_id,
                    name=name,
                    canonical_name=canonical,
                    entity_type="PERSON",
                    mentions=[name],
                    documents={doc_id},
                    aliases={name}
                ))

        # System patterns
        system_patterns = [
            r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b",  # CamelCase
            r"\b([A-Z]{2,6})\b",  # Acronyms
            r"\b(\w+(?:System|Service|API|DB|Platform|Tool|App))\b"
        ]
        for pattern in system_patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1)
                if len(name) > 2:
                    canonical = self.normalizer.merge_if_similar(name)
                    entity_id = self._generate_entity_id(canonical, "SYSTEM")
                    entities.append(Entity(
                        id=entity_id,
                        name=name,
                        canonical_name=canonical,
                        entity_type="SYSTEM",
                        mentions=[name],
                        documents={doc_id},
                        aliases={name}
                    ))

        # Process patterns
        process_patterns = [
            r"(\w+(?:\s+\w+)?\s+process)\b",
            r"(\w+(?:\s+\w+)?\s+workflow)\b",
            r"(\w+(?:\s+\w+)?\s+procedure)\b"
        ]
        for pattern in process_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                name = match.group(1)
                canonical = self.normalizer.merge_if_similar(name)
                entity_id = self._generate_entity_id(canonical, "PROCESS")
                entities.append(Entity(
                    id=entity_id,
                    name=name,
                    canonical_name=canonical,
                    entity_type="PROCESS",
                    mentions=[name],
                    documents={doc_id},
                    aliases={name}
                ))

        return entities

    def _extract_relations(self, text: str, doc_id: str, entities: List[Entity]) -> List[Relation]:
        """Extract relations between entities"""
        relations = []

        entity_map = {e.canonical_name.lower(): e for e in entities}
        entity_map.update({alias.lower(): e for e in entities for alias in e.aliases})

        relation_patterns = [
            (r"(\w+(?:\s+\w+)?)\s+(?:owns|manages|is responsible for)\s+(\w+(?:\s+\w+)?)", "MANAGES"),
            (r"(\w+(?:\s+\w+)?)\s+(?:uses|utilizes|works with)\s+(\w+(?:\s+\w+)?)", "USES"),
            (r"(\w+(?:\s+\w+)?)\s+(?:created|built|developed)\s+(\w+(?:\s+\w+)?)", "CREATED"),
            (r"(\w+(?:\s+\w+)?)\s+(?:depends on|requires)\s+(\w+(?:\s+\w+)?)", "DEPENDS_ON"),
            (r"(\w+(?:\s+\w+)?)\s+(?:decided|approved|rejected)\s+(\w+(?:\s+\w+)?)", "DECIDED"),
        ]

        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            for pattern, rel_type in relation_patterns:
                matches = re.findall(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    source_name, target_name = match
                    source = entity_map.get(source_name.lower())
                    target = entity_map.get(target_name.lower())

                    if source and target:
                        relations.append(Relation(
                            source_entity=source.id,
                            target_entity=target.id,
                            relation_type=rel_type,
                            evidence=[sentence],
                            source_doc_id=doc_id
                        ))

        return relations

    def _get_relations(self, entity1_id: str, entity2_id: str) -> List[Relation]:
        """Get relations between two entities"""
        return [
            r for r in self.relations
            if (r.source_entity == entity1_id and r.target_entity == entity2_id) or
               (r.source_entity == entity2_id and r.target_entity == entity1_id)
        ]

    def _generate_entity_id(self, name: str, entity_type: str) -> str:
        """Generate unique entity ID"""
        normalized = name.lower().strip()
        return hashlib.md5(f"{entity_type}:{normalized}".encode()).hexdigest()[:12]

    def _generate_relation_question(self, e1: Entity, e2: Entity, rel_type: str) -> str:
        """Generate question about missing relation"""
        questions = {
            "OWNS": f"Does {e1.canonical_name} own or manage {e2.canonical_name}?",
            "USES": f"Does {e1.canonical_name} use {e2.canonical_name}? How?",
            "MANAGES": f"Who manages {e2.canonical_name}? Is it {e1.canonical_name}?",
            "CREATED": f"Did {e1.canonical_name} create {e2.canonical_name}? When?",
            "DEPENDS_ON": f"Does {e1.canonical_name} depend on {e2.canonical_name}?",
            "INTEGRATES_WITH": f"Does {e1.canonical_name} integrate with {e2.canonical_name}?",
            "REPLACED_BY": f"Did {e1.canonical_name} get replaced by {e2.canonical_name}?"
        }
        return questions.get(rel_type, f"What is the relationship between {e1.canonical_name} and {e2.canonical_name}?")


# =============================================================================
# LAYER 5: CROSS-DOCUMENT VERIFICATION (Enhanced)
# =============================================================================

class CrossDocumentVerifier:
    """
    Verifies claims across documents with improved contradiction detection.
    """

    def __init__(self):
        self.claims_by_topic: Dict[str, List[Dict]] = defaultdict(list)

    def add_document(self, text: str, doc_id: str, doc_title: str = ""):
        """Extract and store claims"""
        claims = self._extract_claims(text, doc_id, doc_title)
        for claim in claims:
            topic = claim.get("topic", "general")
            self.claims_by_topic[topic].append(claim)

    def find_contradictions(self) -> List[Dict]:
        """Find contradictory claims with improved detection"""
        contradictions = []

        for topic, claims in self.claims_by_topic.items():
            if len(claims) < 2:
                continue

            for i, claim1 in enumerate(claims):
                for claim2 in claims[i+1:]:
                    if claim1["doc_id"] == claim2["doc_id"]:
                        continue

                    contradiction_type = self._are_contradictory(claim1, claim2)
                    if contradiction_type:
                        contradictions.append({
                            "topic": topic,
                            "claim1": claim1["text"],
                            "doc1": claim1["doc_id"],
                            "claim2": claim2["text"],
                            "doc2": claim2["doc_id"],
                            "contradiction_type": contradiction_type,
                            "question": f"Which is correct regarding {topic}? '{claim1['text'][:50]}...' vs '{claim2['text'][:50]}...'"
                        })

        return contradictions

    def find_single_source_knowledge(self) -> List[Dict]:
        """Find knowledge from single source"""
        single_source = []

        for topic, claims in self.claims_by_topic.items():
            doc_sources = set(c["doc_id"] for c in claims)

            if len(doc_sources) == 1 and len(claims) >= 2:
                single_source.append({
                    "topic": topic,
                    "source_doc": list(doc_sources)[0],
                    "claim_count": len(claims),
                    "sample_claims": [c["text"][:100] for c in claims[:3]],
                    "question": f"Topic '{topic}' only in one source. Documented elsewhere?"
                })

        return single_source

    def _extract_claims(self, text: str, doc_id: str, doc_title: str) -> List[Dict]:
        """Extract verifiable claims"""
        claims = []
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            if len(sentence) < 30:
                continue

            is_claim = False
            topic = "general"

            # Numeric claims
            if re.search(r"\d+(?:%|x|times|days|weeks|months|years|users|customers)", sentence):
                is_claim = True
                topic = self._extract_topic(sentence)

            # Definitive statements
            if re.search(r"\b(is|are|was|were|will be|must|always|never)\b", sentence):
                is_claim = True
                topic = self._extract_topic(sentence)

            if is_claim:
                claims.append({
                    "text": sentence,
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "topic": topic,
                    "numbers": re.findall(r"\d+(?:\.\d+)?", sentence),
                })

        return claims

    def _extract_topic(self, sentence: str) -> str:
        """Extract topic from sentence"""
        words = sentence.split()
        for word in words[:5]:
            if word[0].isupper() and len(word) > 2 and word.lower() not in ["the", "this", "that"]:
                return word.lower()
        return "general"

    def _are_contradictory(self, claim1: Dict, claim2: Dict) -> Optional[str]:
        """Check if claims contradict - returns type of contradiction or None"""
        text1 = claim1["text"].lower()
        text2 = claim2["text"].lower()

        # Check numeric contradictions
        nums1 = claim1.get("numbers", [])
        nums2 = claim2.get("numbers", [])

        if nums1 and nums2:
            # Check if same metric with different values
            if nums1[0] != nums2[0]:
                # Look for same context words
                words1 = set(text1.split())
                words2 = set(text2.split())
                common = words1.intersection(words2)
                if len(common) > 5:  # Significant overlap
                    return "NUMERIC_CONTRADICTION"

        # Check negation contradictions
        negations = [
            ("is", "is not"),
            ("are", "are not"),
            ("will", "will not"),
            ("can", "cannot"),
            ("should", "should not"),
            ("does", "does not"),
            ("has", "has not"),
            ("was", "was not"),
            ("were", "were not"),
        ]

        for pos, neg in negations:
            if f" {pos} " in text1 and f" {neg} " in text2:
                return "NEGATION_CONTRADICTION"
            if f" {neg} " in text1 and f" {pos} " in text2:
                return "NEGATION_CONTRADICTION"

        # Check opposite adjectives
        opposites = [
            ("good", "bad"),
            ("high", "low"),
            ("fast", "slow"),
            ("easy", "hard"),
            ("simple", "complex"),
            ("increase", "decrease"),
            ("grow", "shrink"),
            ("more", "less"),
            ("better", "worse"),
        ]

        for word1, word2 in opposites:
            if word1 in text1 and word2 in text2:
                return "SEMANTIC_CONTRADICTION"
            if word2 in text1 and word1 in text2:
                return "SEMANTIC_CONTRADICTION"

        return None


# =============================================================================
# LAYER 6: GROUNDED QUESTION GENERATOR (Enhanced)
# =============================================================================

class GroundedQuestionGenerator:
    """
    Generates questions with quality scoring and deduplication.
    """

    def __init__(self):
        self.seen_fingerprints: Set[str] = set()

    def generate_questions(
        self,
        frames: List[Frame],
        missing_roles: List[Dict],
        unsupported_claims: List[Dict],
        missing_relations: List[Dict],
        bus_factor_risks: List[Dict],
        contradictions: List[Dict]
    ) -> List[Gap]:
        """Generate prioritized, deduplicated questions"""
        gaps = []
        self.seen_fingerprints.clear()

        # Process frame-based gaps
        for frame in frames:
            for missing_slot in frame.missing_slots:
                questions = self._frame_slot_questions(frame, missing_slot)
                fingerprint = self._generate_fingerprint(frame.frame_type, missing_slot, frame.source_sentence)

                if fingerprint not in self.seen_fingerprints:
                    self.seen_fingerprints.add(fingerprint)
                    quality_score = self._calculate_quality(frame, questions)

                    gap = Gap(
                        gap_type=f"MISSING_{missing_slot.upper()}",
                        description=f"Missing {missing_slot} for {frame.frame_type}: {frame.trigger}",
                        evidence=[frame.source_sentence],
                        related_entities=[frame.trigger],
                        confidence=0.9,
                        grounded_questions=questions,
                        priority=self._calculate_priority(frame.frame_type, missing_slot),
                        category=self._frame_to_category(frame.frame_type),
                        source_pattern="FRAME_EXTRACTION",
                        quality_score=quality_score,
                        fingerprint=fingerprint
                    )
                    gaps.append(gap)

        # Process semantic role gaps
        for role_gap in missing_roles:
            for question in role_gap.get("questions", []):
                fingerprint = self._generate_fingerprint("ROLE", role_gap['roles_missing'][0], question)

                if fingerprint not in self.seen_fingerprints:
                    self.seen_fingerprints.add(fingerprint)

                    gap = Gap(
                        gap_type=f"MISSING_ROLE_{role_gap['roles_missing'][0]}",
                        description=f"Missing role in: {role_gap['sentence'][:100]}",
                        evidence=[role_gap["sentence"]],
                        related_entities=[],
                        confidence=0.8,
                        grounded_questions=[question],
                        priority=3,
                        category="context",
                        source_pattern="SEMANTIC_ROLE",
                        quality_score=0.7,
                        fingerprint=fingerprint
                    )
                    gaps.append(gap)

        # Process unsupported claims
        for claim in unsupported_claims:
            question = claim.get("question", "")
            fingerprint = self._generate_fingerprint("CLAIM", "unsupported", question)

            if fingerprint not in self.seen_fingerprints and question:
                self.seen_fingerprints.add(fingerprint)

                gap = Gap(
                    gap_type="UNSUPPORTED_CLAIM",
                    description=f"Claim without evidence: {claim['claim'][:100]}",
                    evidence=[claim["claim"]],
                    related_entities=[],
                    confidence=0.85,
                    grounded_questions=[question],
                    priority=4,
                    category="rationale",
                    source_pattern="DISCOURSE_ANALYSIS",
                    quality_score=0.75,
                    fingerprint=fingerprint
                )
                gaps.append(gap)

        # Process missing relations
        for rel in missing_relations:
            question = rel.get("question", "")
            fingerprint = self._generate_fingerprint("RELATION", rel["source"], rel["target"])

            if fingerprint not in self.seen_fingerprints and question:
                self.seen_fingerprints.add(fingerprint)

                gap = Gap(
                    gap_type="MISSING_RELATION",
                    description=f"Missing relationship between {rel['source']} and {rel['target']}",
                    evidence=rel.get("shared_documents", []),
                    related_entities=[rel["source"], rel["target"]],
                    confidence=0.7,
                    grounded_questions=[question],
                    priority=3,
                    category="relationship",
                    source_pattern="KNOWLEDGE_GRAPH",
                    quality_score=0.65,
                    fingerprint=fingerprint
                )
                gaps.append(gap)

        # Process bus factor risks (high priority)
        for risk in bus_factor_risks:
            question = risk.get("question", "")
            fingerprint = self._generate_fingerprint("BUS_FACTOR", risk["person"], str(risk["owns_count"]))

            if fingerprint not in self.seen_fingerprints and question:
                self.seen_fingerprints.add(fingerprint)

                gap = Gap(
                    gap_type="BUS_FACTOR_RISK",
                    description=f"Knowledge concentrated in {risk['person']}: {', '.join(risk['owns'][:3])}",
                    evidence=[f"{risk['person']} owns/manages: {', '.join(risk['owns'])}"],
                    related_entities=[risk["person"]] + risk["owns"][:3],
                    confidence=0.95,
                    grounded_questions=[question],
                    priority=5,
                    category="relationship",
                    source_pattern="BUS_FACTOR",
                    quality_score=0.9,
                    fingerprint=fingerprint
                )
                gaps.append(gap)

        # Process contradictions (highest priority)
        for contradiction in contradictions:
            question = contradiction.get("question", "")
            fingerprint = self._generate_fingerprint("CONTRADICTION", contradiction["topic"], contradiction["doc1"])

            if fingerprint not in self.seen_fingerprints and question:
                self.seen_fingerprints.add(fingerprint)

                gap = Gap(
                    gap_type="CONTRADICTION",
                    description=f"Contradictory info about {contradiction['topic']}",
                    evidence=[contradiction["claim1"], contradiction["claim2"]],
                    related_entities=[contradiction["doc1"], contradiction["doc2"]],
                    confidence=0.9,
                    grounded_questions=[question],
                    priority=5,
                    category="context",
                    source_pattern="CROSS_DOCUMENT",
                    quality_score=0.85,
                    fingerprint=fingerprint
                )
                gaps.append(gap)

        # Sort by priority then quality
        gaps.sort(key=lambda g: (-g.priority, -g.quality_score))

        return gaps

    def _generate_fingerprint(self, gap_type: str, key1: str, key2: str) -> str:
        """Generate fingerprint for deduplication"""
        content = f"{gap_type}:{key1}:{key2}".lower()
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _calculate_quality(self, frame: Frame, questions: List[str]) -> float:
        """Calculate quality score for a gap"""
        score = 0.5  # Base score

        # Boost for specific evidence
        if len(frame.source_sentence) > 50:
            score += 0.1

        # Boost for questions with context
        if questions and "Context:" in questions[0]:
            score += 0.1

        # Boost for high-value frame types
        if frame.frame_type in ["DECISION", "CONSTRAINT", "OWNERSHIP"]:
            score += 0.2

        # Penalize short/generic
        if len(frame.source_sentence) < 30:
            score -= 0.2

        return min(max(score, 0.0), 1.0)

    def _frame_slot_questions(self, frame: Frame, missing_slot: str) -> List[str]:
        """Generate questions for missing frame slots"""
        context = frame.source_sentence[:100]

        questions = {
            "DECISION": {
                "what": [f"What exactly was decided? Context: '{context}'"],
                "who_decided": [f"Who made this decision? Context: '{context}'"],
                "why": [f"Why was this decided? Context: '{context}'"],
                "alternatives": [f"What alternatives were considered? Context: '{context}'"],
                "when": [f"When was this decided? Context: '{context}'"],
                "impact": [f"What was the impact? Context: '{context}'"]
            },
            "PROCESS": {
                "what": [f"What process? Context: '{context}'"],
                "steps": [f"What are the steps? Context: '{context}'"],
                "owner": [f"Who owns this process? Context: '{context}'"],
            },
            "OWNERSHIP": {
                "what": [f"What is owned? Context: '{context}'"],
                "who": [f"Who owns this? Context: '{context}'"],
            },
            "PROBLEM": {
                "what": [f"What is the problem? Context: '{context}'"],
                "impact": [f"What is the impact? Context: '{context}'"],
                "solution": [f"What is the solution? Context: '{context}'"],
            }
        }

        frame_questions = questions.get(frame.frame_type, {})
        return frame_questions.get(missing_slot, [f"What is the {missing_slot}? Context: '{context}'"])

    def _calculate_priority(self, frame_type: str, missing_slot: str) -> int:
        """Calculate priority"""
        high_priority = [
            ("DECISION", "why"),
            ("DECISION", "who_decided"),
            ("PROCESS", "owner"),
            ("CONSTRAINT", "why"),
            ("OWNERSHIP", "who"),
        ]

        if (frame_type, missing_slot) in high_priority:
            return 5
        elif frame_type in ["DECISION", "CONSTRAINT", "OWNERSHIP"]:
            return 4
        elif frame_type in ["PROCESS", "PROBLEM"]:
            return 3
        else:
            return 2

    def _frame_to_category(self, frame_type: str) -> str:
        """Map frame type to category"""
        mapping = {
            "DECISION": "decision",
            "PROCESS": "process",
            "DEFINITION": "context",
            "EVENT": "timeline",
            "CONSTRAINT": "technical",
            "METRIC": "outcome",
            "PROBLEM": "technical",
            "OWNERSHIP": "relationship",
        }
        return mapping.get(frame_type, "context")


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

class IntelligentGapDetector:
    """
    Main orchestrator for intelligent gap detection v2.0.

    Features:
    - 150+ trigger patterns
    - Entity normalization
    - Negation handling
    - Quality scoring
    - Deduplication
    """

    def __init__(self):
        self.frame_extractor = FrameExtractor()
        self.srl_analyzer = SemanticRoleAnalyzer()
        self.discourse_analyzer = DiscourseAnalyzer()
        self.kg_builder = KnowledgeGraphBuilder()
        self.verifier = CrossDocumentVerifier()
        self.question_generator = GroundedQuestionGenerator()
        self.coref_resolver = CoreferenceResolver()
        self.entity_normalizer = EntityNormalizer()

        self.all_frames: List[Frame] = []
        self.all_missing_roles: List[Dict] = []
        self.all_discourse_units: List[DiscourseUnit] = []

    def add_document(self, doc_id: str, title: str, content: str):
        """Process document through all layers"""
        logger.info(f"[IntelligentGap] Processing: {title}")

        content = content[:100000]

        # Layer 1: Frame Extraction
        frames = self.frame_extractor.extract_frames(content, doc_id)
        self.all_frames.extend(frames)
        logger.debug(f"  - Extracted {len(frames)} frames")

        # Layer 2: Semantic Role Analysis
        sentences = re.split(r'(?<=[.!?])\s+', content)
        missing_roles = self.srl_analyzer.analyze_missing_roles(sentences, doc_id)
        self.all_missing_roles.extend(missing_roles)

        # Layer 3: Discourse Analysis
        units = self.discourse_analyzer.analyze_discourse(content, doc_id)
        self.all_discourse_units.extend(units)

        # Layer 4: Knowledge Graph
        self.kg_builder.add_document(content, doc_id)

        # Layer 5: Cross-Document Verification
        self.verifier.add_document(content, doc_id, title)

    def analyze(self) -> Dict[str, Any]:
        """Run complete analysis"""
        logger.info("[IntelligentGap] Running analysis...")

        frames_with_gaps = [f for f in self.all_frames if f.missing_slots]

        unsupported_claims = self.discourse_analyzer.find_unsupported_claims(self.all_discourse_units)
        results_without_causes = self.discourse_analyzer.find_results_without_causes(self.all_discourse_units)

        missing_relations = self.kg_builder.find_missing_relations()
        isolated_entities = self.kg_builder.find_isolated_entities()
        bus_factor_risks = self.kg_builder.find_bus_factor_risks()

        contradictions = self.verifier.find_contradictions()
        single_source = self.verifier.find_single_source_knowledge()

        gaps = self.question_generator.generate_questions(
            frames=frames_with_gaps,
            missing_roles=self.all_missing_roles[:50],
            unsupported_claims=unsupported_claims[:20],
            missing_relations=missing_relations[:20],
            bus_factor_risks=bus_factor_risks,
            contradictions=contradictions[:10]
        )

        logger.info(f"[IntelligentGap] Complete: {len(gaps)} gaps")

        return {
            "gaps": gaps,
            "stats": {
                "total_frames": len(self.all_frames),
                "frames_with_gaps": len(frames_with_gaps),
                "missing_role_instances": len(self.all_missing_roles),
                "unsupported_claims": len(unsupported_claims),
                "results_without_causes": len(results_without_causes),
                "missing_relations": len(missing_relations),
                "isolated_entities": len(isolated_entities),
                "bus_factor_risks": len(bus_factor_risks),
                "contradictions": len(contradictions),
                "single_source_topics": len(single_source),
                "total_gaps": len(gaps)
            },
            "bus_factor_risks": bus_factor_risks,
            "contradictions": contradictions,
            "single_source_knowledge": single_source
        }

    def to_knowledge_gaps(self, result: Dict[str, Any], project_id: Optional[str] = None) -> List[Dict]:
        """Convert to database format"""
        knowledge_gaps = []

        for gap in result.get("gaps", []):
            knowledge_gaps.append({
                "title": gap.description[:200],
                "description": f"Pattern: {gap.source_pattern}. Evidence: {'; '.join(gap.evidence[:2])}",
                "category": gap.category,
                "priority": gap.priority,
                "questions": [{"text": q, "answered": False} for q in gap.grounded_questions],
                "context": {
                    "gap_type": gap.gap_type,
                    "source_pattern": gap.source_pattern,
                    "confidence": gap.confidence,
                    "quality_score": gap.quality_score,
                    "fingerprint": gap.fingerprint,
                    "related_entities": gap.related_entities[:5],
                    "evidence": gap.evidence[:3]
                }
            })

        return knowledge_gaps

    def clear(self):
        """Clear accumulated data"""
        self.all_frames = []
        self.all_missing_roles = []
        self.all_discourse_units = []
        self.kg_builder = KnowledgeGraphBuilder()
        self.verifier = CrossDocumentVerifier()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_intelligent_gap_detector() -> IntelligentGapDetector:
    """Factory function"""
    return IntelligentGapDetector()
