# Deployment & Testing Checklist

## 🚀 Pre-Deployment Checklist

### 1. Code Status
- [x] All changes committed to GitHub
- [x] All frontend changes pushed
- [x] All backend changes pushed
- [x] Latest commit: Training Guides video player integration

### 2. Environment Variables on Render
Verify these are set in your Render backend environment:

```bash
# Azure OpenAI (Required)
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_ENDPOINT=https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com
AZURE_API_VERSION=2024-12-01-preview
AZURE_CHAT_DEPLOYMENT=gpt-5-chat
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_WHISPER_DEPLOYMENT=whisper

# AWS S3 (Required - Already Added)
AWS_ACCESS_KEY_ID=AKIASN2GEM7OFHC378WB
AWS_SECRET_ACCESS_KEY=lmkhibnWWGXi/vxPZP1u+xEazOMG8Nr44KUWYDaP
AWS_S3_BUCKET=catalyst-uploads-pranav
AWS_S3_REGION=us-east-2

# Azure TTS (Optional - for video narration)
AZURE_TTS_KEY=<your-key>
AZURE_TTS_REGION=eastus2

# Database (Auto-configured by Render)
DATABASE_URL=<auto-set-by-render>

# Integrations (Optional)
GOOGLE_CLIENT_ID=<your-id>
GOOGLE_CLIENT_SECRET=<your-secret>
SLACK_CLIENT_ID=<your-id>
SLACK_CLIENT_SECRET=<your-secret>
BOX_CLIENT_ID=<your-id>
BOX_CLIENT_SECRET=<your-secret>

# Gamma API (Required for video generation)
GAMMA_API_KEY=<your-key>
```

### 3. Dependencies Check
- [x] boto3==1.34.19 added to requirements.txt
- [x] All other dependencies present

---

## 🔄 Deployment Steps

### Step 1: Trigger Render Deploy
1. Go to Render dashboard
2. Select your backend service
3. Click "Manual Deploy" → "Deploy latest commit"
4. Wait for build to complete (~5-10 minutes)

### Step 2: Monitor Deployment
Watch for these in the Render logs:
```
✓ Installing dependencies from requirements.txt
✓ Installing boto3==1.34.19
✓ Database migration (current_step column auto-created)
✓ Starting gunicorn
✓ Listening on port 10000
```

### Step 3: Frontend Deploy (if using Vercel/Netlify)
If frontend is on Vercel/Netlify, it will auto-deploy from GitHub push.
If running locally, no action needed.

---

## ✅ Post-Deployment Testing Checklist

### Test 1: Document Upload + S3
- [ ] Login to your production site
- [ ] Go to Documents page
- [ ] Click "Add Documents"
- [ ] Upload a PDF or DOCX file
- [ ] Wait for upload to complete
- [ ] **Verify in S3**: Check your S3 bucket at:
  ```
  catalyst-uploads-pranav/
    tenants/{your-tenant-id}/
      documents/{filename}_{timestamp}.{ext}
  ```
- [ ] Click the uploaded document to view
- [ ] Click "Download Original File" button
- [ ] Verify file downloads from S3 URL

**Expected Result**: ✅ File appears in S3, download button works

---

### Test 2: Video Generation from Documents
- [ ] Select 2-3 documents in Documents page
- [ ] Click "Generate Video" button
- [ ] Enter video title: "Test Training Video"
- [ ] Enter description: "Testing video generation"
- [ ] Click "Create Video"
- [ ] **Watch progress bar** - Should show:
  - "Generating presentation..." (0-30%)
  - "Creating slides..." (30-60%)
  - "Generating audio..." (60-80%)
  - "Rendering video..." (80-100%)
  - "Completed!" (100%)
- [ ] Wait for completion (may take 3-5 minutes)
- [ ] **Verify in S3**: Check your S3 bucket at:
  ```
  catalyst-uploads-pranav/
    tenants/{your-tenant-id}/
      videos/{video-id}_{timestamp}.mp4
      thumbnails/{video-id}_{timestamp}.jpg
  ```
- [ ] Go to Training Guides page
- [ ] Verify video appears in list
- [ ] Click video card to open player
- [ ] Verify video plays from S3
- [ ] Click "Download Video" button
- [ ] Click "Share Link" button - verify link copied

**Expected Result**: ✅ Video generates, uploads to S3, plays in Training Guides

---

### Test 3: Video Generation from Knowledge Gaps
- [ ] Go to Knowledge Gaps page
- [ ] Click "Find Gaps" to analyze documents
- [ ] Wait for gaps to appear
- [ ] Answer at least 2-3 gaps with text or voice
- [ ] Click "Generate Training Video" button
- [ ] Enter title: "Q&A Training Video"
- [ ] Toggle "Include Answers" ON
- [ ] Click "Create Video"
- [ ] Watch progress (same as Test 2)
- [ ] Verify completion
- [ ] **Verify in S3**: Video and thumbnail uploaded
- [ ] Go to Training Guides
- [ ] Verify video appears in "Training Q&A Videos" column
- [ ] Click to play
- [ ] Verify it shows questions and answers

**Expected Result**: ✅ Q&A video generates and plays correctly

---

### Test 4: Box Integration + S3
- [ ] Go to Integrations page
- [ ] Connect Box account (if not already connected)
- [ ] Click "Sync Now" for Box
- [ ] Wait for sync to complete
- [ ] **Verify in S3**: Check your S3 bucket at:
  ```
  catalyst-uploads-pranav/
    tenants/{your-tenant-id}/
      box_files/{filename}_{timestamp}.{ext}
  ```
- [ ] Go to Documents page
- [ ] Find documents with source "Box"
- [ ] Click a Box document
- [ ] Click "Download Original File"
- [ ] Verify file opens from S3

**Expected Result**: ✅ Box files appear in S3, download works

---

### Test 5: Training Guides Page
- [ ] Go to Training Guides page
- [ ] Verify page loads without errors
- [ ] Verify videos are organized by type:
  - "Document Videos" column (if you have document videos)
  - "Training Q&A Videos" column (if you have Q&A videos)
  - "All Videos" summary (if you have both types)
- [ ] Verify video counts are correct
- [ ] Verify total duration is shown
- [ ] Click a video card
- [ ] Verify video player modal opens
- [ ] Verify video plays automatically
- [ ] Verify metadata shows:
  - Duration
  - Slides count
  - Creation date
- [ ] Click "Download Video" - verify download starts
- [ ] Click "Share Link" - verify link copies
- [ ] Press ESC key - verify modal closes
- [ ] Click outside modal - verify modal closes
- [ ] Click Close button - verify modal closes

**Expected Result**: ✅ All videos display correctly, player works

---

### Test 6: Database Migration Verification
- [ ] Check Render logs for database errors
- [ ] Generate a new video
- [ ] Watch progress - verify current_step shows in UI
- [ ] If errors occur related to "current_step column not found":
  - SSH into Render service
  - Run: `python -c "from database.models import Base; from database.config import engine; Base.metadata.create_all(engine)"`
  - Retry video generation

**Expected Result**: ✅ No database errors, progress steps show correctly

---

## 🐛 Common Issues & Fixes

### Issue 1: S3 Upload Fails
**Symptoms**: Videos/documents upload but don't appear in S3
**Check**:
```bash
# In Render logs, look for:
[S3] Error: S3 upload failed: ...
```
**Fix**:
- Verify AWS credentials are set correctly in Render
- Check S3 bucket permissions (should allow public-read)
- Verify bucket region matches AWS_S3_REGION

### Issue 2: Video Player Shows "Video not available"
**Symptoms**: Video card appears but player shows error
**Check**:
- Video status is "completed"
- file_path field contains S3 URL (starts with https://)
**Fix**:
- Check Render logs during video generation
- Verify S3 upload succeeded
- Check S3 bucket for video file

### Issue 3: current_step Column Error
**Symptoms**: Video generation fails with database error
**Error**: `column "current_step" does not exist`
**Fix**:
```bash
# SSH to Render and run:
python -c "from database.models import Base; from database.config import engine; Base.metadata.create_all(engine)"
```

### Issue 4: Training Guides Shows No Videos
**Symptoms**: Training Guides page empty but videos exist
**Check**:
- Open browser console (F12)
- Look for API errors
- Check network tab for /api/videos request
**Fix**:
- Verify JWT token is valid (try logging out and back in)
- Check video status filter (should be "completed")
- Verify authHeaders are being sent

### Issue 5: Download Button Doesn't Appear
**Symptoms**: Can view document but no download button
**Check**:
- Document metadata has file_url field
**Fix**:
- Re-upload the document (old documents won't have S3 URLs)
- Or manually migrate: Run Box sync again to re-upload to S3

---

## 📊 Success Criteria

All tests must pass for successful deployment:

- [x] Code deployed to Render without errors
- [ ] Document upload saves to S3
- [ ] Document download button works
- [ ] Video generation from documents works
- [ ] Video generation from Q&A works
- [ ] Videos upload to S3
- [ ] Videos play in Training Guides
- [ ] Box files upload to S3
- [ ] Training Guides page loads correctly
- [ ] Video player modal works
- [ ] Download/share buttons work
- [ ] Progress tracking shows current steps
- [ ] No database migration errors

---

## 🎉 Post-Testing

Once all tests pass:

1. Mark Task #13 as completed
2. Clean up any test videos/documents
3. Monitor S3 costs (should be minimal)
4. Set up S3 lifecycle rules if needed (auto-delete old files after X days)
5. Consider enabling CloudFront CDN for faster video delivery

---

## 📝 Completed Features Summary

### ✅ Video Generation System
- Generate videos from documents
- Generate videos from knowledge gaps Q&A
- Progress tracking with real-time updates
- Automatic thumbnail generation
- Azure TTS voice narration
- Gamma API slide generation

### ✅ AWS S3 Integration
- All videos uploaded to S3
- All thumbnails uploaded to S3
- Manual document uploads to S3
- Box file downloads to S3
- Public URLs for easy sharing
- Automatic cleanup of local temp files

### ✅ Training Guides Platform
- Video library organized by source
- Full-screen video player
- Download and share functionality
- Video metadata display
- Duration tracking
- Empty state handling

### ✅ Bug Fixes
- Fixed video status polling
- Added current_step database field
- Fixed frontend-backend API mismatches
- Added download original file button

---

**Last Updated**: 2026-01-29
**Deployed Version**: Ready for production testing
