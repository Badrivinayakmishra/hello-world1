#!/usr/bin/env python3
"""
Takeout Image Processor
Processes 620 images from Google Takeout using OpenAI Vision API
Extracts text, context, and classifies them for integration into Knowledge Vault
"""

import os
import json
import base64
from pathlib import Path
from typing import Dict, List
from openai import AzureOpenAI
from tqdm import tqdm
from dotenv import load_dotenv
import time

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


load_dotenv()

class TakeoutImageProcessor:
    """Process images from Google Takeout with OpenAI Vision"""

    def __init__(self, api_key: str):
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )
        self.processed_images = []

    def encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def process_image(self, image_path: Path) -> Dict:
        """
        Process a single image with OpenAI Vision

        Args:
            image_path: Path to image file

        Returns:
            Dict with extracted content and metadata
        """
        try:
            # Get space/group info from path
            path_parts = str(image_path).split('/')
            space_index = path_parts.index('Groups') if 'Groups' in path_parts else -1
            space_name = path_parts[space_index + 1] if space_index != -1 else "Unknown"

            # Encode image
            base64_image = self.encode_image(str(image_path))

            # Call Vision API
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,  # Use GPT-4o for vision
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this image and provide:
1. **Text Content**: Extract ALL visible text (typed or handwritten)
2. **Visual Description**: Describe what the image shows (diagrams, charts, screenshots, photos, etc.)
3. **Context**: What is this image about? (meeting notes, whiteboard, presentation slide, document, photo, etc.)
4. **Key Information**: Any important data, numbers, names, dates, or concepts
5. **Category**: Classify as one of: work, personal, screenshot, diagram, chart, photo, document, whiteboard, code, design, other

Provide response in JSON format:
{
  "text_content": "extracted text here",
  "visual_description": "description of what image shows",
  "context": "context and purpose",
  "key_information": ["item1", "item2", "item3"],
  "category": "category name",
  "has_sensitive_info": true/false,
  "work_related": true/false
}"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1
            )

            # Parse response
            result_text = response.choices[0].message.content

            # Extract JSON from response
            if '{' in result_text and '}' in result_text:
                start = result_text.index('{')
                end = result_text.rindex('}') + 1
                json_str = result_text[start:end]
                vision_data = json.loads(json_str)
            else:
                vision_data = {
                    "text_content": result_text,
                    "visual_description": "Image processed",
                    "context": "Unknown",
                    "key_information": [],
                    "category": "other",
                    "has_sensitive_info": False,
                    "work_related": False
                }

            # Create document
            document = {
                'doc_id': f"takeout_image_{image_path.stem}",
                'filename': image_path.name,
                'source': 'takeout_image',
                'source_path': str(image_path),
                'space_name': space_name,
                'content': vision_data.get('text_content', ''),
                'metadata': {
                    'visual_description': vision_data.get('visual_description', ''),
                    'context': vision_data.get('context', ''),
                    'key_information': vision_data.get('key_information', []),
                    'category': vision_data.get('category', 'other'),
                    'has_sensitive_info': vision_data.get('has_sensitive_info', False),
                    'work_related': vision_data.get('work_related', False),
                    'file_size': os.path.getsize(image_path),
                    'image_format': image_path.suffix
                },
                'processing_status': 'success'
            }

            return document

        except Exception as e:
            print(f"Error processing {image_path.name}: {e}")
            return {
                'doc_id': f"takeout_image_{image_path.stem}",
                'filename': image_path.name,
                'source': 'takeout_image',
                'source_path': str(image_path),
                'content': '',
                'metadata': {'error': str(e)},
                'processing_status': 'failed'
            }

    def process_all_images(
        self,
        takeout_dir: str,
        output_file: str,
        batch_delay: float = 1.0,
        max_images: int = None
    ) -> List[Dict]:
        """
        Process all images in Takeout directory

        Args:
            takeout_dir: Path to Takeout directory
            output_file: Path to save processed documents
            batch_delay: Delay between API calls (rate limiting)
            max_images: Maximum number of images to process (None = all)

        Returns:
            List of processed documents
        """
        # Find all images
        takeout_path = Path(takeout_dir)
        image_files = []

        print("📁 Scanning for images...")
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
            image_files.extend(list(takeout_path.rglob(ext)))

        print(f"✓ Found {len(image_files)} images")

        if max_images:
            image_files = image_files[:max_images]
            print(f"Processing first {max_images} images...")

        # Process images
        processed_docs = []
        success_count = 0
        fail_count = 0

        for image_file in tqdm(image_files, desc="Processing images"):
            doc = self.process_image(image_file)
            processed_docs.append(doc)

            if doc['processing_status'] == 'success':
                success_count += 1
            else:
                fail_count += 1

            # Rate limiting
            time.sleep(batch_delay)

            # Save progress every 50 images
            if len(processed_docs) % 50 == 0:
                self._save_progress(processed_docs, output_file)

        # Final save
        self._save_progress(processed_docs, output_file)

        print(f"\n✅ Processing complete!")
        print(f"   Success: {success_count}")
        print(f"   Failed: {fail_count}")
        print(f"   Total: {len(processed_docs)}")

        return processed_docs

    def _save_progress(self, documents: List[Dict], output_file: str):
        """Save processing progress"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for doc in documents:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

    def get_statistics(self, documents: List[Dict]) -> Dict:
        """Get processing statistics"""
        stats = {
            'total': len(documents),
            'successful': sum(1 for d in documents if d['processing_status'] == 'success'),
            'failed': sum(1 for d in documents if d['processing_status'] == 'failed'),
            'by_category': {},
            'work_related': 0,
            'personal': 0,
            'has_sensitive_info': 0
        }

        for doc in documents:
            if doc['processing_status'] == 'success':
                category = doc['metadata'].get('category', 'other')
                stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

                if doc['metadata'].get('work_related', False):
                    stats['work_related'] += 1
                else:
                    stats['personal'] += 1

                if doc['metadata'].get('has_sensitive_info', False):
                    stats['has_sensitive_info'] += 1

        return stats


def main():
    print("="*70)
    print("TAKEOUT IMAGE PROCESSOR")
    print("="*70)
    print()

    # Configuration
    TAKEOUT_DIR = "/Users/rishitjain/Downloads/Takeout"
    OUTPUT_FILE = "club_data/takeout_images_processed.jsonl"
    API_KEY = os.getenv("OPENAI_API_KEY")

    if not API_KEY:
        print("❌ OPENAI_API_KEY not found in environment!")
        return

    # Initialize processor
    processor = TakeoutImageProcessor(API_KEY)

    # Process images
    print(f"📂 Takeout directory: {TAKEOUT_DIR}")
    print(f"💾 Output file: {OUTPUT_FILE}")
    print()

    # Ask user for confirmation
    print("This will process up to 620 images using OpenAI Vision API.")
    print("Estimated cost: ~$0.50-1.00 (depends on image sizes)")
    print("Estimated time: ~20-30 minutes with rate limiting")
    print()

    response = input("Continue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("❌ Cancelled")
        return

    # Process all images
    documents = processor.process_all_images(
        takeout_dir=TAKEOUT_DIR,
        output_file=OUTPUT_FILE,
        batch_delay=1.0,  # 1 second between API calls
        max_images=None  # Process all images
    )

    # Show statistics
    print("\n" + "="*70)
    print("PROCESSING STATISTICS")
    print("="*70)

    stats = processor.get_statistics(documents)
    print(f"\nTotal images: {stats['total']}")
    print(f"  ✓ Successful: {stats['successful']}")
    print(f"  ✗ Failed: {stats['failed']}")
    print(f"\nWork-related: {stats['work_related']}")
    print(f"Personal: {stats['personal']}")
    print(f"Sensitive info: {stats['has_sensitive_info']}")
    print(f"\nBy category:")
    for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count}")

    print(f"\n💾 Saved to: {OUTPUT_FILE}")
    print("\n✅ Image processing complete!")
    print("\nNext step: Classify these images and add to RAG system")


if __name__ == "__main__":
    main()
