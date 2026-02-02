"""
Local RAG Service - Development/Fallback for when Pinecone is not available
Uses local pickle-based vector index for search and retrieval
"""

import os
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from services.openai_client import get_openai_client


class LocalRAGService:
    """
    Local RAG service using pickle-based vector index.
    Provides fallback when Pinecone is not configured.
    """

    def __init__(self):
        self.openai_client = get_openai_client()
        self.base_dir = Path(__file__).parent.parent / "tenant_data"

    def _load_index(self, tenant_id: str) -> Dict[str, Any]:
        """Load the local vector index for a tenant"""
        from database.models import SessionLocal, Tenant

        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return None

            index_path = self.base_dir / tenant.slug / "embedding_index.pkl"

            if not index_path.exists():
                print(f"[LocalRAG] No index found at {index_path}")
                return None

            with open(index_path, 'rb') as f:
                index_data = pickle.load(f)

            print(f"[LocalRAG] Loaded index with {len(index_data.get('embeddings', []))} vectors")
            return index_data

        finally:
            db.close()

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        # Ensure vectors are 1D numpy arrays
        vec1 = np.array(vec1).flatten()
        vec2 = np.array(vec2).flatten()

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        # Check for zero vectors using small epsilon
        if norm1 < 1e-10 or norm2 < 1e-10:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def search(self, query: str, tenant_id: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Search the local index using the query

        Args:
            query: Search query
            tenant_id: Tenant ID
            top_k: Number of results to return

        Returns:
            Dict with answer, sources, and metadata
        """
        # Load the index
        index_data = self._load_index(tenant_id)

        if not index_data:
            return {
                "answer": "Your knowledge base is empty. Please add and confirm some documents first.",
                "confidence": 1.0,
                "sources": []
            }

        # Get query embedding
        try:
            embedding_response = self.openai_client.create_embedding(query)
            query_embedding = np.array(embedding_response.data[0].embedding)
        except Exception as e:
            print(f"[LocalRAG] Error creating embedding: {e}")
            return {
                "answer": f"Error creating query embedding: {str(e)}",
                "confidence": 0.0,
                "sources": []
            }

        # Search through the index
        embeddings = index_data.get('embeddings', np.array([]))
        chunks = index_data.get('chunks', [])
        doc_index = index_data.get('doc_index', {})

        if len(embeddings) == 0:
            return {
                "answer": "No embeddings found in the index.",
                "confidence": 0.0,
                "sources": []
            }

        # Calculate similarities
        similarities = []
        for i in range(len(embeddings)):
            score = self._cosine_similarity(query_embedding, embeddings[i])
            chunk_text = chunks[i] if i < len(chunks) else ""
            doc_info = doc_index.get(i, {})

            similarities.append({
                'index': i,
                'score': float(score),
                'text': chunk_text,
                'doc_info': doc_info
            })

        # Sort by score and get top_k
        similarities.sort(key=lambda x: x['score'], reverse=True)
        top_results = similarities[:top_k]

        print(f"[LocalRAG] Found {len(top_results)} results, top score: {top_results[0]['score']:.3f}")

        # Build context from top results
        context = "\n\n".join([
            f"[Document {i+1}] {str(result['text'])[:500]}..."
            for i, result in enumerate(top_results)
        ])

        # Generate answer using OpenAI
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that answers questions based on the provided context. Always cite which document you're referencing."
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer the question based only on the context provided above."
                }
            ]

            response = self.openai_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )

            answer = response.choices[0].message.content

        except Exception as e:
            print(f"[LocalRAG] Error generating answer: {e}")
            answer = f"Found {len(top_results)} relevant documents but couldn't generate answer: {str(e)}"

        # Format sources
        sources = []
        for i, result in enumerate(top_results):
            doc_info = result['doc_info']
            text = str(result['text'])
            sources.append({
                'doc_id': doc_info.get('doc_id', f'doc_{i}'),
                'title': doc_info.get('title', f'Document {i+1}'),
                'content_preview': text[:300] if len(text) > 300 else text,
                'score': result['score'],
                'metadata': doc_info
            })

        return {
            "answer": answer,
            "confidence": top_results[0]['score'] if top_results else 0.0,
            "sources": sources,
            "search_time": 0,
            "storage_mode": "local"
        }


# Singleton instance
_local_rag_service = None


def get_local_rag_service() -> LocalRAGService:
    """Get or create the local RAG service singleton"""
    global _local_rag_service
    if _local_rag_service is None:
        _local_rag_service = LocalRAGService()
    return _local_rag_service
