import os
"""
Display Methodology Results
Shows you the AI-generated clusters, classifications, gaps, and questions
"""

import json
from pathlib import Path
from config.config import Config
from openai import AzureOpenAI
from gap_analysis.gap_analyzer import GapAnalyzer

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


def show_project_clusters():
    """Show the AI-discovered project clusters"""

    print("\n" + "="*80)
    print("1. AI-DISCOVERED PROJECT CLUSTERS")
    print("="*80)

    metadata_file = Config.DATA_DIR / "project_clusters" / "metadata.json"
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)

    # Show top 5 employees
    employees = list(metadata.keys())[:5]

    for emp in employees:
        projects = metadata[emp]
        print(f"\n👤 Employee: {emp}")
        print(f"   Total Projects Found: {len(projects)}")

        for proj_id, proj_info in list(projects.items())[:3]:  # Show first 3 projects
            print(f"\n   📁 {proj_id}:")
            print(f"      Documents: {proj_info['document_count']}")

            # Read sample documents
            proj_file = Path(proj_info['file'])
            if proj_file.exists():
                with open(proj_file, 'r') as f:
                    sample = json.loads(f.readline())
                    print(f"      Sample Subject: {sample['metadata'].get('subject', 'N/A')[:60]}...")


def show_gap_analysis():
    """Run and show gap analysis for a sample employee"""

    print("\n\n" + "="*80)
    print("2. KNOWLEDGE GAP ANALYSIS")
    print("="*80)

    # Analyze kaminski-v as example
    employee = 'kaminski-v'
    print(f"\nAnalyzing employee: {employee}")

    # Load sample documents
    employee_file = Config.DATA_DIR / "employee_clusters" / f"{employee}.jsonl"
    documents = []

    with open(employee_file, 'r') as f:
        for i, line in enumerate(f):
            if i >= 30:  # Sample 30 docs
                break
            documents.append(json.loads(line))

    print(f"Loaded {len(documents)} sample documents")

    # Run gap analysis
    analyzer = GapAnalyzer(api_key=Config.OPENAI_API_KEY)

    project_data = {
        'project_name': f'{employee}_sample',
        'documents': documents
    }

    print("Running AI gap analysis...")
    gaps = analyzer.analyze_project_gaps(project_data)

    # Display results
    print(f"\n📊 GAP ANALYSIS RESULTS:")
    print(f"\nMissing Document Types:")
    for doc_type in gaps.get('missing_document_types', []):
        print(f"  - {doc_type}")

    print(f"\nKnowledge Gaps:")
    for i, gap in enumerate(gaps.get('knowledge_gaps', []), 1):
        print(f"  {i}. {gap}")

    print(f"\nContext Gaps:")
    for i, gap in enumerate(gaps.get('context_gaps', []), 1):
        print(f"  {i}. {gap}")

    return gaps


def show_generated_questions(gaps):
    """Show AI-generated questions"""

    print("\n\n" + "="*80)
    print("3. AI-GENERATED QUESTIONS FOR EMPLOYEE")
    print("="*80)

    questions = gaps.get('questions', [])

    if not questions:
        print("\nNo questions generated yet")
        return

    print(f"\nTotal Questions: {len(questions)}\n")

    for i, q in enumerate(questions, 1):
        print(f"\nQuestion {i}:")
        print(f"  ❓ {q.get('question', 'N/A')}")
        print(f"  Category: {q.get('category', 'N/A')}")
        print(f"  Priority: {q.get('priority', 'N/A')}")
        print(f"  Reasoning: {q.get('reasoning', 'N/A')[:100]}...")


def show_employee_summaries():
    """Show AI-generated employee summaries"""

    print("\n\n" + "="*80)
    print("4. AI-GENERATED EMPLOYEE SUMMARIES")
    print("="*80)

    summaries_file = Config.OUTPUT_DIR / "employee_summaries.json"

    with open(summaries_file, 'r') as f:
        summaries = json.load(f)

    for emp, data in list(summaries.items())[:3]:  # Show first 3
        print(f"\n👤 {emp}")
        print(f"   Total Emails: {data['total_emails']:,}")
        print(f"   Projects: {data['projects']}")
        print(f"\n   Summary:")
        print(f"   {data['summary']}")
        print()


def create_interactive_questionnaire():
    """Create an interactive questionnaire"""

    print("\n\n" + "="*80)
    print("5. INTERACTIVE QUESTIONNAIRE (Sample)")
    print("="*80)

    print("""
This is what the employee would see:

================================================================================
KNOWLEDGE CAPTURE QUESTIONNAIRE
Employee: kaminski-v
================================================================================

We've analyzed your project documentation and identified some knowledge gaps.
Please answer the following questions to help us build a complete knowledge base.

--------------------------------------------------------------------------------
Question 1: What were the key technical decisions in the Energy Derivatives project?

Category: Technical Decision
Priority: High

Your Answer:
[Interactive text box would appear here]

Reason: This information is critical for understanding the architecture choices
and trade-offs made during the project lifecycle.
--------------------------------------------------------------------------------

Question 2: Who were the main stakeholders in the Online Trading Exchange initiative?

Category: Context
Priority: Medium

Your Answer:
[Interactive text box would appear here]

Reason: Understanding stakeholder relationships helps map decision-making authority
and communication patterns.
--------------------------------------------------------------------------------

[... more questions ...]

Once answers are provided, the system would:
1. Store answers in the knowledge base
2. Use AI to generate follow-up questions
3. Re-index with new information
4. Update the RAG system
5. Generate updated PowerPoints/training materials
    """)


def main():
    """Run the complete demo"""

    print("="*80)
    print("KNOWLEDGEVAULT - METHODOLOGY RESULTS VIEWER")
    print("="*80)
    print("\nThis will show you:")
    print("1. AI-discovered project clusters")
    print("2. Knowledge gap analysis")
    print("3. AI-generated questions")
    print("4. Employee summaries")
    print("5. Interactive questionnaire (sample)")
    print()

    input("Press Enter to continue...")

    # Show all results
    show_project_clusters()

    input("\nPress Enter to see gap analysis...")
    gaps = show_gap_analysis()

    input("\nPress Enter to see generated questions...")
    show_generated_questions(gaps)

    input("\nPress Enter to see employee summaries...")
    show_employee_summaries()

    input("\nPress Enter to see interactive questionnaire...")
    create_interactive_questionnaire()

    print("\n\n" + "="*80)
    print("✓ DEMO COMPLETE")
    print("="*80)
    print("\nYou've seen:")
    print("✓ 1. Project clusters discovered by AI")
    print("✓ 2. Knowledge gaps identified")
    print("✓ 3. Questions generated for employees")
    print("✓ 4. Employee summaries")
    print("✓ 5. How the interactive Q&A would work")
    print("\nThe full methodology is ready to deploy!")


if __name__ == '__main__':
    main()
