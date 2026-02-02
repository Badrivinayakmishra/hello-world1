# WebScraper PDF Screenshot Capture

This document describes the PDF screenshot capture feature added to the WebScraper connector.

## Overview

The WebScraper connector can now capture PDF screenshots of each webpage during crawling. This allows users to view the original webpage appearance alongside the extracted text content.

## Features

- **Headless Browser Capture**: Uses Playwright to render webpages in a headless Chromium browser
- **PDF Output**: Captures full webpage as PDF (not just visible viewport)
- **Tenant Isolation**: PDF files stored in tenant-specific directories
- **Graceful Fallback**: If Playwright is not installed or fails, crawling continues without screenshots
- **Configurable**: Can enable/disable screenshot capture per connector instance
- **Metadata Integration**: PDF path automatically added to document metadata

## Installation

1. Install Playwright library (already added to requirements.txt):
```bash
pip install playwright==1.40.0
```

2. Install Chromium browser:
```bash
playwright install chromium
```

Or install all supported browsers:
```bash
playwright install
```

## Configuration

### Settings

Add these settings to your WebScraper connector configuration:

```python
settings = {
    "start_url": "https://example.com",
    "capture_screenshots": True,        # Enable/disable screenshot capture (default: True)
    "screenshot_timeout": 30,           # Seconds to wait for page load (default: 30)
    # ... other settings
}
```

### Environment Variables

No special environment variables needed. The feature works with standard Playwright setup.

## File Structure

PDF screenshots are stored in tenant-specific directories:

```
tenant_data/
├── tenant_123/
│   ├── screenshots/
│   │   ├── a1b2c3d4e5f6.pdf          # Screenshot of first webpage
│   │   ├── b2c3d4e5f6g7.pdf          # Screenshot of second webpage
│   │   └── ...
│   └── documents.db
├── tenant_456/
│   ├── screenshots/
│   │   └── ...
│   └── documents.db
└── default/
    ├── screenshots/
    │   └── ...
    └── documents.db
```

**Filename Format**: `{url_hash}.pdf`
- Uses MD5 hash of URL to create unique, deterministic filenames
- Same URL always produces same filename
- Safe for filesystem (no special characters)

## Document Metadata

When a webpage is successfully captured, the document metadata includes:

```python
metadata = {
    "url": "https://example.com/page1",
    "depth": 0,
    "description": "Page meta description",
    "keywords": "page, keywords",
    "word_count": 1234,
    "pdf_path": "tenant_data/tenant_123/screenshots/a1b2c3d4e5f6.pdf",  # ← NEW
    "html_content": "..."  # Original HTML (used for link extraction)
}
```

## Usage Example

### Python

```python
from connectors.webscraper_connector import WebScraperConnector
from connectors.base_connector import ConnectorConfig
import asyncio

async def crawl_with_screenshots():
    config = ConnectorConfig(
        connector_type="webscraper",
        user_id="user_123",
        settings={
            "start_url": "https://example.com",
            "max_depth": 2,
            "max_pages": 10,
            "capture_screenshots": True,
            "screenshot_timeout": 30,
            "rate_limit_delay": 1.0,
        }
    )

    # Initialize connector with tenant_id for proper directory structure
    connector = WebScraperConnector(config, tenant_id="tenant_xyz")

    # Connect and sync
    if await connector.connect():
        documents = await connector.sync()

        # Each document may have a pdf_path in metadata
        for doc in documents:
            if "pdf_path" in doc.metadata:
                print(f"Screenshot: {doc.metadata['pdf_path']}")

        await connector.disconnect()

asyncio.run(crawl_with_screenshots())
```

### API Integration

When using through the integration API:

```python
# In integration_routes.py or your sync handler:
connector = WebScraperConnector(config, tenant_id=current_user.tenant_id)
documents = await connector.sync()

# Store documents in database
for doc in documents:
    # PDF path is in doc.metadata["pdf_path"] if captured
    db_doc = Document(
        title=doc.title,
        content=doc.content,
        source=doc.source,
        metadata=doc.metadata,  # Includes pdf_path if available
        # ... other fields
    )
    db.session.add(db_doc)
```

## Error Handling

The feature includes comprehensive error handling:

### Missing Playwright
If Playwright is not installed, the connector will:
- Log a message: "Playwright not installed, skipping screenshot"
- Continue crawling without screenshots
- Return documents without pdf_path in metadata

### Directory Creation Fails
If screenshots directory cannot be created:
- Log the error
- Continue without screenshots
- Set `screenshots_dir = None`

### Page Load Timeout
If a page takes longer than `screenshot_timeout`:
- Browser will timeout
- Screenshot is skipped for that page
- Crawling continues with next page

### Browser Launch Fails
If Chromium cannot be launched:
- Exception caught in `_capture_screenshot()`
- Screenshot skipped
- Crawling continues

### Async Error Handling
All async operations in `_capture_screenshot()` are wrapped in try-except blocks:
```python
try:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # ... screenshot logic
except Exception as e:
    print(f"[WebScraper] Failed to capture screenshot: {e}")
    return None
```

## Performance Considerations

### Overhead

Capturing screenshots adds overhead to crawling:
- **Per-page time**: +3-5 seconds per page (browser launch, navigation, PDF export)
- **Memory**: ~100MB per browser instance
- **Disk space**: ~50KB-500KB per PDF (depends on page size and complexity)

### Optimization Tips

1. **Disable for large crawls**: Set `capture_screenshots: False` if crawling 100+ pages
2. **Adjust timeout**: Lower `screenshot_timeout` to fail faster on slow pages
3. **Rate limiting**: Increase `rate_limit_delay` to avoid browser launch conflicts

### Estimated Times

```
Single page crawl:
  Without screenshots: ~1 second
  With screenshots: ~4-6 seconds

10-page crawl:
  Without screenshots: ~10-15 seconds
  With screenshots: ~40-60 seconds
```

## Troubleshooting

### "Playwright not installed"
```bash
pip install playwright
playwright install chromium
```

### "Screenshots directory not available"
- Check file permissions on `tenant_data/` directory
- Ensure the backend process can write to the directory
- Check available disk space

### "Browser launch failed"
- Ensure Chromium is installed: `playwright install chromium`
- Check for system dependencies (on Linux: libatomic1, libgconf-2-4, etc.)
- Check available memory

### "Page load timeout"
- Increase `screenshot_timeout` setting
- Check if target website is slow
- Check network connectivity

### Large PDF file sizes
- This is expected for complex websites with images
- Consider disabling screenshots for image-heavy sites
- PDFs are still searchable and usable

## Advanced Configuration

### Custom Playwright Settings

To modify Playwright behavior, edit `_capture_screenshot()` method:

```python
# Change wait_until behavior
await page.goto(url, wait_until="domcontentloaded")  # Faster, may miss dynamic content

# Add cookies/headers
await page.set_extra_http_headers({"X-Custom-Header": "value"})

# Set viewport size
await page.set_viewport_size({"width": 1920, "height": 1080})

# Add delay after loading
await page.wait_for_timeout(2000)  # Wait 2 seconds after load
```

### PDF Export Options

Playwright's `page.pdf()` supports additional options:

```python
await page.pdf(
    path=pdf_path,
    format="A4",                    # Page size
    margin={"top": "1cm", "bottom": "1cm"},
    print_background=True,          # Include background colors/images
    landscape=False,                # Portrait mode
)
```

## Testing

See `test_webscraper_screenshots.py` for example usage:

```bash
python test_webscraper_screenshots.py
```

This test demonstrates:
1. Creating a WebScraper connector with screenshots enabled
2. Crawling a simple website
3. Checking if pdf_path is present in metadata
4. Testing with screenshots disabled

## Storage Considerations

### Cleanup

To clean up old screenshots:
```bash
# Remove all screenshots for a tenant
rm -rf tenant_data/{tenant_id}/screenshots/

# Remove all screenshots
rm -rf tenant_data/*/screenshots/
```

### Backup

PDF files are considered output artifacts and should be backed up like other user data:
```bash
# Backup all tenant data including screenshots
tar -czf backup_tenant_data.tar.gz tenant_data/
```

## Security

### Filename Generation
- Uses MD5 hash of URL, not the URL itself
- Prevents exposing URLs in filesystem
- Deterministic (same URL = same filename)

### File Permissions
- PDF files created with default umask permissions
- Typically 0644 (readable by all, writable by owner)
- Consider restricting directory permissions if needed: `chmod 700 tenant_data/{tenant_id}/screenshots/`

### No Sensitive Data
- PDFs contain only rendered webpage HTML
- No credentials or secrets stored
- Consider what content you're capturing (avoid PII/sensitive sites)

## Logging

Screenshot capture operations are logged with `[WebScraper]` prefix:

```
[WebScraper] Screenshots directory: tenant_data/tenant_123/screenshots
[WebScraper]   Capturing screenshot for: https://example.com/page1
[WebScraper]   ✓ Screenshot saved: tenant_data/tenant_123/screenshots/a1b2c3d4e5f6.pdf
[WebScraper]   ✓ Added screenshot to metadata
```

Watch logs to verify screenshot capture is working.

## Future Enhancements

Potential improvements:
1. **Screenshot formats**: Support PNG, JPEG in addition to PDF
2. **Lazy loading**: Handle dynamically loaded content
3. **JavaScript execution**: Execute custom JS before screenshot
4. **Diff detection**: Only capture if content changed
5. **Compression**: Compress PDF files automatically
6. **CDN delivery**: Upload PDFs to cloud storage
7. **Thumbnail generation**: Create small preview images
8. **Multi-format**: Capture as PDF + image for faster preview

## Related Files

- **Modified**: `/backend/connectors/webscraper_connector.py`
- **Modified**: `/backend/requirements.txt`
- **New**: `/backend/test_webscraper_screenshots.py`
- **New**: `/backend/WEBSCRAPER_SCREENSHOTS.md` (this file)

## References

- [Playwright Python Documentation](https://playwright.dev/python/)
- [Playwright PDF Export](https://playwright.dev/python/docs/api/class-page#page-pdf)
- [Chromium Browser](https://www.chromium.org/)
