# WebScraper Screenshots - Integration Guide

This guide shows how to integrate PDF screenshot capture into your existing 2nd Brain backend.

## Quick Start

### Step 1: Install Playwright
```bash
cd backend
pip install -r requirements.txt  # Includes playwright==1.40.0
playwright install chromium     # Install Chromium browser
```

### Step 2: Update Your Integration Routes

If you have a webscraper sync endpoint (e.g., in `api/integration_routes.py`):

```python
from connectors.webscraper_connector import WebScraperConnector
from connectors.base_connector import ConnectorConfig

@app.route('/api/integrations/webscraper/sync', methods=['POST'])
def sync_webscraper():
    """Sync content from a website with screenshot capture."""
    data = request.get_json()

    # Get current user's tenant_id
    tenant_id = get_current_user_tenant_id()  # Your auth method

    config = ConnectorConfig(
        connector_type="webscraper",
        user_id=current_user.id,
        settings={
            "start_url": data.get("start_url"),
            "max_depth": data.get("max_depth", 3),
            "max_pages": data.get("max_pages", 50),
            "capture_screenshots": data.get("capture_screenshots", True),  # NEW
            "screenshot_timeout": data.get("screenshot_timeout", 30),     # NEW
            "rate_limit_delay": data.get("rate_limit_delay", 1.0),
        }
    )

    # Initialize connector with tenant_id (NEW)
    connector = WebScraperConnector(config, tenant_id=tenant_id)

    try:
        if not await connector.connect():
            return {"error": connector.last_error}, 400

        documents = await connector.sync()
        await connector.disconnect()

        # Store documents in database
        for doc in documents:
            db_doc = Document(
                tenant_id=tenant_id,
                title=doc.title,
                content=doc.content,
                source="webscraper",
                metadata=doc.metadata,  # Includes pdf_path if captured
                # ... other fields
            )
            db.session.add(db_doc)

        db.session.commit()

        return {
            "status": "success",
            "documents_created": len(documents),
            "with_screenshots": sum(1 for d in documents if "pdf_path" in d.metadata)
        }, 200

    except Exception as e:
        return {"error": str(e)}, 500
```

### Step 3: Update Frontend (Optional)

To display screenshot links in your UI:

```javascript
// In your documents component
{document.metadata?.pdf_path && (
    <a href={document.metadata.pdf_path} target="_blank" rel="noopener noreferrer">
        📄 View Screenshot
    </a>
)}
```

### Step 4: Test the Integration

```bash
# Run the test script
python test_webscraper_screenshots.py

# Or test manually via API:
curl -X POST http://localhost:5003/api/integrations/webscraper/sync \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "start_url": "https://example.com",
    "max_depth": 1,
    "max_pages": 2,
    "capture_screenshots": true
  }'
```

## Configuration Options

### Basic Configuration (Minimal)
```python
config = ConnectorConfig(
    connector_type="webscraper",
    user_id="user_123",
    settings={
        "start_url": "https://example.com",
    }
)
connector = WebScraperConnector(config, tenant_id="tenant_xyz")
```

Default behavior:
- Screenshots enabled
- 30-second timeout
- Creates `tenant_data/tenant_xyz/screenshots/` directory
- Adds pdf_path to all captured documents

### Advanced Configuration
```python
config = ConnectorConfig(
    connector_type="webscraper",
    user_id="user_123",
    settings={
        "start_url": "https://example.com",
        "max_depth": 2,
        "max_pages": 20,
        "capture_screenshots": True,      # Enable/disable screenshots
        "screenshot_timeout": 60,         # Wait up to 60 seconds for page load
        "rate_limit_delay": 2.0,          # 2 seconds between requests
        "include_pdfs": True,             # Include PDF documents
        "allowed_extensions": [".html", ".htm", ".pdf", ""],
        "exclude_patterns": ["#", "mailto:", "tel:"],
    }
)
connector = WebScraperConnector(config, tenant_id="tenant_xyz")
```

## Checking if Screenshots Were Captured

### In Python
```python
# After sync()
for document in documents:
    if "pdf_path" in document.metadata:
        print(f"Screenshot: {document.metadata['pdf_path']}")
    else:
        print(f"No screenshot for: {document.title}")
```

### In Database
```sql
-- Assuming metadata is stored as JSON
SELECT
    title,
    url,
    metadata->>'pdf_path' as pdf_path
FROM documents
WHERE metadata->>'pdf_path' IS NOT NULL;
```

### Via API
Return screenshot info in your sync response:
```python
return {
    "status": "success",
    "documents": [
        {
            "id": doc.id,
            "title": doc.title,
            "url": doc.url,
            "pdf_path": doc.metadata.get("pdf_path")  # Include in response
        }
        for doc in documents
    ]
}, 200
```

## Troubleshooting Integration

### Playwright Not Found
```bash
# Install Playwright
pip install playwright==1.40.0

# Install Chromium
playwright install chromium

# Verify installation
python -c "import playwright; print('OK')"
```

### Permission Denied on Screenshots Directory
```bash
# Check tenant_data permissions
ls -la tenant_data/
ls -la tenant_data/{tenant_id}/

# Fix permissions (allow write)
chmod 755 tenant_data/
chmod 755 tenant_data/{tenant_id}/
mkdir -p tenant_data/{tenant_id}/screenshots
chmod 755 tenant_data/{tenant_id}/screenshots
```

### Screenshots Taking Too Long
- Increase `screenshot_timeout` if pages load slowly
- Or disable screenshots: `"capture_screenshots": False`
- Monitor logs for timeout messages

### PDF Files Not Created
1. Check `PLAYWRIGHT_AVAILABLE` in logs
2. Verify Chromium installed: `playwright install chromium`
3. Check file permissions on `tenant_data/` directory
4. Check available disk space

### Memory Issues with Many Screenshots
- Limit max_pages: `"max_pages": 20` instead of 100
- Disable screenshots: `"capture_screenshots": False`
- Increase server memory or reduce concurrent syncs

## File Access in Your Application

### Serving PDFs
If you want to serve PDFs through your API:

```python
@app.route('/api/documents/<doc_id>/screenshot')
def get_screenshot(doc_id):
    """Download document screenshot PDF."""
    document = Document.query.get(doc_id)

    if not document:
        return {"error": "Document not found"}, 404

    pdf_path = document.metadata.get("pdf_path")
    if not pdf_path:
        return {"error": "No screenshot for this document"}, 404

    # Verify file exists and is in correct tenant directory
    if not os.path.exists(pdf_path):
        return {"error": "Screenshot file not found"}, 404

    # Verify tenant access
    if not pdf_path.startswith(f"tenant_data/{document.tenant_id}/"):
        return {"error": "Unauthorized"}, 403

    return send_file(pdf_path, mimetype="application/pdf")
```

### Direct File Access
```python
import os

def get_screenshot_path(tenant_id, url_hash):
    """Get path to screenshot file."""
    return f"tenant_data/{tenant_id}/screenshots/{url_hash}.pdf"

def screenshot_exists(tenant_id, url_hash):
    """Check if screenshot exists."""
    path = get_screenshot_path(tenant_id, url_hash)
    return os.path.exists(path)

def list_screenshots(tenant_id):
    """List all screenshots for tenant."""
    directory = f"tenant_data/{tenant_id}/screenshots"
    if not os.path.exists(directory):
        return []
    return os.listdir(directory)
```

## Monitoring and Logging

### Check Screenshot Capture Status
```bash
# Monitor logs in real-time
tail -f app.log | grep "WebScraper"

# Look for success messages
tail -f app.log | grep "✓ Screenshot saved"

# Look for errors
tail -f app.log | grep "Error capturing screenshot"
```

### Log Message Examples
```
[WebScraper] Screenshots directory: tenant_data/tenant_123/screenshots
[WebScraper]   Capturing screenshot for: https://example.com/page1
[WebScraper]   ✓ Screenshot saved: tenant_data/tenant_123/screenshots/a1b2c3d4e5f6.pdf
[WebScraper]   ✓ Added screenshot to metadata
[WebScraper] Playwright not installed, skipping screenshot for {url}
[WebScraper] Error capturing screenshot: timeout
```

## Performance Optimization

### For Large Crawls (50+ pages)
```python
settings = {
    "capture_screenshots": False,  # Disable to save time/resources
    # ... other settings
}
```

### For Production
```python
# Use a dedicated server for web scraping
# Set up monitoring for:
# - Disk space (PDFs take space)
# - Memory usage (browser instances)
# - Timeout errors (slow pages)
# - Playwright availability (browser crashes)

settings = {
    "max_pages": 20,                # Reasonable limit
    "screenshot_timeout": 30,       # Not too aggressive
    "capture_screenshots": True,    # Enable for value
    "rate_limit_delay": 1.0,        # Respectful to target sites
}
```

## Cleanup and Maintenance

### Remove Old Screenshots
```bash
# Remove all screenshots for a tenant
rm -rf tenant_data/{tenant_id}/screenshots/

# Remove screenshots older than 30 days
find tenant_data/*/screenshots/ -mtime +30 -delete
```

### Monitor Screenshot Size
```bash
# Check total screenshot size
du -sh tenant_data/*/screenshots/

# Find largest screenshots
du -sh tenant_data/*/screenshots/* | sort -rh | head -10
```

### Archive Screenshots
```bash
# Backup to compressed archive
tar -czf backup_screenshots.tar.gz tenant_data/*/screenshots/

# Restore from archive
tar -xzf backup_screenshots.tar.gz
```

## Next Steps

1. **Install Playwright**: `pip install -r requirements.txt && playwright install chromium`
2. **Run Test Script**: `python test_webscraper_screenshots.py`
3. **Update Integration Endpoint**: Modify your sync handler (see "Update Integration Routes" above)
4. **Test End-to-End**: Sync a small website and verify screenshots
5. **Deploy**: Push changes and redeploy backend
6. **Monitor**: Watch logs for screenshot capture success/errors

## Support

If you encounter issues:

1. Check `WEBSCRAPER_SCREENSHOTS.md` for detailed troubleshooting
2. Review logs for `[WebScraper]` messages
3. Verify Playwright installation: `python -c "from playwright.async_api import async_playwright; print('OK')"`
4. Test screenshot capture manually: `python test_webscraper_screenshots.py`
5. Check file permissions on `tenant_data/` directory

## Files to Review

- `connectors/webscraper_connector.py` - Implementation
- `WEBSCRAPER_SCREENSHOTS.md` - Comprehensive guide
- `test_webscraper_screenshots.py` - Example usage
- `requirements.txt` - Dependencies
