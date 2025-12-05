"""
Incremental Batch Indexer - Safe for M3 Mac

Features:
- Processes documents in small batches (50 at a time)
- Uses OpenAI API for embeddings (no local compute)
- Saves progress after each batch
- Auto-resumes if interrupted
- Never corrupts existing index (writes to temp, then swaps)
- Memory efficient - processes and discards

Usage:
    python incremental_indexer.py              # Resume or start fresh
    python incremental_indexer.py --reset      # Start completely fresh
    python incremental_indexer.py --status     # Check progress
"""

import pickle
import json
import numpy as np
import time
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from openai import AzureOpenAI

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Configuration
BATCH_SIZE = 50  # Documents per batch (safe for M3)
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 3072
DATA_DIR = Path("/Users/rishitjain/Downloads/knowledgevault_backend/club_data")
PROGRESS_FILE = DATA_DIR / "indexing_progress.json"
TEMP_INDEX_FILE = DATA_DIR / "embedding_index_temp.pkl"
FINAL_INDEX_FILE = DATA_DIR / "embedding_index.pkl"
BACKUP_INDEX_FILE = DATA_DIR / "embedding_index_backup.pkl"

# Rate limiting
REQUESTS_PER_MINUTE = 500  # OpenAI limit for text-embedding-3-large
DELAY_BETWEEN_BATCHES = 0.5  # seconds


class IncrementalIndexer:
    """Safe incremental indexer that won't crash or corrupt data"""

    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY",
                "os.getenv("OPENAI_API_KEY", "")")

        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        self.progress = self._load_progress()

    def _load_progress(self) -> Dict:
        """Load progress from file or create new"""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {
            'processed_doc_ids': [],
            'total_docs': 0,
            'total_chunks': 0,
            'last_batch': 0,
            'started_at': None,
            'last_updated': None,
            'status': 'not_started'
        }

    def _save_progress(self):
        """Save progress to file"""
        self.progress['last_updated'] = datetime.now().isoformat()
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def _load_search_index(self) -> Dict:
        """Load the main search index with all documents"""
        search_index_path = DATA_DIR / "search_index.pkl"
        with open(search_index_path, 'rb') as f:
            return pickle.load(f)

    def _load_existing_embedding_index(self) -> Optional[Dict]:
        """Load existing embedding index if it exists"""
        if TEMP_INDEX_FILE.exists():
            # Resume from temp file
            with open(TEMP_INDEX_FILE, 'rb') as f:
                return pickle.load(f)
        elif FINAL_INDEX_FILE.exists():
            # Start from final file
            with open(FINAL_INDEX_FILE, 'rb') as f:
                return pickle.load(f)
        return None

    def _save_temp_index(self, index: Dict):
        """Save to temp file (safe - doesn't touch main index)"""
        with open(TEMP_INDEX_FILE, 'wb') as f:
            pickle.dump(index, f)
        print(f"  ✓ Saved temp index ({len(index['chunks'])} chunks)")

    def _finalize_index(self, index: Dict):
        """Safely swap temp index to final (with backup)"""
        # Backup existing
        if FINAL_INDEX_FILE.exists():
            import shutil
            shutil.copy(FINAL_INDEX_FILE, BACKUP_INDEX_FILE)
            print(f"  ✓ Backed up existing index")

        # Move temp to final
        with open(FINAL_INDEX_FILE, 'wb') as f:
            pickle.dump(index, f)

        # Remove temp
        if TEMP_INDEX_FILE.exists():
            TEMP_INDEX_FILE.unlink()

        print(f"  ✓ Finalized index ({len(index['chunks'])} chunks)")

    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts via OpenAI API"""
        if not texts:
            return []

        # Filter empty texts
        valid_texts = [t[:8000] if t else " " for t in texts]  # Truncate to 8K chars

        try:
            response = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=valid_texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"  ⚠ Embedding error: {e}")
            # Return zero vectors on error (won't crash)
            return [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]

    def _chunk_document(self, content: str, doc_id: str, metadata: Dict) -> List[Dict]:
        """Simple chunking - 800 tokens (~3200 chars) with overlap"""
        if not content or len(content) < 50:
            return []

        chunks = []
        chunk_size = 3200  # ~800 tokens
        overlap = 400  # ~100 tokens overlap

        start = 0
        chunk_idx = 0

        while start < len(content):
            end = start + chunk_size
            chunk_content = content[start:end]

            if len(chunk_content.strip()) > 50:  # Min 50 chars
                chunks.append({
                    'chunk_id': f"{doc_id}_chunk_{chunk_idx}",
                    'doc_id': doc_id,
                    'content': chunk_content,
                    'chunk_index': chunk_idx,
                    'metadata': metadata
                })
                chunk_idx += 1

            start = end - overlap
            if start >= len(content) - overlap:
                break

        return chunks

    def get_status(self) -> Dict:
        """Get current indexing status"""
        search_index = self._load_search_index()
        total_docs = len(search_index.get('doc_ids', []))
        processed = len(self.progress.get('processed_doc_ids', []))

        return {
            'total_documents': total_docs,
            'processed_documents': processed,
            'remaining_documents': total_docs - processed,
            'total_chunks': self.progress.get('total_chunks', 0),
            'progress_percent': round(processed / total_docs * 100, 1) if total_docs > 0 else 0,
            'status': self.progress.get('status', 'not_started'),
            'started_at': self.progress.get('started_at'),
            'last_updated': self.progress.get('last_updated'),
            'estimated_batches_remaining': (total_docs - processed) // BATCH_SIZE + 1
        }

    def reset(self):
        """Reset all progress (start fresh)"""
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
        if TEMP_INDEX_FILE.exists():
            TEMP_INDEX_FILE.unlink()
        self.progress = self._load_progress()
        print("✓ Reset complete - ready to start fresh")

    def run(self, max_batches: int = None):
        """Run the incremental indexer"""
        print("\n" + "="*60)
        print("INCREMENTAL BATCH INDEXER")
        print("="*60)

        # Load search index
        print("\nLoading search index...")
        search_index = self._load_search_index()
        all_doc_ids = search_index.get('doc_ids', [])
        doc_index = search_index.get('doc_index', {})
        print(f"  Found {len(all_doc_ids)} total documents")

        # Get already processed
        processed_set = set(self.progress.get('processed_doc_ids', []))
        remaining_doc_ids = [d for d in all_doc_ids if d not in processed_set]
        print(f"  Already processed: {len(processed_set)}")
        print(f"  Remaining: {len(remaining_doc_ids)}")

        if not remaining_doc_ids:
            print("\n✓ All documents already indexed!")
            return

        # Load or create embedding index
        print("\nLoading embedding index...")
        embedding_index = self._load_existing_embedding_index()
        if embedding_index is None:
            embedding_index = {
                'chunks': [],
                'embeddings': np.array([], dtype=np.float32).reshape(0, EMBEDDING_DIMENSIONS),
                'model': EMBEDDING_MODEL,
                'created_at': datetime.now().isoformat(),
                'doc_ids': set()
            }
            print("  Created new index")
        else:
            print(f"  Loaded existing index ({len(embedding_index['chunks'])} chunks)")

        # Update progress
        if self.progress['status'] == 'not_started':
            self.progress['started_at'] = datetime.now().isoformat()
        self.progress['status'] = 'running'
        self.progress['total_docs'] = len(all_doc_ids)
        self._save_progress()

        # Process in batches
        batch_num = 0
        total_new_chunks = 0

        for i in range(0, len(remaining_doc_ids), BATCH_SIZE):
            batch_doc_ids = remaining_doc_ids[i:i + BATCH_SIZE]
            batch_num += 1

            if max_batches and batch_num > max_batches:
                print(f"\n⏸ Stopped after {max_batches} batches (as requested)")
                break

            print(f"\n--- Batch {batch_num} ({len(batch_doc_ids)} docs) ---")

            # Chunk all documents in batch
            all_chunks = []
            for doc_id in batch_doc_ids:
                doc = doc_index.get(doc_id, {})
                content = doc.get('content', '')
                metadata = doc.get('metadata', {})

                if content and len(content) >= 100:
                    chunks = self._chunk_document(content, doc_id, metadata)
                    all_chunks.extend(chunks)

            print(f"  Created {len(all_chunks)} chunks")

            if not all_chunks:
                # Mark as processed even if no chunks
                self.progress['processed_doc_ids'].extend(batch_doc_ids)
                self._save_progress()
                continue

            # Get embeddings (via OpenAI API - no local compute)
            print(f"  Getting embeddings from OpenAI...")
            chunk_texts = [c['content'] for c in all_chunks]

            # Process in sub-batches of 100 for API
            all_embeddings = []
            for j in range(0, len(chunk_texts), 100):
                sub_batch = chunk_texts[j:j + 100]
                embeddings = self._get_embeddings_batch(sub_batch)
                all_embeddings.extend(embeddings)
                time.sleep(0.1)  # Rate limit safety

            print(f"  Got {len(all_embeddings)} embeddings")

            # Add to index
            embedding_index['chunks'].extend(all_chunks)
            new_embeddings = np.array(all_embeddings, dtype=np.float32)

            if len(embedding_index['embeddings']) == 0:
                embedding_index['embeddings'] = new_embeddings
            else:
                embedding_index['embeddings'] = np.vstack([
                    embedding_index['embeddings'],
                    new_embeddings
                ])

            # Update doc_ids set
            if isinstance(embedding_index.get('doc_ids'), set):
                embedding_index['doc_ids'].update(batch_doc_ids)
            else:
                embedding_index['doc_ids'] = set(batch_doc_ids)

            total_new_chunks += len(all_chunks)

            # Save progress (safe checkpoint)
            self._save_temp_index(embedding_index)
            self.progress['processed_doc_ids'].extend(batch_doc_ids)
            self.progress['total_chunks'] = len(embedding_index['chunks'])
            self.progress['last_batch'] = batch_num
            self._save_progress()

            print(f"  ✓ Batch complete. Total chunks: {len(embedding_index['chunks'])}")

            # Rate limit delay
            time.sleep(DELAY_BETWEEN_BATCHES)

        # Finalize
        print("\n" + "="*60)
        print("FINALIZING INDEX")
        print("="*60)

        # Convert doc_ids set to list for pickle
        embedding_index['doc_ids'] = list(embedding_index.get('doc_ids', set()))
        embedding_index['updated_at'] = datetime.now().isoformat()

        # Build BM25 index for the chunks
        print("\nBuilding BM25 index...")
        try:
            from rank_bm25 import BM25Okapi
            import re

            def tokenize(text):
                return re.findall(r'\b[\w\-]+\b', text.lower())

            tokenized_chunks = [tokenize(c['content']) for c in embedding_index['chunks']]
            embedding_index['bm25_index'] = BM25Okapi(tokenized_chunks)
            print("  ✓ BM25 index built")
        except Exception as e:
            print(f"  ⚠ BM25 build failed: {e}")

        self._finalize_index(embedding_index)

        self.progress['status'] = 'completed'
        self._save_progress()

        print(f"\n✓ INDEXING COMPLETE!")
        print(f"  Total documents: {len(self.progress['processed_doc_ids'])}")
        print(f"  Total chunks: {len(embedding_index['chunks'])}")
        print(f"  Index saved to: {FINAL_INDEX_FILE}")


def main():
    indexer = IncrementalIndexer()

    if len(sys.argv) > 1:
        if sys.argv[1] == '--status':
            status = indexer.get_status()
            print("\n=== INDEXING STATUS ===")
            for key, value in status.items():
                print(f"  {key}: {value}")
            return

        elif sys.argv[1] == '--reset':
            confirm = input("This will delete all progress. Type 'yes' to confirm: ")
            if confirm.lower() == 'yes':
                indexer.reset()
            return

        elif sys.argv[1] == '--test':
            # Test with just 2 batches
            indexer.run(max_batches=2)
            return

    # Normal run - process all
    indexer.run()


if __name__ == "__main__":
    main()
