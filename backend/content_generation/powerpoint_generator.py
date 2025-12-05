import os
"""
PowerPoint Generator for Training Materials
Creates professional PowerPoint presentations from knowledge base
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from openai import AzureOpenAI

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"



class PowerPointGenerator:
    """Generate professional PowerPoint presentations"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize PowerPoint generator

        Args:
            api_key: OpenAI API key
            model: LLM model to use
        """
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        self.model = model

    def generate_project_content(self, project_data: Dict) -> Dict:
        """
        Generate PowerPoint content for a project using LLM

        Args:
            project_data: Project information and documents

        Returns:
            Dictionary with slide content
        """
        project_name = project_data.get('project_name', 'Unknown Project')
        documents = project_data.get('documents', [])

        # Summarize documents
        doc_summaries = []
        for doc in documents[:20]:  # Limit to first 20 docs
            subject = doc.get('metadata', {}).get('subject', '')
            content = doc.get('content', '')[:300]
            doc_summaries.append(f"- {subject}: {content}")

        docs_text = '\n'.join(doc_summaries)

        prompt = f"""Create a professional PowerPoint presentation outline for a training session about the following project.

Project: {project_name}

Sample Documents:
{docs_text}

Generate a presentation with:
1. Title slide
2. Project Overview
3. Key Objectives
4. Major Activities/Milestones
5. Important Decisions
6. Lessons Learned
7. Key Contacts/Resources

For each slide, provide:
- Title
- Bullet points (3-5 points)
- Speaker notes

Respond in JSON format:
{{
    "presentation_title": "...",
    "slides": [
        {{
            "title": "...",
            "bullets": ["...", "...", "..."],
            "notes": "..."
        }},
        ...
    ]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating professional training presentations from project documentation."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4,
                max_tokens=2000,
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON
            if '{' in result_text:
                start = result_text.index('{')
                end = result_text.rindex('}') + 1
                json_str = result_text[start:end]
                content = json.loads(json_str)
                return content

        except Exception as e:
            print(f"Error generating content: {e}")

        # Fallback content
        return {
            'presentation_title': project_name,
            'slides': [
                {
                    'title': 'Project Overview',
                    'bullets': [
                        'Project details from documentation',
                        'Key activities and milestones',
                        'Important stakeholders'
                    ],
                    'notes': f'Overview of {project_name}'
                }
            ]
        }

    def create_presentation(self, content: Dict, output_path: str):
        """
        Create PowerPoint presentation from content

        Args:
            content: Presentation content dictionary
            output_path: Path to save presentation
        """
        # Create presentation
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)

        # Define color scheme (professional blue theme)
        PRIMARY_COLOR = RGBColor(0, 51, 102)  # Dark blue
        ACCENT_COLOR = RGBColor(0, 112, 192)  # Light blue
        TEXT_COLOR = RGBColor(64, 64, 64)     # Dark gray

        # Title slide
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)

        title = slide.shapes.title
        subtitle = slide.placeholders[1]

        title.text = content.get('presentation_title', 'Project Overview')
        subtitle.text = "Knowledge Transfer Training\nGenerated by KnowledgeVault"

        # Style title
        title.text_frame.paragraphs[0].font.size = Pt(44)
        title.text_frame.paragraphs[0].font.bold = True
        title.text_frame.paragraphs[0].font.color.rgb = PRIMARY_COLOR

        # Content slides
        for slide_content in content.get('slides', []):
            # Add slide with title and content layout
            bullet_slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(bullet_slide_layout)

            # Title
            title = slide.shapes.title
            title.text = slide_content.get('title', 'Slide')
            title.text_frame.paragraphs[0].font.size = Pt(32)
            title.text_frame.paragraphs[0].font.bold = True
            title.text_frame.paragraphs[0].font.color.rgb = PRIMARY_COLOR

            # Content
            body_shape = slide.shapes.placeholders[1]
            text_frame = body_shape.text_frame
            text_frame.clear()

            # Add bullets
            bullets = slide_content.get('bullets', [])
            for i, bullet_text in enumerate(bullets):
                if i == 0:
                    p = text_frame.paragraphs[0]
                else:
                    p = text_frame.add_paragraph()

                p.text = bullet_text
                p.level = 0
                p.font.size = Pt(18)
                p.font.color.rgb = TEXT_COLOR
                p.space_before = Pt(6)

            # Add speaker notes
            notes_slide = slide.notes_slide
            notes_text_frame = notes_slide.notes_text_frame
            notes_text_frame.text = slide_content.get('notes', '')

        # Save presentation
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_file))

        print(f"✓ Created presentation: {output_file}")

    def generate_employee_presentations(
        self,
        project_clusters_dir: str,
        output_dir: str
    ):
        """
        Generate presentations for all employee projects

        Args:
            project_clusters_dir: Directory with project clusters
            output_dir: Directory to save presentations
        """
        print("\nGenerating PowerPoint presentations...")

        project_dir = Path(project_clusters_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Process each employee
        for employee_dir in project_dir.iterdir():
            if not employee_dir.is_dir():
                continue

            employee = employee_dir.name
            print(f"\nGenerating presentations for {employee}...")

            # Load metadata
            metadata_file = employee_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # Generate presentation for each project
            for project_name in list(metadata.get('projects', {}).keys())[:3]:  # Limit to first 3 projects
                project_file = employee_dir / f"{project_name}.jsonl"

                if project_file.exists():
                    # Load project documents
                    documents = []
                    with open(project_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            documents.append(json.loads(line))

                    # Generate content
                    project_data = {
                        'project_name': project_name,
                        'documents': documents
                    }

                    content = self.generate_project_content(project_data)

                    # Create presentation
                    safe_name = project_name.replace('/', '_').replace('\\', '_')
                    ppt_file = output_path / f"{employee}_{safe_name}.pptx"

                    self.create_presentation(content, str(ppt_file))

        print("\n✓ Generated all presentations")

    def generate_master_presentation(
        self,
        employee: str,
        projects_data: List[Dict],
        output_path: str
    ):
        """
        Generate a master presentation covering multiple projects

        Args:
            employee: Employee name
            projects_data: List of project data dictionaries
            output_path: Path to save presentation
        """
        print(f"Generating master presentation for {employee}...")

        # Create presentation
        prs = Presentation()

        # Title slide
        title_slide = prs.slides.add_slide(prs.slide_layouts[0])
        title_slide.shapes.title.text = f"{employee.replace('-', ' ').title()}"
        title_slide.placeholders[1].text = "Knowledge Transfer - Complete Project Portfolio"

        # Overview slide
        overview_slide = prs.slides.add_slide(prs.slide_layouts[1])
        overview_slide.shapes.title.text = "Portfolio Overview"
        body = overview_slide.shapes.placeholders[1].text_frame

        body.text = f"Total Projects: {len(projects_data)}"
        for project in projects_data:
            p = body.add_paragraph()
            p.text = f"• {project.get('project_name', 'Unknown')}"

        # Add slide for each project
        for project in projects_data[:5]:  # Limit to 5 projects
            content = self.generate_project_content(project)

            for slide_content in content.get('slides', [])[:3]:  # 3 slides per project
                slide = prs.slides.add_slide(prs.slide_layouts[1])
                slide.shapes.title.text = f"{project.get('project_name', '')} - {slide_content.get('title', '')}"

                body = slide.shapes.placeholders[1].text_frame
                body.clear()

                for i, bullet in enumerate(slide_content.get('bullets', [])):
                    if i == 0:
                        p = body.paragraphs[0]
                    else:
                        p = body.add_paragraph()
                    p.text = bullet

        # Save
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_file))

        print(f"✓ Created master presentation: {output_file}")


if __name__ == "__main__":
    from config.config import Config

    generator = PowerPointGenerator(api_key=Config.OPENAI_API_KEY)

    generator.generate_employee_presentations(
        project_clusters_dir=str(Config.DATA_DIR / "project_clusters"),
        output_dir=str(Config.OUTPUT_DIR / "powerpoints")
    )
