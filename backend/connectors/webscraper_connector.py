"""
Website Scraper Connector - Firecrawl API Implementation
Uses Firecrawl API for reliable, managed web scraping.

Firecrawl handles all browser complexity, JavaScript rendering,
and returns clean markdown content ready for LLM processing.
"""

import os
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
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

    Firecrawl provides:
    - JavaScript rendering
    - Clean markdown output
    - Automatic crawling
    - Rate limiting handled
    - No browser management needed
    """

    CONNECTOR_TYPE = "webscraper"
    REQUIRED_CREDENTIALS = []  # API key from env var
    OPTIONAL_SETTINGS = {
        "start_url": "",
        "max_pages": 10,
        "scrape_formats": ["markdown"],  # markdown, html, links, screenshot
        "include_metadata": True,
        "wait_for_timeout": 30000,  # ms to wait for page load
    }

    def __init__(self, config: ConnectorConfig, tenant_id: Optional[str] = None):
        print(f"[WebScraper] __init__ called")
        print(f"[WebScraper] FIRECRAWL_AVAILABLE: {FIRECRAWL_AVAILABLE}")
        print(f"[WebScraper] Config settings: {config.settings}")

        super().__init__(config)
        self.tenant_id = tenant_id
        self.client = None
        self.error_count = 0
        self.success_count = 0

        # Initialize Firecrawl client
        if FIRECRAWL_AVAILABLE:
            api_key = os.getenv("FIRECRAWL_API_KEY")
            print(f"[WebScraper] FIRECRAWL_API_KEY present: {bool(api_key)}")

            if api_key:
                try:
                    self.client = FirecrawlApp(api_key=api_key)
                    print("[WebScraper] Firecrawl client initialized successfully")
                except Exception as e:
                    print(f"[WebScraper] ERROR initializing Firecrawl client: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    self._set_error(f"Failed to initialize Firecrawl: {e}")
            else:
                print("[WebScraper] ERROR: FIRECRAWL_API_KEY not set in environment")
                self._set_error("FIRECRAWL_API_KEY not configured")
        else:
            print(f"[WebScraper] ERROR: Firecrawl not available: {FIRECRAWL_ERROR}")
            self._set_error(f"Firecrawl SDK not installed: {FIRECRAWL_ERROR}")

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        return f"page_{url_hash}"

    async def connect(self) -> bool:
        """Test connection to Firecrawl API"""
        print("[WebScraper] connect() called")

        if not FIRECRAWL_AVAILABLE:
            error_msg = f"Firecrawl SDK not available: {FIRECRAWL_ERROR}"
            print(f"[WebScraper] ERROR: {error_msg}")
            self._set_error(error_msg)
            return False

        if not self.client:
            error_msg = "Firecrawl client not initialized - check FIRECRAWL_API_KEY"
            print(f"[WebScraper] ERROR: {error_msg}")
            self._set_error(error_msg)
            return False

        try:
            self.status = ConnectorStatus.CONNECTING
            start_url = self.config.settings.get("start_url", "").strip()
            print(f"[WebScraper] start_url: {start_url}")

            if not start_url:
                error_msg = "No start_url configured"
                print(f"[WebScraper] ERROR: {error_msg}")
                self._set_error(error_msg)
                return False

            # Ensure URL has protocol
            if not start_url.startswith(("http://", "https://")):
                start_url = "https://" + start_url
                self.config.settings["start_url"] = start_url
                print(f"[WebScraper] Added https prefix: {start_url}")

            # Test connection with a simple scrape
            print(f"[WebScraper] Testing connection by scraping: {start_url}")
            try:
                test_result = self.client.scrape_url(
                    start_url,
                    params={'formats': ['markdown']}
                )
                print(f"[WebScraper] Test scrape successful")
                print(f"[WebScraper] Test result keys: {test_result.keys() if isinstance(test_result, dict) else 'not a dict'}")
            except Exception as e:
                error_msg = f"Failed to connect to {start_url}: {type(e).__name__}: {e}"
                print(f"[WebScraper] ERROR: {error_msg}")
                traceback.print_exc()
                self._set_error(error_msg)
                return False

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print(f"[WebScraper] Connected successfully to {start_url}")
            return True

        except Exception as e:
            error_msg = f"Connection failed: {type(e).__name__}: {e}"
            print(f"[WebScraper] ERROR: {error_msg}")
            traceback.print_exc()
            self._set_error(error_msg)
            return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Crawl website using Firecrawl API"""
        print(f"[WebScraper] ========== SYNC STARTED ==========")
        print(f"[WebScraper] since: {since}")
        print(f"[WebScraper] settings: {self.config.settings}")

        # Connect if not already connected
        if self.status != ConnectorStatus.CONNECTED:
            print(f"[WebScraper] Not connected, attempting connection...")
            if not await self.connect():
                print(f"[WebScraper] Connection failed, returning empty list")
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []
        self.error_count = 0
        self.success_count = 0

        start_url = self.config.settings.get("start_url", "")
        max_pages = self.config.settings.get("max_pages", 10)
        formats = self.config.settings.get("scrape_formats", ["markdown"])

        print(f"[WebScraper] Crawling {start_url}")
        print(f"[WebScraper] Max pages: {max_pages}")
        print(f"[WebScraper] Formats: {formats}")

        try:
            # Use Firecrawl's crawl endpoint for multi-page scraping
            print(f"[WebScraper] Starting crawl job...")

            crawl_params = {
                'limit': max_pages,
                'scrapeOptions': {
                    'formats': formats
                }
            }
            print(f"[WebScraper] Crawl params: {crawl_params}")

            # Start the crawl - this is synchronous and waits for completion
            crawl_result = self.client.crawl_url(
                start_url,
                params=crawl_params,
                poll_interval=2  # Check every 2 seconds
            )

            print(f"[WebScraper] Crawl completed")
            print(f"[WebScraper] Result type: {type(crawl_result)}")

            # Handle the result
            if isinstance(crawl_result, dict):
                print(f"[WebScraper] Result keys: {crawl_result.keys()}")

                # Get the data array
                data = crawl_result.get('data', [])
                if not isinstance(data, list):
                    data = [data] if data else []

                print(f"[WebScraper] Found {len(data)} pages")

                for i, page in enumerate(data):
                    try:
                        print(f"[WebScraper] Processing page {i+1}/{len(data)}")

                        if not isinstance(page, dict):
                            print(f"[WebScraper] WARNING: Page {i} is not a dict: {type(page)}")
                            continue

                        # Extract content
                        content = page.get('markdown', '') or page.get('content', '') or page.get('html', '')
                        url = page.get('url', '') or page.get('sourceURL', '') or start_url

                        # Get metadata
                        metadata = page.get('metadata', {}) or {}
                        title = metadata.get('title', '') or page.get('title', '') or url

                        print(f"[WebScraper] Page URL: {url}")
                        print(f"[WebScraper] Page title: {title[:50] if title else 'No title'}...")
                        print(f"[WebScraper] Content length: {len(content)} chars")

                        if not content or len(content.strip()) < 50:
                            print(f"[WebScraper] Skipping page - too little content")
                            continue

                        # Create document
                        doc = Document(
                            doc_id=f"webscraper_{self._url_to_filename(url)}",
                            source="webscraper",
                            content=content,
                            title=title,
                            metadata={
                                "url": url,
                                "word_count": len(content.split()),
                                "source_metadata": metadata,
                                "scrape_formats": formats,
                            },
                            timestamp=datetime.now(),
                            url=url,
                            doc_type="webpage"
                        )
                        documents.append(doc)
                        self.success_count += 1
                        print(f"[WebScraper] Successfully processed: {title[:50]}...")

                    except Exception as e:
                        print(f"[WebScraper] ERROR processing page {i}: {type(e).__name__}: {e}")
                        traceback.print_exc()
                        self.error_count += 1

            elif isinstance(crawl_result, list):
                # Handle if result is directly a list
                print(f"[WebScraper] Result is a list with {len(crawl_result)} items")
                for i, page in enumerate(crawl_result):
                    try:
                        content = page.get('markdown', '') or page.get('content', '')
                        url = page.get('url', start_url)
                        metadata = page.get('metadata', {})
                        title = metadata.get('title', url)

                        if not content or len(content.strip()) < 50:
                            continue

                        doc = Document(
                            doc_id=f"webscraper_{self._url_to_filename(url)}",
                            source="webscraper",
                            content=content,
                            title=title,
                            metadata={
                                "url": url,
                                "word_count": len(content.split()),
                            },
                            timestamp=datetime.now(),
                            url=url,
                            doc_type="webpage"
                        )
                        documents.append(doc)
                        self.success_count += 1
                    except Exception as e:
                        print(f"[WebScraper] ERROR processing item {i}: {e}")
                        self.error_count += 1
            else:
                print(f"[WebScraper] WARNING: Unexpected result type: {type(crawl_result)}")
                print(f"[WebScraper] Result content: {str(crawl_result)[:500]}")

        except Exception as e:
            error_msg = f"Crawl failed: {type(e).__name__}: {e}"
            print(f"[WebScraper] FATAL ERROR: {error_msg}")
            traceback.print_exc()
            self._set_error(error_msg)
            raise  # Re-raise to let caller handle it

        print(f"[WebScraper] ========== SYNC COMPLETE ==========")
        print(f"[WebScraper] Documents created: {len(documents)}")
        print(f"[WebScraper] Success: {self.success_count}, Errors: {self.error_count}")

        self.status = ConnectorStatus.CONNECTED
        return documents

    async def disconnect(self) -> bool:
        """Disconnect"""
        print("[WebScraper] disconnect() called")
        self.status = ConnectorStatus.DISCONNECTED
        self.client = None
        return True

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific document - not supported for web scraper"""
        return None

    async def test_connection(self) -> bool:
        """Test the connection"""
        print("[WebScraper] test_connection() called")
        return await self.connect()
