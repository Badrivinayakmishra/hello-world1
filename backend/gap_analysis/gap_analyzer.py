import os
"""
Gap Analysis Engine
Analyzes clustered data to identify missing information and knowledge gaps
"""

import json
from pathlib import Path
from typing import Dict, List, Set
from openai import AzureOpenAI
from collections import defaultdict
import re

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"



class GapAnalyzer:
    """Analyze projects for knowledge gaps and missing information"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize gap analyzer

        Args:
            api_key: OpenAI API key
            model: Model to use for analysis
        """
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        self.model = model
        self.gap_results = {}

    def analyze_project_gaps(self, project_data: Dict) -> Dict:
        """
        Analyze a single project for knowledge gaps

        Args:
            project_data: Dictionary containing project documents and metadata

        Returns:
            Dictionary with gap analysis results
        """
        project_name = project_data.get('project_name', 'Unknown')
        documents = project_data.get('documents', [])

        if not documents:
            return {
                'project_name': project_name,
                'gaps': [],
                'missing_elements': [],
                'questions': []
            }

        print(f"Analyzing gaps for project: {project_name}")

        # Prepare project summary
        project_summary = self._create_project_summary(documents)

        # Identify gaps using LLM
        gaps = self._identify_gaps_with_llm(project_name, project_summary, documents)

        return gaps

    def _create_project_summary(self, documents: List[Dict]) -> Dict:
        """Create a summary of project documents"""
        summary = {
            'total_documents': len(documents),
            'subjects': [],
            'keywords': set(),
            'mentioned_people': set(),
            'mentioned_projects': set(),
            'date_range': {'earliest': None, 'latest': None},
            'document_types': defaultdict(int),
        }

        timestamps = []

        for doc in documents:
            metadata = doc['metadata']

            # Collect subjects (or group names for chat data)
            subject = metadata.get('subject', metadata.get('group', ''))
            if subject:
                summary['subjects'].append(subject)

            # Collect timestamps
            timestamp = metadata.get('timestamp')
            if timestamp:
                timestamps.append(timestamp)

            # Analyze content for patterns
            content = doc.get('content', '')

            # Find mentioned people (simple heuristic)
            people_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
            people = re.findall(people_pattern, content[:500])  # Check first 500 chars
            summary['mentioned_people'].update(people[:5])  # Limit to 5

            # Classify document type based on content
            doc_type = self._classify_document_type(subject, content)
            summary['document_types'][doc_type] += 1

        # Set date range
        if timestamps:
            summary['date_range'] = {
                'earliest': min(timestamps),
                'latest': max(timestamps)
            }

        # Get top subjects
        summary['subjects'] = summary['subjects'][:20]
        summary['mentioned_people'] = list(summary['mentioned_people'])

        return summary

    def _classify_document_type(self, subject: str, content: str) -> str:
        """Classify document type based on content patterns"""
        subject_lower = subject.lower()
        content_lower = content.lower()

        # Decision documents
        if any(word in subject_lower or word in content_lower[:200]
               for word in ['decision', 'decided', 'approve', 'approval']):
            return 'decision'

        # Meeting documents
        if any(word in subject_lower
               for word in ['meeting', 'agenda', 'minutes', 'call']):
            return 'meeting'

        # Technical documents
        if any(word in subject_lower or word in content_lower[:200]
               for word in ['spec', 'technical', 'architecture', 'design', 'implementation']):
            return 'technical'

        # Status updates
        if any(word in subject_lower
               for word in ['status', 'update', 'progress', 'report']):
            return 'status_update'

        # Questions
        if '?' in subject or content[:100].count('?') > 2:
            return 'question'

        return 'general'

    def _identify_gaps_with_llm(
        self,
        project_name: str,
        summary: Dict,
        documents: List[Dict]
    ) -> Dict:
        """Use LLM to identify knowledge gaps"""

        # Create analysis prompt
        prompt = self._create_gap_analysis_prompt(project_name, summary, documents)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert knowledge management analyst. You identify gaps in project documentation and generate insightful questions to fill those gaps."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=1500,
            )

            result_text = response.choices[0].message.content.strip()
            gaps = self._parse_gap_analysis(result_text, project_name)

            return gaps

        except Exception as e:
            print(f"Error analyzing gaps: {e}")
            return {
                'project_name': project_name,
                'gaps': [],
                'missing_elements': [],
                'questions': []
            }

    def _create_gap_analysis_prompt(
        self,
        project_name: str,
        summary: Dict,
        documents: List[Dict]
    ) -> str:
        """Create prompt for gap analysis"""

        # Sample document subjects and content
        sample_subjects = '\n'.join(f"- {s}" for s in summary['subjects'][:10])

        # Document type breakdown
        doc_types = '\n'.join(
            f"- {dtype}: {count}"
            for dtype, count in summary['document_types'].items()
        )

        # Sample content snippets
        content_samples = []
        for doc in documents[:3]:
            content = doc.get('content', '')[:200]
            subject = doc['metadata'].get('subject', doc['metadata'].get('group', 'No subject'))
            content_samples.append(f"Subject/Group: {subject}\nContent: {content}...")

        content_preview = '\n\n'.join(content_samples)

        prompt = f"""Analyze the following project documentation for knowledge gaps and missing information.

Project: {project_name}

Summary:
- Total documents: {summary['total_documents']}
- Date range: {summary['date_range']['earliest']} to {summary['date_range']['latest']}

Document Types:
{doc_types}

Sample Subjects:
{sample_subjects}

Sample Content:
{content_preview}

Based on this documentation, identify:

1. MISSING_DOCUMENT_TYPES: What types of documents would you expect but are missing? (e.g., technical specs, decision records, meeting notes, handoff documentation)

2. KNOWLEDGE_GAPS: What critical information appears to be missing or incomplete?

3. CONTEXT_GAPS: What background context or decisions are referenced but not explained?

4. QUESTIONS: Generate 5-10 specific questions that an employee should answer to fill these gaps. These questions should:
   - Be specific and actionable
   - Target the most critical missing information
   - Help reconstruct project context and decisions
   - Capture tacit knowledge not in documents

Provide your response in the following JSON format:
{{
    "missing_document_types": ["type1", "type2", ...],
    "knowledge_gaps": ["gap1", "gap2", ...],
    "context_gaps": ["gap1", "gap2", ...],
    "questions": [
        {{
            "question": "...",
            "category": "decision|technical|context|process",
            "priority": "high|medium|low",
            "reasoning": "why this question is important"
        }},
        ...
    ]
}}"""

        return prompt

    def _parse_gap_analysis(self, result_text: str, project_name: str) -> Dict:
        """Parse LLM gap analysis response"""
        try:
            # Extract JSON from response
            if '{' in result_text and '}' in result_text:
                start = result_text.index('{')
                end = result_text.rindex('}') + 1
                json_str = result_text[start:end]
                result = json.loads(json_str)

                return {
                    'project_name': project_name,
                    'missing_document_types': result.get('missing_document_types', []),
                    'knowledge_gaps': result.get('knowledge_gaps', []),
                    'context_gaps': result.get('context_gaps', []),
                    'questions': result.get('questions', []),
                }
        except Exception as e:
            print(f"Error parsing gap analysis: {e}")

        return {
            'project_name': project_name,
            'gaps': [],
            'missing_elements': [],
            'questions': []
        }

    def analyze_all_projects(
        self,
        project_clusters_dir: str,
        output_dir: str
    ) -> Dict:
        """
        Analyze all projects for gaps

        Args:
            project_clusters_dir: Directory with project clusters
            output_dir: Directory to save gap analysis results

        Returns:
            Dictionary with all gap analyses
        """
        project_dir = Path(project_clusters_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        all_gaps = {}

        # Iterate through employee directories
        for employee_dir in project_dir.iterdir():
            if not employee_dir.is_dir():
                continue

            employee = employee_dir.name
            print(f"\nAnalyzing projects for {employee}...")

            employee_gaps = {}

            # Load metadata
            metadata_file = employee_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                # Analyze each project
                for project_name in metadata.get('projects', {}).keys():
                    project_file = employee_dir / f"{project_name}.jsonl"

                    if project_file.exists():
                        # Load project documents
                        documents = []
                        with open(project_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                documents.append(json.loads(line))

                        # Analyze gaps
                        project_data = {
                            'project_name': project_name,
                            'documents': documents
                        }

                        gaps = self.analyze_project_gaps(project_data)
                        employee_gaps[project_name] = gaps

            all_gaps[employee] = employee_gaps

            # Save employee gap analysis
            self._save_employee_gaps(employee, employee_gaps, output_path)

        # Save overall summary
        self._save_gap_summary(all_gaps, output_path)

        print(f"\n✓ Completed gap analysis for all projects")
        return all_gaps

    def _save_employee_gaps(self, employee: str, gaps: Dict, output_dir: Path):
        """Save gap analysis for an employee"""
        employee_file = output_dir / f"{employee}_gaps.json"

        with open(employee_file, 'w', encoding='utf-8') as f:
            json.dump(gaps, f, indent=2, ensure_ascii=False)

        print(f"  ✓ Saved gap analysis for {employee}")

    def _save_gap_summary(self, all_gaps: Dict, output_dir: Path):
        """Save overall gap analysis summary"""
        summary = {
            'total_employees': len(all_gaps),
            'total_projects_analyzed': sum(len(gaps) for gaps in all_gaps.values()),
            'employees': {}
        }

        for employee, projects in all_gaps.items():
            total_questions = sum(
                len(project.get('questions', []))
                for project in projects.values()
            )

            summary['employees'][employee] = {
                'projects_analyzed': len(projects),
                'total_questions_generated': total_questions,
            }

        summary_file = output_dir / "gap_analysis_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved gap analysis summary to {summary_file}")


if __name__ == "__main__":
    from config.config import Config

    analyzer = GapAnalyzer(api_key=Config.OPENAI_API_KEY)

    results = analyzer.analyze_all_projects(
        project_clusters_dir=str(Config.DATA_DIR / "project_clusters"),
        output_dir=str(Config.OUTPUT_DIR / "gap_analysis")
    )
