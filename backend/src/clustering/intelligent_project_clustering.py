"""
Intelligent Project Clustering Module
=====================================
Uses LLM to extract precise project information from documents,
filter irrelevant content, deduplicate, and create canonical projects.

Pipeline:
1. LLM-based document project extraction
2. Quality filtering (remove irrelevant)
3. Semantic project deduplication (HDBSCAN on embeddings)
4. LLM canonical naming
5. Cross-employee project merging
"""

import json
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
import numpy as np
from collections import defaultdict
import pickle
import warnings
warnings.filterwarnings('ignore')

from openai import AzureOpenAI
from sentence_transformers import SentenceTransformer
from hdbscan import HDBSCAN
from sklearn.metrics.pairwise import cosine_similarity

# Load environment
from dotenv import load_dotenv

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"

load_dotenv()


@dataclass
class DocumentProjectInfo:
    """Extracted project information from a document"""
    doc_id: str
    project_name: str  # Specific project name
    project_description: str  # 1-2 sentence summary
    client_name: Optional[str] = None
    is_relevant: bool = True  # Is this actually project work?
    relevance_reason: str = ""  # Why relevant/not relevant
    confidence: float = 0.0
    key_topics: List[str] = field(default_factory=list)
    people_mentioned: List[str] = field(default_factory=list)
    raw_metadata: Dict = field(default_factory=dict)


@dataclass
class CanonicalProject:
    """A unified, deduplicated project"""
    id: str
    name: str  # LLM-generated meaningful name
    description: str  # Summary of what the project is
    client: Optional[str] = None
    team_members: List[str] = field(default_factory=list)
    document_ids: List[str] = field(default_factory=list)
    date_range: Optional[Tuple[str, str]] = None
    status: str = "active"  # active, completed, archived
    key_topics: List[str] = field(default_factory=list)
    merged_from: List[str] = field(default_factory=list)  # Original project names
    confidence: float = 0.0
    document_count: int = 0


class IntelligentProjectClusterer:
    """
    Intelligent project clustering using LLM extraction and semantic deduplication.
    """

    def __init__(
        self,
        openai_api_key: str = None,
        embedding_model: str = "all-mpnet-base-v2",
        cache_dir: str = None,
        use_cache: bool = True
    ):
        """
        Initialize the intelligent clusterer.

        Args:
            openai_api_key: OpenAI API key for LLM calls
            embedding_model: Sentence transformer model for semantic similarity
            cache_dir: Directory to cache results
            use_cache: Whether to use caching
        """
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        self.embedding_model_name = embedding_model
        self.embedding_model = None  # Lazy load
        self.use_cache = use_cache

        # Cache setup
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).parent.parent / "club_data" / "project_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Results storage
        self.document_extractions: Dict[str, DocumentProjectInfo] = {}
        self.canonical_projects: Dict[str, CanonicalProject] = {}

        print("✓ Intelligent Project Clusterer initialized")

    def _get_embedding_model(self):
        """Lazy load embedding model"""
        if self.embedding_model is None:
            print(f"Loading embedding model: {self.embedding_model_name}...")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            print("✓ Embedding model loaded")
        return self.embedding_model

    def _get_cache_key(self, content: str) -> str:
        """Generate cache key from content"""
        return hashlib.md5(content[:1000].encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Load result from cache"""
        if not self.use_cache:
            return None
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                return json.load(f)
        return None

    def _save_to_cache(self, cache_key: str, data: Dict):
        """Save result to cache"""
        if not self.use_cache:
            return
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump(data, f)

    # =========================================================================
    # Step 1: LLM-Based Document Project Extraction
    # =========================================================================

    def extract_project_from_document(self, document: Dict) -> DocumentProjectInfo:
        """
        Use LLM to extract project information from a single document.

        Args:
            document: Document dict with 'content', 'metadata', 'doc_id'

        Returns:
            DocumentProjectInfo with extracted details
        """
        doc_id = document.get('doc_id', document.get('metadata', {}).get('file_name', 'unknown'))
        content = document.get('content', '')
        metadata = document.get('metadata', {})

        # Check cache first
        cache_key = self._get_cache_key(content)
        cached = self._load_from_cache(cache_key)
        if cached:
            return DocumentProjectInfo(
                doc_id=doc_id,
                raw_metadata=metadata,
                **cached
            )

        # Prepare content for LLM (truncate if too long)
        subject = metadata.get('subject', metadata.get('file_name', ''))
        truncated_content = content[:3000] if len(content) > 3000 else content

        prompt = f"""Analyze this document and extract project information.

DOCUMENT:
Subject/Title: {subject}
Content: {truncated_content}

Extract the following information in JSON format:
{{
    "project_name": "Specific, descriptive project name (e.g., 'Nike Q4 Marketing Campaign', 'Healthcare Dashboard Development'). NOT generic like 'Work Project' or 'Email Thread'",
    "project_description": "1-2 sentence summary of what this project/work is about",
    "client_name": "Client or company name if mentioned, null otherwise",
    "is_relevant": true/false - Is this actual project/work content? false for: spam, newsletters, system notifications, personal emails, generic FYI messages,
    "relevance_reason": "Brief explanation of why this is or isn't relevant project content",
    "confidence": 0.0-1.0 - How confident are you in this extraction?,
    "key_topics": ["topic1", "topic2"] - Main topics/themes in this document,
    "people_mentioned": ["Name1", "Name2"] - People mentioned in the document
}}

IMPORTANT:
- Be SPECIFIC with project names - avoid generic names
- If the document is about multiple projects, use the PRIMARY one
- Set is_relevant=false for non-work content
- Return ONLY valid JSON, no explanation"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a project analysis assistant. Extract project information from documents. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            result_text = response.choices[0].message.content.strip()

            # Clean up response if it has markdown code blocks
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()

            result = json.loads(result_text)

            # Cache the result
            self._save_to_cache(cache_key, result)

            return DocumentProjectInfo(
                doc_id=doc_id,
                project_name=result.get('project_name', 'Unknown Project'),
                project_description=result.get('project_description', ''),
                client_name=result.get('client_name'),
                is_relevant=result.get('is_relevant', True),
                relevance_reason=result.get('relevance_reason', ''),
                confidence=result.get('confidence', 0.5),
                key_topics=result.get('key_topics', []),
                people_mentioned=result.get('people_mentioned', []),
                raw_metadata=metadata
            )

        except Exception as e:
            print(f"  ⚠ LLM extraction failed for {doc_id}: {e}")
            # Fallback to basic extraction
            return DocumentProjectInfo(
                doc_id=doc_id,
                project_name=subject if subject else "Unknown Project",
                project_description="",
                is_relevant=True,  # Assume relevant if we can't determine
                confidence=0.2,
                raw_metadata=metadata
            )

    def extract_all_documents(
        self,
        documents: List[Dict],
        batch_size: int = 10,
        show_progress: bool = True
    ) -> List[DocumentProjectInfo]:
        """
        Extract project information from all documents.

        Args:
            documents: List of document dicts
            batch_size: Process in batches for progress display
            show_progress: Whether to show progress

        Returns:
            List of DocumentProjectInfo
        """
        print(f"\n{'='*60}")
        print("STEP 1: LLM-Based Document Project Extraction")
        print(f"{'='*60}")
        print(f"Processing {len(documents)} documents...")

        extractions = []

        for i, doc in enumerate(documents):
            if show_progress and (i + 1) % batch_size == 0:
                print(f"  Processed {i + 1}/{len(documents)} documents...")

            extraction = self.extract_project_from_document(doc)
            extractions.append(extraction)
            self.document_extractions[extraction.doc_id] = extraction

        print(f"✓ Extracted project info from {len(extractions)} documents")

        # Summary
        relevant_count = sum(1 for e in extractions if e.is_relevant)
        print(f"  - Relevant documents: {relevant_count}")
        print(f"  - Irrelevant documents: {len(extractions) - relevant_count}")

        return extractions

    # =========================================================================
    # Step 2: Quality Filtering
    # =========================================================================

    def filter_irrelevant_documents(
        self,
        extractions: List[DocumentProjectInfo],
        min_confidence: float = 0.3
    ) -> Tuple[List[DocumentProjectInfo], List[DocumentProjectInfo]]:
        """
        Filter out irrelevant documents.

        Args:
            extractions: List of document extractions
            min_confidence: Minimum confidence to keep document

        Returns:
            Tuple of (relevant_docs, filtered_docs)
        """
        print(f"\n{'='*60}")
        print("STEP 2: Quality Filtering")
        print(f"{'='*60}")

        relevant = []
        filtered = []

        for extraction in extractions:
            # Filter criteria:
            # 1. is_relevant must be True
            # 2. confidence must be above threshold
            # 3. project_name must not be generic

            is_generic_name = extraction.project_name.lower() in [
                'unknown project', 'email', 'message', 'document',
                'work project', 'general', 'misc', 'other'
            ]

            if extraction.is_relevant and extraction.confidence >= min_confidence and not is_generic_name:
                relevant.append(extraction)
            else:
                filtered.append(extraction)

        print(f"✓ Quality filtering complete")
        print(f"  - Kept: {len(relevant)} documents")
        print(f"  - Filtered: {len(filtered)} documents")

        # Show filter reasons
        if filtered:
            reasons = defaultdict(int)
            for f in filtered:
                if not f.is_relevant:
                    reasons["Not relevant (spam/system/personal)"] += 1
                elif f.confidence < min_confidence:
                    reasons[f"Low confidence (<{min_confidence})"] += 1
                else:
                    reasons["Generic project name"] += 1

            print("  Filter breakdown:")
            for reason, count in reasons.items():
                print(f"    - {reason}: {count}")

        return relevant, filtered

    # =========================================================================
    # Step 3: Semantic Project Deduplication
    # =========================================================================

    def deduplicate_projects(
        self,
        extractions: List[DocumentProjectInfo],
        min_cluster_size: int = 2,
        similarity_threshold: float = 0.7
    ) -> Dict[str, List[DocumentProjectInfo]]:
        """
        Group similar projects together using semantic clustering.

        Args:
            extractions: Filtered document extractions
            min_cluster_size: Minimum documents to form a cluster
            similarity_threshold: Similarity threshold for merging

        Returns:
            Dict mapping cluster_id to list of documents
        """
        print(f"\n{'='*60}")
        print("STEP 3: Semantic Project Deduplication")
        print(f"{'='*60}")

        if len(extractions) < 2:
            print("⚠ Not enough documents for clustering")
            return {"cluster_0": extractions}

        # Create embeddings for project name + description
        model = self._get_embedding_model()

        texts = []
        for e in extractions:
            text = f"{e.project_name}. {e.project_description}"
            if e.client_name:
                text += f" Client: {e.client_name}"
            texts.append(text)

        print(f"  Embedding {len(texts)} project descriptions...")
        embeddings = model.encode(texts, show_progress_bar=False)

        # Use HDBSCAN for clustering
        print("  Clustering with HDBSCAN...")
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=1,
            metric='euclidean',
            cluster_selection_epsilon=0.3
        )

        clusters = clusterer.fit_predict(embeddings)

        # Group documents by cluster
        cluster_groups: Dict[str, List[DocumentProjectInfo]] = defaultdict(list)

        for i, (extraction, cluster_id) in enumerate(zip(extractions, clusters)):
            if cluster_id == -1:
                # Outlier - create its own cluster
                cluster_groups[f"single_{i}"].append(extraction)
            else:
                cluster_groups[f"cluster_{cluster_id}"].append(extraction)

        print(f"✓ Created {len(cluster_groups)} project clusters")

        # Show cluster sizes
        for cluster_id, docs in sorted(cluster_groups.items(), key=lambda x: -len(x[1])):
            sample_name = docs[0].project_name[:50]
            print(f"  - {cluster_id}: {len(docs)} docs (e.g., '{sample_name}')")

        return dict(cluster_groups)

    # =========================================================================
    # Step 4: LLM Canonical Naming
    # =========================================================================

    def generate_canonical_name(
        self,
        cluster_docs: List[DocumentProjectInfo]
    ) -> Tuple[str, str]:
        """
        Generate a canonical name for a cluster of documents.

        Args:
            cluster_docs: Documents in the cluster

        Returns:
            Tuple of (canonical_name, description)
        """
        # Collect all project names and descriptions
        names = [d.project_name for d in cluster_docs]
        descriptions = [d.project_description for d in cluster_docs if d.project_description]
        clients = [d.client_name for d in cluster_docs if d.client_name]
        all_topics = []
        for d in cluster_docs:
            all_topics.extend(d.key_topics)

        # Create prompt
        prompt = f"""Given these related project references from different documents, generate ONE canonical project name and description.

PROJECT NAMES FOUND:
{chr(10).join(f'- {n}' for n in names[:10])}

DESCRIPTIONS:
{chr(10).join(f'- {d}' for d in descriptions[:5])}

CLIENTS MENTIONED: {', '.join(set(clients)) if clients else 'None'}
KEY TOPICS: {', '.join(set(all_topics)[:10]) if all_topics else 'None'}

Generate a response in JSON format:
{{
    "canonical_name": "The best, most descriptive name for this project (2-6 words, title case)",
    "description": "A 1-2 sentence description of what this project is about",
    "client": "Client name if identifiable, null otherwise"
}}

IMPORTANT:
- The name should be SPECIFIC and DESCRIPTIVE
- Avoid generic names like 'General Project' or 'Work Items'
- Return ONLY valid JSON"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a project naming assistant. Create clear, professional project names."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )

            result_text = response.choices[0].message.content.strip()

            # Clean up response
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()

            result = json.loads(result_text)
            return result.get('canonical_name', names[0]), result.get('description', '')

        except Exception as e:
            print(f"  ⚠ Canonical naming failed: {e}")
            # Fallback: use most common name
            from collections import Counter
            most_common = Counter(names).most_common(1)[0][0]
            return most_common, descriptions[0] if descriptions else ""

    def create_canonical_projects(
        self,
        cluster_groups: Dict[str, List[DocumentProjectInfo]]
    ) -> Dict[str, CanonicalProject]:
        """
        Create canonical projects from clusters.

        Args:
            cluster_groups: Dict mapping cluster_id to documents

        Returns:
            Dict mapping project_id to CanonicalProject
        """
        print(f"\n{'='*60}")
        print("STEP 4: Creating Canonical Projects")
        print(f"{'='*60}")

        canonical_projects = {}

        for cluster_id, docs in cluster_groups.items():
            print(f"  Processing {cluster_id} ({len(docs)} docs)...")

            # Generate canonical name
            name, description = self.generate_canonical_name(docs)

            # Collect all unique data
            team_members = set()
            doc_ids = []
            topics = set()
            merged_names = set()
            dates = []
            client = None

            for doc in docs:
                doc_ids.append(doc.doc_id)
                merged_names.add(doc.project_name)
                topics.update(doc.key_topics)
                team_members.update(doc.people_mentioned)

                if doc.client_name:
                    client = doc.client_name

                # Extract dates from metadata
                if 'timestamp' in doc.raw_metadata:
                    dates.append(doc.raw_metadata['timestamp'])
                elif 'date' in doc.raw_metadata:
                    dates.append(doc.raw_metadata['date'])

            # Determine date range
            date_range = None
            if dates:
                dates_sorted = sorted(dates)
                date_range = (dates_sorted[0], dates_sorted[-1])

            # Create canonical project
            project_id = f"proj_{hashlib.md5(name.encode()).hexdigest()[:8]}"

            canonical = CanonicalProject(
                id=project_id,
                name=name,
                description=description,
                client=client,
                team_members=list(team_members),
                document_ids=doc_ids,
                date_range=date_range,
                status="active",
                key_topics=list(topics)[:10],
                merged_from=list(merged_names),
                confidence=sum(d.confidence for d in docs) / len(docs),
                document_count=len(docs)
            )

            canonical_projects[project_id] = canonical
            self.canonical_projects[project_id] = canonical

            print(f"    ✓ Created: '{name}' ({len(docs)} docs)")

        print(f"\n✓ Created {len(canonical_projects)} canonical projects")
        return canonical_projects

    # =========================================================================
    # Step 5: Cross-Employee Project Merging
    # =========================================================================

    def merge_similar_projects(
        self,
        projects: Dict[str, CanonicalProject],
        similarity_threshold: float = 0.85
    ) -> Dict[str, CanonicalProject]:
        """
        Merge projects that are the same but from different employees.

        Args:
            projects: Dict of canonical projects
            similarity_threshold: Similarity threshold for merging

        Returns:
            Dict of merged projects
        """
        print(f"\n{'='*60}")
        print("STEP 5: Cross-Employee Project Merging")
        print(f"{'='*60}")

        if len(projects) < 2:
            print("⚠ Not enough projects to merge")
            return projects

        # Embed project names + descriptions
        model = self._get_embedding_model()

        project_list = list(projects.values())
        texts = [f"{p.name}. {p.description}" for p in project_list]

        print(f"  Computing similarities for {len(texts)} projects...")
        embeddings = model.encode(texts, show_progress_bar=False)

        # Compute pairwise similarity
        similarity_matrix = cosine_similarity(embeddings)

        # Find pairs to merge
        merged = set()
        merge_groups = []

        for i in range(len(project_list)):
            if i in merged:
                continue

            group = [i]
            for j in range(i + 1, len(project_list)):
                if j in merged:
                    continue
                if similarity_matrix[i][j] >= similarity_threshold:
                    group.append(j)
                    merged.add(j)

            merge_groups.append(group)
            merged.add(i)

        # Create merged projects
        final_projects = {}

        for group in merge_groups:
            if len(group) == 1:
                # No merge needed
                proj = project_list[group[0]]
                final_projects[proj.id] = proj
            else:
                # Merge projects
                projects_to_merge = [project_list[i] for i in group]

                print(f"  Merging {len(projects_to_merge)} similar projects:")
                for p in projects_to_merge:
                    print(f"    - {p.name}")

                # Use the one with most documents as base
                base = max(projects_to_merge, key=lambda p: p.document_count)

                # Merge data
                all_doc_ids = []
                all_team_members = set()
                all_topics = set()
                all_merged_from = set()

                for p in projects_to_merge:
                    all_doc_ids.extend(p.document_ids)
                    all_team_members.update(p.team_members)
                    all_topics.update(p.key_topics)
                    all_merged_from.update(p.merged_from)

                merged_project = CanonicalProject(
                    id=base.id,
                    name=base.name,
                    description=base.description,
                    client=base.client,
                    team_members=list(all_team_members),
                    document_ids=all_doc_ids,
                    date_range=base.date_range,
                    status=base.status,
                    key_topics=list(all_topics)[:10],
                    merged_from=list(all_merged_from),
                    confidence=base.confidence,
                    document_count=len(all_doc_ids)
                )

                final_projects[merged_project.id] = merged_project
                print(f"    → Merged into: '{merged_project.name}' ({merged_project.document_count} docs)")

        print(f"\n✓ Final project count: {len(final_projects)} (from {len(projects)})")
        return final_projects

    # =========================================================================
    # Main Pipeline
    # =========================================================================

    def process_documents(
        self,
        documents: List[Dict],
        min_confidence: float = 0.3,
        min_cluster_size: int = 2,
        merge_threshold: float = 0.85
    ) -> Dict[str, CanonicalProject]:
        """
        Run the complete intelligent clustering pipeline.

        Args:
            documents: List of document dicts
            min_confidence: Minimum confidence for quality filter
            min_cluster_size: Minimum docs for a cluster
            merge_threshold: Similarity threshold for merging

        Returns:
            Dict of canonical projects
        """
        print("\n" + "="*70)
        print("INTELLIGENT PROJECT CLUSTERING PIPELINE")
        print("="*70)
        print(f"Input: {len(documents)} documents")
        print(f"Settings: min_confidence={min_confidence}, min_cluster={min_cluster_size}, merge={merge_threshold}")
        print("="*70)

        # Step 1: Extract project info from all documents
        extractions = self.extract_all_documents(documents)

        # Step 2: Filter irrelevant documents
        relevant, filtered = self.filter_irrelevant_documents(extractions, min_confidence)

        if not relevant:
            print("⚠ No relevant documents after filtering!")
            return {}

        # Step 3: Deduplicate projects with semantic clustering
        cluster_groups = self.deduplicate_projects(relevant, min_cluster_size)

        # Step 4: Create canonical projects
        canonical = self.create_canonical_projects(cluster_groups)

        # Step 5: Merge similar projects across employees
        final_projects = self.merge_similar_projects(canonical, merge_threshold)

        # Final summary
        print("\n" + "="*70)
        print("PIPELINE COMPLETE")
        print("="*70)
        print(f"Input documents: {len(documents)}")
        print(f"Relevant documents: {len(relevant)}")
        print(f"Filtered out: {len(filtered)}")
        print(f"Final projects: {len(final_projects)}")
        print("="*70)

        # Store results
        self.canonical_projects = final_projects

        return final_projects

    def save_results(self, output_dir: str):
        """Save all results to files"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save canonical projects
        projects_file = output_path / "canonical_projects.json"
        projects_data = {
            pid: asdict(proj)
            for pid, proj in self.canonical_projects.items()
        }
        with open(projects_file, 'w') as f:
            json.dump(projects_data, f, indent=2, default=str)
        print(f"✓ Saved projects to {projects_file}")

        # Save document extractions
        extractions_file = output_path / "document_extractions.json"
        extractions_data = {
            doc_id: asdict(info)
            for doc_id, info in self.document_extractions.items()
        }
        with open(extractions_file, 'w') as f:
            json.dump(extractions_data, f, indent=2, default=str)
        print(f"✓ Saved extractions to {extractions_file}")

        # Save summary
        summary_file = output_path / "clustering_summary.json"
        summary = {
            "total_documents": len(self.document_extractions),
            "total_projects": len(self.canonical_projects),
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "document_count": p.document_count,
                    "team_size": len(p.team_members)
                }
                for p in self.canonical_projects.values()
            ]
        }
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"✓ Saved summary to {summary_file}")

    def load_results(self, input_dir: str) -> bool:
        """Load previously saved results"""
        input_path = Path(input_dir)

        projects_file = input_path / "canonical_projects.json"
        if projects_file.exists():
            with open(projects_file, 'r') as f:
                data = json.load(f)

            self.canonical_projects = {}
            for pid, proj_data in data.items():
                self.canonical_projects[pid] = CanonicalProject(**proj_data)

            print(f"✓ Loaded {len(self.canonical_projects)} projects from {projects_file}")
            return True

        return False


# Utility function for easy use
def run_intelligent_clustering(
    documents: List[Dict],
    output_dir: str = None,
    **kwargs
) -> Dict[str, CanonicalProject]:
    """
    Run intelligent clustering on a list of documents.

    Args:
        documents: List of document dicts with 'content' and 'metadata'
        output_dir: Optional directory to save results
        **kwargs: Additional arguments for IntelligentProjectClusterer.process_documents

    Returns:
        Dict of canonical projects
    """
    clusterer = IntelligentProjectClusterer()
    projects = clusterer.process_documents(documents, **kwargs)

    if output_dir:
        clusterer.save_results(output_dir)

    return projects


if __name__ == "__main__":
    # Test with sample data
    sample_docs = [
        {
            "doc_id": "doc1",
            "content": "Meeting notes for Nike Q4 marketing campaign. Discussed social media strategy and influencer partnerships.",
            "metadata": {"subject": "Nike Campaign Meeting", "employee": "john@company.com"}
        },
        {
            "doc_id": "doc2",
            "content": "Nike marketing budget review. Q4 spend on digital ads performing well.",
            "metadata": {"subject": "Budget Review - Nike", "employee": "jane@company.com"}
        },
        {
            "doc_id": "doc3",
            "content": "Healthcare dashboard development sprint planning. Need to implement patient data visualization.",
            "metadata": {"subject": "Sprint Planning - Healthcare", "employee": "john@company.com"}
        }
    ]

    projects = run_intelligent_clustering(
        sample_docs,
        output_dir="./test_output",
        min_cluster_size=1
    )

    print("\nFinal Projects:")
    for pid, proj in projects.items():
        print(f"  - {proj.name}: {proj.document_count} docs")
