import os
"""
Multi-Modal Understanding Module
Uses GPT-4o vision to interpret charts, graphs, and visual content.
"""

import base64
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass
from openai import AzureOpenAI
import re

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"



@dataclass
class VisualContent:
    """Represents extracted visual content"""
    content_id: str
    source_doc_id: str
    image_path: Optional[str]
    image_base64: Optional[str]
    content_type: str  # chart, graph, table, diagram, screenshot
    extracted_text: str
    structured_data: Dict[str, Any]
    metadata: Dict[str, Any]


class MultiModalProcessor:
    """
    Processes visual content using GPT-4o vision.

    Capabilities:
    - Chart interpretation (bar, line, pie, etc.)
    - Graph data extraction
    - Table OCR and structuring
    - Diagram understanding
    - Screenshot analysis
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or "os.getenv("OPENAI_API_KEY", "")"
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        self.model=AZURE_CHAT_DEPLOYMENT

    def encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        with open(image_path, "rb") as image_file:
            return base64.standard_b64encode(image_file.read()).decode("utf-8")

    def get_image_media_type(self, image_path: str) -> str:
        """Get media type from file extension"""
        ext = Path(image_path).suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp"
        }
        return media_types.get(ext, "image/png")

    def analyze_image(
        self,
        image_path: str = None,
        image_base64: str = None,
        prompt: str = None,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze an image using GPT-4o vision.

        Args:
            image_path: Path to image file
            image_base64: Base64 encoded image
            prompt: Specific question about the image
            context: Additional context about the document

        Returns:
            Dict with analysis results
        """
        if not image_path and not image_base64:
            return {"error": "No image provided"}

        # Prepare image for API
        if image_path:
            image_base64 = self.encode_image(image_path)
            media_type = self.get_image_media_type(image_path)
        else:
            media_type = "image/png"

        # Default prompt for comprehensive analysis
        if not prompt:
            prompt = """Analyze this image and provide:
1. TYPE: What type of visual is this? (chart, graph, table, diagram, screenshot, etc.)
2. TITLE: What is the title or main subject?
3. DATA: Extract all data points, numbers, and values you can see
4. INSIGHTS: What are the key takeaways or insights?
5. TRENDS: Any trends or patterns visible?
6. TEXT: Transcribe any text visible in the image

Format your response as JSON with these keys: type, title, data, insights, trends, text"""

        # Add context if provided
        full_prompt = prompt
        if context:
            full_prompt = f"Context: {context}\n\n{prompt}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": full_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )

            result_text = response.choices[0].message.content

            # Try to parse as JSON
            try:
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {"raw_response": result_text}
            except json.JSONDecodeError:
                result = {"raw_response": result_text}

            return {
                "success": True,
                "analysis": result,
                "model": self.model,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def extract_chart_data(self, image_path: str = None, image_base64: str = None) -> Dict[str, Any]:
        """
        Extract structured data from a chart.
        """
        prompt = """This image contains a chart or graph. Please extract all the data:

1. CHART_TYPE: (bar, line, pie, scatter, area, etc.)
2. TITLE: The chart title
3. X_AXIS: Label and values for X axis
4. Y_AXIS: Label and values for Y axis
5. DATA_SERIES: List each data series with its values
6. LEGEND: Any legend items
7. ANNOTATIONS: Any notes or callouts

Respond with JSON in this exact format:
{
    "chart_type": "string",
    "title": "string",
    "x_axis": {"label": "string", "values": []},
    "y_axis": {"label": "string", "min": 0, "max": 0},
    "data_series": [
        {"name": "string", "values": [{"x": "value", "y": 0}]}
    ],
    "legend": [],
    "annotations": [],
    "summary": "string describing the main insight"
}"""

        return self.analyze_image(image_path, image_base64, prompt)

    def extract_table_data(self, image_path: str = None, image_base64: str = None) -> Dict[str, Any]:
        """
        Extract structured data from a table image.
        """
        prompt = """This image contains a table. Please extract all the data:

1. Extract the table headers
2. Extract each row of data
3. Identify the table title if present
4. Note any formatting (bold, colors, merged cells)

Respond with JSON in this exact format:
{
    "title": "string or null",
    "headers": ["col1", "col2", ...],
    "rows": [
        ["cell1", "cell2", ...],
        ...
    ],
    "notes": "any additional observations",
    "summary": "brief summary of what the table shows"
}"""

        return self.analyze_image(image_path, image_base64, prompt)

    def extract_diagram_info(self, image_path: str = None, image_base64: str = None) -> Dict[str, Any]:
        """
        Extract information from diagrams, flowcharts, org charts, etc.
        """
        prompt = """This image contains a diagram. Please analyze it:

1. DIAGRAM_TYPE: (flowchart, org chart, process diagram, architecture, network, etc.)
2. ELEMENTS: List all boxes, shapes, or nodes with their labels
3. CONNECTIONS: Describe how elements are connected (arrows, lines)
4. FLOW: If it's a process, describe the flow
5. HIERARCHY: If it's hierarchical, describe the structure

Respond with JSON in this exact format:
{
    "diagram_type": "string",
    "title": "string or null",
    "elements": [
        {"id": "1", "label": "string", "type": "box/circle/etc"}
    ],
    "connections": [
        {"from": "1", "to": "2", "label": "string or null"}
    ],
    "hierarchy": "description of structure if applicable",
    "process_summary": "description of the process/flow",
    "key_insights": []
}"""

        return self.analyze_image(image_path, image_base64, prompt)

    def answer_question_about_image(
        self,
        question: str,
        image_path: str = None,
        image_base64: str = None,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Answer a specific question about an image.
        """
        prompt = f"""Please answer this question about the image:

{question}

{f'Additional context: {context}' if context else ''}

Provide a clear, detailed answer based on what you can see in the image.
If you cannot answer the question from the image, explain why."""

        return self.analyze_image(image_path, image_base64, prompt)

    def process_document_images(
        self,
        doc_id: str,
        image_paths: List[str],
        doc_context: str = ""
    ) -> List[VisualContent]:
        """
        Process all images from a document.
        """
        visual_contents = []

        for i, image_path in enumerate(image_paths):
            try:
                # Analyze the image
                result = self.analyze_image(
                    image_path=image_path,
                    context=doc_context
                )

                if result.get("success"):
                    analysis = result.get("analysis", {})

                    # Determine content type
                    content_type = analysis.get("type", "unknown")
                    if isinstance(content_type, str):
                        content_type = content_type.lower()
                        if "chart" in content_type or "graph" in content_type:
                            content_type = "chart"
                        elif "table" in content_type:
                            content_type = "table"
                        elif "diagram" in content_type or "flow" in content_type:
                            content_type = "diagram"
                        else:
                            content_type = "image"

                    # Create text representation
                    extracted_text = self._analysis_to_text(analysis)

                    visual_content = VisualContent(
                        content_id=f"{doc_id}_visual_{i}",
                        source_doc_id=doc_id,
                        image_path=image_path,
                        image_base64=None,  # Don't store to save memory
                        content_type=content_type,
                        extracted_text=extracted_text,
                        structured_data=analysis,
                        metadata={
                            "image_index": i,
                            "tokens_used": result.get("tokens_used", 0)
                        }
                    )

                    visual_contents.append(visual_content)

            except Exception as e:
                print(f"Error processing image {image_path}: {e}")

        return visual_contents

    def _analysis_to_text(self, analysis: Dict) -> str:
        """Convert analysis dict to searchable text"""
        text_parts = []

        if isinstance(analysis, dict):
            # Title
            if analysis.get("title"):
                text_parts.append(f"Title: {analysis['title']}")

            # Type
            if analysis.get("type"):
                text_parts.append(f"Type: {analysis['type']}")

            # Data
            if analysis.get("data"):
                if isinstance(analysis["data"], list):
                    text_parts.append("Data: " + ", ".join(str(d) for d in analysis["data"]))
                elif isinstance(analysis["data"], dict):
                    text_parts.append("Data: " + json.dumps(analysis["data"]))
                else:
                    text_parts.append(f"Data: {analysis['data']}")

            # Insights
            if analysis.get("insights"):
                if isinstance(analysis["insights"], list):
                    text_parts.append("Insights: " + "; ".join(analysis["insights"]))
                else:
                    text_parts.append(f"Insights: {analysis['insights']}")

            # Trends
            if analysis.get("trends"):
                text_parts.append(f"Trends: {analysis['trends']}")

            # Summary
            if analysis.get("summary"):
                text_parts.append(f"Summary: {analysis['summary']}")

            # Text content
            if analysis.get("text"):
                text_parts.append(f"Text: {analysis['text']}")

            # Raw response fallback
            if analysis.get("raw_response"):
                text_parts.append(analysis["raw_response"])

        elif isinstance(analysis, str):
            text_parts.append(analysis)

        return "\n".join(text_parts)

    def create_searchable_chunks(self, visual_contents: List[VisualContent]) -> List[Dict]:
        """
        Create searchable chunks from visual content for RAG indexing.
        """
        chunks = []

        for vc in visual_contents:
            chunk = {
                "chunk_id": vc.content_id,
                "doc_id": vc.source_doc_id,
                "content": vc.extracted_text,
                "chunk_type": f"visual_{vc.content_type}",
                "metadata": {
                    **vc.metadata,
                    "content_type": vc.content_type,
                    "has_image": True,
                    "image_path": vc.image_path,
                    "structured_data": vc.structured_data
                }
            }
            chunks.append(chunk)

        return chunks


# Global instance
multimodal_processor = MultiModalProcessor()


if __name__ == "__main__":
    # Test the multimodal processor
    processor = MultiModalProcessor()

    # Test with a sample prompt (no actual image)
    print("Multi-Modal Processor initialized")
    print(f"Model: {processor.model}")

    # Example usage documentation
    print("""
Usage Examples:
--------------

1. Analyze any image:
   result = processor.analyze_image(image_path="chart.png")

2. Extract chart data:
   data = processor.extract_chart_data(image_path="sales_chart.png")

3. Extract table data:
   table = processor.extract_table_data(image_path="financial_table.png")

4. Answer questions about an image:
   answer = processor.answer_question_about_image(
       question="What is the highest value shown?",
       image_path="chart.png"
   )

5. Process all images in a document:
   visuals = processor.process_document_images(
       doc_id="doc_001",
       image_paths=["img1.png", "img2.png"],
       doc_context="Q4 Financial Report"
   )

6. Create searchable chunks for RAG:
   chunks = processor.create_searchable_chunks(visuals)
""")
