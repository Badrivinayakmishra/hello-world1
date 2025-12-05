import os
"""
Complete KnowledgeVault Methodology
Includes: Work/Personal Classification, Gap Analysis, Question Generation
"""

import json
from pathlib import Path
from openai import AzureOpenAI
from config.config import Config
from classification.work_personal_classifier import WorkPersonalClassifier
from gap_analysis.gap_analyzer import GapAnalyzer
from gap_analysis.question_generator import QuestionGenerator
from tqdm import tqdm

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


def classify_projects_for_employee(employee_name: str, classifier: WorkPersonalClassifier):
    """Classify all projects for an employee as work vs personal"""

    print(f"\n{'='*80}")
    print(f"CLASSIFYING PROJECTS FOR: {employee_name}")
    print('='*80)

    # Load metadata
    metadata_file = Config.DATA_DIR / "project_clusters" / "metadata.json"
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)

    if employee_name not in metadata:
        print(f"❌ Employee {employee_name} not found in metadata")
        return None

    employee_projects = metadata[employee_name]
    classification_results = {
        'employee': employee_name,
        'projects': {},
        'summary': {'keep': 0, 'remove': 0, 'review': 0}
    }

    for project_id, project_info in employee_projects.items():
        project_file = Path(project_info['file'])

        if not project_file.exists():
            continue

        print(f"\n📁 Analyzing {project_id} ({project_info['document_count']} documents)...")

        # Sample documents from the project
        documents = []
        with open(project_file, 'r') as f:
            for i, line in enumerate(f):
                if i >= 10:  # Sample first 10 docs
                    break
                documents.append(json.loads(line))

        # Classify each document
        classifications = []
        for doc in documents[:3]:  # Classify first 3 for speed
            result = classifier.classify_document(doc)
            classifications.append(result)

        # Aggregate results
        avg_confidence = sum(c['confidence'] for c in classifications) / len(classifications)
        work_count = sum(1 for c in classifications if c['category'] == 'work')

        project_decision = 'keep' if work_count >= 2 else 'remove'
        if 0.4 <= avg_confidence <= 0.85:
            project_decision = 'review'

        classification_results['projects'][project_id] = {
            'document_count': project_info['document_count'],
            'decision': project_decision,
            'avg_confidence': avg_confidence,
            'sample_classifications': classifications
        }

        classification_results['summary'][project_decision] += 1

        print(f"   Decision: {project_decision.upper()} (confidence: {avg_confidence:.2f})")

    return classification_results


def run_gap_analysis_for_employee(employee_name: str, analyzer: GapAnalyzer):
    """Run gap analysis for an employee"""

    print(f"\n{'='*80}")
    print(f"GAP ANALYSIS FOR: {employee_name}")
    print('='*80)

    # Load employee cluster
    employee_file = Config.DATA_DIR / "employee_clusters" / f"{employee_name}.jsonl"

    if not employee_file.exists():
        print(f"❌ Employee file not found: {employee_file}")
        return None

    # Load sample documents
    documents = []
    with open(employee_file, 'r') as f:
        for i, line in enumerate(f):
            if i >= 50:  # Sample 50 documents
                break
            documents.append(json.loads(line))

    print(f"📊 Analyzing {len(documents)} sample documents...")

    # Prepare project data
    project_data = {
        'project_name': f'{employee_name}_overview',
        'documents': documents
    }

    # Run gap analysis
    gap_result = analyzer.analyze_project_gaps(project_data)

    gaps = gap_result.get('knowledge_gaps', []) + gap_result.get('context_gaps', [])
    questions = gap_result.get('questions', [])

    print(f"\n✓ Found {len(gaps)} knowledge gaps")
    print(f"✓ Generated {len(questions)} questions")

    return {
        'gaps': gaps,
        'questions': questions,
        'missing_doc_types': gap_result.get('missing_document_types', [])
    }


def generate_questions_for_employee(employee_name: str, gaps: list, generator: QuestionGenerator):
    """Generate questions to fill knowledge gaps"""

    print(f"\n{'='*80}")
    print(f"GENERATING QUESTIONS FOR: {employee_name}")
    print('='*80)

    questions = generator.generate_questions(gaps, employee_name)

    print(f"\n✓ Generated {len(questions)} questions")

    return questions


def main():
    """Run the complete methodology"""

    print("="*80)
    print("KNOWLEDGEVAULT - COMPLETE METHODOLOGY")
    print("="*80)
    print("\nThis will:")
    print("1. Classify projects as Work vs Personal")
    print("2. Analyze knowledge gaps")
    print("3. Generate questions for employees")
    print("4. Create interactive Q&A reports")
    print()

    # Initialize components
    client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
    classifier = WorkPersonalClassifier(client)
    analyzer = GapAnalyzer(api_key=Config.OPENAI_API_KEY)
    generator = QuestionGenerator(client)

    # Select employees to analyze (top 3 for demo)
    employees_to_analyze = ['kaminski-v', 'dasovich-j', 'kean-s']

    all_results = {}

    for employee in employees_to_analyze:
        print(f"\n\n{'#'*80}")
        print(f"# PROCESSING: {employee}")
        print(f"{'#'*80}")

        # Step 1: Classify projects
        classification = classify_projects_for_employee(employee, classifier)

        # Step 2: Gap analysis
        gap_result = run_gap_analysis_for_employee(employee, analyzer)

        # Step 3: Generate additional questions (already have some from gap analysis)
        combined_questions = gap_result['questions']
        if gap_result['gaps']:
            additional_questions = generate_questions_for_employee(employee, gap_result['gaps'], generator)
            combined_questions.extend(additional_questions)

        # Save results
        all_results[employee] = {
            'classification': classification,
            'gaps': gap_result['gaps'],
            'missing_doc_types': gap_result.get('missing_doc_types', []),
            'questions': combined_questions
        }

    # Save comprehensive results
    output_file = Config.OUTPUT_DIR / "methodology_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n\n{'='*80}")
    print("✓ METHODOLOGY COMPLETE")
    print('='*80)
    print(f"\nResults saved to: {output_file}")
    print(f"\nProcessed {len(employees_to_analyze)} employees:")

    for emp in employees_to_analyze:
        results = all_results[emp]
        print(f"\n{emp}:")
        print(f"  - Projects: {len(results['classification']['projects'])}")
        print(f"    Keep: {results['classification']['summary']['keep']}")
        print(f"    Remove: {results['classification']['summary']['remove']}")
        print(f"    Review: {results['classification']['summary']['review']}")
        print(f"  - Knowledge Gaps: {len(results['gaps'])}")
        print(f"  - Questions Generated: {len(results['questions'])}")

    # Create human-readable report
    create_readable_report(all_results)


def create_readable_report(results):
    """Create a human-readable report"""

    report_file = Config.OUTPUT_DIR / "methodology_report.txt"

    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("KNOWLEDGEVAULT - METHODOLOGY RESULTS\n")
        f.write("="*80 + "\n\n")

        for employee, data in results.items():
            f.write(f"\n{'#'*80}\n")
            f.write(f"EMPLOYEE: {employee}\n")
            f.write(f"{'#'*80}\n\n")

            # Classification summary
            f.write("1. PROJECT CLASSIFICATION (Work vs Personal)\n")
            f.write("-"*80 + "\n")
            f.write(f"Total Projects: {len(data['classification']['projects'])}\n")
            f.write(f"  ✓ Keep (Work-related): {data['classification']['summary']['keep']}\n")
            f.write(f"  ✗ Remove (Personal): {data['classification']['summary']['remove']}\n")
            f.write(f"  ? Review (Uncertain): {data['classification']['summary']['review']}\n\n")

            # Project details
            for project_id, proj_data in data['classification']['projects'].items():
                f.write(f"\n  {project_id}:\n")
                f.write(f"    Decision: {proj_data['decision'].upper()}\n")
                f.write(f"    Confidence: {proj_data['avg_confidence']:.2f}\n")
                f.write(f"    Documents: {proj_data['document_count']}\n")

                if proj_data['sample_classifications']:
                    f.write(f"    Sample: {proj_data['sample_classifications'][0]['reasoning'][:100]}...\n")

            # Gaps
            f.write(f"\n\n2. KNOWLEDGE GAPS IDENTIFIED\n")
            f.write("-"*80 + "\n")

            for i, gap in enumerate(data['gaps'], 1):
                f.write(f"\nGap {i}: {gap.get('gap_type', 'Unknown')}\n")
                f.write(f"  {gap.get('description', 'No description')}\n")

            # Questions
            f.write(f"\n\n3. QUESTIONS FOR EMPLOYEE\n")
            f.write("-"*80 + "\n")

            for i, question in enumerate(data['questions'], 1):
                f.write(f"\n{i}. {question.get('question', 'No question')}\n")
                f.write(f"   Purpose: {question.get('purpose', 'N/A')}\n")
                f.write(f"   Gap Type: {question.get('gap_type', 'N/A')}\n")

            f.write("\n" + "="*80 + "\n\n")

    print(f"\n✓ Human-readable report saved to: {report_file}")


if __name__ == '__main__':
    main()
