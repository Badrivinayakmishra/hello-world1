import os
"""
Vector Database using ChromaDB
Creates and manages vector embeddings for semantic search
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
import numpy as np
from tqdm import tqdm

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"



class VectorDatabaseBuilder:
    """Build and manage vector database with ChromaDB"""

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "knowledgevault",
        embedding_model: str = "sentence-transformers/all-mpnet-base-v2",
        use_openai_embeddings: bool = False,
        openai_api_key: Optional[str] = None
    ):
        """
        Initialize ChromaDB vector database

        Args:
            persist_directory: Directory to persist ChromaDB
            collection_name: Name of the collection
            embedding_model: Model for embeddings
            use_openai_embeddings: Whether to use OpenAI embeddings
            openai_api_key: OpenAI API key if using OpenAI embeddings
        """
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection_name = collection_name
        self.use_openai = use_openai_embeddings

        # Initialize embedding model
        if use_openai_embeddings and openai_api_key:
            self.openai_client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
            self.embedding_model_name = "text-embedding-3-large"
            self.embedding_model = None
            print(f"✓ Using OpenAI embeddings: {self.embedding_model_name}")
        else:
            self.embedding_model = SentenceTransformer(embedding_model)
            self.embedding_model_name = embedding_model
            self.openai_client = None
            print(f"✓ Loaded embedding model: {embedding_model}")

        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"✓ Loaded existing collection: {collection_name}")
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "KnowledgeVault document embeddings"}
            )
            print(f"✓ Created new collection: {collection_name}")

    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if self.use_openai and self.openai_client:
            # Use OpenAI embeddings
            response = self.openai_client.embeddings.create(
                model=self.embedding_model_name,
                input=text
            )
            return response.data[0].embedding
        else:
            # Use sentence transformers
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()

    def prepare_document_for_indexing(self, document: Dict) -> Dict:
        """
        Prepare a document for indexing

        Args:
            document: Document dictionary

        Returns:
            Dictionary with text, metadata, and id
        """
        # Create enriched text for embedding
        metadata = document.get('metadata', {})
        subject = metadata.get('subject', '')
        content = document.get('content', '')

        # Combine subject and content (weight subject higher)
        enriched_text = f"{subject}\n{subject}\n{content}"

        # Truncate if too long (max ~8000 chars for embeddings)
        max_length = 8000
        if len(enriched_text) > max_length:
            enriched_text = enriched_text[:max_length]

        # Prepare metadata for ChromaDB (must be simple types)
        chroma_metadata = {
            'doc_id': document.get('doc_id', ''),
            'employee': metadata.get('employee', ''),
            'subject': metadata.get('subject', '')[:500] if metadata.get('subject') else '',
            'timestamp': metadata.get('timestamp', ''),
            'folder': metadata.get('folder', ''),
            'source_type': metadata.get('source_type', ''),
            'cluster_id': document.get('cluster_id', ''),
            'cluster_label': document.get('cluster_label', ''),
            'cluster_type': document.get('cluster_type', ''),
            'source_path': metadata.get('source_path', '')[:500] if metadata.get('source_path') else '',
        }

        return {
            'id': document.get('doc_id', ''),
            'text': enriched_text,
            'metadata': chroma_metadata
        }

    def add_documents(self, documents: List[Dict], batch_size: int = 100):
        """
        Add documents to vector database

        Args:
            documents: List of document dictionaries
            batch_size: Batch size for adding documents
        """
        print(f"\nIndexing {len(documents)} documents...")

        # Prepare documents
        prepared_docs = [self.prepare_document_for_indexing(doc) for doc in documents]

        # Process in batches
        for i in tqdm(range(0, len(prepared_docs), batch_size), desc="Indexing batches"):
            batch = prepared_docs[i:i + batch_size]

            ids = [doc['id'] for doc in batch]
            texts = [doc['text'] for doc in batch]
            metadatas = [doc['metadata'] for doc in batch]

            # Generate embeddings
            if self.use_openai and self.openai_client:
                # OpenAI batch embedding
                embeddings = []
                for text in texts:
                    emb = self.get_embedding(text)
                    embeddings.append(emb)
            else:
                # Sentence transformers batch embedding
                embeddings = self.embedding_model.encode(
                    texts,
                    convert_to_numpy=True,
                    show_progress_bar=False
                ).tolist()

            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )

        print(f"✓ Indexed {len(documents)} documents")

    def index_all_projects(self, project_clusters_dir: str):
        """
        Index all project documents from cluster directory

        Args:
            project_clusters_dir: Directory with project clusters
        """
        print("\nIndexing all project documents...")

        project_dir = Path(project_clusters_dir)
        all_documents = []

        # Collect all documents
        for employee_dir in project_dir.iterdir():
            if not employee_dir.is_dir():
                continue

            print(f"Loading documents for {employee_dir.name}...")

            # Load all JSONL files
            for jsonl_file in employee_dir.glob("*.jsonl"):
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        doc = json.loads(line)
                        all_documents.append(doc)

        print(f"\nTotal documents to index: {len(all_documents)}")

        # Add documents to vector database
        self.add_documents(all_documents)

        # Save collection info
        print(f"\n✓ Vector database built successfully")
        print(f"  Collection: {self.collection_name}")
        print(f"  Total documents: {self.collection.count()}")
        print(f"  Persist directory: {self.persist_dir}")

    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Search vector database

        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {'cluster_id': 'project_1'})

        Returns:
            Search results
        """
        # Get query embedding
        query_embedding = self.get_embedding(query)

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata if filter_metadata else None
        )

        return results

    def search_within_clusters(
        self,
        query: str,
        cluster_ids: List[str],
        n_results: int = 10
    ) -> Dict:
        """
        Search within specific clusters (hierarchical search)

        Args:
            query: Search query
            cluster_ids: List of cluster IDs to search within
            n_results: Number of results

        Returns:
            Search results
        """
        # Get query embedding
        query_embedding = self.get_embedding(query)

        # Search with cluster filter
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"cluster_id": {"$in": cluster_ids}}
        )

        return results

    def get_collection_stats(self) -> Dict:
        """Get statistics about the collection"""
        count = self.collection.count()

        stats = {
            'collection_name': self.collection_name,
            'total_documents': count,
            'embedding_model': self.embedding_model_name,
            'persist_directory': str(self.persist_dir),
        }

        return stats


def build_vector_database(
    project_clusters_dir: str,
    persist_dir: str,
    config
) -> VectorDatabaseBuilder:
    """
    Main function to build vector database

    Args:
        project_clusters_dir: Directory with project clusters
        persist_dir: Directory to persist vector database
        config: Configuration object

    Returns:
        VectorDatabaseBuilder instance
    """
    # Initialize vector database
    vdb = VectorDatabaseBuilder(
        persist_directory=persist_dir,
        collection_name=config.COLLECTION_NAME,
        embedding_model=config.EMBEDDING_MODEL,
        use_openai_embeddings=False,  # Use sentence transformers for cost efficiency
    )

    # Index all documents
    vdb.index_all_projects(project_clusters_dir)

    # Print stats
    stats = vdb.get_collection_stats()
    print("\n" + "="*60)
    print("VECTOR DATABASE STATISTICS")
    print("="*60)
    for key, value in stats.items():
        print(f"{key}: {value}")

    return vdb


if __name__ == "__main__":
    from config.config import Config

    vdb = build_vector_database(
        project_clusters_dir=str(Config.DATA_DIR / "project_clusters"),
        persist_dir=Config.CHROMA_PERSIST_DIR,
        config=Config
    )

    # Test search
    print("\n" + "="*60)
    print("TESTING SEARCH")
    print("="*60)
    results = vdb.search("project timeline and deadlines", n_results=5)
    print(f"Found {len(results['ids'][0])} results")
    for i, (doc_id, distance) in enumerate(zip(results['ids'][0], results['distances'][0])):
        print(f"{i+1}. {doc_id} (distance: {distance:.4f})")
