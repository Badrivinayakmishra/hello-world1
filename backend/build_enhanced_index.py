import os
"""
Enhanced Embedding Index Builder
Uses semantic chunking instead of fixed-size token chunking
"""

import json
import pickle
import numpy as np
from pathlib import Path
from openai import AzureOpenAI
import tiktoken
from typing import List, Dict
import time
from rank_bm25 import BM25Okapi
import re
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from rag.semantic_chunker import SemanticChunker, create_chunker

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Configuration
DATA_DIR = Path('/Users/rishitjain/Downloads/knowledgevault_backend/club_data')
OUTPUT_DIR = DATA_DIR
OPENAI_API_KEY = "os.getenv("OPENAI_API_KEY", "")"

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 3072

client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
tokenizer = tiktoken.encoding_for_model("gpt-4")


def count_tokens(text: str) -> int:
    """Count tokens in text"""
    return len(tokenizer.encode(text))


def get_embeddings_batch(texts: List[str], batch_size: int = 50) -> List[List[float]]:
    """Get embeddings in batches to avoid rate limits"""
    all_embeddings = []
    failed_count = 0

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        # Truncate any texts that are too long
        processed_batch = []
        for text in batch:
            tokens = tokenizer.encode(text)
            if len(tokens) > 7000:
                text = tokenizer.decode(tokens[:7000])
            processed_batch.append(text)

        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=processed_batch
            )

            for item in response.data:
                all_embeddings.append(item.embedding)

            print(f"      Processed {min(i + batch_size, len(texts))}/{len(texts)} chunks...")

            # Rate limiting
            if i + batch_size < len(texts):
                time.sleep(0.5)

        except Exception as e:
            print(f"Error in batch {i}: {e}")
            # Add zero vectors for failed batch
            for _ in batch:
                all_embeddings.append([0.0] * EMBEDDING_DIMENSIONS)
                failed_count += 1

    if failed_count > 0:
        print(f"   WARNING: {failed_count} chunks failed to embed")

    return all_embeddings


def build_bm25_index(chunks: List[Dict]) -> BM25Okapi:
    """Build BM25 index for keyword search"""
    tokenized_docs = []
    for chunk in chunks:
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


def build_enhanced_index():
    """Build embedding index with semantic chunking"""
    print("=" * 60)
    print("Building Enhanced Embedding Index with Semantic Chunking")
    print("=" * 60)

    # Load existing index to get documents
    existing_index = load_existing_index()
    if not existing_index:
        print("ERROR: No existing search index found. Run build_enhanced_knowledge_base.py first.")
        return

    print(f"\nLoaded {len(existing_index['doc_ids'])} documents from existing index")

    # Initialize semantic chunker
    chunker = create_chunker()

    # Process ALL documents with meaningful content (not just LlamaParse)
    all_docs = []
    skipped_empty = 0
    skipped_short = 0

    for doc_id in existing_index['doc_ids']:
        doc = existing_index['doc_index'].get(doc_id, {})
        content = doc.get('content', '')

        if not content:
            skipped_empty += 1
            continue

        # Skip very short documents (less than 100 chars)
        if len(content) < 100:
            skipped_short += 1
            continue

        all_docs.append({
            'doc_id': doc_id,
            'content': content,
            'metadata': doc.get('metadata', {})
        })

    print(f"Found {len(all_docs)} documents with content to process")
    print(f"  Skipped {skipped_empty} empty documents")
    print(f"  Skipped {skipped_short} very short documents (<100 chars)")

    # Use all_docs for processing (renamed for compatibility)
    llamaparse_docs = all_docs

    # Chunk all documents using semantic chunking
    print("\n1. Semantic chunking documents...")
    all_chunks = []
    chunk_stats = {
        'section': 0,
        'paragraph': 0,
        'slide': 0,
        'section_parent': 0,
        'other': 0
    }

    for doc in llamaparse_docs:
        chunks = chunker.chunk_document(
            doc['content'],
            doc['doc_id'],
            doc['metadata']
        )

        for chunk in chunks:
            chunk_dict = chunker.chunk_to_dict(chunk)
            all_chunks.append(chunk_dict)

            # Track chunk types
            chunk_type = chunk_dict.get('chunk_type', 'other')
            if chunk_type in chunk_stats:
                chunk_stats[chunk_type] += 1
            else:
                chunk_stats['other'] += 1

    print(f"   Created {len(all_chunks)} chunks from {len(llamaparse_docs)} documents")
    print(f"   Average chunks per document: {len(all_chunks) / len(llamaparse_docs):.1f}")
    print(f"   Chunk types: {chunk_stats}")

    # Calculate token statistics
    token_counts = [count_tokens(c['content']) for c in all_chunks]
    print(f"   Token stats: min={min(token_counts)}, max={max(token_counts)}, avg={np.mean(token_counts):.0f}")

    # Get embeddings for all chunks
    print("\n2. Generating embeddings...")
    chunk_texts = [chunk['content'] for chunk in all_chunks]

    total_tokens = sum(token_counts)
    estimated_cost = (total_tokens / 1_000_000) * 0.02
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
        'chunk_texts': chunk_texts,
        'doc_index': existing_index['doc_index'],
        'model': EMBEDDING_MODEL,
        'chunking_method': 'semantic',
        'chunk_stats': chunk_stats,
        'num_chunks': len(all_chunks),
        'num_documents': len(llamaparse_docs),
        'version': '2.0'  # Mark as enhanced version
    }

    # Save the index
    output_file = OUTPUT_DIR / "embedding_index.pkl"

    # Backup old index
    if output_file.exists():
        backup_file = OUTPUT_DIR / "embedding_index_backup.pkl"
        import shutil
        shutil.copy(output_file, backup_file)
        print(f"\n   Backed up old index to {backup_file}")

    print(f"\n4. Saving index to {output_file}...")
    with open(output_file, 'wb') as f:
        pickle.dump(embedding_index, f)

    file_size = output_file.stat().st_size / (1024 * 1024)
    print(f"   Index size: {file_size:.2f} MB")

    # Print summary
    print("\n" + "=" * 60)
    print("ENHANCED INDEX BUILD COMPLETE")
    print("=" * 60)
    print(f"Documents processed: {len(llamaparse_docs)}")
    print(f"Chunks created: {len(all_chunks)}")
    print(f"Chunking method: Semantic (section/paragraph/slide aware)")
    print(f"Embedding dimensions: {EMBEDDING_DIMENSIONS}")
    print(f"Index file: {output_file}")
    print(f"Index size: {file_size:.2f} MB")
    print(f"Version: 2.0 (Enhanced)")

    return embedding_index


if __name__ == "__main__":
    build_enhanced_index()
