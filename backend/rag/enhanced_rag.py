import os
"""
Enhanced RAG Module with:
- Query classification and expansion
- Cross-encoder re-ranking (ms-marco)
- Dynamic hybrid search weights
- MMR for diversity
- Context deduplication
- GPT-4o with answer validation
"""

import json
import pickle
import numpy as np
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from openai import AzureOpenAI
from functools import lru_cache
import time

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2024-12-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Cross-encoder for re-ranking
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    print("Warning: sentence-transformers not installed. Re-ranking disabled.")


class QueryClassifier:
    """Classify queries into types for optimized retrieval"""

    QUERY_TYPES = {
        'factual': {
            'description': 'Specific fact lookup (numbers, dates, names)',
            'semantic_weight': 0.8,
            'bm25_weight': 0.2,
            'top_k': 10
        },
        'exploratory': {
            'description': 'Open-ended exploration of a topic',
            'semantic_weight': 0.6,
            'bm25_weight': 0.4,
            'top_k': 15
        },
        'comparative': {
            'description': 'Comparing two or more things',
            'semantic_weight': 0.7,
            'bm25_weight': 0.3,
            'top_k': 20
        },
        'procedural': {
            'description': 'How to do something, steps, process',
            'semantic_weight': 0.65,
            'bm25_weight': 0.35,
            'top_k': 12
        }
    }

    # Pattern-based classification (fast, no API call)
    FACTUAL_PATTERNS = [
        r'\bhow many\b', r'\bwhat is the\b', r'\bhow much\b',
        r'\bwhen did\b', r'\bwho is\b', r'\bwhat was\b',
        r'\bROI\b', r'\brevenue\b', r'\bcost\b', r'\bnumber of\b',
        r'\bpercentage\b', r'\b\$\d+', r'\b\d+%'
    ]

    COMPARATIVE_PATTERNS = [
        r'\bcompare\b', r'\bvs\.?\b', r'\bversus\b', r'\bdifference between\b',
        r'\bbetter\b', r'\bworse\b', r'\boption 1\b', r'\boption 2\b'
    ]

    PROCEDURAL_PATTERNS = [
        r'\bhow to\b', r'\bsteps\b', r'\bprocess\b', r'\bprocedure\b',
        r'\bimplement\b', r'\bset up\b'
    ]

    @classmethod
    def classify(cls, query: str) -> Dict:
        """Classify query type based on patterns"""
        query_lower = query.lower()

        # Check patterns
        for pattern in cls.FACTUAL_PATTERNS:
            if re.search(pattern, query_lower):
                return cls.QUERY_TYPES['factual']

        for pattern in cls.COMPARATIVE_PATTERNS:
            if re.search(pattern, query_lower):
                return cls.QUERY_TYPES['comparative']

        for pattern in cls.PROCEDURAL_PATTERNS:
            if re.search(pattern, query_lower):
                return cls.QUERY_TYPES['procedural']

        # Default to exploratory
        return cls.QUERY_TYPES['exploratory']


class QueryExpander:
    """Expand queries with synonyms, acronyms, and related terms"""

    # Common acronym expansions
    ACRONYMS = {
        'ROI': 'Return on Investment',
        'NICU': 'Neonatal Intensive Care Unit',
        'PICU': 'Pediatric Intensive Care Unit',
        'OB-ED': 'Obstetric Emergency Department',
        'OBED': 'Obstetric Emergency Department',
        'L&D': 'Labor and Delivery',
        'TAM': 'Total Addressable Market',
        'SAM': 'Serviceable Addressable Market',
        'SOM': 'Serviceable Obtainable Market',
        'NPV': 'Net Present Value',
        'IRR': 'Internal Rate of Return',
        'FDU': 'Fetal Diagnostic Unit',
        'DPP': 'Diabetes Prevention Program',
        'CGM': 'Continuous Glucose Monitor',
    }

    # Synonym mappings
    SYNONYMS = {
        'turned away': ['rejected', 'declined', 'refused', 'denied'],
        'patients': ['cases', 'admissions', 'individuals'],
        'revenue': ['income', 'earnings', 'sales'],
        'cost': ['expense', 'expenditure', 'investment'],
        'market size': ['TAM', 'market opportunity', 'addressable market'],
    }

    def __init__(self, client: OpenAI = None):
        self.client = client

    def expand_acronyms(self, query: str) -> str:
        """Expand acronyms in query"""
        expanded = query
        for acronym, expansion in self.ACRONYMS.items():
            # Add expansion but keep original acronym
            if acronym in query and expansion not in query:
                expanded = expanded.replace(acronym, f"{acronym} ({expansion})")
        return expanded

    def get_synonyms(self, query: str) -> List[str]:
        """Get synonym variations of key terms"""
        query_lower = query.lower()
        additional_terms = []

        for term, syns in self.SYNONYMS.items():
            if term in query_lower:
                additional_terms.extend(syns)

        return additional_terms

    def expand_with_llm(self, query: str) -> Dict:
        """Use LLM for intelligent query expansion"""
        if not self.client:
            return {'expanded_query': query, 'search_terms': []}

        prompt = f"""Expand this search query to improve retrieval.

Query: {query}

Provide:
1. expanded_query: The query with acronyms expanded and clarified
2. search_terms: List of 3-5 additional relevant search terms/phrases

Return as JSON:
{{"expanded_query": "...", "search_terms": ["...", "..."]}}"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,  # Use mini for speed
                messages=[
                    {"role": "system", "content": "You expand search queries for better retrieval."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )

            result = response.choices[0].message.content
            # Parse JSON from response
            if '{' in result:
                start = result.index('{')
                end = result.rindex('}') + 1
                return json.loads(result[start:end])
        except Exception as e:
            print(f"LLM expansion failed: {e}")

        return {'expanded_query': query, 'search_terms': []}

    def expand(self, query: str, use_llm: bool = False) -> Dict:
        """Full query expansion"""
        # Basic expansions (fast)
        expanded = self.expand_acronyms(query)
        synonyms = self.get_synonyms(query)

        result = {
            'original_query': query,
            'expanded_query': expanded,
            'synonyms': synonyms,
            'search_terms': []
        }

        # Optional LLM expansion
        if use_llm and self.client:
            llm_result = self.expand_with_llm(query)
            result['expanded_query'] = llm_result.get('expanded_query', expanded)
            result['search_terms'] = llm_result.get('search_terms', [])

        return result


class CrossEncoderReranker:
    """Re-rank results using cross-encoder for better precision"""

    # Best performing model on MS MARCO
    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-12-v2"

    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the cross-encoder model"""
        if not CROSS_ENCODER_AVAILABLE:
            return

        try:
            print("Loading cross-encoder model...")
            self.model = CrossEncoder(self.MODEL_NAME)
            print(f"✓ Cross-encoder loaded: {self.MODEL_NAME}")
        except Exception as e:
            print(f"Failed to load cross-encoder: {e}")
            self.model = None

    def rerank(self, query: str, documents: List[Dict], top_k: int = 10) -> List[Dict]:
        """Re-rank documents using cross-encoder"""
        if not self.model or not documents:
            return documents[:top_k]

        # Prepare pairs for scoring
        pairs = [(query, doc.get('content', '')[:512]) for doc in documents]

        try:
            # Get cross-encoder scores
            scores = self.model.predict(pairs)

            # Add scores to documents
            for i, doc in enumerate(documents):
                doc['rerank_score'] = float(scores[i])

            # Sort by rerank score
            reranked = sorted(documents, key=lambda x: x.get('rerank_score', 0), reverse=True)

            return reranked[:top_k]
        except Exception as e:
            print(f"Re-ranking failed: {e}")
            return documents[:top_k]


class MMRSelector:
    """Maximal Marginal Relevance for diverse result selection"""

    @staticmethod
    def select(
        query_embedding: np.ndarray,
        doc_embeddings: np.ndarray,
        documents: List[Dict],
        k: int = 10,
        lambda_param: float = 0.7
    ) -> List[Dict]:
        """
        Select documents using MMR to balance relevance and diversity.

        Args:
            query_embedding: Query embedding vector
            doc_embeddings: Document embedding matrix
            documents: List of document dicts
            k: Number of documents to select
            lambda_param: Trade-off between relevance (1.0) and diversity (0.0)
        """
        if len(documents) <= k:
            return documents

        # Normalize embeddings
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        doc_norms = doc_embeddings / (np.linalg.norm(doc_embeddings, axis=1, keepdims=True) + 1e-8)

        # Compute query-document similarities
        query_sims = np.dot(doc_norms, query_norm)

        # Compute document-document similarities
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
                    # Max similarity to already selected docs
                    diversity_penalty = max(doc_sims[idx][s] for s in selected_indices)
                else:
                    diversity_penalty = 0

                mmr = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
                mmr_scores.append((idx, mmr))

            # Select highest MMR score
            best_idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

        return [documents[i] for i in selected_indices]


class ContextDeduplicator:
    """Remove redundant content from context"""

    @staticmethod
    def deduplicate(chunks: List[Dict], similarity_threshold: float = 0.8) -> List[Dict]:
        """Remove highly similar chunks"""
        if len(chunks) <= 1:
            return chunks

        unique_chunks = [chunks[0]]

        for chunk in chunks[1:]:
            is_duplicate = False
            chunk_text = chunk.get('content', '')

            for unique in unique_chunks:
                unique_text = unique.get('content', '')

                # Simple overlap check
                similarity = ContextDeduplicator._text_similarity(chunk_text, unique_text)
                if similarity > similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_chunks.append(chunk)

        return unique_chunks

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """Compute text similarity using character n-grams"""
        def get_ngrams(text, n=3):
            text = text.lower()
            return set(text[i:i+n] for i in range(len(text) - n + 1))

        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)

        return intersection / union if union > 0 else 0.0


class EnhancedRAG:
    """
    Enhanced RAG system with all improvements:
    - Query classification & expansion
    - Cross-encoder re-ranking
    - MMR diversity
    - Context deduplication
    - GPT-4o generation with validation
    """

    def __init__(
        self,
        embedding_index_path: str,
        openai_api_key: str,
        use_reranker: bool = True,
        use_mmr: bool = True,
        cache_queries: bool = True
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
        self.use_mmr = use_mmr

        # Query cache
        self.query_cache = {} if cache_queries else None

        print("✓ Enhanced RAG initialized")

    def _get_query_embedding(self, query: str) -> np.ndarray:
        """Get embedding for query with caching"""
        # Check cache
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if self.query_cache is not None and cache_key in self.query_cache:
            return self.query_cache[cache_key]

        # Get embedding from OpenAI
        # Use dimensions=1536 to match existing index (built with text-embedding-3-small)
        response = self.client.embeddings.create(
            model="text-embedding-3-large",
            input=query,
            dimensions=1536  # Match the existing index dimensions
        )
        embedding = np.array(response.data[0].embedding, dtype=np.float32)

        # Cache
        if self.query_cache is not None:
            self.query_cache[cache_key] = embedding
            # Limit cache size
            if len(self.query_cache) > 1000:
                # Remove oldest entries
                keys = list(self.query_cache.keys())[:100]
                for k in keys:
                    del self.query_cache[k]

        return embedding

    def _hybrid_search(
        self,
        query: str,
        expanded_query: str,
        query_config: Dict,
        top_k: int = 20
    ) -> List[Dict]:
        """Perform hybrid semantic + BM25 search with dynamic weights"""

        # Get query embedding
        query_embedding = self._get_query_embedding(expanded_query)

        # Get stored data
        chunk_embeddings = self.index['embeddings']
        chunks = self.index['chunks']
        bm25_index = self.index.get('bm25_index')

        # Semantic search
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        chunk_norms = chunk_embeddings / (np.linalg.norm(chunk_embeddings, axis=1, keepdims=True) + 1e-8)
        semantic_scores = np.dot(chunk_norms, query_norm)

        # BM25 search
        if bm25_index:
            query_tokens = re.findall(r'\b\w+\b', query.lower())
            bm25_scores = bm25_index.get_scores(query_tokens)
            bm25_max = np.max(bm25_scores) if np.max(bm25_scores) > 0 else 1
            bm25_scores = bm25_scores / bm25_max
        else:
            bm25_scores = np.zeros(len(chunks))

        # Dynamic weights based on query type
        semantic_weight = query_config.get('semantic_weight', 0.7)
        bm25_weight = query_config.get('bm25_weight', 0.3)

        combined_scores = semantic_weight * semantic_scores + bm25_weight * bm25_scores

        # Get top results
        top_indices = np.argsort(combined_scores)[::-1][:top_k * 2]  # Get more for re-ranking

        results = []
        for idx in top_indices:
            if combined_scores[idx] > 0.01:
                chunk = chunks[idx]
                results.append({
                    'chunk_id': chunk['chunk_id'],
                    'doc_id': chunk['doc_id'],
                    'content': chunk['content'],
                    'chunk_index': chunk['chunk_index'],
                    'metadata': chunk.get('metadata', {}),
                    'score': float(combined_scores[idx]),
                    'semantic_score': float(semantic_scores[idx]),
                    'bm25_score': float(bm25_scores[idx]),
                    'embedding_idx': idx
                })

        return results

    def retrieve(
        self,
        query: str,
        use_llm_expansion: bool = False,
        top_k: int = 10
    ) -> Dict:
        """
        Full retrieval pipeline:
        1. Classify query
        2. Expand query
        3. Hybrid search
        4. Re-rank
        5. Apply MMR
        6. Deduplicate
        """
        start_time = time.time()

        # Step 1: Classify query
        query_config = QueryClassifier.classify(query)

        # Step 2: Expand query
        expansion = self.query_expander.expand(query, use_llm=use_llm_expansion)
        expanded_query = expansion['expanded_query']

        # Step 3: Hybrid search
        search_top_k = query_config.get('top_k', 15)
        results = self._hybrid_search(query, expanded_query, query_config, top_k=search_top_k * 2)

        # Step 4: Re-rank with cross-encoder
        if self.reranker and self.reranker.model:
            results = self.reranker.rerank(query, results, top_k=search_top_k)

        # Step 5: Apply MMR for diversity
        if self.use_mmr and len(results) > top_k:
            # Get embeddings for MMR
            embedding_indices = [r['embedding_idx'] for r in results]
            doc_embeddings = self.index['embeddings'][embedding_indices]
            query_embedding = self._get_query_embedding(expanded_query)

            results = MMRSelector.select(
                query_embedding,
                doc_embeddings,
                results,
                k=top_k,
                lambda_param=0.7
            )
        else:
            results = results[:top_k]

        # Step 6: Deduplicate
        results = ContextDeduplicator.deduplicate(results, similarity_threshold=0.85)

        retrieval_time = time.time() - start_time

        return {
            'query': query,
            'expanded_query': expanded_query,
            'query_type': query_config['description'],
            'results': results,
            'num_results': len(results),
            'retrieval_time': retrieval_time,
            'expansion': expansion
        }

    def generate_answer(
        self,
        query: str,
        retrieval_results: Dict,
        validate_answer: bool = True
    ) -> Dict:
        """Generate answer using GPT-4o with optional validation"""

        results = retrieval_results['results']

        if not results:
            return {
                'answer': "I couldn't find any relevant information to answer your question.",
                'confidence': 0.0,
                'sources': [],
                'validated': False
            }

        # Build context
        context_parts = []
        for i, result in enumerate(results[:10], 1):
            content = result['content'][:3000]  # Limit per chunk

            context_parts.append(
                f"[Source {i}] (Relevance: {result.get('rerank_score', result['score']):.2%})\n"
                f"Document: {result['doc_id']}\n"
                f"Content: {content}\n"
            )

        context = "\n---\n".join(context_parts)

        # Generate with GPT-4o
        prompt = f"""Based on the following source documents, answer the user's question accurately.

IMPORTANT RULES:
1. ONLY use information from the provided sources
2. Cite sources using [Source X] format
3. If information is incomplete or missing, acknowledge it
4. Include specific numbers, dates, and facts when available
5. Be concise but thorough

SOURCES:
{context}

QUESTION: {query}

ANSWER:"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,  # Using GPT-4o as requested
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert analyst providing accurate, well-cited answers based on provided documents. Always cite your sources."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )

            answer = response.choices[0].message.content.strip()

            # Validate answer if requested
            confidence = 1.0
            validated = False

            if validate_answer:
                validation = self._validate_answer(query, answer, results)
                confidence = validation['confidence']
                validated = True

                if confidence < 0.5:
                    answer += "\n\n⚠️ Note: This answer has lower confidence. The sources may not fully address your question."

            return {
                'answer': answer,
                'confidence': confidence,
                'sources': results[:10],
                'validated': validated,
                'model': 'gpt-4o'
            }

        except Exception as e:
            return {
                'answer': f"Error generating answer: {str(e)}",
                'confidence': 0.0,
                'sources': results[:10],
                'validated': False,
                'error': str(e)
            }

    def _validate_answer(self, query: str, answer: str, sources: List[Dict]) -> Dict:
        """Validate that the answer addresses the question"""

        validation_prompt = f"""Evaluate if this answer properly addresses the question.

Question: {query}
Answer: {answer}

Rate from 0-100:
1. Relevance: Does the answer address the specific question asked?
2. Grounding: Is the answer supported by factual information?
3. Completeness: Does it fully answer the question?

Return JSON: {{"relevance": X, "grounding": X, "completeness": X, "overall": X}}"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,  # Use mini for validation (faster, cheaper)
                messages=[
                    {"role": "system", "content": "You evaluate answer quality. Return only JSON."},
                    {"role": "user", "content": validation_prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )

            result = response.choices[0].message.content
            if '{' in result:
                start = result.index('{')
                end = result.rindex('}') + 1
                scores = json.loads(result[start:end])
                confidence = scores.get('overall', 70) / 100
                return {'confidence': confidence, 'scores': scores}
        except:
            pass

        return {'confidence': 0.7, 'scores': {}}

    def query(
        self,
        query: str,
        use_llm_expansion: bool = False,
        validate: bool = True,
        top_k: int = 10
    ) -> Dict:
        """
        Complete RAG query pipeline.

        Args:
            query: User question
            use_llm_expansion: Use LLM for query expansion (slower but better)
            validate: Validate the answer quality
            top_k: Number of sources to retrieve

        Returns:
            Complete response with answer, sources, and metadata
        """
        # Retrieve
        retrieval = self.retrieve(query, use_llm_expansion=use_llm_expansion, top_k=top_k)

        # Generate
        response = self.generate_answer(query, retrieval, validate_answer=validate)

        # Combine
        return {
            'query': query,
            'answer': response['answer'],
            'confidence': response['confidence'],
            'sources': response['sources'],
            'num_sources': len(response['sources']),
            'query_type': retrieval['query_type'],
            'expanded_query': retrieval['expanded_query'],
            'retrieval_time': retrieval['retrieval_time'],
            'model': response.get('model', 'gpt-4o'),
            'validated': response['validated']
        }


# Convenience function for app integration
def create_enhanced_rag(
    index_path: str = None,
    api_key: str = None
) -> EnhancedRAG:
    """Create EnhancedRAG instance with defaults"""

    if index_path is None:
        index_path = "/Users/rishitjain/Downloads/knowledgevault_backend/club_data/embedding_index.pkl"

    # api_key is ignored, Azure config is used directly in EnhancedRAG class

    return EnhancedRAG(
        embedding_index_path=index_path,
        use_reranker=True,
        use_mmr=True,
        cache_queries=True
    )


if __name__ == "__main__":
    # Test the enhanced RAG
    print("Testing Enhanced RAG...")

    rag = create_enhanced_rag()

    test_queries = [
        "What is the ROI for NICU Step Down?",
        "How many patients were turned away from PICU?",
        "Compare OB-ED vs NICU Step-Down options",
        "What is the market size for NICU services?"
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)

        result = rag.query(query)

        print(f"Query Type: {result['query_type']}")
        print(f"Expanded: {result['expanded_query']}")
        print(f"Sources: {result['num_sources']}")
        print(f"Confidence: {result['confidence']:.1%}")
        print(f"Time: {result['retrieval_time']:.2f}s")
        print(f"\nAnswer:\n{result['answer'][:500]}...")
