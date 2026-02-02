"""
Website Scraper Connector - Firecrawl API Implementation
Uses Firecrawl API for reliable, managed web scraping.

This is a SYNCHRONOUS implementation - no async/await.
Firecrawl is a REST API, so we don't need async.

SDK v2 API (firecrawl-py >= 1.0.0):
- from firecrawl import Firecrawl
- client = Firecrawl(api_key="...")
- client.scrape(url, formats=['markdown'])
- client.crawl(url, limit=N, scrape_options=ScrapeOptions(...))
"""

import os
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Any
import hashlib

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

# Firecrawl SDK - Try multiple import patterns for compatibility
FIRECRAWL_AVAILABLE = False
FIRECRAWL_ERROR = None
FIRECRAWL_VERSION = None
FirecrawlClient = None

# Try v2 SDK first (Firecrawl class)
try:
    from firecrawl import Firecrawl
    FirecrawlClient = Firecrawl
    FIRECRAWL_AVAILABLE = True
    FIRECRAWL_VERSION = "v2"
    print("[WebScraper] Firecrawl SDK v2 imported successfully (Firecrawl class)")
except ImportError:
    pass

# Try v1 SDK (FirecrawlApp class) as fallback
if not FIRECRAWL_AVAILABLE:
    try:
        from firecrawl import FirecrawlApp
        FirecrawlClient = FirecrawlApp
        FIRECRAWL_AVAILABLE = True
        FIRECRAWL_VERSION = "v1"
        print("[WebScraper] Firecrawl SDK v1 imported successfully (FirecrawlApp class)")
    except ImportError as e:
        FIRECRAWL_ERROR = str(e)
        print(f"[WebScraper] Firecrawl SDK not installed: {e}")
        print("[WebScraper] Install with: pip install firecrawl-py")
    except Exception as e:
        FIRECRAWL_ERROR = str(e)
        print(f"[WebScraper] Error importing Firecrawl: {e}")


class WebScraperConnector(BaseConnector):
    """
    Website scraper using Firecrawl API.

    SYNCHRONOUS implementation - works with gevent workers.
    """

    CONNECTOR_TYPE = "webscraper"
    REQUIRED_CREDENTIALS = []
    OPTIONAL_SETTINGS = {
        "start_url": "",
        "max_pages": 10,
        "scrape_formats": ["markdown"],
    }

    def __init__(self, config: ConnectorConfig, tenant_id: Optional[str] = None):
        print(f"[WebScraper] __init__ called")
        print(f"[WebScraper] FIRECRAWL_AVAILABLE: {FIRECRAWL_AVAILABLE}")
        print(f"[WebScraper] FIRECRAWL_VERSION: {FIRECRAWL_VERSION}")

        super().__init__(config)
        self.tenant_id = tenant_id
        self.client = None
        self.error_count = 0
        self.success_count = 0

        if FIRECRAWL_AVAILABLE and FirecrawlClient:
            api_key = os.getenv("FIRECRAWL_API_KEY")
            print(f"[WebScraper] FIRECRAWL_API_KEY present: {bool(api_key)}")
            if api_key:
                print(f"[WebScraper] API key length: {len(api_key)}")
                print(f"[WebScraper] API key prefix: {api_key[:10]}...")

            if api_key:
                try:
                    self.client = FirecrawlClient(api_key=api_key)
                    print(f"[WebScraper] Firecrawl client initialized (version: {FIRECRAWL_VERSION})")
                    # Log available methods for debugging
                    methods = [m for m in dir(self.client) if not m.startswith('_')]
                    print(f"[WebScraper] Client methods: {methods}")
                except Exception as e:
                    print(f"[WebScraper] ERROR init client: {e}")
                    traceback.print_exc()
            else:
                print("[WebScraper] ERROR: FIRECRAWL_API_KEY not set")
        else:
            print(f"[WebScraper] ERROR: Firecrawl not available: {FIRECRAWL_ERROR}")

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        return f"page_{hashlib.sha256(url.encode()).hexdigest()[:16]}"

    # SYNCHRONOUS methods - override async base class methods
    async def connect(self) -> bool:
        """Test connection - calls sync version"""
        return self._connect_sync()

    def _connect_sync(self) -> bool:
        """Synchronous connect"""
        print("[WebScraper] _connect_sync() called")

        if not FIRECRAWL_AVAILABLE:
            print(f"[WebScraper] ERROR: Firecrawl not available: {FIRECRAWL_ERROR}")
            self._set_error(f"Firecrawl not available: {FIRECRAWL_ERROR}")
            return False

        if not self.client:
            print("[WebScraper] ERROR: No client - check FIRECRAWL_API_KEY")
            self._set_error("Firecrawl client not initialized")
            return False

        start_url = self.config.settings.get("start_url", "").strip()
        print(f"[WebScraper] start_url: {start_url}")

        if not start_url:
            print("[WebScraper] ERROR: No start_url")
            self._set_error("No start_url configured")
            return False

        if not start_url.startswith(("http://", "https://")):
            start_url = "https://" + start_url
            self.config.settings["start_url"] = start_url

        # Test with a simple scrape - detect available method
        print(f"[WebScraper] Testing connection to: {start_url}")
        try:
            result = self._do_scrape(start_url)
            print(f"[WebScraper] Test scrape OK, result type: {type(result)}")
            if result:
                print(f"[WebScraper] Test scrape result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
            self.status = ConnectorStatus.CONNECTED
            return True
        except Exception as e:
            print(f"[WebScraper] Test scrape FAILED: {e}")
            traceback.print_exc()
            self._set_error(f"Connection failed: {e}")
            return False

    def _do_scrape(self, url: str) -> Dict[str, Any]:
        """
        Perform a single-page scrape with SDK version detection.
        Tries multiple method signatures for compatibility.
        """
        print(f"[WebScraper] _do_scrape({url})")

        # Try v2 API: client.scrape(url, formats=['markdown'])
        if hasattr(self.client, 'scrape'):
            print("[WebScraper] Using v2 API: scrape()")
            try:
                result = self.client.scrape(url, formats=['markdown'])
                print(f"[WebScraper] scrape() succeeded")
                return result if isinstance(result, dict) else {'markdown': str(result)}
            except TypeError as te:
                # Maybe different signature - try with params dict
                print(f"[WebScraper] scrape() TypeError: {te}, trying alternate signature")
                try:
                    result = self.client.scrape(url, params={'formats': ['markdown']})
                    print(f"[WebScraper] scrape(params=...) succeeded")
                    return result if isinstance(result, dict) else {'markdown': str(result)}
                except Exception as e2:
                    print(f"[WebScraper] scrape(params=...) also failed: {e2}")
                    raise

        # Try v1 API: client.scrape_url(url, params={...})
        if hasattr(self.client, 'scrape_url'):
            print("[WebScraper] Using v1 API: scrape_url()")
            result = self.client.scrape_url(url, params={'formats': ['markdown']})
            print(f"[WebScraper] scrape_url() succeeded")
            return result if isinstance(result, dict) else {'markdown': str(result)}

        raise AttributeError(f"Firecrawl client has no scrape method. Available: {dir(self.client)}")

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Sync - calls sync version"""
        return self._sync_sync(since)

    def _do_crawl(self, url: str, max_pages: int) -> List[Dict[str, Any]]:
        """
        Perform a multi-page crawl with SDK version detection.
        Returns list of page data dictionaries.
        """
        print(f"[WebScraper] _do_crawl({url}, max_pages={max_pages})")

        # Try v2 API: client.crawl(url, limit=N, ...)
        if hasattr(self.client, 'crawl'):
            print("[WebScraper] Using v2 API: crawl()")
            try:
                # v2 API uses keyword args directly
                result = self.client.crawl(
                    url,
                    limit=max_pages,
                    poll_interval=5
                )
                print(f"[WebScraper] crawl() succeeded, type: {type(result)}")
                return self._extract_crawl_data(result)
            except TypeError as te:
                # Try alternate signature with scrape_options
                print(f"[WebScraper] crawl() TypeError: {te}, trying alternate signature")
                try:
                    result = self.client.crawl(
                        url,
                        params={
                            'limit': max_pages,
                            'scrapeOptions': {'formats': ['markdown']}
                        },
                        poll_interval=5
                    )
                    print(f"[WebScraper] crawl(params=...) succeeded")
                    return self._extract_crawl_data(result)
                except Exception as e2:
                    print(f"[WebScraper] crawl(params=...) also failed: {e2}")
                    # Fall through to try other methods

        # Try v1 API: client.crawl_url(url, params={...})
        if hasattr(self.client, 'crawl_url'):
            print("[WebScraper] Using v1 API: crawl_url()")
            result = self.client.crawl_url(
                url,
                params={
                    'limit': max_pages,
                    'scrapeOptions': {'formats': ['markdown']}
                },
                poll_interval=5
            )
            print(f"[WebScraper] crawl_url() succeeded, type: {type(result)}")
            return self._extract_crawl_data(result)

        # Try async crawl with polling as fallback
        if hasattr(self.client, 'start_crawl') and hasattr(self.client, 'get_crawl_status'):
            print("[WebScraper] Using async crawl API: start_crawl() + get_crawl_status()")
            import time
            job = self.client.start_crawl(url, limit=max_pages)
            job_id = job.get('id') or job.get('jobId')
            print(f"[WebScraper] Crawl job started: {job_id}")

            # Poll for completion
            for attempt in range(60):  # Max 5 minutes (60 * 5s)
                time.sleep(5)
                status = self.client.get_crawl_status(job_id)
                state = status.get('status', status.get('state', 'unknown'))
                print(f"[WebScraper] Crawl status ({attempt+1}): {state}")

                if state in ('completed', 'done', 'finished'):
                    return self._extract_crawl_data(status)
                elif state in ('failed', 'error'):
                    raise Exception(f"Crawl job failed: {status}")

            raise Exception("Crawl job timed out after 5 minutes")

        raise AttributeError(f"Firecrawl client has no crawl method. Available: {dir(self.client)}")

    def _extract_crawl_data(self, result: Any) -> List[Dict[str, Any]]:
        """Extract page data from crawl result, handling different response formats."""
        print(f"[WebScraper] _extract_crawl_data, result type: {type(result)}")
        print(f"[WebScraper] Result repr: {repr(result)[:500]}")

        if result is None:
            print("[WebScraper] Result is None")
            return []

        # Handle Firecrawl v2 CrawlJob object - access .data attribute
        if hasattr(result, 'data'):
            print(f"[WebScraper] Result has .data attribute, type: {type(result.data)}")
            data = result.data
            if data is not None:
                return self._extract_crawl_data(data)  # Recursively process the data
            print("[WebScraper] .data attribute is None")

        # If result is already a list
        if isinstance(result, list):
            print(f"[WebScraper] Result is list with {len(result)} items")
            if len(result) > 0:
                print(f"[WebScraper] First item type: {type(result[0])}")
                # Check if list items are ScrapeResult objects with attributes
                if hasattr(result[0], 'markdown') or hasattr(result[0], 'content'):
                    print("[WebScraper] List items are ScrapeResult objects, converting to dicts")
                    converted = []
                    for item in result:
                        item_dict = {}
                        # Extract all relevant attributes
                        for attr in ['markdown', 'content', 'html', 'text', 'url', 'sourceURL', 'source_url', 'title', 'metadata']:
                            if hasattr(item, attr):
                                val = getattr(item, attr)
                                if val is not None:
                                    item_dict[attr] = val
                        if item_dict:
                            converted.append(item_dict)
                            print(f"[WebScraper] Converted item: {list(item_dict.keys())}")
                    return converted
            return result

        # If result is a dict, look for data key
        if isinstance(result, dict):
            print(f"[WebScraper] Result keys: {list(result.keys())}")

            # Try common data keys
            for key in ['data', 'results', 'pages', 'documents']:
                if key in result:
                    data = result[key]
                    if isinstance(data, list):
                        print(f"[WebScraper] Found {len(data)} items in '{key}'")
                        return self._extract_crawl_data(data)  # Recursively process
                    elif data:
                        print(f"[WebScraper] '{key}' is not a list, wrapping")
                        return [data]

            # Maybe the dict IS the data (single page result)
            if 'markdown' in result or 'content' in result or 'url' in result:
                print("[WebScraper] Result looks like single page data")
                return [result]

        # Check if result is a typed object with attributes (like ScrapeResult)
        if hasattr(result, 'markdown') or hasattr(result, 'content') or hasattr(result, 'url'):
            print("[WebScraper] Result is a typed object with content attributes")
            item_dict = {}
            for attr in ['markdown', 'content', 'html', 'text', 'url', 'sourceURL', 'source_url', 'title', 'metadata']:
                if hasattr(result, attr):
                    val = getattr(result, attr)
                    if val is not None:
                        item_dict[attr] = val
            if item_dict:
                print(f"[WebScraper] Converted single object: {list(item_dict.keys())}")
                return [item_dict]

        # Last resort: try to iterate if it's iterable (but NOT for CrawlJob-like objects)
        # This was causing the tuple issue - CrawlJob iterates as key-value pairs
        type_name = type(result).__name__.lower()
        if 'job' not in type_name and 'result' not in type_name:
            try:
                data = list(result)
                print(f"[WebScraper] Converted iterable to list: {len(data)} items")
                # Verify items are dicts
                if data and isinstance(data[0], dict):
                    return data
                print(f"[WebScraper] List items are not dicts: {type(data[0]) if data else 'empty'}")
            except (TypeError, ValueError):
                pass

        print(f"[WebScraper] Could not extract data from result")
        return []

    def _sync_sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Synchronous sync"""
        print(f"[WebScraper] ========== SYNC START ==========")

        if self.status != ConnectorStatus.CONNECTED:
            if not self._connect_sync():
                print("[WebScraper] Connection failed")
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        start_url = self.config.settings.get("start_url", "")
        max_pages = self.config.settings.get("max_pages", 10)

        print(f"[WebScraper] Crawling: {start_url}")
        print(f"[WebScraper] Max pages: {max_pages}")

        try:
            print("[WebScraper] Starting Firecrawl crawl...")

            # Call appropriate crawl method based on SDK version
            data = self._do_crawl(start_url, max_pages)

            print(f"[WebScraper] Processing {len(data)} pages")

            for i, page in enumerate(data):
                try:
                    if not isinstance(page, dict):
                        print(f"[WebScraper] Page {i} is not a dict: {type(page)}")
                        continue

                    # Extract content - try multiple keys
                    content = (
                        page.get('markdown') or
                        page.get('content') or
                        page.get('text') or
                        page.get('html') or
                        ''
                    )

                    # Extract URL
                    url = (
                        page.get('url') or
                        page.get('sourceURL') or
                        page.get('source_url') or
                        start_url
                    )

                    # Extract metadata and title
                    metadata = page.get('metadata', {}) or {}
                    title = (
                        metadata.get('title') or
                        page.get('title') or
                        metadata.get('og:title') or
                        url
                    )

                    print(f"[WebScraper] Page {i+1}: {url[:60]}... ({len(content)} chars)")

                    if len(content.strip()) < 50:
                        print(f"[WebScraper] Skipping - too short ({len(content.strip())} chars)")
                        continue

                    doc = Document(
                        doc_id=f"webscraper_{self._url_to_filename(url)}",
                        source="webscraper",
                        content=content,
                        title=title,
                        metadata={"url": url, "word_count": len(content.split())},
                        timestamp=datetime.now(),
                        url=url,
                        doc_type="webpage"
                    )
                    documents.append(doc)
                    self.success_count += 1

                except Exception as e:
                    print(f"[WebScraper] Error processing page {i}: {e}")
                    traceback.print_exc()
                    self.error_count += 1

        except Exception as e:
            print(f"[WebScraper] CRAWL FAILED: {e}")
            traceback.print_exc()
            self._set_error(str(e))
            raise

        print(f"[WebScraper] ========== SYNC DONE ==========")
        print(f"[WebScraper] Documents: {len(documents)}, Success: {self.success_count}, Errors: {self.error_count}")

        self.status = ConnectorStatus.CONNECTED
        return documents

    async def disconnect(self) -> bool:
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def get_document(self, doc_id: str) -> Optional[Document]:
        return None

    async def test_connection(self) -> bool:
        return self._connect_sync()
