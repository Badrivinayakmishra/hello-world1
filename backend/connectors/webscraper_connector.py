"""
Website Scraper Connector
Crawls websites to extract protocols, documentation, and other content.
Useful for scraping PI lab websites, documentation sites, etc.
"""

import os
import re
import time
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
from collections import deque

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

try:
    import requests
    from bs4 import BeautifulSoup
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False


class WebScraperConnector(BaseConnector):
    """
    Website scraper connector for extracting content from websites.

    Features:
    - Crawls starting URL and follows internal links
    - Extracts text from HTML pages
    - Downloads and parses PDFs
    - Respects max depth and max pages limits
    - Same-domain restriction (no external links)
    - Configurable rate limiting
    """

    CONNECTOR_TYPE = "webscraper"
    REQUIRED_CREDENTIALS = []
    OPTIONAL_SETTINGS = {
        "start_url": "",  # Required - starting URL to crawl
        "priority_paths": [],  # Optional - paths to prioritize (e.g., ["/resources/", "/protocols/"])
        "max_depth": 3,  # Maximum link depth from start URL
        "max_pages": 50,  # Maximum pages to crawl
        "include_pdfs": True,  # Download and parse PDFs
        "rate_limit_delay": 1.0,  # Seconds between requests
        "allowed_extensions": [".html", ".htm", ".pdf", ""],  # Empty string = no extension (index pages)
        "exclude_patterns": ["#", "mailto:", "tel:"],  # URL patterns to exclude
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.visited_urls: Set[str] = set()
        self.session = None
        self.base_domain = None

    async def connect(self) -> bool:
        """Test website connection"""
        if not SCRAPER_AVAILABLE:
            self._set_error("BeautifulSoup4 and requests not installed. Run: pip install beautifulsoup4 requests")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING

            start_url = self.config.settings.get("start_url", "").strip()
            if not start_url:
                self._set_error("No start_url configured. Please set 'start_url' in settings.")
                return False

            # Validate URL
            if not start_url.startswith(("http://", "https://")):
                start_url = "https://" + start_url
                self.config.settings["start_url"] = start_url

            # Extract base domain
            parsed = urlparse(start_url)
            self.base_domain = f"{parsed.scheme}://{parsed.netloc}"

            # Create session
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (compatible; 2ndBrainBot/1.0; +https://github.com/your-repo)"
            })

            # Test connection
            response = self.session.get(start_url, timeout=10, allow_redirects=True)
            if response.status_code != 200:
                self._set_error(f"Failed to connect: HTTP {response.status_code}")
                return False

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print(f"[WebScraper] Connected to {start_url}")
            return True

        except Exception as e:
            self._set_error(f"Failed to connect: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect"""
        if self.session:
            self.session.close()
        self.visited_urls.clear()
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Test connection"""
        return await self.connect()

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Crawl website and extract content.

        Args:
            since: Not used for web scraping (always fetches current content)

        Returns:
            List of Document objects
        """
        if self.status != ConnectorStatus.CONNECTED:
            if not await self.connect():
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            start_url = self.config.settings["start_url"]
            max_depth = self.config.settings.get("max_depth", 3)
            max_pages = self.config.settings.get("max_pages", 50)
            priority_paths = self.config.settings.get("priority_paths", [])
            rate_limit = self.config.settings.get("rate_limit_delay", 1.0)

            print(f"[WebScraper] Starting crawl from {start_url}")
            print(f"[WebScraper] Max depth: {max_depth}, Max pages: {max_pages}")
            if priority_paths:
                print(f"[WebScraper] Priority paths: {priority_paths}")

            # BFS crawl with priority queue
            # Format: (url, depth, is_priority)
            queue = deque([(start_url, 0, False)])
            priority_queue = deque()

            # Add priority URLs to front of queue
            if priority_paths:
                for path in priority_paths:
                    priority_url = urljoin(start_url, path)
                    priority_queue.append((priority_url, 1, True))

            self.visited_urls.clear()
            pages_crawled = 0

            # Process priority URLs first
            while priority_queue and pages_crawled < max_pages:
                url, depth, _ = priority_queue.popleft()

                if url in self.visited_urls:
                    continue

                doc = await self._crawl_page(url, depth)
                if doc:
                    documents.append(doc)
                    pages_crawled += 1
                    print(f"[WebScraper] Crawled priority page {pages_crawled}/{max_pages}: {url}")

                    # Extract links from priority pages
                    if depth < max_depth:
                        links = self._extract_links(doc.metadata.get("html_content", ""), url)
                        for link in links:
                            if link not in self.visited_urls:
                                queue.append((link, depth + 1, False))

                time.sleep(rate_limit)

            # Process regular queue
            while queue and pages_crawled < max_pages:
                url, depth, _ = queue.popleft()

                if url in self.visited_urls:
                    continue

                if depth > max_depth:
                    continue

                doc = await self._crawl_page(url, depth)
                if doc:
                    documents.append(doc)
                    pages_crawled += 1
                    print(f"[WebScraper] Crawled page {pages_crawled}/{max_pages}: {url}")

                    # Extract links and add to queue
                    if depth < max_depth:
                        links = self._extract_links(doc.metadata.get("html_content", ""), url)
                        for link in links:
                            if link not in self.visited_urls:
                                queue.append((link, depth + 1, False))

                time.sleep(rate_limit)

            print(f"[WebScraper] Crawl complete. Pages: {pages_crawled}, Documents: {len(documents)}")

            self.config.last_sync = datetime.now()
            self.status = ConnectorStatus.CONNECTED
            self._clear_error()

        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            print(f"[WebScraper] Sync error: {e}")
            import traceback
            traceback.print_exc()

        return documents

    async def _crawl_page(self, url: str, depth: int) -> Optional[Document]:
        """
        Crawl a single page and extract content.

        Args:
            url: URL to crawl
            depth: Current depth from start URL

        Returns:
            Document object or None
        """
        try:
            # Mark as visited
            self.visited_urls.add(url)

            # Check if URL should be excluded
            exclude_patterns = self.config.settings.get("exclude_patterns", [])
            if any(pattern in url for pattern in exclude_patterns):
                return None

            # Check allowed extensions
            allowed_extensions = self.config.settings.get("allowed_extensions", [])
            url_path = urlparse(url).path.lower()
            if allowed_extensions:
                if not any(url_path.endswith(ext) for ext in allowed_extensions):
                    return None

            # Fetch page
            response = self.session.get(url, timeout=30, allow_redirects=True)
            if response.status_code != 200:
                print(f"[WebScraper] Failed to fetch {url}: HTTP {response.status_code}")
                return None

            content_type = response.headers.get("Content-Type", "").lower()

            # Handle PDF
            if "application/pdf" in content_type or url_path.endswith(".pdf"):
                if self.config.settings.get("include_pdfs", True):
                    return self._parse_pdf(url, response.content)
                return None

            # Handle HTML
            if "text/html" in content_type or not content_type:
                return self._parse_html(url, response.text, depth)

            return None

        except Exception as e:
            print(f"[WebScraper] Error crawling {url}: {e}")
            return None

    def _parse_html(self, url: str, html_content: str, depth: int) -> Optional[Document]:
        """Parse HTML page and extract text content"""
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Extract title
            title = soup.find("title")
            title_text = title.get_text().strip() if title else urlparse(url).path

            # Extract main content
            # Try to find main content area
            main_content = (
                soup.find("main") or
                soup.find("article") or
                soup.find("div", class_=re.compile(r"content|main|body", re.I)) or
                soup.find("body") or
                soup
            )

            # Extract text
            text = main_content.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            content = "\n\n".join(lines)

            if len(content) < 100:  # Skip pages with very little content
                return None

            # Extract metadata
            description = soup.find("meta", attrs={"name": "description"})
            description_text = description.get("content", "").strip() if description else ""

            keywords = soup.find("meta", attrs={"name": "keywords"})
            keywords_text = keywords.get("content", "").strip() if keywords else ""

            return Document(
                doc_id=f"webscraper_{self._url_to_id(url)}",
                source="webscraper",
                content=content,
                title=title_text,
                metadata={
                    "url": url,
                    "depth": depth,
                    "description": description_text,
                    "keywords": keywords_text,
                    "word_count": len(content.split()),
                    "html_content": html_content  # Store for link extraction
                },
                timestamp=datetime.now(),
                url=url,
                doc_type="webpage"
            )

        except Exception as e:
            print(f"[WebScraper] Error parsing HTML from {url}: {e}")
            return None

    def _parse_pdf(self, url: str, pdf_content: bytes) -> Optional[Document]:
        """Parse PDF content"""
        try:
            import PyPDF2
            import io

            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
            text_parts = []

            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    text_parts.append(f"--- Page {page_num} ---\n{text}")

            content = "\n\n".join(text_parts)

            if len(content) < 100:
                return None

            # Extract title from URL or PDF metadata
            title = urlparse(url).path.split("/")[-1]
            if pdf_reader.metadata and pdf_reader.metadata.title:
                title = pdf_reader.metadata.title

            return Document(
                doc_id=f"webscraper_{self._url_to_id(url)}",
                source="webscraper",
                content=content,
                title=title,
                metadata={
                    "url": url,
                    "content_type": "pdf",
                    "page_count": len(pdf_reader.pages),
                    "word_count": len(content.split())
                },
                timestamp=datetime.now(),
                url=url,
                doc_type="pdf"
            )

        except Exception as e:
            print(f"[WebScraper] Error parsing PDF from {url}: {e}")
            return None

    def _extract_links(self, html_content: str, base_url: str) -> List[str]:
        """Extract and filter links from HTML content"""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            links = []

            for anchor in soup.find_all("a", href=True):
                href = anchor["href"].strip()

                # Skip empty, anchor, mailto, tel links
                if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                    continue

                # Convert to absolute URL
                absolute_url = urljoin(base_url, href)

                # Remove fragment
                absolute_url = absolute_url.split("#")[0]

                # Check if same domain
                parsed = urlparse(absolute_url)
                url_domain = f"{parsed.scheme}://{parsed.netloc}"

                if url_domain == self.base_domain:
                    links.append(absolute_url)

            return list(set(links))  # Deduplicate

        except Exception as e:
            print(f"[WebScraper] Error extracting links: {e}")
            return []

    def _url_to_id(self, url: str) -> str:
        """Convert URL to a unique ID"""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific document by ID"""
        # Not implemented for web scraper
        return None
