import os
"""
Hierarchical RAG (Retrieval-Augmented Generation) Engine
Combines Knowledge Graph and Vector Database for intelligent querying
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from openai import AzureOpenAI
import re

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2024-12-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"



class HierarchicalRAG:
    """Hierarchical RAG system combining graph traversal and vector search"""

    def __init__(
        self,
        vector_db,
        knowledge_graph=None,
        api_key: str = None,
        model: str = "gpt-4o-mini"
    ):
        """
        Initialize Hierarchical RAG

        Args:
            vector_db: VectorDatabaseBuilder instance
            knowledge_graph: KnowledgeGraphBuilder instance (optional)
            api_key: OpenAI API key
            model: LLM model to use
        """
        self.vector_db = vector_db
        self.knowledge_graph = knowledge_graph
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        ) if api_key else None
        self.model = model

        print("✓ Hierarchical RAG initialized")

    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract entities from query using LLM

        Args:
            query: User query

        Returns:
            Dictionary of extracted entities
        """
        if not self.client:
            # Fallback to simple keyword extraction
            return self._simple_entity_extraction(query)

        prompt = f"""Extract entities from the following query. Identify:
- employees: Names or email addresses of people
- projects: Project names or identifiers
- topics: Main topics or keywords
- time_references: Time periods or dates mentioned

Query: {query}

Provide response as JSON:
{{
    "employees": [...],
    "projects": [...],
    "topics": [...],
    "time_references": [...]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting entities from queries for knowledge retrieval."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=300,
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON
            if '{' in result_text:
                start = result_text.index('{')
                end = result_text.rindex('}') + 1
                json_str = result_text[start:end]
                entities = json.loads(json_str)
                return entities

        except Exception as e:
            print(f"Entity extraction failed: {e}")

        return self._simple_entity_extraction(query)

    def _simple_entity_extraction(self, query: str) -> Dict[str, List[str]]:
        """Simple fallback entity extraction"""
        # Extract capitalized words as potential entities
        words = query.split()
        capitalized = [w for w in words if w[0].isupper() and len(w) > 1]

        return {
            'employees': [],
            'projects': [],
            'topics': [w.lower() for w in words if len(w) > 4],
            'time_references': []
        }

    def get_relevant_clusters(
        self,
        entities: Dict[str, List[str]],
        query: str
    ) -> List[str]:
        """
        Determine relevant cluster IDs based on entities

        Args:
            entities: Extracted entities
            query: Original query

        Returns:
            List of relevant cluster IDs
        """
        cluster_ids = []

        # If knowledge graph is available, query it
        if self.knowledge_graph and self.knowledge_graph.driver:
            cluster_ids = self._query_graph_for_clusters(entities)

        # If no graph results, fall back to vector similarity on cluster labels
        if not cluster_ids:
            cluster_ids = self._find_clusters_by_similarity(query)

        return cluster_ids

    def _query_graph_for_clusters(self, entities: Dict[str, List[str]]) -> List[str]:
        """Query knowledge graph for relevant clusters"""
        # This would query Neo4j based on entities
        # For now, return empty list as graph might not be running
        return []

    def _find_clusters_by_similarity(self, query: str, top_k: int = 5) -> List[str]:
        """Find clusters using vector similarity"""
        # Search vector database without cluster filtering
        results = self.vector_db.search(query, n_results=top_k)

        # Extract unique cluster IDs
        cluster_ids = set()
        if results and 'metadatas' in results and results['metadatas']:
            for metadata_list in results['metadatas']:
                for metadata in metadata_list:
                    cluster_id = metadata.get('cluster_id')
                    if cluster_id:
                        cluster_ids.add(cluster_id)

        return list(cluster_ids)

    def hierarchical_retrieve(
        self,
        query: str,
        top_k: int = 10,
        use_hierarchy: bool = True
    ) -> Dict:
        """
        Perform hierarchical retrieval

        Args:
            query: User query
            top_k: Number of results to retrieve
            use_hierarchy: Whether to use hierarchical filtering

        Returns:
            Retrieved documents and metadata
        """
        print(f"\nQuery: {query}")

        retrieval_metadata = {
            'query': query,
            'use_hierarchy': use_hierarchy,
            'entities': {},
            'cluster_ids': [],
        }

        if use_hierarchy:
            # Step 1: Extract entities
            print("  Step 1: Extracting entities...")
            entities = self.extract_entities(query)
            retrieval_metadata['entities'] = entities
            print(f"    Entities: {entities}")

            # Step 2: Get relevant clusters
            print("  Step 2: Finding relevant clusters...")
            cluster_ids = self.get_relevant_clusters(entities, query)
            retrieval_metadata['cluster_ids'] = cluster_ids
            print(f"    Found {len(cluster_ids)} relevant clusters")

            # Step 3: Vector search within clusters
            if cluster_ids:
                print("  Step 3: Searching within clusters...")
                results = self.vector_db.search_within_clusters(
                    query,
                    cluster_ids,
                    n_results=top_k
                )
            else:
                print("  Step 3: No specific clusters found, searching all documents...")
                results = self.vector_db.search(query, n_results=top_k)
        else:
            # Direct vector search without hierarchy
            print("  Performing direct vector search...")
            results = self.vector_db.search(query, n_results=top_k)

        retrieval_metadata['num_results'] = len(results['ids'][0]) if results['ids'] else 0

        return {
            'results': results,
            'metadata': retrieval_metadata
        }

    def generate_response(
        self,
        query: str,
        retrieval_results: Dict,
        max_context_length: int = 8000
    ) -> Dict:
        """
        Generate response using retrieved context

        Args:
            query: User query
            retrieval_results: Results from hierarchical_retrieve
            max_context_length: Maximum context length for LLM

        Returns:
            Generated response with citations
        """
        if not self.client:
            return {
                'answer': 'LLM not configured',
                'sources': [],
                'error': 'OpenAI API key not provided'
            }

        # Extract documents from results
        results = retrieval_results['results']

        if not results or not results['ids'] or not results['ids'][0]:
            return {
                'answer': 'No relevant documents found for your query.',
                'sources': [],
                'metadata': retrieval_results['metadata']
            }

        # Build context from retrieved documents
        context_parts = []
        sources = []

        for i, (doc_id, document, metadata, distance) in enumerate(zip(
            results['ids'][0],
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            # Limit document length
            doc_text = document[:1000]  # Truncate long documents

            source_info = {
                'doc_id': doc_id,
                'subject': metadata.get('subject', 'No subject'),
                'employee': metadata.get('employee', ''),
                'timestamp': metadata.get('timestamp', ''),
                'cluster': metadata.get('cluster_label', ''),
                'relevance_score': 1.0 - distance,  # Convert distance to similarity
            }

            sources.append(source_info)

            context_parts.append(
                f"[Document {i+1}]\n"
                f"Source: {metadata.get('employee', 'Unknown')} - {metadata.get('subject', 'No subject')}\n"
                f"Date: {metadata.get('timestamp', 'Unknown')}\n"
                f"Project: {metadata.get('cluster_label', 'Unknown')}\n"
                f"Content: {doc_text}\n"
            )

        # Combine context
        context = "\n\n".join(context_parts[:10])  # Limit to top 10 documents

        # Truncate if too long
        if len(context) > max_context_length:
            context = context[:max_context_length] + "\n... [truncated]"

        # Create prompt
        prompt = f"""Using the following verified source documents, answer the user's question.

Provide a comprehensive answer based ONLY on the information in the documents. If the documents don't contain enough information to fully answer the question, acknowledge what's missing.

Include citations by referring to document numbers (e.g., "According to Document 1...").

Source Documents:
{context}

User Question: {query}

Please provide a detailed answer with citations:"""

        try:
            # Generate response
            print("  Generating response...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a knowledgeable assistant helping users understand information from their organizational knowledge base. Always cite your sources and acknowledge limitations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            answer = response.choices[0].message.content.strip()

            return {
                'answer': answer,
                'sources': sources,
                'metadata': retrieval_results['metadata'],
                'num_sources': len(sources)
            }

        except Exception as e:
            return {
                'answer': f'Error generating response: {str(e)}',
                'sources': sources,
                'metadata': retrieval_results['metadata'],
                'error': str(e)
            }

    def query(
        self,
        query: str,
        use_hierarchy: bool = True,
        top_k: int = 10
    ) -> Dict:
        """
        Complete RAG query pipeline

        Args:
            query: User query
            use_hierarchy: Use hierarchical retrieval
            top_k: Number of documents to retrieve

        Returns:
            Complete response with answer and sources
        """
        # Retrieve relevant documents
        retrieval_results = self.hierarchical_retrieve(
            query,
            top_k=top_k,
            use_hierarchy=use_hierarchy
        )

        # Generate response
        response = self.generate_response(query, retrieval_results)

        return response

    def interactive_query(self):
        """Interactive query session"""
        print("\n" + "="*80)
        print("KNOWLEDGEVAULT HIERARCHICAL RAG - INTERACTIVE MODE")
        print("="*80)
        print("Ask questions about the knowledge base. Type 'exit' to quit.\n")

        while True:
            query = input("\nYour question: ").strip()

            if query.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break

            if not query:
                continue

            # Process query
            response = self.query(query)

            # Display response
            print("\n" + "-"*80)
            print("ANSWER:")
            print("-"*80)
            print(response['answer'])

            print("\n" + "-"*80)
            print(f"SOURCES ({response.get('num_sources', 0)}):")
            print("-"*80)

            for i, source in enumerate(response.get('sources', [])[:5], 1):
                print(f"\n{i}. {source['subject']}")
                print(f"   Employee: {source['employee']}")
                print(f"   Date: {source['timestamp']}")
                print(f"   Project: {source['cluster']}")
                print(f"   Relevance: {source['relevance_score']:.2%}")


if __name__ == "__main__":
    from config.config import Config
    from indexing.vector_database import VectorDatabaseBuilder

    # Load vector database
    print("Loading vector database...")
    vdb = VectorDatabaseBuilder(
        persist_directory=Config.CHROMA_PERSIST_DIR,
        collection_name=Config.COLLECTION_NAME,
        embedding_model=Config.EMBEDDING_MODEL
    )

    # Initialize RAG
    rag = HierarchicalRAG(
        vector_db=vdb,
        api_key=Config.OPENAI_API_KEY,
        model=Config.LLM_MODEL
    )

    # Test query
    test_query = "What were the main projects and their status?"
    response = rag.query(test_query)

    print("\n" + "="*80)
    print(f"TEST QUERY: {test_query}")
    print("="*80)
    print(f"\nAnswer: {response['answer']}")
    print(f"\nSources: {response.get('num_sources', 0)}")
