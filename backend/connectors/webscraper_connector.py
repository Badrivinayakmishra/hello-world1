"""
Website Scraper Connector - Firecrawl API Implementation
Uses Firecrawl API for reliable, managed web scraping.

This is a SYNCHRONOUS implementation - no async/await.
Firecrawl is a REST API, so we don't need async.
"""

import os
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Any
import hashlib

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

# Firecrawl SDK
FIRECRAWL_AVAILABLE = False
FIRECRAWL_ERROR = None

try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
    print("[WebScraper] Firecrawl SDK imported successfully")
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

        super().__init__(config)
        self.tenant_id = tenant_id
        self.client = None
        self.error_count = 0
        self.success_count = 0

        if FIRECRAWL_AVAILABLE:
            api_key = os.getenv("FIRECRAWL_API_KEY")
            print(f"[WebScraper] FIRECRAWL_API_KEY present: {bool(api_key)}")

            if api_key:
                try:
                    self.client = FirecrawlApp(api_key=api_key)
                    print("[WebScraper] Firecrawl client initialized")
                except Exception as e:
                    print(f"[WebScraper] ERROR init client: {e}")
                    traceback.print_exc()
            else:
                print("[WebScraper] ERROR: FIRECRAWL_API_KEY not set")

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

        # Test with a simple scrape
        print(f"[WebScraper] Testing connection to: {start_url}")
        try:
            result = self.client.scrape_url(start_url, params={'formats': ['markdown']})
            print(f"[WebScraper] Test scrape OK, result type: {type(result)}")
            self.status = ConnectorStatus.CONNECTED
            return True
        except Exception as e:
            print(f"[WebScraper] Test scrape FAILED: {e}")
            traceback.print_exc()
            self._set_error(f"Connection failed: {e}")
            return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Sync - calls sync version"""
        return self._sync_sync(since)

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

            # Call Firecrawl crawl API
            result = self.client.crawl_url(
                start_url,
                params={
                    'limit': max_pages,
                    'scrapeOptions': {'formats': ['markdown']}
                },
                poll_interval=2
            )

            print(f"[WebScraper] Crawl complete, result type: {type(result)}")

            # Process results
            if isinstance(result, dict):
                print(f"[WebScraper] Result keys: {list(result.keys())}")
                data = result.get('data', [])
                if not isinstance(data, list):
                    data = [data] if data else []
            elif isinstance(result, list):
                data = result
            else:
                print(f"[WebScraper] Unexpected result type: {type(result)}")
                data = []

            print(f"[WebScraper] Processing {len(data)} pages")

            for i, page in enumerate(data):
                try:
                    if not isinstance(page, dict):
                        continue

                    content = page.get('markdown', '') or page.get('content', '') or ''
                    url = page.get('url', '') or page.get('sourceURL', '') or start_url
                    metadata = page.get('metadata', {}) or {}
                    title = metadata.get('title', '') or page.get('title', '') or url

                    print(f"[WebScraper] Page {i+1}: {url[:60]}... ({len(content)} chars)")

                    if len(content.strip()) < 50:
                        print(f"[WebScraper] Skipping - too short")
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
                    print(f"[WebScraper] Error on page {i}: {e}")
                    self.error_count += 1

        except Exception as e:
            print(f"[WebScraper] CRAWL FAILED: {e}")
            traceback.print_exc()
            self._set_error(str(e))
            raise

        print(f"[WebScraper] ========== SYNC DONE ==========")
        print(f"[WebScraper] Documents: {len(documents)}, Errors: {self.error_count}")

        self.status = ConnectorStatus.CONNECTED
        return documents

    async def disconnect(self) -> bool:
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def get_document(self, doc_id: str) -> Optional[Document]:
        return None

    async def test_connection(self) -> bool:
        return self._connect_sync()
