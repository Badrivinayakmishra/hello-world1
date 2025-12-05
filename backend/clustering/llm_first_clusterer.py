"""
LLM-First Project Clustering - Maximum Accuracy
================================================
Pure content-based clustering with zero metadata dependency.
Uses LLM for understanding, graph for natural grouping.

Pipeline:
1. LLM extracts rich project signatures from content only
2. LLM pairwise comparison (with embedding pre-filter for speed)
3. Graph-based community detection (Louvain algorithm)
4. LLM cluster validation and naming
5. LLM cross-cluster merge detection
"""

import json
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import numpy as np
from collections import defaultdict
import pickle
import warnings
warnings.filterwarnings('ignore')

from openai import AzureOpenAI
from sentence_transformers import SentenceTransformer
import networkx as nx
from networkx.algorithms import community

# Load environment
from dotenv import load_dotenv

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"

load_dotenv()


@dataclass
class ProjectSignature:
    """Rich project signature extracted from content"""
    doc_id: str
    core_deliverable: str  # What is being built/delivered
    project_goal: str  # Why this exists
    key_entities: List[str]  # Companies, products, systems
    technical_keywords: List[str]  # Tech stack, methodologies
    timeline_phase: str  # planning, development, deployment, completed
    unique_identifiers: List[str]  # Project codes, names, acronyms
    content_summary: str  # Brief content summary
    confidence: float = 0.0
    is_project_work: bool = True


@dataclass
class ProjectCluster:
    """A cluster of documents forming one project"""
    id: str
    name: str
    description: str
    document_ids: List[str]
    signatures: List[ProjectSignature]
    confidence: float = 0.0
    validation_status: str = "pending"  # pending, validated, split_required


class LLMFirstClusterer:
    """
    Maximum accuracy project clustering using LLM-first approach.
    Ignores all metadata, uses only content.
    """

    def __init__(
        self,
        openai_api_key: str = None,
        embedding_model: str = "all-mpnet-base-v2",
        cache_dir: str = None
    ):
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        self.embedding_model_name = embedding_model
        self.embedding_model = None  # Lazy load

        # Cache setup
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).parent.parent / "club_data" / "llm_cluster_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Storage
        self.signatures: Dict[str, ProjectSignature] = {}
        self.similarity_matrix: Optional[np.ndarray] = None
        self.clusters: Dict[str, ProjectCluster] = {}

        print("✓ LLM-First Clusterer initialized (high-accuracy mode)")

    def _get_embedding_model(self):
        """Lazy load embedding model"""
        if self.embedding_model is None:
            print(f"Loading embedding model: {self.embedding_model_name}...")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
        return self.embedding_model

    def _get_cache_key(self, content: str, operation: str) -> str:
        """Generate cache key"""
        content_hash = hashlib.md5(content[:1000].encode()).hexdigest()
        return f"{operation}_{content_hash}"

    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Load from cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                return json.load(f)
        return None

    def _save_to_cache(self, cache_key: str, data: Dict):
        """Save to cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # Phase 1: Deep Document Understanding
    # =========================================================================

    def extract_project_signature(self, document: Dict) -> ProjectSignature:
        """
        Extract rich project signature from document content ONLY.
        Zero metadata dependency.

        Args:
            document: Dict with 'content' and 'doc_id'

        Returns:
            ProjectSignature with deep project understanding
        """
        content = document.get('content', '')
        doc_id = document.get('doc_id', 'unknown')

        # Check cache
        cache_key = self._get_cache_key(content, "signature")
        cached = self._load_from_cache(cache_key)
        if cached:
            try:
                return ProjectSignature(doc_id=doc_id, **cached)
            except TypeError as e:
                # Cache corrupted or old format, regenerate
                print(f"Cache miss (format error): {e}")
                pass  # Continue to regenerate

        # Truncate content for LLM (use first 8000 chars)
        content_sample = content[:8000]

        prompt = f"""Analyze this document content and extract project information. IGNORE any metadata - use ONLY the content below.

CONTENT:
{content_sample}

Extract the following (respond in JSON):
{{
  "is_project_work": true/false,  // Is this actual project work (not spam/personal/system)?
  "core_deliverable": "What specific thing is being built/delivered/produced?",
  "project_goal": "Why does this project exist? What problem does it solve?",
  "key_entities": ["Company names", "Product names", "System names"],
  "technical_keywords": ["Technologies", "methodologies", "tools mentioned"],
  "timeline_phase": "planning|development|deployment|completed|ongoing",
  "unique_identifiers": ["Project codes", "specific names", "acronyms"],
  "content_summary": "2-3 sentence summary of this document",
  "confidence": 0.0-1.0  // How confident are you this is project work?
}}

If this is NOT project work (spam, personal email, system notification), set is_project_work=false.
Focus on CONCRETE deliverables, not vague mentions of work."""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # Cache result
            self._save_to_cache(cache_key, result)

            return ProjectSignature(
                doc_id=doc_id,
                core_deliverable=result.get('core_deliverable', ''),
                project_goal=result.get('project_goal', ''),
                key_entities=result.get('key_entities', []),
                technical_keywords=result.get('technical_keywords', []),
                timeline_phase=result.get('timeline_phase', 'unknown'),
                unique_identifiers=result.get('unique_identifiers', []),
                content_summary=result.get('content_summary', ''),
                confidence=result.get('confidence', 0.0),
                is_project_work=result.get('is_project_work', True)
            )

        except Exception as e:
            print(f"⚠ Extraction failed for {doc_id}: {e}")
            return ProjectSignature(
                doc_id=doc_id,
                core_deliverable="Unknown",
                project_goal="Unknown",
                confidence=0.0,
                is_project_work=False
            )

    def extract_all_signatures(
        self,
        documents: List[Dict],
        batch_size: int = 10
    ) -> List[ProjectSignature]:
        """Extract signatures from all documents"""
        print(f"\n{'='*70}")
        print("PHASE 1: Deep Document Understanding (Content Only)")
        print(f"{'='*70}")
        print(f"Processing {len(documents)} documents...")

        signatures = []
        for i, doc in enumerate(documents):
            if (i + 1) % batch_size == 0:
                print(f"  Processed {i + 1}/{len(documents)} documents...")

            sig = self.extract_project_signature(doc)
            signatures.append(sig)
            self.signatures[sig.doc_id] = sig

        # Filter out non-project work
        project_sigs = [s for s in signatures if s.is_project_work and s.confidence >= 0.3]

        print(f"✓ Extracted {len(signatures)} signatures")
        print(f"  - Project work: {len(project_sigs)}")
        print(f"  - Filtered out: {len(signatures) - len(project_sigs)}")

        return project_sigs

    # =========================================================================
    # Phase 2: Pairwise LLM Comparison with Embedding Pre-filter
    # =========================================================================

    def compare_documents_llm(
        self,
        sig1: ProjectSignature,
        sig2: ProjectSignature
    ) -> Tuple[str, float, str]:
        """
        Use LLM to determine if two documents are part of same project.

        Returns:
            Tuple of (decision, confidence, reasoning)
            decision: "YES" | "NO" | "MAYBE"
        """
        # Create cache key from both signatures
        content_key = f"{sig1.doc_id}_{sig2.doc_id}"
        cache_key = self._get_cache_key(content_key, "comparison")
        cached = self._load_from_cache(cache_key)
        if cached:
            return cached['decision'], cached['confidence'], cached['reasoning']

        prompt = f"""Are these two documents part of the SAME project?

DOCUMENT 1:
- Deliverable: {sig1.core_deliverable}
- Goal: {sig1.project_goal}
- Entities: {', '.join(sig1.key_entities)}
- Keywords: {', '.join(sig1.technical_keywords)}
- Identifiers: {', '.join(sig1.unique_identifiers)}
- Phase: {sig1.timeline_phase}
- Summary: {sig1.content_summary}

DOCUMENT 2:
- Deliverable: {sig2.core_deliverable}
- Goal: {sig2.project_goal}
- Entities: {', '.join(sig2.key_entities)}
- Keywords: {', '.join(sig2.technical_keywords)}
- Identifiers: {', '.join(sig2.unique_identifiers)}
- Phase: {sig2.timeline_phase}
- Summary: {sig2.content_summary}

Consider:
- Same core deliverable? (even if worded differently)
- Same entities/client/stakeholder?
- Shared unique identifiers (project codes, names)?
- Compatible timeline phases?
- Same ultimate goal?

Respond in JSON:
{{
  "decision": "YES|NO|MAYBE",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your decision"
}}

Be conservative with YES (high recall). Only say NO if clearly different projects."""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,  # Fast for comparisons
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # Cache result
            self._save_to_cache(cache_key, result)

            return (
                result.get('decision', 'MAYBE'),
                result.get('confidence', 0.5),
                result.get('reasoning', '')
            )

        except Exception as e:
            print(f"⚠ Comparison failed: {e}")
            return "MAYBE", 0.5, "Comparison error"

    def build_similarity_graph(
        self,
        signatures: List[ProjectSignature],
        embedding_threshold: float = 0.6,
        llm_threshold: float = 0.5
    ) -> nx.Graph:
        """
        Build graph where edges connect documents in same project.
        Uses embedding pre-filter + LLM comparison.

        Args:
            signatures: List of project signatures
            embedding_threshold: Min embedding similarity to do LLM comparison
            llm_threshold: Min LLM confidence to add edge

        Returns:
            NetworkX graph
        """
        print(f"\n{'='*70}")
        print("PHASE 2: Pairwise Similarity Analysis")
        print(f"{'='*70}")
        print(f"Building similarity graph for {len(signatures)} documents...")

        # Create embeddings for pre-filtering
        model = self._get_embedding_model()
        texts = [
            f"{s.core_deliverable}. {s.project_goal}. {' '.join(s.key_entities)}"
            for s in signatures
        ]
        print("  Computing embeddings...")
        embeddings = model.encode(texts, show_progress_bar=False)

        # Compute embedding similarities
        print("  Computing embedding similarities...")
        from sklearn.metrics.pairwise import cosine_similarity
        embedding_sim = cosine_similarity(embeddings)

        # Build graph
        G = nx.Graph()
        for i, sig in enumerate(signatures):
            G.add_node(sig.doc_id, signature=sig)

        # Only do LLM comparison for pairs above embedding threshold
        total_pairs = len(signatures) * (len(signatures) - 1) // 2
        candidate_pairs = 0
        llm_comparisons = 0
        edges_added = 0

        print(f"  Total possible pairs: {total_pairs}")
        print(f"  Filtering with embedding threshold: {embedding_threshold}")

        for i in range(len(signatures)):
            for j in range(i + 1, len(signatures)):
                candidate_pairs += 1

                # Pre-filter with embeddings
                if embedding_sim[i][j] < embedding_threshold:
                    continue

                # Do LLM comparison
                llm_comparisons += 1
                if llm_comparisons % 50 == 0:
                    print(f"    LLM comparisons: {llm_comparisons}...")

                decision, confidence, reasoning = self.compare_documents_llm(
                    signatures[i],
                    signatures[j]
                )

                # Add edge based on decision
                edge_weight = 0.0
                if decision == "YES":
                    edge_weight = confidence
                elif decision == "MAYBE":
                    edge_weight = confidence * 0.5

                if edge_weight >= llm_threshold:
                    G.add_edge(
                        signatures[i].doc_id,
                        signatures[j].doc_id,
                        weight=edge_weight,
                        decision=decision,
                        reasoning=reasoning
                    )
                    edges_added += 1

        print(f"✓ Graph built")
        print(f"  - Candidate pairs (embedding > {embedding_threshold}): {llm_comparisons}")
        print(f"  - LLM comparisons performed: {llm_comparisons}")
        print(f"  - Edges added: {edges_added}")
        print(f"  - Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

        return G

    # =========================================================================
    # Phase 3: Graph-Based Community Detection
    # =========================================================================

    def detect_project_communities(self, G: nx.Graph) -> Dict[str, List[str]]:
        """
        Use Louvain community detection to find natural project clusters.

        Args:
            G: Similarity graph

        Returns:
            Dict mapping cluster_id to list of doc_ids
        """
        print(f"\n{'='*70}")
        print("PHASE 3: Graph-Based Community Detection")
        print(f"{'='*70}")

        if G.number_of_edges() == 0:
            print("⚠ No edges in graph - each document is its own project")
            return {f"cluster_{i}": [node] for i, node in enumerate(G.nodes())}

        # Run Louvain community detection
        print("  Running Louvain algorithm...")
        communities_generator = community.louvain_communities(G, seed=42)
        communities_list = list(communities_generator)

        # Convert to dict
        clusters = {}
        for i, comm in enumerate(communities_list):
            cluster_id = f"cluster_{i}"
            clusters[cluster_id] = list(comm)

        print(f"✓ Detected {len(clusters)} project communities")

        # Show cluster sizes
        sizes = [len(docs) for docs in clusters.values()]
        print(f"  - Cluster size distribution:")
        print(f"    - Min: {min(sizes)}, Max: {max(sizes)}, Mean: {np.mean(sizes):.1f}")
        print(f"    - Singleton clusters: {sum(1 for s in sizes if s == 1)}")

        return clusters

    # =========================================================================
    # Phase 4: Cluster Validation & Naming
    # =========================================================================

    def validate_and_name_cluster(
        self,
        cluster_id: str,
        doc_ids: List[str]
    ) -> ProjectCluster:
        """
        Validate cluster coherence and generate canonical name.

        Args:
            cluster_id: Cluster ID
            doc_ids: Document IDs in cluster

        Returns:
            ProjectCluster with validation results
        """
        signatures = [self.signatures[doc_id] for doc_id in doc_ids]

        # Single document cluster - no validation needed
        if len(signatures) == 1:
            sig = signatures[0]
            return ProjectCluster(
                id=cluster_id,
                name=sig.core_deliverable or "Unknown Project",
                description=sig.project_goal or sig.content_summary,
                document_ids=doc_ids,
                signatures=signatures,
                confidence=sig.confidence,
                validation_status="validated"
            )

        # Multi-document cluster - validate coherence
        summaries = []
        for sig in signatures[:10]:  # Use up to 10 docs for validation
            summaries.append({
                'deliverable': sig.core_deliverable,
                'goal': sig.project_goal,
                'entities': sig.key_entities,
                'identifiers': sig.unique_identifiers,
                'summary': sig.content_summary[:200]
            })

        prompt = f"""These {len(signatures)} documents were grouped as ONE project. Validate this clustering.

DOCUMENT SUMMARIES:
{json.dumps(summaries, indent=2)}

Analyze:
1. Are these all part of the SAME project?
2. Or are there multiple distinct projects here?
3. What is the canonical project name?

Respond in JSON:
{{
  "is_coherent": true/false,
  "should_split": true/false,
  "canonical_name": "Meaningful project name",
  "description": "1-2 sentence project description",
  "confidence": 0.0-1.0,
  "reasoning": "Why these belong together or should split"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            status = "validated" if result.get('is_coherent', True) else "split_required"

            return ProjectCluster(
                id=cluster_id,
                name=result.get('canonical_name', 'Unknown Project'),
                description=result.get('description', ''),
                document_ids=doc_ids,
                signatures=signatures,
                confidence=result.get('confidence', 0.7),
                validation_status=status
            )

        except Exception as e:
            print(f"⚠ Validation failed for {cluster_id}: {e}")
            # Fallback: use most common deliverable
            deliverables = [s.core_deliverable for s in signatures if s.core_deliverable]
            name = deliverables[0] if deliverables else "Unknown Project"

            return ProjectCluster(
                id=cluster_id,
                name=name,
                description="Validation failed",
                document_ids=doc_ids,
                signatures=signatures,
                confidence=0.5,
                validation_status="pending"
            )

    def validate_all_clusters(
        self,
        clusters: Dict[str, List[str]]
    ) -> Dict[str, ProjectCluster]:
        """Validate and name all clusters"""
        print(f"\n{'='*70}")
        print("PHASE 4: Cluster Validation & Naming")
        print(f"{'='*70}")

        validated = {}
        for cluster_id, doc_ids in clusters.items():
            project = self.validate_and_name_cluster(cluster_id, doc_ids)
            validated[cluster_id] = project
            self.clusters[cluster_id] = project

        # Show validation stats
        coherent = sum(1 for p in validated.values() if p.validation_status == "validated")
        needs_split = sum(1 for p in validated.values() if p.validation_status == "split_required")

        print(f"✓ Validated {len(validated)} clusters")
        print(f"  - Coherent clusters: {coherent}")
        print(f"  - Needs splitting: {needs_split}")

        return validated

    # =========================================================================
    # Phase 5: Cross-Cluster Merge Detection
    # =========================================================================

    def detect_cluster_merges(
        self,
        clusters: Dict[str, ProjectCluster],
        merge_threshold: float = 0.85
    ) -> List[Tuple[str, str, float]]:
        """
        Detect if any clusters should be merged.

        Returns:
            List of (cluster_id1, cluster_id2, confidence) tuples to merge
        """
        print(f"\n{'='*70}")
        print("PHASE 5: Cross-Cluster Merge Detection")
        print(f"{'='*70}")

        cluster_ids = list(clusters.keys())
        merges = []

        print(f"  Comparing {len(cluster_ids)} clusters...")

        for i in range(len(cluster_ids)):
            for j in range(i + 1, len(cluster_ids)):
                c1 = clusters[cluster_ids[i]]
                c2 = clusters[cluster_ids[j]]

                # Ask LLM if these should merge
                prompt = f"""Are these two detected projects actually the SAME project?

PROJECT A: {c1.name}
Description: {c1.description}
Documents: {len(c1.document_ids)}
Key entities: {set([e for s in c1.signatures for e in s.key_entities])}

PROJECT B: {c2.name}
Description: {c2.description}
Documents: {len(c2.document_ids)}
Key entities: {set([e for s in c2.signatures for e in s.key_entities])}

Respond in JSON:
{{
  "should_merge": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Why they should/shouldn't merge"
}}"""

                try:
                    response = self.client.chat.completions.create(
                        model=AZURE_CHAT_DEPLOYMENT,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        response_format={"type": "json_object"}
                    )

                    result = json.loads(response.choices[0].message.content)

                    if result.get('should_merge', False):
                        confidence = result.get('confidence', 0.0)
                        if confidence >= merge_threshold:
                            merges.append((cluster_ids[i], cluster_ids[j], confidence))
                            print(f"  ✓ Merge detected: {c1.name} ← {c2.name} ({confidence:.2f})")

                except Exception as e:
                    print(f"⚠ Merge comparison failed: {e}")
                    continue

        print(f"✓ Detected {len(merges)} potential merges")

        return merges

    def merge_clusters(
        self,
        clusters: Dict[str, ProjectCluster],
        merges: List[Tuple[str, str, float]]
    ) -> Dict[str, ProjectCluster]:
        """Execute cluster merges"""
        if not merges:
            return clusters

        print(f"\n  Executing {len(merges)} merges...")

        # Build merge groups using union-find
        parent = {}

        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Apply all merges
        for c1, c2, _ in merges:
            union(c1, c2)

        # Group by parent
        merge_groups = defaultdict(list)
        for cluster_id in clusters.keys():
            root = find(cluster_id)
            merge_groups[root].append(cluster_id)

        # Create merged clusters
        merged = {}
        for root, cluster_ids in merge_groups.items():
            if len(cluster_ids) == 1:
                # No merge needed
                merged[cluster_ids[0]] = clusters[cluster_ids[0]]
            else:
                # Merge multiple clusters
                all_docs = []
                all_sigs = []
                for cid in cluster_ids:
                    all_docs.extend(clusters[cid].document_ids)
                    all_sigs.extend(clusters[cid].signatures)

                # Use first cluster's name (or re-validate)
                primary = clusters[cluster_ids[0]]

                merged[root] = ProjectCluster(
                    id=root,
                    name=primary.name,
                    description=primary.description,
                    document_ids=all_docs,
                    signatures=all_sigs,
                    confidence=np.mean([clusters[c].confidence for c in cluster_ids]),
                    validation_status="validated"
                )

        print(f"✓ Merged {len(clusters)} → {len(merged)} final clusters")

        return merged

    # =========================================================================
    # Main Pipeline
    # =========================================================================

    def process_documents(
        self,
        documents: List[Dict],
        embedding_threshold: float = 0.6,
        llm_threshold: float = 0.5,
        merge_threshold: float = 0.85
    ) -> Dict[str, ProjectCluster]:
        """
        Complete high-accuracy clustering pipeline.

        Args:
            documents: List of dicts with 'content' and 'doc_id'
            embedding_threshold: Pre-filter threshold
            llm_threshold: Min confidence to connect documents
            merge_threshold: Min confidence to merge clusters

        Returns:
            Dict of cluster_id -> ProjectCluster
        """
        print("\n" + "="*70)
        print("LLM-FIRST HIGH-ACCURACY PROJECT CLUSTERING")
        print("="*70)

        # Phase 1: Extract signatures
        signatures = self.extract_all_signatures(documents)

        if len(signatures) == 0:
            print("⚠ No project work detected")
            return {}

        # Phase 2: Build similarity graph
        G = self.build_similarity_graph(
            signatures,
            embedding_threshold=embedding_threshold,
            llm_threshold=llm_threshold
        )

        # Phase 3: Detect communities
        clusters = self.detect_project_communities(G)

        # Phase 4: Validate and name
        validated_clusters = self.validate_all_clusters(clusters)

        # Phase 5: Detect and execute merges
        merges = self.detect_cluster_merges(validated_clusters, merge_threshold)
        final_clusters = self.merge_clusters(validated_clusters, merges)

        self.clusters = final_clusters

        print(f"\n{'='*70}")
        print(f"CLUSTERING COMPLETE - {len(final_clusters)} final projects")
        print(f"{'='*70}")

        return final_clusters

    def save_results(self, output_dir: str):
        """Save clustering results"""
        output_path = Path(output_dir)

        # Save signatures
        signatures_file = output_path / "project_signatures.json"
        with open(signatures_file, 'w') as f:
            json.dump(
                {k: asdict(v) for k, v in self.signatures.items()},
                f,
                indent=2
            )

        # Save clusters
        clusters_file = output_path / "canonical_projects.json"
        clusters_data = {}
        for cluster_id, cluster in self.clusters.items():
            clusters_data[cluster_id] = {
                'id': cluster.id,
                'name': cluster.name,
                'description': cluster.description,
                'document_ids': cluster.document_ids,
                'document_count': len(cluster.document_ids),
                'confidence': cluster.confidence,
                'validation_status': cluster.validation_status
            }

        with open(clusters_file, 'w') as f:
            json.dump(clusters_data, f, indent=2)

        print(f"\n✓ Results saved to {output_dir}")
        print(f"  - Signatures: {signatures_file}")
        print(f"  - Clusters: {clusters_file}")

    def get_project_summary(self) -> Dict:
        """Get summary statistics"""
        if not self.clusters:
            return {}

        sizes = [len(c.document_ids) for c in self.clusters.values()]

        return {
            'total_projects': len(self.clusters),
            'total_documents': sum(sizes),
            'avg_docs_per_project': np.mean(sizes),
            'largest_project': max(sizes),
            'singleton_projects': sum(1 for s in sizes if s == 1),
            'projects': [
                {
                    'name': c.name,
                    'doc_count': len(c.document_ids),
                    'confidence': c.confidence,
                    'status': c.validation_status
                }
                for c in sorted(self.clusters.values(), key=lambda x: len(x.document_ids), reverse=True)
            ]
        }
