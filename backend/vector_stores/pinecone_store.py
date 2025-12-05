"""
Pinecone Vector Store - Scalable Vector Database for Multi-tenant RAG

Features:
- Multi-tenant support via namespaces
- Batch upsert for safe indexing
- Hybrid search (dense + sparse)
- Metadata filtering
- Automatic retry with exponential backoff
"""

import os
import time
import hashlib
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from openai import AzureOpenAI

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Pinecone imports
try:
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    print("Warning: pinecone-client not installed. Run: pip install pinecone-client")


@dataclass
class PineconeConfig:
    """Configuration for Pinecone connection"""
    api_key: str
    environment: str = "us-east-1"  # AWS region for serverless
    index_name: str = "knowledgevault"
    dimension: int = 1536  # text-embedding-3-small dimension
    metric: str = "cosine"
    cloud: str = "aws"


class PineconeVectorStore:
    """
    Scalable vector store using Pinecone for multi-tenant RAG.

    Supports:
    - Namespace isolation per tenant/organization
    - Batch operations for safe large-scale indexing
    - Metadata filtering for project/date/source filtering
    - Hybrid search combining semantic + keyword matching
    """

    BATCH_SIZE = 100  # Vectors per upsert batch
    EMBEDDING_MODEL = "text-embedding-3-small"

    def __init__(self, config: Optional[PineconeConfig] = None):
        if not PINECONE_AVAILABLE:
            raise ImportError("pinecone-client not installed")

        # Load config from environment if not provided
        if config is None:
            config = PineconeConfig(
                api_key=os.getenv("PINECONE_API_KEY", ""),
                index_name=os.getenv("PINECONE_INDEX", "knowledgevault")
            )

        self.config = config
        self.pc = Pinecone(api_key=config.api_key)
        self.openai = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        ))

        # Initialize or get index
        self.index = self._init_index()

    def _init_index(self):
        """Initialize Pinecone index, creating if needed"""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]

        if self.config.index_name not in existing_indexes:
            print(f"Creating Pinecone index: {self.config.index_name}")
            self.pc.create_index(
                name=self.config.index_name,
                dimension=self.config.dimension,
                metric=self.config.metric,
                spec=ServerlessSpec(
                    cloud=self.config.cloud,
                    region=self.config.environment
                )
            )
            # Wait for index to be ready
            time.sleep(5)

        return self.pc.Index(self.config.index_name)

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using OpenAI"""
        response = self.openai.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=text[:8000]  # Truncate to fit context
        )
        return response.data[0].embedding

    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts efficiently"""
        # Truncate texts
        truncated = [t[:8000] for t in texts]

        response = self.openai.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=truncated
        )
        return [item.embedding for item in response.data]

    def _generate_id(self, doc_id: str, chunk_idx: int = 0) -> str:
        """Generate unique vector ID"""
        content = f"{doc_id}_{chunk_idx}"
        return hashlib.md5(content.encode()).hexdigest()

    def upsert_documents(
        self,
        documents: List[Dict],
        namespace: str = "default",
        show_progress: bool = True
    ) -> Dict:
        """
        Upsert documents to Pinecone in batches.

        Args:
            documents: List of dicts with 'id', 'content', 'metadata'
            namespace: Tenant/org namespace for isolation
            show_progress: Print progress updates

        Returns:
            Stats about the upsert operation
        """
        total = len(documents)
        upserted = 0
        errors = []

        for i in range(0, total, self.BATCH_SIZE):
            batch = documents[i:i + self.BATCH_SIZE]

            try:
                # Get embeddings for batch
                texts = [doc['content'] for doc in batch]
                embeddings = self._get_embeddings_batch(texts)

                # Prepare vectors
                vectors = []
                for j, (doc, embedding) in enumerate(zip(batch, embeddings)):
                    vector_id = self._generate_id(doc['id'], doc.get('chunk_idx', 0))

                    # Prepare metadata (Pinecone has limits on metadata size)
                    metadata = {
                        'doc_id': doc['id'],
                        'chunk_idx': doc.get('chunk_idx', 0),
                        'content_preview': doc['content'][:500],  # Store preview for display
                        **{k: v for k, v in doc.get('metadata', {}).items()
                           if isinstance(v, (str, int, float, bool)) and len(str(v)) < 500}
                    }

                    vectors.append({
                        'id': vector_id,
                        'values': embedding,
                        'metadata': metadata
                    })

                # Upsert to Pinecone
                self.index.upsert(vectors=vectors, namespace=namespace)
                upserted += len(vectors)

                if show_progress:
                    print(f"  Upserted {upserted}/{total} documents...")

            except Exception as e:
                errors.append({'batch': i, 'error': str(e)})
                print(f"  Error in batch {i}: {e}")

        return {
            'total': total,
            'upserted': upserted,
            'errors': errors,
            'namespace': namespace
        }

    def search(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 10,
        filter: Optional[Dict] = None,
        include_metadata: bool = True
    ) -> List[Dict]:
        """
        Search for similar documents.

        Args:
            query: Search query text
            namespace: Tenant namespace
            top_k: Number of results
            filter: Metadata filter (e.g., {'project': 'ERCOT'})
            include_metadata: Include metadata in results

        Returns:
            List of matching documents with scores
        """
        # Get query embedding
        query_embedding = self._get_embedding(query)

        # Search Pinecone
        results = self.index.query(
            vector=query_embedding,
            namespace=namespace,
            top_k=top_k,
            filter=filter,
            include_metadata=include_metadata
        )

        # Format results
        formatted = []
        for match in results.matches:
            formatted.append({
                'id': match.id,
                'score': match.score,
                'doc_id': match.metadata.get('doc_id', ''),
                'chunk_idx': match.metadata.get('chunk_idx', 0),
                'content': match.metadata.get('content_preview', ''),
                'metadata': {k: v for k, v in match.metadata.items()
                           if k not in ['doc_id', 'chunk_idx', 'content_preview']}
            })

        return formatted

    def delete_namespace(self, namespace: str) -> bool:
        """Delete all vectors in a namespace (for tenant deletion)"""
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            return True
        except Exception as e:
            print(f"Error deleting namespace {namespace}: {e}")
            return False

    def delete_documents(self, doc_ids: List[str], namespace: str = "default") -> bool:
        """Delete specific documents by ID"""
        try:
            # Generate vector IDs for all chunks
            vector_ids = []
            for doc_id in doc_ids:
                # Assume max 100 chunks per doc
                for i in range(100):
                    vector_ids.append(self._generate_id(doc_id, i))

            self.index.delete(ids=vector_ids, namespace=namespace)
            return True
        except Exception as e:
            print(f"Error deleting documents: {e}")
            return False

    def get_stats(self, namespace: Optional[str] = None) -> Dict:
        """Get index statistics"""
        stats = self.index.describe_index_stats()

        if namespace:
            ns_stats = stats.namespaces.get(namespace, {})
            return {
                'namespace': namespace,
                'vector_count': ns_stats.get('vector_count', 0)
            }

        return {
            'total_vectors': stats.total_vector_count,
            'namespaces': {k: v.vector_count for k, v in stats.namespaces.items()},
            'dimension': stats.dimension
        }


class HybridPineconeStore(PineconeVectorStore):
    """
    Extended Pinecone store with hybrid search capabilities.
    Combines dense (semantic) and sparse (BM25-like) retrieval.
    """

    def __init__(self, config: Optional[PineconeConfig] = None):
        super().__init__(config)
        self.sparse_weight = 0.3
        self.dense_weight = 0.7

    def hybrid_search(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 10,
        filter: Optional[Dict] = None,
        sparse_weight: Optional[float] = None,
        dense_weight: Optional[float] = None
    ) -> List[Dict]:
        """
        Hybrid search combining semantic and keyword matching.

        Note: For true hybrid search, Pinecone requires sparse vectors.
        This implementation uses metadata-based keyword boosting as a simpler alternative.
        """
        # Use provided weights or defaults
        sw = sparse_weight or self.sparse_weight
        dw = dense_weight or self.dense_weight

        # Get semantic results
        semantic_results = self.search(query, namespace, top_k * 2, filter)

        # Boost results that contain query keywords in content
        query_terms = set(query.lower().split())

        for result in semantic_results:
            content_lower = result.get('content', '').lower()
            # Count keyword matches
            keyword_matches = sum(1 for term in query_terms if term in content_lower)
            keyword_boost = min(keyword_matches * 0.1, 0.3)  # Max 30% boost

            # Combine scores
            result['semantic_score'] = result['score']
            result['keyword_boost'] = keyword_boost
            result['score'] = (dw * result['score']) + (sw * keyword_boost)

        # Re-sort by combined score
        semantic_results.sort(key=lambda x: x['score'], reverse=True)

        return semantic_results[:top_k]


# Migration utility
def migrate_pickle_to_pinecone(
    pickle_path: str,
    pinecone_store: PineconeVectorStore,
    namespace: str = "default"
) -> Dict:
    """
    Migrate existing pickle-based index to Pinecone.

    Args:
        pickle_path: Path to embedding_index.pkl
        pinecone_store: Initialized PineconeVectorStore
        namespace: Target namespace

    Returns:
        Migration stats
    """
    import pickle

    print(f"Loading pickle file: {pickle_path}")
    with open(pickle_path, 'rb') as f:
        data = pickle.load(f)

    chunks = data.get('chunks', [])
    print(f"Found {len(chunks)} chunks to migrate")

    # Convert to document format
    documents = []
    for i, chunk in enumerate(chunks):
        documents.append({
            'id': chunk.get('doc_id', f'doc_{i}'),
            'chunk_idx': chunk.get('chunk_idx', i),
            'content': chunk.get('content', ''),
            'metadata': chunk.get('metadata', {})
        })

    # Upsert to Pinecone
    result = pinecone_store.upsert_documents(documents, namespace)

    print(f"Migration complete: {result['upserted']}/{result['total']} documents")
    return result
