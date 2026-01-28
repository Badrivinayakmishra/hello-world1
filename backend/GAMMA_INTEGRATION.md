# Gamma API Integration for Video Generation

## Overview

The 2nd Brain platform now supports **AI-powered presentation generation** using Gamma.app API. This enables automatic creation of professional training videos from your documents and knowledge base.

## Workflow: Option B (Gamma → PPTX → Video)

```
Documents/Knowledge Gaps
        ↓
   Gamma API (AI Generation)
        ↓
   PPTX Export
        ↓
   Download & Parse
        ↓
   Extract Slides + Notes
        ↓
   Generate Audio Narration (Azure TTS)
        ↓
   Create MP4 Video
        ↓
   Viewable on Portal
```

---

## Setup

### 1. **Get Gamma API Credentials**

1. Go to [gamma.app](https://gamma.app)
2. Sign up or log in
3. Navigate to **Settings → API Keys**
4. Generate a new API key
5. Create a template presentation (or use existing)
6. Get the template ID from the URL: `gamma.app/docs/[TEMPLATE_ID]`
7. Get the theme ID from your template settings

### 2. **Configure Environment Variables**

Add to `/Users/pranavreddymogathala/use2ndbrain/backend/.env`:

```bash
# Gamma AI Presentation API
GAMMA_API_KEY=sk-gamma-wlYM1BVDdlBCBnVJaUsLAtGY7ikjekJet9xXnuGSu8w
GAMMA_TEMPLATE_ID=g_3g8gkijbwnm7wxk
GAMMA_THEME_ID=adfbsgcj2cfbfw6

# Azure TTS (for narration)
AZURE_TTS_KEY=your_azure_tts_key_here
AZURE_TTS_REGION=eastus2
AZURE_TTS_VOICE=en-US-JennyNeural
```

### 3. **Install Dependencies**

Already installed:
- ✅ `python-pptx` - PPTX parsing
- ✅ `requests` - HTTP client
- ✅ `pillow` - Image processing
- ✅ `moviepy` - Video creation

Optional (for better narration):
```bash
pip install azure-cognitiveservices-speech
```

---

## Usage

### **API Endpoint**

```http
POST /api/videos
Content-Type: application/json
Authorization: Bearer <jwt_token>

{
  "title": "Onboarding Training",
  "description": "Introduction to our processes",
  "source_type": "documents",
  "source_ids": ["doc-id-1", "doc-id-2"],
  "project_id": "optional-project-id"
}
```

**Note:** Gamma is used by default (`use_gamma=True`). Videos will automatically use Gamma API.

---

## Features

### **1. Smart Content Generation**

**From Documents:**
```python
# Automatically formats as business presentation
- Executive summary from document collection
- Key insights and takeaways
- Data visualizations
- Professional business format
```

**From Knowledge Gaps:**
```python
# Q&A format presentation
- Question slides
- Answer slides with context
- Speaker notes from gap descriptions
- Knowledge transfer focus
```

### **2. Automatic Fallback**

If Gamma API fails (network issues, API limits, etc.):
- ✅ Automatically falls back to local slide generation
- ✅ Uses GPT-4 for content structuring
- ✅ No video generation failure
- ✅ Logged warnings for debugging

### **3. Professional Output**

- **Slides:** AI-designed from Gamma template
- **Narration:** Azure TTS professional voice
- **Duration:** Auto-calculated from content (~15 chars/sec)
- **Quality:** 1920x1080, 24 FPS MP4
- **Viewable:** Download endpoint + portal integration

---

## How It Works

### **Step 1: Content Preparation**

```python
# For documents
content = """
PRESENTATION TITLE: {title}

Create a professional business presentation from the following documents:

## Document 1: {title}
{content_preview}

## Document 2: {title}
{content_preview}

INSTRUCTIONS:
- Create a cohesive presentation with clear sections
- Use professional business format
- Include key insights and takeaways
"""

# For knowledge gaps
content = """
PRESENTATION TITLE: {title}
SUBTITLE: Critical Knowledge & Answers

Create a knowledge transfer presentation covering these Q&A pairs:

## Topic 1: {gap_title}
**Q:** {question}
**A:** {answer}
"""
```

### **Step 2: Gamma API Call**

```python
POST https://public-api.gamma.app/v1.0/generations/from-template

{
  "gammaId": "g_3g8gkijbwnm7wxk",
  "prompt": "{content}",
  "themeId": "adfbsgcj2cfbfw6",
  "exportAs": "pptx"
}

Response:
{
  "generationId": "gen_abc123",
  "status": "processing"
}
```

### **Step 3: Poll for Completion**

```python
GET https://public-api.gamma.app/v1.0/generations/{generationId}

# Polls every 5 seconds for up to 5 minutes

Response (when complete):
{
  "status": "completed",
  "url": "https://gamma.app/docs/xxx",
  "exportUrl": "https://storage.gamma.app/xxx.pptx"
}
```

### **Step 4: Download PPTX**

```python
GET {exportUrl}
# Downloads PPTX file to tenant's video directory
```

### **Step 5: Parse PPTX**

```python
from pptx import Presentation

prs = Presentation("gamma.pptx")

for slide in prs.slides:
    title = slide.shapes.title.text
    content = extract_text_from_shapes(slide)
    notes = slide.notes_slide.notes_text_frame.text

    slides.append(SlideContent(
        title=title,
        content=content,
        notes=notes
    ))
```

### **Step 6: Generate Video**

```python
# Existing pipeline
1. Generate audio from notes (Azure TTS)
2. Render slides to images (PIL)
3. Combine slides + audio (MoviePy)
4. Output: MP4 video
```

---

## Progress Tracking

Videos show real-time progress:

```
Queued (0%)
  ↓
Generating presentation with Gamma AI... (10%)
  ↓
Waiting for Gamma export... (25%)
  ↓
Downloading PPTX... (30%)
  ↓
Generating narration... (50%)
  ↓
Rendering slides... (70%)
  ↓
Creating video... (90%)
  ↓
Completed (100%)
```

Check status:
```http
GET /api/videos/{video_id}/status

Response:
{
  "status": "processing",
  "progress_percent": 50,
  "current_step": "Generating narration..."
}
```

---

## Error Handling

### **Gamma API Errors**

| Error | Cause | Fallback |
|-------|-------|----------|
| 401 Unauthorized | Invalid API key | Local generation |
| 429 Rate Limit | Too many requests | Local generation |
| Timeout | Slow generation | Local generation after 5min |
| Export URL missing | Export failed | Local generation |
| Download failed | Network issue | Local generation |

All errors are logged:
```python
print(f"[VideoService] Gamma generation error: {error}")
print(f"[VideoService] Falling back to local slide generation...")
```

### **PPTX Parsing Errors**

If PPTX is corrupt or unreadable:
- Falls back to local generation
- Video status set to FAILED
- Error message stored in database

---

## Testing

### **Test Gamma Service**

```python
PYTHONPATH=/Users/pranavreddymogathala/use2ndbrain/backend \
./venv312/bin/python -c "
from services.gamma_service import get_gamma_service

service = get_gamma_service()
result, error = service.generate_presentation(
    content='Create a 5-slide presentation about AI in healthcare',
    title='AI Healthcare',
    export_format='pptx'
)

if error:
    print(f'Error: {error}')
else:
    print(f'Success!')
    print(f'URL: {result.get(\"url\")}')
    print(f'Export URL: {result.get(\"exportUrl\")}')
"
```

### **Test Full Video Pipeline**

```bash
# 1. Start backend
cd /Users/pranavreddymogathala/use2ndbrain/backend
./venv312/bin/python app_v2.py

# 2. Create video via API
curl -X POST http://localhost:5003/api/videos \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "title": "Test Presentation",
    "source_type": "documents",
    "source_ids": ["doc-id-1"]
  }'

# 3. Check status
curl http://localhost:5003/api/videos/{video_id}/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 4. Download when complete
curl http://localhost:5003/api/videos/{video_id}/download \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -o video.mp4
```

---

## Costs

### **Gamma API**
- Pricing: Check gamma.app/pricing
- Typical: $0.10-0.50 per presentation generation
- Export included in generation cost

### **Azure TTS**
- Pricing: $16/1M characters
- Typical 10-slide video: ~2000 chars = $0.03
- Free tier: 5M chars/month

### **Total per Video**
- **Gamma:** ~$0.30
- **Azure TTS:** ~$0.03
- **Total:** ~$0.33/video

---

## Troubleshooting

### **"Gamma API key not found"**
```bash
# Check .env file exists
ls -la /Users/pranavreddymogathala/use2ndbrain/backend/.env

# Check GAMMA_API_KEY is set
grep GAMMA_API_KEY .env

# Restart backend after updating .env
```

### **"PPTX parsing failed"**
```bash
# Install python-pptx
pip install python-pptx

# Check PPTX file is valid
unzip -l gamma.pptx
```

### **"Gamma generation timed out"**
```python
# Increase timeout in gamma_service.py
max_attempts = 120  # 10 minutes instead of 5
```

### **Videos have no sound**
```bash
# Install Azure SDK
pip install azure-cognitiveservices-speech

# Check Azure TTS key
grep AZURE_TTS_KEY .env

# Fallback: Install gTTS
pip install gtts
```

---

## Future Enhancements

- [ ] User-selectable templates
- [ ] Custom themes per tenant
- [ ] Batch video generation
- [ ] Video editing capabilities
- [ ] Direct Gamma URL sharing (skip video conversion)
- [ ] Webhook notifications for completion
- [ ] Cost tracking and limits

---

## Support

For issues or questions:
1. Check logs: `tail -f logs/video_service.log`
2. Test Gamma API: Run test script above
3. Check API status: https://status.gamma.app
4. Review error messages in video record

---

**Implementation Date:** 2026-01-28
**Version:** 1.0
**Status:** ✅ Production Ready
