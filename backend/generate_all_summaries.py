import os
"""
Generate AI summaries for all 150 employees
"""

import json
from pathlib import Path
from openai import AzureOpenAI
from config.config import Config
from tqdm import tqdm

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


def generate_all_summaries():
    """Generate summaries for all employees"""

    print("="*80)
    print("GENERATING SUMMARIES FOR ALL EMPLOYEES")
    print("="*80)

    # Load existing summaries
    summaries_file = Config.OUTPUT_DIR / "employee_summaries.json"
    if summaries_file.exists():
        with open(summaries_file, 'r') as f:
            employee_summaries = json.load(f)
        print(f"\n✓ Loaded {len(employee_summaries)} existing summaries")
    else:
        employee_summaries = {}

    # Load project metadata to get all employees
    metadata_file = Config.DATA_DIR / "project_clusters" / "metadata.json"
    with open(metadata_file, 'r') as f:
        project_metadata = json.load(f)

    print(f"✓ Found {len(project_metadata)} employees total")

    # Initialize OpenAI
    client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

    # Get employees that need summaries
    employees_to_process = []
    for employee in project_metadata.keys():
        if employee not in employee_summaries:
            # Count emails
            employee_file = Config.DATA_DIR / "employee_clusters" / f"{employee}.jsonl"
            if employee_file.exists():
                with open(employee_file, 'r') as f:
                    email_count = sum(1 for _ in f)
                employees_to_process.append((employee, email_count))

    # Sort by email count (process high-volume employees first)
    employees_to_process.sort(key=lambda x: x[1], reverse=True)

    print(f"\n✓ Need to generate {len(employees_to_process)} new summaries")
    print(f"✓ Already have {len(employee_summaries)} summaries")

    if len(employees_to_process) == 0:
        print("\n✓ All summaries already generated!")
        return

    # Generate summaries
    print(f"\nGenerating summaries...")

    for employee, email_count in tqdm(employees_to_process, desc="Processing employees"):
        # Load sample emails
        employee_file = Config.DATA_DIR / "employee_clusters" / f"{employee}.jsonl"

        emp_docs = []
        with open(employee_file, 'r') as f:
            for i, line in enumerate(f):
                if i >= 20:  # Sample 20 emails
                    break
                emp_docs.append(json.loads(line))

        # Extract subjects
        subjects = [doc['metadata'].get('subject', '')[:100] for doc in emp_docs]
        subjects_text = '\n'.join(f"- {s}" for s in subjects if s)

        prompt = f"""Analyze this employee's email data and provide a brief summary.

Employee: {employee}
Total emails: {email_count}
Sample subjects:
{subjects_text}

Provide a 2-3 sentence summary of their main responsibilities and projects.
Be specific and factual based on the email subjects."""

        try:
            response = client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150
            )

            summary = response.choices[0].message.content.strip()
            employee_summaries[employee] = {
                'summary': summary,
                'total_emails': email_count,
                'projects': len(project_metadata.get(employee, {}))
            }

        except Exception as e:
            print(f"\n✗ Failed for {employee}: {e}")
            employee_summaries[employee] = {
                'summary': f"Employee with {email_count} emails across various projects",
                'total_emails': email_count,
                'projects': len(project_metadata.get(employee, {}))
            }

        # Save after every 10 employees (checkpoint)
        if len(employee_summaries) % 10 == 0:
            with open(summaries_file, 'w', encoding='utf-8') as f:
                json.dump(employee_summaries, f, indent=2)

    # Final save
    with open(summaries_file, 'w', encoding='utf-8') as f:
        json.dump(employee_summaries, f, indent=2)

    print(f"\n\n{'='*80}")
    print("✓ COMPLETE!")
    print('='*80)
    print(f"\n✓ Generated {len(employee_summaries)} total summaries")
    print(f"✓ Saved to: {summaries_file}")

    # Show statistics
    total_emails = sum(s['total_emails'] for s in employee_summaries.values())
    total_projects = sum(s['projects'] for s in employee_summaries.values())

    print(f"\nStatistics:")
    print(f"  Total Employees: {len(employee_summaries)}")
    print(f"  Total Emails: {total_emails:,}")
    print(f"  Total Projects: {total_projects}")
    print(f"  Avg Emails/Employee: {total_emails // len(employee_summaries):,}")

    # Show top 5
    print(f"\nTop 5 employees by email volume:")
    sorted_employees = sorted(
        employee_summaries.items(),
        key=lambda x: x[1]['total_emails'],
        reverse=True
    )

    for i, (emp, data) in enumerate(sorted_employees[:5], 1):
        print(f"  {i}. {emp}: {data['total_emails']:,} emails, {data['projects']} projects")


if __name__ == '__main__':
    generate_all_summaries()
