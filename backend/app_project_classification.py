import os
"""
KnowledgeVault Web Application with Global Project Classification
Displays employee-project mappings and project information
"""

from flask import Flask, render_template, request, jsonify
import json
from pathlib import Path
from openai import AzureOpenAI
from datetime import datetime

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


app = Flask(__name__)

# Configuration
DATA_DIR = Path('/Users/rishitjain/Downloads/knowledgevault_backend')
CLUB_OUTPUT_DIR = DATA_DIR / 'output' / 'club_project_classification'
GLOBAL_OUTPUT_DIR = DATA_DIR / 'output' / 'global_project_classification'

# Global variables
project_mapping = None
employee_mapping = None
classification_summary = None
current_output_dir = CLUB_OUTPUT_DIR

# Initialize OpenAI
OPENAI_API_KEY = "os.getenv("OPENAI_API_KEY", "")"
client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )


def load_classification_data(output_dir: Path):
    """Load project classification data"""
    global project_mapping, employee_mapping, classification_summary, current_output_dir

    current_output_dir = output_dir
    print(f"\nLoading classification data from: {output_dir}")

    # Load project mapping
    project_file = output_dir / "project_mapping.json"
    if project_file.exists():
        with open(project_file, 'r') as f:
            project_mapping = json.load(f)
        print(f"✓ Loaded {len(project_mapping)} projects")
    else:
        project_mapping = {}
        print("⚠ Project mapping not found")

    # Load employee mapping
    employee_file = output_dir / "employee_mapping.json"
    if employee_file.exists():
        with open(employee_file, 'r') as f:
            employee_mapping = json.load(f)
        print(f"✓ Loaded {len(employee_mapping)} employees")
    else:
        employee_mapping = {}
        print("⚠ Employee mapping not found")

    # Load summary
    summary_file = output_dir / "classification_summary.json"
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            classification_summary = json.load(f)
        print(f"✓ Loaded classification summary")
    else:
        classification_summary = {}
        print("⚠ Classification summary not found")

    print("✓ Data loaded successfully\n")


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('project_dashboard.html',
                         projects=project_mapping,
                         employees=employee_mapping,
                         summary=classification_summary)


@app.route('/projects')
def projects():
    """List all projects"""
    if not project_mapping:
        return jsonify({'error': 'No project data available'}), 404

    # Sort projects by document count
    sorted_projects = sorted(
        project_mapping.items(),
        key=lambda x: x[1]['total_documents'],
        reverse=True
    )

    return jsonify({
        'total': len(sorted_projects),
        'projects': [
            {
                'name': name,
                'total_documents': data['total_documents'],
                'num_employees': data['num_employees'],
                'employees': data['employees'],
                'avg_confidence': data['avg_confidence']
            }
            for name, data in sorted_projects
        ]
    })


@app.route('/project/<path:project_name>')
def project_detail(project_name):
    """Get details for a specific project"""
    if not project_mapping or project_name not in project_mapping:
        return jsonify({'error': 'Project not found'}), 404

    project_data = project_mapping[project_name]

    # Load project documents
    safe_name = project_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
    project_file = current_output_dir / "projects" / f"{safe_name}.jsonl"

    documents = []
    if project_file.exists():
        with open(project_file, 'r') as f:
            for line in f:
                documents.append(json.loads(line))

    return jsonify({
        'project_name': project_name,
        'total_documents': project_data['total_documents'],
        'num_employees': project_data['num_employees'],
        'employees': project_data['employees'],
        'employee_contributions': project_data['employee_contributions'],
        'avg_confidence': project_data['avg_confidence'],
        'documents': documents[:50]  # Limit to first 50 for performance
    })


@app.route('/employees')
def employees():
    """List all employees"""
    if not employee_mapping:
        return jsonify({'error': 'No employee data available'}), 404

    # Sort employees by document count
    sorted_employees = sorted(
        employee_mapping.items(),
        key=lambda x: x[1]['total_documents'],
        reverse=True
    )

    return jsonify({
        'total': len(sorted_employees),
        'employees': [
            {
                'name': name,
                'total_documents': data['total_documents'],
                'num_projects': data['num_projects'],
                'primary_projects': data['primary_projects']
            }
            for name, data in sorted_employees
        ]
    })


@app.route('/employee/<path:employee_name>')
def employee_detail(employee_name):
    """Get details for a specific employee"""
    if not employee_mapping or employee_name not in employee_mapping:
        return jsonify({'error': 'Employee not found'}), 404

    employee_data = employee_mapping[employee_name]

    # Load employee documents
    safe_name = employee_name.replace('/', '_').replace('\\', '_').replace('@', '_at_')
    employee_file = current_output_dir / "employees" / f"{safe_name}.jsonl"

    documents = []
    if employee_file.exists():
        with open(employee_file, 'r') as f:
            for line in f:
                documents.append(json.loads(line))

    return jsonify({
        'employee': employee_name,
        'total_documents': employee_data['total_documents'],
        'num_projects': employee_data['num_projects'],
        'all_projects': employee_data['all_projects'],
        'primary_projects': employee_data['primary_projects'],
        'documents': documents[:50]  # Limit to first 50
    })


@app.route('/employee/<path:employee_name>/projects')
def employee_projects(employee_name):
    """Get all projects for an employee"""
    if not employee_mapping or employee_name not in employee_mapping:
        return jsonify({'error': 'Employee not found'}), 404

    employee_data = employee_mapping[employee_name]

    # Sort projects by document count
    sorted_projects = sorted(
        employee_data['all_projects'].items(),
        key=lambda x: x[1],
        reverse=True
    )

    return jsonify({
        'employee': employee_name,
        'total_projects': len(sorted_projects),
        'projects': [
            {
                'name': proj_name,
                'document_count': count,
                'is_primary': proj_name in employee_data['primary_projects']
            }
            for proj_name, count in sorted_projects
        ]
    })


@app.route('/project/<path:project_name>/employees')
def project_employees(project_name):
    """Get all employees for a project"""
    if not project_mapping or project_name not in project_mapping:
        return jsonify({'error': 'Project not found'}), 404

    project_data = project_mapping[project_name]

    # Sort employees by contribution
    sorted_employees = sorted(
        project_data['employee_contributions'].items(),
        key=lambda x: x[1],
        reverse=True
    )

    return jsonify({
        'project': project_name,
        'total_employees': len(sorted_employees),
        'employees': [
            {
                'name': emp_name,
                'document_count': count,
                'percentage': (count / project_data['total_documents'] * 100)
            }
            for emp_name, count in sorted_employees
        ]
    })


@app.route('/summary')
def summary():
    """Get overall classification summary"""
    return jsonify(classification_summary or {})


@app.route('/search')
def search():
    """Search across all documents"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    # Simple search across project names and employee names
    results = {
        'projects': [],
        'employees': []
    }

    query_lower = query.lower()

    # Search projects
    if project_mapping:
        for proj_name, proj_data in project_mapping.items():
            if query_lower in proj_name.lower():
                results['projects'].append({
                    'name': proj_name,
                    'total_documents': proj_data['total_documents'],
                    'num_employees': proj_data['num_employees']
                })

    # Search employees
    if employee_mapping:
        for emp_name, emp_data in employee_mapping.items():
            if query_lower in emp_name.lower():
                results['employees'].append({
                    'name': emp_name,
                    'total_documents': emp_data['total_documents'],
                    'num_projects': emp_data['num_projects']
                })

    return jsonify(results)


@app.route('/switch-dataset/<dataset>')
def switch_dataset(dataset):
    """Switch between datasets"""
    if dataset == 'club':
        load_classification_data(CLUB_OUTPUT_DIR)
    else:
        load_classification_data(GLOBAL_OUTPUT_DIR)

    return jsonify({
        'success': True,
        'dataset': dataset,
        'projects': len(project_mapping) if project_mapping else 0,
        'employees': len(employee_mapping) if employee_mapping else 0
    })


if __name__ == '__main__':
    # Load club data by default
    if CLUB_OUTPUT_DIR.exists():
        load_classification_data(CLUB_OUTPUT_DIR)
    else:
        load_classification_data(GLOBAL_OUTPUT_DIR)

    app.run(debug=True, port=5002)
