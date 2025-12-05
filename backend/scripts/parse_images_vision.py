#!/usr/bin/env python3
"""
Parse all images from Takeout using OpenAI Vision API.
Saves parsed data to Parsed_data_Final directory.
"""

import os
import json
import base64
from pathlib import Path
from openai import AzureOpenAI
import mimetypes
from PIL import Image
import io

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Configuration
TAKEOUT_DIR = Path("/Users/rishitjain/Downloads/Takeout")
OUTPUT_DIR = Path("/Users/rishitjain/Downloads/Parsed_data_Final")
PROGRESS_FILE = OUTPUT_DIR / "parsing_progress.json"

# Image extensions to process
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic'}

client = OpenAI()

def setup_output_dir():
    """Create output directory structure"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "images").mkdir(exist_ok=True)
    (OUTPUT_DIR / "metadata").mkdir(exist_ok=True)
    print(f"✓ Output directory created: {OUTPUT_DIR}")

def load_progress():
    """Load parsing progress"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"parsed": [], "failed": [], "total_processed": 0}

def save_progress(progress):
    """Save parsing progress"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def encode_image_to_base64(image_path):
    """Convert image to base64 for Vision API"""
    try:
        # Handle HEIC files by converting to JPEG
        if image_path.suffix.lower() == '.heic':
            img = Image.open(image_path)
            buffer = io.BytesIO()
            img.convert('RGB').save(buffer, format='JPEG')
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

        # Regular images
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"⚠ Failed to encode {image_path.name}: {e}")
        return None

def parse_image_with_vision(image_path, image_base64):
    """Use OpenAI Vision to parse image content"""

    # Determine mime type
    mime_type = mimetypes.guess_type(str(image_path))[0] or 'image/jpeg'
    if image_path.suffix.lower() == '.heic':
        mime_type = 'image/jpeg'  # HEIC converted to JPEG

    prompt = """Analyze this image and provide a detailed description.

Include:
1. **Type**: What kind of image is this? (screenshot, photo, document, diagram, chart, etc.)
2. **Content**: What does the image show? Be specific and detailed.
3. **Text**: Extract ALL visible text, including:
   - Titles, headings, labels
   - Body text, paragraphs
   - Numbers, dates, names
   - URLs, email addresses
   - Any other readable text
4. **Context**: What is the purpose or context of this image?
5. **Key Information**: List the most important facts, data points, or insights

Be thorough and extract as much information as possible. This will be used for search and retrieval.

Respond in JSON:
{
  "type": "screenshot|photo|document|diagram|chart|other",
  "description": "Detailed description of the image",
  "extracted_text": "All visible text extracted from the image",
  "context": "Purpose and context",
  "key_information": ["fact1", "fact2", "fact3"],
  "entities": ["person", "organization", "location", "date"],
  "topics": ["topic1", "topic2"]
}
"""

    try:
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}",
                                "detail": "high"  # Use high detail for better text extraction
                            }
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.1
        )

        content = response.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        print(f"⚠ Vision API failed: {e}")
        return None

def find_all_images():
    """Find all images in Takeout directory"""
    images = []
    for ext in IMAGE_EXTENSIONS:
        images.extend(TAKEOUT_DIR.rglob(f"*{ext}"))
        images.extend(TAKEOUT_DIR.rglob(f"*{ext.upper()}"))
    return sorted(set(images))

def main():
    print("="*70)
    print("IMAGE PARSING: OpenAI Vision API")
    print("="*70)

    # Setup
    setup_output_dir()

    # Find images
    print(f"\nScanning {TAKEOUT_DIR} for images...")
    all_images = find_all_images()
    print(f"✓ Found {len(all_images)} images to process")

    # Load progress
    progress = load_progress()
    parsed_set = set(progress['parsed'])
    failed_set = set(progress['failed'])

    # Filter out already processed
    to_process = [img for img in all_images if str(img) not in parsed_set and str(img) not in failed_set]

    if not to_process:
        print("\n✓ All images already processed!")
        print(f"  Parsed: {len(parsed_set)}")
        print(f"  Failed: {len(failed_set)}")
        return

    print(f"\nProcessing {len(to_process)} new images...")
    print(f"  Already parsed: {len(parsed_set)}")
    print(f"  Previously failed: {len(failed_set)}")

    # Process each image
    for i, image_path in enumerate(to_process, 1):
        print(f"\n[{i}/{len(to_process)}] {image_path.name}")

        try:
            # Encode image
            image_base64 = encode_image_to_base64(image_path)
            if not image_base64:
                failed_set.add(str(image_path))
                continue

            # Parse with Vision
            print(f"  Analyzing with GPT-4o Vision...")
            result = parse_image_with_vision(image_path, image_base64)

            if not result:
                failed_set.add(str(image_path))
                continue

            # Save parsed data
            relative_path = image_path.relative_to(TAKEOUT_DIR)
            output_path = OUTPUT_DIR / "images" / relative_path.with_suffix('.json')
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create comprehensive metadata
            metadata = {
                "original_path": str(image_path),
                "relative_path": str(relative_path),
                "file_name": image_path.name,
                "file_size": image_path.stat().st_size,
                "file_type": image_path.suffix,
                "parsed_content": result,
                "source": "openai_vision_gpt4o"
            }

            with open(output_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            parsed_set.add(str(image_path))
            print(f"  ✓ Saved to {output_path.relative_to(OUTPUT_DIR)}")
            print(f"    Type: {result.get('type', 'unknown')}")
            print(f"    Text length: {len(result.get('extracted_text', ''))} chars")

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed_set.add(str(image_path))

        # Save progress every 10 images
        if i % 10 == 0:
            progress['parsed'] = list(parsed_set)
            progress['failed'] = list(failed_set)
            progress['total_processed'] = len(parsed_set) + len(failed_set)
            save_progress(progress)
            print(f"\n  Progress saved: {len(parsed_set)} parsed, {len(failed_set)} failed")

    # Final save
    progress['parsed'] = list(parsed_set)
    progress['failed'] = list(failed_set)
    progress['total_processed'] = len(parsed_set) + len(failed_set)
    save_progress(progress)

    print(f"\n{'='*70}")
    print(f"✓ IMAGE PARSING COMPLETE")
    print(f"{'='*70}")
    print(f"  Total images: {len(all_images)}")
    print(f"  Successfully parsed: {len(parsed_set)}")
    print(f"  Failed: {len(failed_set)}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
