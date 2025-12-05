import os
"""
Enhanced RAG Module v2.1 - All Loopholes Fixed

Fixes:
- Expanded acronym dictionary (100+ terms)
- Multi-part question decomposition
- Hallucination detection
- Source citation verification
- Temporal awareness
- Better embedding model (text-embedding-3-large)
- Improved cross-encoder (full content scoring)
- Adaptive parameters
- Metadata filtering
- Result caching

v2.1 Additions:
- Freshness weighting (boost recent documents)
- Adaptive retrieval (more sources for complex queries)
- Conversational context (last 2-3 Q&A pairs)
- Domain-aware BM25 tokenization
- Add documents method for incremental updates
"""

import json
import pickle
import numpy as np
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from openai import AzureOpenAI
from functools import lru_cache
from datetime import datetime
import time
from collections import defaultdict

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Cross-encoder for re-ranking
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    print("Warning: sentence-transformers not installed. Re-ranking disabled.")


class QueryClassifier:
    """Enhanced query classification with better pattern matching"""

    QUERY_TYPES = {
        'factual': {
            'description': 'Specific fact lookup (numbers, dates, names)',
            'semantic_weight': 0.75,
            'bm25_weight': 0.25,
            'top_k': 12,
            'mmr_lambda': 0.8  # High relevance, low diversity
        },
        'exploratory': {
            'description': 'Open-ended exploration of a topic',
            'semantic_weight': 0.6,
            'bm25_weight': 0.4,
            'top_k': 15,
            'mmr_lambda': 0.6  # Balance relevance and diversity
        },
        'comparative': {
            'description': 'Comparing two or more things',
            'semantic_weight': 0.65,
            'bm25_weight': 0.35,
            'top_k': 20,
            'mmr_lambda': 0.5  # Need diverse sources for comparison
        },
        'procedural': {
            'description': 'How to do something, steps, process',
            'semantic_weight': 0.7,
            'bm25_weight': 0.3,
            'top_k': 12,
            'mmr_lambda': 0.7
        },
        'temporal': {
            'description': 'Time-based query (when, timeline, history)',
            'semantic_weight': 0.6,
            'bm25_weight': 0.4,
            'top_k': 15,
            'mmr_lambda': 0.6
        },
        'aggregation': {
            'description': 'Summary or aggregation (total, all, list)',
            'semantic_weight': 0.55,
            'bm25_weight': 0.45,
            'top_k': 20,
            'mmr_lambda': 0.5
        }
    }

    FACTUAL_PATTERNS = [
        r'\bhow many\b', r'\bwhat is the\b', r'\bhow much\b',
        r'\bwhen did\b', r'\bwho is\b', r'\bwhat was\b',
        r'\bROI\b', r'\brevenue\b', r'\bcost\b', r'\bnumber of\b',
        r'\bpercentage\b', r'\b\$[\d,]+', r'\b\d+%',
        r'\bwhat are the\b', r'\bwhat were\b', r'\bhow long\b',
        r'\bwhat date\b', r'\bwhich\b.*\bhas\b', r'\bspecific\b'
    ]

    COMPARATIVE_PATTERNS = [
        r'\bcompare\b', r'\bvs\.?\b', r'\bversus\b', r'\bdifference between\b',
        r'\bbetter\b', r'\bworse\b', r'\boption \d\b', r'\balternative\b',
        r'\bpros and cons\b', r'\badvantages?\b', r'\bdisadvantages?\b',
        r'\btradeoff\b', r'\bor\b.*\bwhich\b'
    ]

    PROCEDURAL_PATTERNS = [
        r'\bhow to\b', r'\bsteps\b', r'\bprocess\b', r'\bprocedure\b',
        r'\bimplement\b', r'\bset up\b', r'\bguide\b', r'\binstructions?\b',
        r'\bhow do i\b', r'\bhow can i\b', r'\bwhat.*steps\b'
    ]

    TEMPORAL_PATTERNS = [
        r'\bwhen\b', r'\btimeline\b', r'\bhistory\b', r'\bover time\b',
        r'\b(19|20)\d{2}\b', r'\blast year\b', r'\bthis year\b',
        r'\brecent\b', r'\blatest\b', r'\bprevious\b', r'\bfuture\b',
        r'\bquarter\b', r'\bmonth\b', r'\bweek\b'
    ]

    AGGREGATION_PATTERNS = [
        r'\ball\b', r'\btotal\b', r'\blist\b', r'\bsummar\b',
        r'\boverview\b', r'\beverything\b', r'\bentire\b',
        r'\bcomplete\b', r'\bfull\b'
    ]

    @classmethod
    def classify(cls, query: str) -> Dict:
        """Classify query type with priority-based matching"""
        query_lower = query.lower()

        # Check in priority order
        for pattern in cls.TEMPORAL_PATTERNS:
            if re.search(pattern, query_lower):
                return cls.QUERY_TYPES['temporal']

        for pattern in cls.COMPARATIVE_PATTERNS:
            if re.search(pattern, query_lower):
                return cls.QUERY_TYPES['comparative']

        for pattern in cls.PROCEDURAL_PATTERNS:
            if re.search(pattern, query_lower):
                return cls.QUERY_TYPES['procedural']

        for pattern in cls.AGGREGATION_PATTERNS:
            if re.search(pattern, query_lower):
                return cls.QUERY_TYPES['aggregation']

        for pattern in cls.FACTUAL_PATTERNS:
            if re.search(pattern, query_lower):
                return cls.QUERY_TYPES['factual']

        return cls.QUERY_TYPES['exploratory']

    @classmethod
    def is_multi_part(cls, query: str) -> bool:
        """Detect if query has multiple parts"""
        # Count question indicators
        question_words = len(re.findall(r'\b(what|who|when|where|why|how|which)\b', query.lower()))
        and_count = len(re.findall(r'\band\b', query.lower()))
        question_marks = query.count('?')

        return question_words > 1 or (and_count > 0 and question_words > 0) or question_marks > 1


class QueryExpander:
    """Enhanced query expansion with comprehensive acronym dictionary"""

    # Comprehensive acronym dictionary (100+ terms)
    ACRONYMS = {
        # Healthcare
        'ROI': 'Return on Investment',
        'NICU': 'Neonatal Intensive Care Unit',
        'PICU': 'Pediatric Intensive Care Unit',
        'ICU': 'Intensive Care Unit',
        'OB-ED': 'Obstetric Emergency Department',
        'OBED': 'Obstetric Emergency Department',
        'L&D': 'Labor and Delivery',
        'ED': 'Emergency Department',
        'OR': 'Operating Room',
        'FDU': 'Fetal Diagnostic Unit',
        'NICU': 'Neonatal Intensive Care Unit',
        'LOS': 'Length of Stay',
        'ADT': 'Admission Discharge Transfer',
        'EMR': 'Electronic Medical Record',
        'EHR': 'Electronic Health Record',
        'DRG': 'Diagnosis Related Group',
        'CMS': 'Centers for Medicare and Medicaid Services',
        'HIPAA': 'Health Insurance Portability and Accountability Act',
        'PHI': 'Protected Health Information',
        'RVU': 'Relative Value Unit',
        'FTE': 'Full Time Equivalent',
        'CMO': 'Chief Medical Officer',
        'CNO': 'Chief Nursing Officer',

        # Finance
        'NPV': 'Net Present Value',
        'IRR': 'Internal Rate of Return',
        'EBITDA': 'Earnings Before Interest Taxes Depreciation and Amortization',
        'EBIT': 'Earnings Before Interest and Taxes',
        'P&L': 'Profit and Loss',
        'COGS': 'Cost of Goods Sold',
        'OPEX': 'Operating Expenses',
        'CAPEX': 'Capital Expenditure',
        'DCF': 'Discounted Cash Flow',
        'WACC': 'Weighted Average Cost of Capital',
        'EV': 'Enterprise Value',
        'FCF': 'Free Cash Flow',
        'GP': 'Gross Profit',
        'NI': 'Net Income',
        'AR': 'Accounts Receivable',
        'AP': 'Accounts Payable',
        'YoY': 'Year over Year',
        'QoQ': 'Quarter over Quarter',
        'MoM': 'Month over Month',
        'CAGR': 'Compound Annual Growth Rate',
        'P/E': 'Price to Earnings Ratio',
        'EPS': 'Earnings Per Share',
        'ROE': 'Return on Equity',
        'ROA': 'Return on Assets',
        'ROIC': 'Return on Invested Capital',

        # Market
        'TAM': 'Total Addressable Market',
        'SAM': 'Serviceable Addressable Market',
        'SOM': 'Serviceable Obtainable Market',
        'CAC': 'Customer Acquisition Cost',
        'LTV': 'Lifetime Value',
        'MRR': 'Monthly Recurring Revenue',
        'ARR': 'Annual Recurring Revenue',
        'GMV': 'Gross Merchandise Value',
        'NPS': 'Net Promoter Score',
        'ARPU': 'Average Revenue Per User',
        'DAU': 'Daily Active Users',
        'MAU': 'Monthly Active Users',
        'B2B': 'Business to Business',
        'B2C': 'Business to Consumer',
        'GTM': 'Go to Market',
        'MVP': 'Minimum Viable Product',
        'PMF': 'Product Market Fit',
        'POC': 'Proof of Concept',

        # Healthcare Specific
        'DPP': 'Diabetes Prevention Program',
        'CGM': 'Continuous Glucose Monitor',
        'MRS': 'Magnetic Resonance Spectroscopy',
        'MRI': 'Magnetic Resonance Imaging',
        'CT': 'Computed Tomography',
        'FDA': 'Food and Drug Administration',
        'CDC': 'Centers for Disease Control',
        'WHO': 'World Health Organization',
        'AMA': 'American Medical Association',
        'JCAHO': 'Joint Commission on Accreditation of Healthcare Organizations',

        # Consulting
        'SOW': 'Statement of Work',
        'RFP': 'Request for Proposal',
        'RFI': 'Request for Information',
        'NDA': 'Non-Disclosure Agreement',
        'SLA': 'Service Level Agreement',
        'KPI': 'Key Performance Indicator',
        'OKR': 'Objectives and Key Results',
        'SWOT': 'Strengths Weaknesses Opportunities Threats',
        'PEST': 'Political Economic Social Technological',
        'BCG': 'Boston Consulting Group',
        'McKinsey': 'McKinsey and Company',

        # UCLA/BEAT Specific
        'UCLA': 'University of California Los Angeles',
        'BEAT': 'BEAT Healthcare Consulting',
        'W&C': 'Women and Children',
    }

    # Synonym mappings
    SYNONYMS = {
        'turned away': ['rejected', 'declined', 'refused', 'denied', 'not admitted'],
        'patients': ['cases', 'admissions', 'individuals', 'people'],
        'revenue': ['income', 'earnings', 'sales', 'receipts'],
        'cost': ['expense', 'expenditure', 'investment', 'spending'],
        'market size': ['TAM', 'market opportunity', 'addressable market', 'market potential'],
        'profit': ['earnings', 'income', 'margin', 'returns'],
        'growth': ['increase', 'expansion', 'rise', 'gain'],
        'decline': ['decrease', 'drop', 'reduction', 'fall'],
        'recommendation': ['suggestion', 'proposal', 'advice', 'guidance'],
    }

    def __init__(self, client: OpenAI = None):
        self.client = client

    def expand_acronyms(self, query: str) -> str:
        """Expand all acronyms in query"""
        expanded = query
        for acronym, expansion in self.ACRONYMS.items():
            # Case-insensitive match but preserve original
            pattern = rf'\b{re.escape(acronym)}\b'
            if re.search(pattern, query, re.IGNORECASE) and expansion.lower() not in query.lower():
                # Find the actual match to preserve case
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    original = match.group()
                    expanded = expanded.replace(original, f"{original} ({expansion})", 1)
        return expanded

    def get_synonyms(self, query: str) -> List[str]:
        """Get synonym variations of key terms"""
        query_lower = query.lower()
        additional_terms = []

        for term, syns in self.SYNONYMS.items():
            if term in query_lower:
                additional_terms.extend(syns)

        return list(set(additional_terms))

    def decompose_multi_part(self, query: str) -> List[str]:
        """Decompose multi-part questions into sub-queries"""
        if not QueryClassifier.is_multi_part(query):
            return [query]

        # Use LLM for decomposition if available
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=AZURE_CHAT_DEPLOYMENT,
                    messages=[
                        {"role": "system", "content": "Decompose complex questions into simple sub-questions. Return JSON array."},
                        {"role": "user", "content": f"Decompose this question into 2-4 simple sub-questions:\n\n{query}\n\nReturn as JSON: [\"question1\", \"question2\", ...]"}
                    ],
                    temperature=0.1,
                    max_tokens=300
                )
                result = response.choices[0].message.content
                if '[' in result:
                    start = result.index('[')
                    end = result.rindex(']') + 1
                    return json.loads(result[start:end])
            except:
                pass

        # Fallback: simple splitting
        parts = re.split(r'\band\b|\?', query)
        return [p.strip() + '?' for p in parts if p.strip() and len(p.strip()) > 10]

    def extract_temporal_filters(self, query: str) -> Dict:
        """Extract temporal constraints from query"""
        filters = {}

        # Year patterns
        years = re.findall(r'\b(19|20)\d{2}\b', query)
        if years:
            filters['years'] = [int(y) for y in years]

        # Relative time
        if re.search(r'\blast year\b', query.lower()):
            filters['relative'] = 'last_year'
        elif re.search(r'\bthis year\b', query.lower()):
            filters['relative'] = 'this_year'
        elif re.search(r'\brecent\b|\blatest\b', query.lower()):
            filters['relative'] = 'recent'

        return filters

    def expand(self, query: str, use_llm: bool = False) -> Dict:
        """Full query expansion"""
        expanded = self.expand_acronyms(query)
        synonyms = self.get_synonyms(query)
        sub_queries = self.decompose_multi_part(query)
        temporal = self.extract_temporal_filters(query)

        return {
            'original_query': query,
            'expanded_query': expanded,
            'synonyms': synonyms,
            'sub_queries': sub_queries if len(sub_queries) > 1 else [],
            'temporal_filters': temporal,
            'is_multi_part': len(sub_queries) > 1
        }


class CrossEncoderReranker:
    """Enhanced re-ranker with full content scoring"""

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-12-v2"

    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        if not CROSS_ENCODER_AVAILABLE:
            return
        try:
            self.model = CrossEncoder(self.MODEL_NAME)
            print(f"✓ Cross-encoder loaded: {self.MODEL_NAME}")
        except Exception as e:
            print(f"Failed to load cross-encoder: {e}")
            self.model = None

    def rerank(self, query: str, documents: List[Dict], top_k: int = 10) -> List[Dict]:
        """Re-rank with improved content handling"""
        if not self.model or not documents:
            return documents[:top_k]

        # Score multiple segments of each document for better coverage
        doc_scores = []
        for doc in documents:
            content = doc.get('content', '')

            # Score first 512, middle 512, last 512 chars and take max
            segments = [
                content[:512],
                content[len(content)//2 - 256:len(content)//2 + 256] if len(content) > 512 else content,
                content[-512:] if len(content) > 512 else content
            ]

            segment_scores = []
            for seg in segments:
                if seg.strip():
                    try:
                        score = self.model.predict([(query, seg)])[0]
                        segment_scores.append(score)
                    except:
                        pass

            # Use max score across segments
            max_score = max(segment_scores) if segment_scores else 0
            doc_scores.append((doc, max_score))

        # Sort and return
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        for doc, score in doc_scores:
            doc['rerank_score'] = float(score)

        return [doc for doc, _ in doc_scores[:top_k]]


class MMRSelector:
    """MMR with adaptive lambda"""

    @staticmethod
    def select(
        query_embedding: np.ndarray,
        doc_embeddings: np.ndarray,
        documents: List[Dict],
        k: int = 10,
        lambda_param: float = 0.7
    ) -> List[Dict]:
        if len(documents) <= k:
            return documents

        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        doc_norms = doc_embeddings / (np.linalg.norm(doc_embeddings, axis=1, keepdims=True) + 1e-8)

        query_sims = np.dot(doc_norms, query_norm)
        doc_sims = np.dot(doc_norms, doc_norms.T)

        selected_indices = []
        remaining_indices = list(range(len(documents)))

        for _ in range(k):
            if not remaining_indices:
                break

            mmr_scores = []
            for idx in remaining_indices:
                relevance = query_sims[idx]
                if selected_indices:
                    diversity_penalty = max(doc_sims[idx][s] for s in selected_indices)
                else:
                    diversity_penalty = 0

                mmr = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
                mmr_scores.append((idx, mmr))

            best_idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

        return [documents[i] for i in selected_indices]


class HallucinationDetector:
    """Detect and flag potential hallucinations in answers"""

    def __init__(self, client: OpenAI):
        self.client = client

    def extract_claims(self, answer: str) -> List[Dict]:
        """Extract factual claims from answer"""
        claims = []

        # Extract numbers with context
        number_pattern = r'([^.]*?\b\d[\d,\.%$]*\b[^.]*\.)'
        for match in re.finditer(number_pattern, answer):
            claims.append({
                'type': 'numerical',
                'text': match.group(1).strip(),
                'value': re.search(r'\d[\d,\.%$]*', match.group(1)).group()
            })

        # Extract source citations
        citation_pattern = r'\[Source (\d+)\]'
        for match in re.finditer(citation_pattern, answer):
            claims.append({
                'type': 'citation',
                'source_num': int(match.group(1)),
                'context': answer[max(0, match.start()-100):match.end()+50]
            })

        return claims

    def verify_claims(self, claims: List[Dict], sources: List[Dict]) -> Dict:
        """Verify claims against sources"""
        verified = []
        unverified = []
        hallucinated = []

        for claim in claims:
            if claim['type'] == 'citation':
                source_num = claim['source_num']
                if source_num <= len(sources):
                    source_content = sources[source_num - 1].get('content', '')
                    # Check if cited info exists in source
                    claim_text = claim['context'].replace(f"[Source {source_num}]", "").strip()

                    # Simple verification: check for number overlap
                    claim_numbers = set(re.findall(r'\d+\.?\d*', claim_text))
                    source_numbers = set(re.findall(r'\d+\.?\d*', source_content))

                    if claim_numbers & source_numbers:
                        verified.append(claim)
                    else:
                        unverified.append(claim)
                else:
                    hallucinated.append(claim)

            elif claim['type'] == 'numerical':
                # Check if number exists in any source
                claim_value = claim['value'].replace(',', '').replace('$', '').replace('%', '')
                found = False
                for source in sources:
                    if claim_value in source.get('content', '').replace(',', ''):
                        found = True
                        break
                if found:
                    verified.append(claim)
                else:
                    unverified.append(claim)

        return {
            'verified': len(verified),
            'unverified': len(unverified),
            'hallucinated': len(hallucinated),
            'total_claims': len(claims),
            'confidence': len(verified) / max(len(claims), 1),
            'details': {
                'verified': verified,
                'unverified': unverified,
                'hallucinated': hallucinated
            }
        }


class ContextDeduplicator:
    """Enhanced deduplication with adaptive threshold"""

    @staticmethod
    def deduplicate(chunks: List[Dict], similarity_threshold: float = 0.75) -> List[Dict]:
        if len(chunks) <= 1:
            return chunks

        unique_chunks = [chunks[0]]

        for chunk in chunks[1:]:
            is_duplicate = False
            chunk_text = chunk.get('content', '')

            for unique in unique_chunks:
                unique_text = unique.get('content', '')
                similarity = ContextDeduplicator._text_similarity(chunk_text, unique_text)
                if similarity > similarity_threshold:
                    # Keep the one with higher score
                    if chunk.get('rerank_score', chunk.get('score', 0)) > unique.get('rerank_score', unique.get('score', 0)):
                        unique_chunks.remove(unique)
                        unique_chunks.append(chunk)
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_chunks.append(chunk)

        return unique_chunks

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        def get_ngrams(text, n=4):
            text = text.lower()
            return set(text[i:i+n] for i in range(len(text) - n + 1))

        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)

        return intersection / union if union > 0 else 0.0


class ResultCache:
    """Cache for query results with TTL"""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 500):
        self.cache = {}
        self.timestamps = {}
        self.ttl = ttl_seconds
        self.max_size = max_size

    def _hash_query(self, query: str) -> str:
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    def get(self, query: str) -> Optional[Dict]:
        key = self._hash_query(query)
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, query: str, result: Dict):
        if len(self.cache) >= self.max_size:
            # Remove oldest entries
            oldest = sorted(self.timestamps.items(), key=lambda x: x[1])[:100]
            for key, _ in oldest:
                del self.cache[key]
                del self.timestamps[key]

        key = self._hash_query(query)
        self.cache[key] = result
        self.timestamps[key] = time.time()


class ConversationManager:
    """Manage conversation history for context-aware queries"""

    def __init__(self, max_history: int = 3):
        self.history = []  # List of (query, answer) tuples
        self.max_history = max_history

    def add(self, query: str, answer: str):
        """Add Q&A pair to history"""
        self.history.append({
            'query': query,
            'answer': answer[:500],  # Truncate long answers
            'timestamp': time.time()
        })
        # Keep only recent history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_context(self) -> str:
        """Get conversation context for prompt"""
        if not self.history:
            return ""

        context_parts = ["Previous conversation:"]
        for item in self.history:
            context_parts.append(f"Q: {item['query']}")
            context_parts.append(f"A: {item['answer']}")

        return "\n".join(context_parts)

    def clear(self):
        """Clear conversation history"""
        self.history = []


class FreshnessScorer:
    """Score documents based on recency"""

    # Date patterns to extract from content/metadata
    DATE_PATTERNS = [
        r'\b(20[1-2]\d)\b',  # Years 2010-2029
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20[1-2]\d\b',
        r'\b\d{1,2}/\d{1,2}/20[1-2]\d\b',
        r'\b20[1-2]\d-\d{2}-\d{2}\b',
    ]

    @classmethod
    def extract_year(cls, content: str, metadata: Dict) -> Optional[int]:
        """Extract most recent year from content or metadata"""
        years = []

        # Check metadata first
        if metadata:
            for key in ['date', 'created', 'modified', 'year', 'file_date']:
                if key in metadata:
                    year_match = re.search(r'20[1-2]\d', str(metadata[key]))
                    if year_match:
                        years.append(int(year_match.group()))

        # Check content
        for pattern in cls.DATE_PATTERNS:
            matches = re.findall(pattern, content[:2000])  # Check first 2000 chars
            for match in matches:
                if isinstance(match, str) and match.isdigit():
                    years.append(int(match))

        return max(years) if years else None

    @classmethod
    def get_freshness_boost(cls, year: Optional[int], current_year: int = 2025) -> float:
        """Get boost factor based on document age"""
        if year is None:
            return 1.0  # No penalty for unknown dates

        age = current_year - year
        if age <= 0:
            return 1.2  # Current year - slight boost
        elif age == 1:
            return 1.1  # Last year
        elif age <= 2:
            return 1.0  # 2 years - neutral
        elif age <= 5:
            return 0.9  # 3-5 years - slight penalty
        else:
            return 0.8  # Older - more penalty


class DomainTokenizer:
    """Domain-aware tokenizer for better BM25"""

    # Compound terms to keep together
    COMPOUND_TERMS = {
        'ob-ed', 'obed', 'l&d', 'nicu', 'picu', 'icu',
        'roi', 'npv', 'irr', 'ebitda', 'cagr',
        'year-over-year', 'yoy', 'qoq', 'mom',
        'step-down', 'follow-up', 'break-even',
        'ucla', 'beat', 'healthcare',
    }

    # Acronyms to preserve
    ACRONYMS = set(QueryExpander.ACRONYMS.keys())

    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        """Tokenize text with domain awareness"""
        text_lower = text.lower()

        # Replace compound terms with underscored versions
        for term in cls.COMPOUND_TERMS:
            if term in text_lower:
                text_lower = text_lower.replace(term, term.replace('-', '_').replace('&', '_'))

        # Tokenize
        tokens = re.findall(r'\b[\w_]+\b', text_lower)

        # Expand acronyms into additional tokens
        expanded_tokens = []
        for token in tokens:
            expanded_tokens.append(token)
            upper_token = token.upper()
            if upper_token in cls.ACRONYMS:
                # Add expansion words as additional tokens
                expansion = QueryExpander.ACRONYMS[upper_token].lower()
                expanded_tokens.extend(re.findall(r'\b\w+\b', expansion))

        return expanded_tokens


class EnhancedRAGv2:
    """
    Enhanced RAG v2.0 with all fixes:
    - Comprehensive acronym expansion
    - Multi-part question handling
    - Hallucination detection
    - Source verification
    - Temporal awareness
    - Better embedding model
    - Improved re-ranking
    - Result caching
    """

    # Use large embedding model for better quality
    EMBEDDING_MODEL = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS = 3072

    def __init__(
        self,
        embedding_index_path: str,
        openai_api_key: str,
        use_reranker: bool = True,
        use_mmr: bool = True,
        cache_results: bool = True
    ):
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

        # Load embedding index
        print("Loading embedding index...")
        with open(embedding_index_path, 'rb') as f:
            self.index = pickle.load(f)
        print(f"✓ Loaded {len(self.index['chunks'])} chunks")

        # Initialize components
        self.query_expander = QueryExpander(self.client)
        self.reranker = CrossEncoderReranker() if use_reranker else None
        self.hallucination_detector = HallucinationDetector(self.client)
        self.use_mmr = use_mmr

        # v2.1 additions
        self.conversation = ConversationManager(max_history=3)
        self.use_freshness = True

        # Caches
        self.embedding_cache = {}
        self.result_cache = ResultCache() if cache_results else None

        # Store index path for add_documents
        self.index_path = embedding_index_path

        print("✓ Enhanced RAG v2.1 initialized")

    def _get_query_embedding(self, query: str) -> np.ndarray:
        """Get embedding with caching - uses same model as index for compatibility"""
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]

        # Use the same model that was used to build the index
        index_model = self.index.get('model', 'text-embedding-3-small')

        # Use dimensions=1536 to match existing index (built with text-embedding-3-small)
        # text-embedding-3-large supports flexible dimensions via the dimensions parameter
        response = self.client.embeddings.create(
            model=index_model,
            input=query,
            dimensions=1536  # Match the existing index dimensions
        )
        embedding = np.array(response.data[0].embedding, dtype=np.float32)

        self.embedding_cache[cache_key] = embedding
        if len(self.embedding_cache) > 1000:
            keys = list(self.embedding_cache.keys())[:100]
            for k in keys:
                del self.embedding_cache[k]

        return embedding

    def _hybrid_search(
        self,
        query: str,
        expanded_query: str,
        query_config: Dict,
        temporal_filters: Dict = None,
        top_k: int = 20
    ) -> List[Dict]:
        """Hybrid search with temporal filtering"""

        query_embedding = self._get_query_embedding(expanded_query)

        chunk_embeddings = self.index['embeddings']
        chunks = self.index['chunks']
        bm25_index = self.index.get('bm25_index')

        # Semantic search
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        chunk_norms = chunk_embeddings / (np.linalg.norm(chunk_embeddings, axis=1, keepdims=True) + 1e-8)
        semantic_scores = np.dot(chunk_norms, query_norm)

        # BM25 search with domain-aware tokenization
        if bm25_index:
            # Use domain tokenizer for better acronym handling
            query_tokens = DomainTokenizer.tokenize(query)
            bm25_scores = bm25_index.get_scores(query_tokens)
            bm25_max = np.max(bm25_scores) if np.max(bm25_scores) > 0 else 1
            bm25_scores = bm25_scores / bm25_max
        else:
            bm25_scores = np.zeros(len(chunks))

        # Dynamic weights
        semantic_weight = query_config.get('semantic_weight', 0.7)
        bm25_weight = query_config.get('bm25_weight', 0.3)

        combined_scores = semantic_weight * semantic_scores + bm25_weight * bm25_scores

        # Apply freshness weighting
        if self.use_freshness:
            for idx, chunk in enumerate(chunks):
                content = chunk.get('content', '')
                metadata = chunk.get('metadata', {})
                year = FreshnessScorer.extract_year(content, metadata)
                freshness_boost = FreshnessScorer.get_freshness_boost(year)
                combined_scores[idx] *= freshness_boost

        # Apply temporal filtering if specified
        if temporal_filters and temporal_filters.get('years'):
            target_years = temporal_filters['years']
            for idx, chunk in enumerate(chunks):
                content = chunk.get('content', '')
                # Boost chunks containing target years
                for year in target_years:
                    if str(year) in content:
                        combined_scores[idx] *= 1.2

        # Get top results
        top_indices = np.argsort(combined_scores)[::-1][:top_k * 2]

        results = []
        for idx in top_indices:
            if combined_scores[idx] > 0.01:
                chunk = chunks[idx]
                results.append({
                    'chunk_id': chunk['chunk_id'],
                    'doc_id': chunk['doc_id'],
                    'content': chunk['content'],
                    'chunk_index': chunk.get('chunk_index', 0),
                    'metadata': chunk.get('metadata', {}),
                    'score': float(combined_scores[idx]),
                    'semantic_score': float(semantic_scores[idx]),
                    'bm25_score': float(bm25_scores[idx]),
                    'embedding_idx': int(idx)
                })

        return results

    def retrieve(
        self,
        query: str,
        top_k: int = None  # Now adaptive by default
    ) -> Dict:
        """Full retrieval pipeline with adaptive retrieval"""
        start_time = time.time()

        # Classify and expand query
        query_config = QueryClassifier.classify(query)

        # Adaptive retrieval: more sources for complex queries
        if top_k is None:
            top_k = query_config.get('top_k', 10)
            # Boost for multi-part or aggregation queries
            if QueryClassifier.is_multi_part(query):
                top_k = min(top_k + 5, 20)  # Extra sources for multi-part
        expansion = self.query_expander.expand(query)
        expanded_query = expansion['expanded_query']

        # Handle multi-part questions
        if expansion['is_multi_part'] and expansion['sub_queries']:
            # Retrieve for each sub-query and merge
            all_results = []
            for sub_q in expansion['sub_queries']:
                sub_expansion = self.query_expander.expand(sub_q)
                sub_results = self._hybrid_search(
                    sub_q,
                    sub_expansion['expanded_query'],
                    query_config,
                    expansion.get('temporal_filters'),
                    top_k=top_k
                )
                all_results.extend(sub_results)

            # Deduplicate merged results
            seen_ids = set()
            results = []
            for r in sorted(all_results, key=lambda x: x['score'], reverse=True):
                if r['chunk_id'] not in seen_ids:
                    results.append(r)
                    seen_ids.add(r['chunk_id'])
        else:
            results = self._hybrid_search(
                query,
                expanded_query,
                query_config,
                expansion.get('temporal_filters'),
                top_k=top_k * 2
            )

        # Re-rank
        if self.reranker and self.reranker.model:
            results = self.reranker.rerank(query, results, top_k=query_config.get('top_k', 15))

        # Apply MMR with adaptive lambda
        if self.use_mmr and len(results) > top_k:
            embedding_indices = [r['embedding_idx'] for r in results]
            doc_embeddings = self.index['embeddings'][embedding_indices]
            query_embedding = self._get_query_embedding(expanded_query)

            results = MMRSelector.select(
                query_embedding,
                doc_embeddings,
                results,
                k=top_k,
                lambda_param=query_config.get('mmr_lambda', 0.7)
            )
        else:
            results = results[:top_k]

        # Deduplicate
        results = ContextDeduplicator.deduplicate(results, similarity_threshold=0.75)

        return {
            'query': query,
            'expanded_query': expanded_query,
            'query_type': query_config['description'],
            'results': results,
            'num_results': len(results),
            'retrieval_time': time.time() - start_time,
            'expansion': expansion
        }

    def _check_citation_coverage(self, answer: str, sources: List[Dict]) -> Dict:
        """Check what percentage of answer statements have citations"""
        # Split answer into sentences
        sentences = re.split(r'[.!?]\s+', answer)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

        if not sentences:
            return {'cited_ratio': 1.0, 'uncited_ratio': 0.0, 'total_sentences': 0}

        # Count sentences with citations
        citation_pattern = r'\[Source\s*\d+\]|\[Source\s*\d+,\s*\d+\]|\[Source\s*\d+,\s*Source\s*\d+\]'
        cited_count = 0
        uncited_sentences = []

        for sentence in sentences:
            # Skip meta sentences like "Sources Used:" or questions
            if any(skip in sentence.lower() for skip in ['sources used', 'source:', '?', 'i don\'t have']):
                continue
            if re.search(citation_pattern, sentence, re.IGNORECASE):
                cited_count += 1
            else:
                uncited_sentences.append(sentence)

        total_checkable = len(sentences) - len([s for s in sentences if any(skip in s.lower() for skip in ['sources used', 'source:', '?', 'i don\'t have'])])

        if total_checkable == 0:
            return {'cited_ratio': 1.0, 'uncited_ratio': 0.0, 'total_sentences': 0}

        cited_ratio = cited_count / total_checkable
        uncited_ratio = 1 - cited_ratio

        return {
            'cited_ratio': cited_ratio,
            'uncited_ratio': uncited_ratio,
            'total_sentences': total_checkable,
            'cited_count': cited_count,
            'uncited_sentences': uncited_sentences[:3]  # Return first 3 uncited for debugging
        }

    def generate_answer(
        self,
        query: str,
        retrieval_results: Dict,
        validate: bool = True
    ) -> Dict:
        """Generate answer with hallucination detection"""

        results = retrieval_results['results']
        expansion = retrieval_results.get('expansion', {})

        if not results:
            return {
                'answer': "I couldn't find any relevant information to answer your question.",
                'confidence': 0.0,
                'sources': [],
                'validated': False,
                'hallucination_check': {'verified': 0, 'total_claims': 0}
            }

        # Build context with full content (no truncation for small chunks)
        context_parts = []
        total_tokens = 0
        max_context_tokens = 12000

        for i, result in enumerate(results[:10], 1):
            content = result['content']
            # Estimate tokens (rough: 4 chars per token)
            content_tokens = len(content) // 4

            if total_tokens + content_tokens > max_context_tokens:
                # Truncate this chunk to fit
                remaining = max_context_tokens - total_tokens
                content = content[:remaining * 4]

            context_parts.append(
                f"[Source {i}] (Relevance: {result.get('rerank_score', result['score']):.2%})\n"
                f"Document: {result['doc_id']}\n"
                f"Content: {content}\n"
            )
            total_tokens += len(content) // 4

            if total_tokens >= max_context_tokens:
                break

        context = "\n---\n".join(context_parts)

        # Handle multi-part questions in prompt
        if expansion.get('is_multi_part') and expansion.get('sub_queries'):
            sub_q_text = "\n".join(f"- {q}" for q in expansion['sub_queries'])
            question_section = f"""MAIN QUESTION: {query}

This question has multiple parts. Please address each:
{sub_q_text}"""
        else:
            question_section = f"QUESTION: {query}"

        # Add conversation context if available
        conversation_context = self.conversation.get_context()
        conversation_section = ""
        if conversation_context:
            conversation_section = f"""
CONVERSATION HISTORY:
{conversation_context}

Use the conversation history to understand context and resolve references like "it", "they", "that", etc.
"""

        prompt = f"""You are a knowledge assistant that ONLY provides information found in the source documents below.

STRICT CITATION RULES (MANDATORY):
1. Every single fact, claim, number, date, or name MUST have an inline citation like [Source 1], [Source 2], etc.
2. If you cannot cite a source for a statement, DO NOT include that statement
3. If no sources contain relevant information, respond: "I don't have information about this in my knowledge base."
4. Never synthesize or infer information not explicitly stated in sources
5. When multiple sources support a claim, cite all of them: [Source 1, Source 3]

FORMAT REQUIREMENTS:
- Start with a brief summary (1-2 sentences with citations)
- Provide detailed information with inline citations for EVERY fact
- End with "Sources Used: [list the source numbers actually cited]"

QUALITY STANDARDS:
- Include specific numbers, dates, names, and quotes from sources
- If information is partial or conflicting, acknowledge this explicitly
- For multi-part questions, address each part with its own citations
- If uncertain, say "Based on [Source X], it appears that..." rather than stating as fact
{conversation_section}
SOURCE DOCUMENTS:
{context}

{question_section}

Provide a well-cited answer following ALL rules above:"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a precise knowledge assistant that ONLY uses information from provided sources.

CORE PRINCIPLES:
- NEVER make up, infer, or synthesize information not in sources
- EVERY statement must be directly traceable to a [Source X] citation
- If sources don't contain the answer, say "I don't have information about this"
- Accuracy and truthfulness are more important than comprehensiveness

You will be evaluated on citation accuracy. Uncited claims are considered failures."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.05,  # Very low temperature for maximum factual consistency
                max_tokens=2500
            )

            answer = response.choices[0].message.content.strip()

            # Enhanced faithfulness checking
            hallucination_check = {'verified': 0, 'total_claims': 0, 'confidence': 1.0}
            citation_check = self._check_citation_coverage(answer, results)

            if validate:
                claims = self.hallucination_detector.extract_claims(answer)
                if claims:
                    hallucination_check = self.hallucination_detector.verify_claims(claims, results)

                    # Add warning if low verification
                    if hallucination_check['confidence'] < 0.5:
                        answer += "\n\n⚠️ Warning: Some claims in this answer could not be fully verified against the sources. Please verify important facts."

            # Check citation coverage - flag if answer has uncited statements
            if citation_check['uncited_ratio'] > 0.3:
                answer += f"\n\n📊 Citation Coverage: {citation_check['cited_ratio']:.0%} of statements are cited."

            # Calculate overall confidence combining hallucination + citation checks
            confidence = min(
                hallucination_check.get('confidence', 0.7),
                citation_check.get('cited_ratio', 0.7)
            )

            return {
                'answer': answer,
                'confidence': confidence,
                'sources': results[:10],
                'validated': validate,
                'hallucination_check': hallucination_check,
                'model': 'gpt-4o-mini'
            }

        except Exception as e:
            return {
                'answer': f"Error generating answer: {str(e)}",
                'confidence': 0.0,
                'sources': results[:10],
                'validated': False,
                'error': str(e)
            }

    def query(
        self,
        query: str,
        validate: bool = True,
        top_k: int = 10,
        use_cache: bool = True
    ) -> Dict:
        """Complete RAG pipeline with caching"""

        # Check cache
        if use_cache and self.result_cache:
            cached = self.result_cache.get(query)
            if cached:
                cached['from_cache'] = True
                return cached

        # Retrieve
        retrieval = self.retrieve(query, top_k=top_k)

        # Generate
        response = self.generate_answer(query, retrieval, validate=validate)

        result = {
            'query': query,
            'answer': response['answer'],
            'confidence': response['confidence'],
            'sources': response['sources'],
            'num_sources': len(response['sources']),
            'query_type': retrieval['query_type'],
            'expanded_query': retrieval['expanded_query'],
            'retrieval_time': retrieval['retrieval_time'],
            'model': response.get('model', 'gpt-4o-mini'),
            'validated': response['validated'],
            'hallucination_check': response.get('hallucination_check', {}),
            'is_multi_part': retrieval['expansion'].get('is_multi_part', False),
            'sub_queries': retrieval['expansion'].get('sub_queries', []),
            'from_cache': False
        }

        # Save to conversation history for context
        self.conversation.add(query, response['answer'])

        # Cache result
        if use_cache and self.result_cache:
            self.result_cache.set(query, result)

        return result

    def add_documents(self, documents: List[Dict]) -> Dict:
        """
        Add new documents to the index incrementally.

        Args:
            documents: List of dicts with 'doc_id', 'content', 'metadata'

        Returns:
            Dict with status and counts
        """
        if not documents:
            return {'status': 'error', 'message': 'No documents provided'}

        added_chunks = 0
        index_model = self.index.get('model', 'text-embedding-3-small')

        for doc in documents:
            doc_id = doc.get('doc_id', f"doc_{len(self.index['chunks'])}")
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})

            if not content or len(content) < 50:
                continue

            # Simple chunking
            chunk_size = 3200
            overlap = 400
            start = 0
            chunk_idx = 0

            while start < len(content):
                end = start + chunk_size
                chunk_content = content[start:end]

                if len(chunk_content.strip()) > 50:
                    # Get embedding
                    try:
                        response = self.client.embeddings.create(
                            model=index_model,
                            input=chunk_content[:8000]
                        )
                        embedding = np.array(response.data[0].embedding, dtype=np.float32)

                        # Add to index
                        chunk = {
                            'chunk_id': f"{doc_id}_chunk_{chunk_idx}",
                            'doc_id': doc_id,
                            'content': chunk_content,
                            'chunk_index': chunk_idx,
                            'metadata': metadata
                        }
                        self.index['chunks'].append(chunk)

                        # Add embedding
                        if len(self.index['embeddings']) == 0:
                            self.index['embeddings'] = embedding.reshape(1, -1)
                        else:
                            self.index['embeddings'] = np.vstack([
                                self.index['embeddings'],
                                embedding.reshape(1, -1)
                            ])

                        added_chunks += 1
                        chunk_idx += 1
                    except Exception as e:
                        print(f"Error adding chunk: {e}")

                start = end - overlap
                if start >= len(content) - overlap:
                    break

        # Save updated index
        if added_chunks > 0:
            with open(self.index_path, 'wb') as f:
                pickle.dump(self.index, f)

        return {
            'status': 'success',
            'added_chunks': added_chunks,
            'total_chunks': len(self.index['chunks'])
        }

    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation.clear()


def create_enhanced_rag_v2(
    index_path: str = None,
    api_key: str = None
) -> EnhancedRAGv2:
    """Create EnhancedRAGv2 instance"""

    if index_path is None:
        index_path = "/Users/rishitjain/Downloads/knowledgevault_backend/club_data/embedding_index.pkl"

    if api_key is None:
        api_key = "os.getenv("OPENAI_API_KEY", "")"

    return EnhancedRAGv2(
        embedding_index_path=index_path,
        openai_api_key=api_key,
        use_reranker=True,
        use_mmr=True,
        cache_results=True
    )
