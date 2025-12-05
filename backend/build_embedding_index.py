import os
"""
Advanced RAG Index Builder with OpenAI Embeddings + Hierarchical Chunking
Uses text-embedding-3-small for semantic search
"""

import json
import pickle
import numpy as np
from pathlib import Path
from openai import AzureOpenAI
import tiktoken
from typing import List, Dict, Tuple
import time
from rank_bm25 import BM25Okapi
import re

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2024-12-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"
AZURE_EMBEDDING_DEPLOYMENT = "text-embedding-3-large"
AZURE_EMBEDDING_API_VERSION = "2024-12-01-preview"


# Configuration
DATA_DIR = Path('/Users/rishitjain/Downloads/2nd-brain/backend/club_data')
OUTPUT_DIR = DATA_DIR

# Chunking parameters
CHUNK_SIZE = 600  # tokens
CHUNK_OVERLAP = 100  # tokens
EMBEDDING_MODEL = AZURE_EMBEDDING_DEPLOYMENT
EMBEDDING_DIMENSIONS = 3072  # text-embedding-3-large uses 3072 dimensions

# Use embedding API version for embeddings client
client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_EMBEDDING_API_VERSION
        )
tokenizer = tiktoken.encoding_for_model("gpt-4")


def count_tokens(text: str) -> int:
    """Count tokens in text"""
    return len(tokenizer.encode(text))


def chunk_document(text: str, doc_id: str, metadata: dict) -> List[Dict]:
    """
    Split document into overlapping chunks with metadata.
    Uses token-based sliding window for proper size control.
    Max 7000 tokens per chunk (below 8192 limit for embedding model).
    """
    MAX_CHUNK_TOKENS = 7000  # Below 8192 limit
    chunks = []

    # Tokenize entire document
    tokens = tokenizer.encode(text)
    total_tokens = len(tokens)

    if total_tokens <= CHUNK_SIZE:
        # Small document - use as single chunk
        chunks.append({
            'chunk_id': f"{doc_id}_chunk_0",
            'doc_id': doc_id,
            'content': text.strip(),
            'chunk_index': 0,
            'metadata': metadata
        })
        return chunks

    # Sliding window chunking
    chunk_idx = 0
    start = 0

    while start < total_tokens:
        # Calculate end position (don't exceed CHUNK_SIZE or MAX_CHUNK_TOKENS)
        end = min(start + CHUNK_SIZE, total_tokens)

        # Ensure we don't exceed max tokens
        if end - start > MAX_CHUNK_TOKENS:
            end = start + MAX_CHUNK_TOKENS

        # Get chunk tokens and decode back to text
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens)

        chunks.append({
            'chunk_id': f"{doc_id}_chunk_{chunk_idx}",
            'doc_id': doc_id,
            'content': chunk_text.strip(),
            'chunk_index': chunk_idx,
            'metadata': metadata
        })
        chunk_idx += 1

        # Move start forward, keeping overlap
        start = end - CHUNK_OVERLAP

        # Make sure we make progress
        if start >= total_tokens - CHUNK_OVERLAP:
            break

    return chunks


def get_embeddings_batch(texts: List[str], batch_size: int = 1) -> List[List[float]]:
    """Get embeddings one at a time to avoid batch token limit issues"""
    all_embeddings = []
    failed_count = 0

    for i, text in enumerate(texts):
        try:
            # Truncate if still too long
            tokens = tokenizer.encode(text)
            if len(tokens) > 7000:
                text = tokenizer.decode(tokens[:7000])

            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            all_embeddings.append(response.data[0].embedding)

            if (i + 1) % 50 == 0:
                print(f"      Processed {i + 1}/{len(texts)} chunks...")
                time.sleep(0.2)  # Small delay every 50 requests

        except Exception as e:
            print(f"Error getting embedding for chunk {i}: {e}")
            # Return zero vector for failed chunk
            all_embeddings.append([0.0] * EMBEDDING_DIMENSIONS)
            failed_count += 1

    if failed_count > 0:
        print(f"   WARNING: {failed_count} chunks failed to embed")

    return all_embeddings


def build_bm25_index(chunks: List[Dict]) -> BM25Okapi:
    """Build BM25 index for keyword search"""
    # Tokenize documents for BM25
    tokenized_docs = []
    for chunk in chunks:
        # Simple tokenization: lowercase, split on non-alphanumeric
        tokens = re.findall(r'\b\w+\b', chunk['content'].lower())
        tokenized_docs.append(tokens)

    return BM25Okapi(tokenized_docs)


def load_existing_index():
    """Load existing search index to get documents"""
    index_file = DATA_DIR / "search_index.pkl"
    if index_file.exists():
        with open(index_file, 'rb') as f:
            return pickle.load(f)
    return None


def build_embedding_index():
    """Main function to build the embedding index"""
    print("=" * 60)
    print("Building Advanced RAG Index with OpenAI Embeddings")
    print("=" * 60)

    # Load existing index to get documents
    existing_index = load_existing_index()
    if not existing_index:
        print("ERROR: No existing search index found. Run build_enhanced_knowledge_base.py first.")
        return

    print(f"\nLoaded {len(existing_index['doc_ids'])} documents from existing index")

    # Filter to only LlamaParse documents (they have the actual content)
    llamaparse_docs = []
    for doc_id in existing_index['doc_ids']:
        if doc_id.startswith('llamaparse_'):
            doc = existing_index['doc_index'].get(doc_id, {})
            if doc.get('content'):
                llamaparse_docs.append({
                    'doc_id': doc_id,
                    'content': doc['content'],
                    'metadata': doc.get('metadata', {})
                })

    print(f"Found {len(llamaparse_docs)} LlamaParse documents to process")

    # Chunk all documents
    print("\n1. Chunking documents...")
    all_chunks = []
    for doc in llamaparse_docs:
        chunks = chunk_document(doc['content'], doc['doc_id'], doc['metadata'])
        all_chunks.extend(chunks)

    print(f"   Created {len(all_chunks)} chunks from {len(llamaparse_docs)} documents")
    print(f"   Average chunks per document: {len(all_chunks) / len(llamaparse_docs):.1f}")

    # Get embeddings for all chunks
    print("\n2. Generating embeddings (this may take a few minutes)...")
    chunk_texts = [chunk['content'] for chunk in all_chunks]

    # Estimate cost
    total_tokens = sum(count_tokens(text) for text in chunk_texts)
    estimated_cost = (total_tokens / 1_000_000) * 0.02  # $0.02 per 1M tokens
    print(f"   Total tokens: {total_tokens:,}")
    print(f"   Estimated cost: ${estimated_cost:.4f}")

    embeddings = get_embeddings_batch(chunk_texts)
    embeddings_array = np.array(embeddings, dtype=np.float32)

    print(f"   Generated {len(embeddings)} embeddings")
    print(f"   Embedding shape: {embeddings_array.shape}")

    # Build BM25 index for hybrid search
    print("\n3. Building BM25 index for hybrid search...")
    bm25_index = build_bm25_index(all_chunks)

    # Create the index structure
    embedding_index = {
        'chunks': all_chunks,
        'embeddings': embeddings_array,
        'bm25_index': bm25_index,
        'chunk_texts': chunk_texts,  # For BM25 scoring
        'doc_index': existing_index['doc_index'],  # Keep full documents for context
        'model': EMBEDDING_MODEL,
        'chunk_size': CHUNK_SIZE,
        'chunk_overlap': CHUNK_OVERLAP,
        'num_chunks': len(all_chunks),
        'num_documents': len(llamaparse_docs)
    }

    # Save the index
    output_file = OUTPUT_DIR / "embedding_index.pkl"
    print(f"\n4. Saving index to {output_file}...")
    with open(output_file, 'wb') as f:
        pickle.dump(embedding_index, f)

    file_size = output_file.stat().st_size / (1024 * 1024)
    print(f"   Index size: {file_size:.2f} MB")

    # Print summary
    print("\n" + "=" * 60)
    print("INDEX BUILD COMPLETE")
    print("=" * 60)
    print(f"Documents processed: {len(llamaparse_docs)}")
    print(f"Chunks created: {len(all_chunks)}")
    print(f"Embedding dimensions: {EMBEDDING_DIMENSIONS}")
    print(f"Index file: {output_file}")
    print(f"Index size: {file_size:.2f} MB")

    return embedding_index


if __name__ == "__main__":
    build_embedding_index()
