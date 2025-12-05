import os
"""
Question Generation System
Generates targeted questions to extract tacit knowledge from employees
"""

import json
from pathlib import Path
from typing import Dict, List
from openai import AzureOpenAI

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"



class QuestionGenerator:
    """Generate intelligent questions to fill knowledge gaps"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize question generator

        Args:
            api_key: OpenAI API key
            model: Model to use
        """
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        self.model = model

    def generate_followup_questions(
        self,
        project_name: str,
        gap_analysis: Dict,
        max_questions: int = 10
    ) -> List[Dict]:
        """
        Generate follow-up questions based on gap analysis

        Args:
            project_name: Name of the project
            gap_analysis: Gap analysis results
            max_questions: Maximum number of questions to generate

        Returns:
            List of question dictionaries
        """
        print(f"Generating follow-up questions for {project_name}...")

        # Use existing questions from gap analysis as base
        existing_questions = gap_analysis.get('questions', [])

        if len(existing_questions) >= max_questions:
            return existing_questions[:max_questions]

        # Generate additional questions if needed
        additional_needed = max_questions - len(existing_questions)

        if additional_needed > 0:
            additional_questions = self._generate_additional_questions(
                project_name,
                gap_analysis,
                additional_needed
            )
            existing_questions.extend(additional_questions)

        return existing_questions[:max_questions]

    def _generate_additional_questions(
        self,
        project_name: str,
        gap_analysis: Dict,
        num_questions: int
    ) -> List[Dict]:
        """Generate additional targeted questions"""

        prompt = f"""Based on the following gap analysis for project "{project_name}", generate {num_questions} additional specific questions that would help capture critical tacit knowledge from the employee.

Gap Analysis:
- Missing Document Types: {', '.join(gap_analysis.get('missing_document_types', []))}
- Knowledge Gaps: {', '.join(gap_analysis.get('knowledge_gaps', []))}
- Context Gaps: {', '.join(gap_analysis.get('context_gaps', []))}

Generate questions that:
1. Focus on decisions, rationale, and context that wouldn't be in documents
2. Capture lessons learned and best practices
3. Identify key relationships and stakeholders
4. Understand critical workflows and processes
5. Uncover unwritten rules and institutional knowledge

Provide response as a JSON array:
[
    {{
        "question": "...",
        "category": "decision|technical|context|process|relationships",
        "priority": "high|medium|low",
        "reasoning": "why this question matters"
    }},
    ...
]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at knowledge management and extracting tacit knowledge through strategic questioning."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4,
                max_tokens=1000,
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON array
            if '[' in result_text and ']' in result_text:
                start = result_text.index('[')
                end = result_text.rindex(']') + 1
                json_str = result_text[start:end]
                questions = json.loads(json_str)
                return questions

        except Exception as e:
            print(f"Error generating additional questions: {e}")

        return []

    def create_questionnaire(
        self,
        employee: str,
        projects_gaps: Dict,
        output_path: str
    ):
        """
        Create a structured questionnaire for an employee

        Args:
            employee: Employee name
            projects_gaps: Dictionary of project gap analyses
            output_path: Path to save questionnaire
        """
        questionnaire = {
            'employee': employee,
            'total_projects': len(projects_gaps),
            'generated_date': None,
            'projects': {}
        }

        total_questions = 0

        for project_name, gap_analysis in projects_gaps.items():
            questions = self.generate_followup_questions(
                project_name,
                gap_analysis,
                max_questions=10
            )

            questionnaire['projects'][project_name] = {
                'project_name': project_name,
                'missing_elements': {
                    'document_types': gap_analysis.get('missing_document_types', []),
                    'knowledge_gaps': gap_analysis.get('knowledge_gaps', []),
                    'context_gaps': gap_analysis.get('context_gaps', []),
                },
                'questions': questions,
                'question_count': len(questions)
            }

            total_questions += len(questions)

        questionnaire['total_questions'] = total_questions

        # Save questionnaire
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(questionnaire, f, indent=2, ensure_ascii=False)

        print(f"✓ Created questionnaire with {total_questions} questions for {employee}")

        # Also create a human-readable version
        self._create_readable_questionnaire(questionnaire, output_file)

        return questionnaire

    def _create_readable_questionnaire(self, questionnaire: Dict, json_path: Path):
        """Create a human-readable text version of the questionnaire"""
        readable_path = json_path.with_suffix('.txt')

        with open(readable_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write(f"KNOWLEDGE CAPTURE QUESTIONNAIRE\n")
            f.write(f"Employee: {questionnaire['employee']}\n")
            f.write(f"Total Questions: {questionnaire['total_questions']}\n")
            f.write("="*80 + "\n\n")

            for project_name, project_data in questionnaire['projects'].items():
                f.write(f"\n{'='*80}\n")
                f.write(f"PROJECT: {project_name}\n")
                f.write(f"{'='*80}\n\n")

                # Write missing elements
                missing = project_data['missing_elements']

                if missing.get('document_types'):
                    f.write("Missing Document Types:\n")
                    for dtype in missing['document_types']:
                        f.write(f"  - {dtype}\n")
                    f.write("\n")

                if missing.get('knowledge_gaps'):
                    f.write("Identified Knowledge Gaps:\n")
                    for gap in missing['knowledge_gaps']:
                        f.write(f"  - {gap}\n")
                    f.write("\n")

                # Write questions
                f.write(f"\nQUESTIONS ({len(project_data['questions'])}):\n")
                f.write("-"*80 + "\n\n")

                for i, q in enumerate(project_data['questions'], 1):
                    f.write(f"Q{i}. {q['question']}\n")
                    f.write(f"    Category: {q.get('category', 'N/A')}\n")
                    f.write(f"    Priority: {q.get('priority', 'N/A')}\n")
                    if q.get('reasoning'):
                        f.write(f"    Why: {q['reasoning']}\n")
                    f.write("\n")

        print(f"✓ Created readable questionnaire at {readable_path}")

    def generate_all_questionnaires(
        self,
        gap_analysis_dir: str,
        output_dir: str
    ):
        """
        Generate questionnaires for all employees

        Args:
            gap_analysis_dir: Directory with gap analysis results
            output_dir: Directory to save questionnaires
        """
        gap_dir = Path(gap_analysis_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print("\nGenerating questionnaires for all employees...")

        # Load gap analyses
        for gap_file in gap_dir.glob("*_gaps.json"):
            employee = gap_file.stem.replace('_gaps', '')

            with open(gap_file, 'r', encoding='utf-8') as f:
                projects_gaps = json.load(f)

            if projects_gaps:
                questionnaire_file = output_path / f"{employee}_questionnaire.json"
                self.create_questionnaire(employee, projects_gaps, str(questionnaire_file))

        print("\n✓ Generated all questionnaires")


if __name__ == "__main__":
    from config.config import Config

    generator = QuestionGenerator(api_key=Config.OPENAI_API_KEY)

    generator.generate_all_questionnaires(
        gap_analysis_dir=str(Config.OUTPUT_DIR / "gap_analysis"),
        output_dir=str(Config.OUTPUT_DIR / "questionnaires")
    )
