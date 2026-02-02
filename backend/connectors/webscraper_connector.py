"""
Website Scraper Connector - Powered by Crawl4AI
Uses Crawl4AI for LLM-friendly web crawling with JavaScript rendering,
clean markdown extraction, and screenshot capture.

Features:
- Crawl4AI integration (59k+ GitHub stars)
- JavaScript rendering via Playwright
- Clean markdown extraction (LLM-ready)
- Screenshot/PDF capture
- Robots.txt compliance
- Sitemap discovery
- Comprehensive URL filtering
- Timeout handling
- Memory-efficient crawling
"""

import os
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import hashlib
import base64

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

# Try to import Crawl4AI
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    print("[WebScraper] Crawl4AI not installed. Run: pip install crawl4ai && crawl4ai-setup")

# Fallback imports
try:
    import requests
    from bs4 import BeautifulSoup
    FALLBACK_AVAILABLE = True
except ImportError:
    FALLBACK_AVAILABLE = False


class WebScraperConnector(BaseConnector):
    """
    Website scraper connector powered by Crawl4AI.

    Features:
    - JavaScript rendering for dynamic pages
    - Clean markdown extraction (LLM-ready)
    - Built-in screenshot capture
    - Smart link discovery and crawling
    - Respects max depth and max pages limits
    - Same-domain restriction
    - Robots.txt compliance
    - Sitemap discovery
    """

    CONNECTOR_TYPE = "webscraper"
    REQUIRED_CREDENTIALS = []
    OPTIONAL_SETTINGS = {
        "start_url": "",
        "max_depth": 2,
        "max_pages": 20,
        "include_pdfs": True,
        "wait_for_js": True,
        "screenshot": True,
        "respect_robots_txt": True,
        "use_sitemap": True,
        "crawl_delay": 1.0,  # Seconds between requests
        "timeout": 30,  # Seconds per page
        "exclude_patterns": [
            # Protocols
            "#", "mailto:", "tel:", "javascript:", "data:", "file:",
            # Authentication
            "login", "signin", "signup", "register", "logout", "logoff", "signout",
            "/auth/", "/account/", "/user/", "/profile/", "/dashboard/", "/settings/",
            "/admin/", "/password", "/forgot", "/reset", "/verify",
            # E-commerce
            "cart", "checkout", "/basket", "/order", "/payment", "/billing",
            # Search & filters
            "/search", "?search=", "?q=", "?query=", "?sort=", "?filter=",
            # Tracking
            "?utm_", "?fbclid=", "?gclid=", "?ref=", "?session",
            # API & system
            "/api/", "/v1/", "/v2/", "/graphql", "/webhook",
            # Dev/test
            "/test/", "/staging/", "/dev/", "/debug",
        ],
    }

    # Bot identification with contact info
    BOT_USER_AGENT = "Mozilla/5.0 (compatible; 2ndBrainBot/1.0; +https://2ndbrain.app/bot-policy) Enterprise Knowledge Crawler"

    def __init__(self, config: ConnectorConfig, tenant_id: Optional[str] = None):
        super().__init__(config)
        self.tenant_id = tenant_id
        self.visited_urls: Set[str] = set()
        self.base_domain = None
        self.robots_parser: Optional[RobotFileParser] = None
        self.sitemap_urls: List[str] = []
        self.error_count = 0
        self.success_count = 0

    def _get_screenshots_dir(self) -> str:
        """Get directory for storing screenshots"""
        base_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tenant_data",
            self.tenant_id or "default",
            "screenshots"
        )
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename using SHA256 (collision-resistant)"""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        return f"screenshot_{url_hash}"

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to prevent duplicates"""
        if not url:
            return ""

        # Parse the URL
        parsed = urlparse(url)

        # Lowercase scheme and domain
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()

        # Remove default ports
        if netloc.endswith(":80") and scheme == "http":
            netloc = netloc[:-3]
        elif netloc.endswith(":443") and scheme == "https":
            netloc = netloc[:-4]

        # Remove trailing slash from path (unless it's just "/")
        path = parsed.path
        if path != "/" and path.endswith("/"):
            path = path[:-1]

        # Remove fragment
        # Keep query for now (some pages need it)

        return f"{scheme}://{netloc}{path}"

    async def _load_robots_txt(self) -> bool:
        """Load and parse robots.txt"""
        if not self.config.settings.get("respect_robots_txt", True):
            return True

        try:
            robots_url = f"{self.base_domain}/robots.txt"
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()

            # Extract sitemap URLs from robots.txt
            if FALLBACK_AVAILABLE:
                response = requests.get(robots_url, timeout=10, headers={
                    "User-Agent": self.BOT_USER_AGENT
                })
                if response.status_code == 200:
                    for line in response.text.splitlines():
                        if line.lower().startswith("sitemap:"):
                            sitemap_url = line.split(":", 1)[1].strip()
                            self.sitemap_urls.append(sitemap_url)
                            print(f"[WebScraper] Found sitemap: {sitemap_url}")

            print(f"[WebScraper] Loaded robots.txt from {robots_url}")
            return True
        except Exception as e:
            print(f"[WebScraper] Could not load robots.txt: {e}")
            return True  # Continue crawling if robots.txt unavailable

    def _is_allowed_by_robots(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        if not self.robots_parser:
            return True
        try:
            return self.robots_parser.can_fetch(self.BOT_USER_AGENT, url)
        except Exception:
            return True

    async def _discover_sitemap_urls(self) -> List[str]:
        """Discover URLs from sitemap.xml"""
        if not self.config.settings.get("use_sitemap", True):
            return []

        urls = []

        # Check standard sitemap location if not found in robots.txt
        if not self.sitemap_urls:
            self.sitemap_urls = [f"{self.base_domain}/sitemap.xml"]

        for sitemap_url in self.sitemap_urls[:3]:  # Limit to 3 sitemaps
            try:
                if not FALLBACK_AVAILABLE:
                    continue

                response = requests.get(sitemap_url, timeout=10, headers={
                    "User-Agent": self.BOT_USER_AGENT
                })

                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.content, "xml")

                # Check if it's a sitemap index
                sitemaps = soup.find_all("sitemap")
                if sitemaps:
                    for sitemap in sitemaps[:5]:  # Limit nested sitemaps
                        loc = sitemap.find("loc")
                        if loc:
                            # Recursively add child sitemap URLs
                            self.sitemap_urls.append(loc.text)
                    continue

                # Extract URLs from sitemap
                for url_tag in soup.find_all("url"):
                    loc = url_tag.find("loc")
                    if loc and loc.text:
                        normalized = self._normalize_url(loc.text)
                        if normalized.startswith(self.base_domain):
                            urls.append(normalized)

                print(f"[WebScraper] Found {len(urls)} URLs in sitemap")

            except Exception as e:
                print(f"[WebScraper] Could not parse sitemap {sitemap_url}: {e}")

        return urls[:100]  # Limit sitemap URLs

    async def connect(self) -> bool:
        """Test website connection"""
        if not CRAWL4AI_AVAILABLE and not FALLBACK_AVAILABLE:
            self._set_error("Neither Crawl4AI nor fallback libraries installed")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING
            start_url = self.config.settings.get("start_url", "").strip()

            if not start_url:
                self._set_error("No start_url configured")
                return False

            if not start_url.startswith(("http://", "https://")):
                start_url = "https://" + start_url
                self.config.settings["start_url"] = start_url

            parsed = urlparse(start_url)
            self.base_domain = f"{parsed.scheme}://{parsed.netloc}"

            # Quick connectivity check
            if FALLBACK_AVAILABLE:
                response = requests.head(
                    start_url,
                    timeout=10,
                    allow_redirects=True,
                    headers={"User-Agent": self.BOT_USER_AGENT}
                )
                if response.status_code >= 400:
                    self._set_error(f"Failed to connect: HTTP {response.status_code}")
                    return False

            # Load robots.txt
            await self._load_robots_txt()

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print(f"[WebScraper] Connected to {start_url}")
            return True

        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Crawl website using Crawl4AI"""
        print(f"[WebScraper] === SYNC STARTED ===")

        if self.status != ConnectorStatus.CONNECTED:
            if not await self.connect():
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []
        self.error_count = 0
        self.success_count = 0

        start_url = self.config.settings["start_url"]
        max_depth = self.config.settings.get("max_depth", 2)
        max_pages = self.config.settings.get("max_pages", 20)
        wait_for_js = self.config.settings.get("wait_for_js", True)
        take_screenshot = self.config.settings.get("screenshot", True)
        exclude_patterns = self.config.settings.get("exclude_patterns", [])

        print(f"[WebScraper] Starting crawl from {start_url}")
        print(f"[WebScraper] Max depth: {max_depth}, Max pages: {max_pages}")
        print(f"[WebScraper] Using Crawl4AI: {CRAWL4AI_AVAILABLE}")

        self.visited_urls.clear()

        # Discover sitemap URLs first (faster than link crawling)
        sitemap_urls = await self._discover_sitemap_urls()
        if sitemap_urls:
            print(f"[WebScraper] Using {len(sitemap_urls)} URLs from sitemap")

        if CRAWL4AI_AVAILABLE:
            documents = await self._crawl_with_crawl4ai(
                start_url, max_depth, max_pages, wait_for_js,
                take_screenshot, exclude_patterns, sitemap_urls
            )
        else:
            documents = await self._crawl_fallback(
                start_url, max_depth, max_pages, exclude_patterns, sitemap_urls
            )

        print(f"[WebScraper] === CRAWL COMPLETE ===")
        print(f"[WebScraper] Pages crawled: {len(self.visited_urls)}")
        print(f"[WebScraper] Documents created: {len(documents)}")
        print(f"[WebScraper] Success: {self.success_count}, Errors: {self.error_count}")

        self.status = ConnectorStatus.CONNECTED
        return documents

    async def _crawl_with_crawl4ai(
        self,
        start_url: str,
        max_depth: int,
        max_pages: int,
        wait_for_js: bool,
        take_screenshot: bool,
        exclude_patterns: List[str],
        sitemap_urls: List[str] = None
    ) -> List[Document]:
        """Crawl using Crawl4AI - the good scraper"""
        documents = []
        screenshots_dir = self._get_screenshots_dir()
        crawl_delay = self.config.settings.get("crawl_delay", 1.0)
        timeout = self.config.settings.get("timeout", 30)

        # Initialize URL queue with sitemap URLs first (depth 0), then start URL
        urls_to_crawl = []
        if sitemap_urls:
            for url in sitemap_urls[:max_pages]:
                urls_to_crawl.append((url, 0))
        urls_to_crawl.append((start_url, 0))

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent=self.BOT_USER_AGENT,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            while urls_to_crawl and len(documents) < max_pages:
                url, depth = urls_to_crawl.pop(0)

                # Normalize URL
                url = self._normalize_url(url)
                if not url:
                    continue

                # Skip if already visited
                if url in self.visited_urls:
                    continue

                # Validate URL BEFORE adding to visited
                if not self._is_valid_url(url, exclude_patterns):
                    continue

                # Check robots.txt
                if not self._is_allowed_by_robots(url):
                    print(f"[WebScraper] Blocked by robots.txt: {url}")
                    continue

                # Mark as visited only after all validation passes
                self.visited_urls.add(url)
                print(f"[WebScraper] Crawling ({len(documents)+1}/{max_pages}): {url}")

                try:
                    run_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        screenshot=take_screenshot,
                        pdf=take_screenshot,
                        wait_until="networkidle" if wait_for_js else "domcontentloaded",
                    )

                    # Add timeout to prevent hanging
                    try:
                        result = await asyncio.wait_for(
                            crawler.arun(url=url, config=run_config),
                            timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        print(f"[WebScraper] Timeout after {timeout}s: {url}")
                        self.error_count += 1
                        continue

                    if not result.success:
                        print(f"[WebScraper] Failed to crawl {url}: {result.error_message}")
                        self.error_count += 1
                        continue

                    # Get clean markdown content (LLM-ready)
                    content = result.markdown or result.cleaned_html or ""

                    if len(content.strip()) < 100:
                        print(f"[WebScraper] Skipping {url} - too little content")
                        continue

                    # Save screenshot/PDF if available
                    screenshot_path = None
                    pdf_path = None

                    if take_screenshot and result.screenshot:
                        screenshot_path = os.path.join(
                            screenshots_dir,
                            f"{self._url_to_filename(url)}.png"
                        )
                        try:
                            with open(screenshot_path, "wb") as f:
                                f.write(base64.b64decode(result.screenshot))
                            print(f"[WebScraper] Screenshot saved: {screenshot_path}")
                        except Exception as e:
                            print(f"[WebScraper] Failed to save screenshot: {e}")
                            # Cleanup orphaned file
                            if os.path.exists(screenshot_path):
                                try:
                                    os.remove(screenshot_path)
                                except:
                                    pass
                            screenshot_path = None

                    # Save PDF if available
                    if take_screenshot and hasattr(result, 'pdf') and result.pdf:
                        pdf_path = os.path.join(
                            screenshots_dir,
                            f"{self._url_to_filename(url)}.pdf"
                        )
                        try:
                            with open(pdf_path, "wb") as f:
                                f.write(result.pdf)  # PDF is binary, not base64
                            print(f"[WebScraper] PDF saved: {pdf_path}")
                        except Exception as e:
                            print(f"[WebScraper] Failed to save PDF: {e}")
                            if os.path.exists(pdf_path):
                                try:
                                    os.remove(pdf_path)
                                except:
                                    pass
                            pdf_path = None

                    # Get title safely
                    title = url
                    if result.metadata and isinstance(result.metadata, dict):
                        title = result.metadata.get("title", url) or url

                    # Create document
                    doc = Document(
                        doc_id=f"webscraper_{self._url_to_filename(url)}",
                        source="webscraper",
                        content=content,
                        title=title,
                        metadata={
                            "url": url,
                            "depth": depth,
                            "word_count": len(content.split()),
                            "links_found": len(result.links.get("internal", [])) if result.links else 0,
                            "screenshot_path": screenshot_path,
                            "pdf_path": pdf_path,
                            "crawl4ai": True,
                        },
                        timestamp=datetime.now(),
                        url=url,
                        doc_type="webpage"
                    )
                    documents.append(doc)
                    self.success_count += 1
                    print(f"[WebScraper] ✓ Extracted {len(content)} chars from {url}")

                    # Extract and queue internal links
                    if depth < max_depth and result.links:
                        internal_links = result.links.get("internal", [])
                        for link_info in internal_links[:50]:  # Limit links per page
                            # Safely extract link
                            if isinstance(link_info, dict):
                                link = link_info.get("href", "")
                            elif isinstance(link_info, str):
                                link = link_info
                            else:
                                continue

                            # Validate link format
                            if not link or not isinstance(link, str):
                                continue

                            # Handle relative URLs
                            if link.startswith("/"):
                                link = self.base_domain + link
                            elif not link.startswith("http"):
                                continue

                            # Normalize and check
                            link = self._normalize_url(link)
                            if link and link not in self.visited_urls:
                                if self._is_valid_url(link, exclude_patterns):
                                    urls_to_crawl.append((link, depth + 1))

                    # Respect crawl delay
                    if crawl_delay > 0:
                        await asyncio.sleep(crawl_delay)

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"[WebScraper] Error crawling {url}: {type(e).__name__}: {e}")
                    self.error_count += 1
                    continue

        return documents

    async def _crawl_fallback(
        self,
        start_url: str,
        max_depth: int,
        max_pages: int,
        exclude_patterns: List[str],
        sitemap_urls: List[str] = None
    ) -> List[Document]:
        """Fallback crawler using requests + BeautifulSoup"""
        print("[WebScraper] Using fallback crawler (no JS rendering)")
        documents = []
        crawl_delay = self.config.settings.get("crawl_delay", 1.0)

        # Initialize URL queue
        urls_to_crawl = []
        if sitemap_urls:
            for url in sitemap_urls[:max_pages]:
                urls_to_crawl.append((url, 0))
        urls_to_crawl.append((start_url, 0))

        while urls_to_crawl and len(documents) < max_pages:
            url, depth = urls_to_crawl.pop(0)

            # Normalize URL
            url = self._normalize_url(url)
            if not url:
                continue

            if url in self.visited_urls:
                continue

            if not self._is_valid_url(url, exclude_patterns):
                continue

            # Check robots.txt
            if not self._is_allowed_by_robots(url):
                print(f"[WebScraper] Blocked by robots.txt: {url}")
                continue

            self.visited_urls.add(url)
            print(f"[WebScraper] Crawling ({len(documents)+1}/{max_pages}): {url}")

            try:
                response = requests.get(
                    url,
                    timeout=self.config.settings.get("timeout", 30),
                    headers={"User-Agent": self.BOT_USER_AGENT}
                )

                if response.status_code != 200:
                    self.error_count += 1
                    continue

                soup = BeautifulSoup(response.text, "html.parser")

                # Remove unwanted elements
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                    tag.decompose()

                # Get title
                title = soup.title.string if soup.title else url

                # Get main content
                main = soup.find("main") or soup.find("article") or soup.find("body")
                content = main.get_text(separator="\n", strip=True) if main else ""

                if len(content) < 100:
                    continue

                doc = Document(
                    doc_id=f"webscraper_{self._url_to_filename(url)}",
                    source="webscraper",
                    content=content,
                    title=title,
                    metadata={
                        "url": url,
                        "depth": depth,
                        "word_count": len(content.split()),
                        "crawl4ai": False,
                    },
                    timestamp=datetime.now(),
                    url=url,
                    doc_type="webpage"
                )
                documents.append(doc)
                self.success_count += 1
                print(f"[WebScraper] ✓ Extracted {len(content)} chars from {url}")

                # Extract links
                if depth < max_depth:
                    for a in soup.find_all("a", href=True):
                        link = a["href"]

                        # Handle relative URLs
                        if link.startswith("/"):
                            link = self.base_domain + link
                        elif not link.startswith("http"):
                            # Could be relative like "page.html"
                            link = urljoin(url, link)

                        link = self._normalize_url(link)
                        if link and link.startswith(self.base_domain) and link not in self.visited_urls:
                            if self._is_valid_url(link, exclude_patterns):
                                urls_to_crawl.append((link, depth + 1))

                # Respect crawl delay
                if crawl_delay > 0:
                    await asyncio.sleep(crawl_delay)

            except requests.Timeout:
                print(f"[WebScraper] Timeout: {url}")
                self.error_count += 1
                continue
            except requests.RequestException as e:
                print(f"[WebScraper] Request error: {e}")
                self.error_count += 1
                continue
            except Exception as e:
                print(f"[WebScraper] Error: {type(e).__name__}: {e}")
                self.error_count += 1
                continue

        return documents

    def _is_valid_url(self, url: str, exclude_patterns: List[str]) -> bool:
        """Check if URL should be crawled"""
        if not url:
            return False

        if not url.startswith(self.base_domain):
            return False

        url_lower = url.lower()

        # Check exclude patterns
        for pattern in exclude_patterns:
            if pattern.lower() in url_lower:
                return False

        # Skip common non-content file extensions
        skip_extensions = [
            # Images
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',
            # Styles/scripts
            '.css', '.js', '.map',
            # Fonts
            '.woff', '.woff2', '.ttf', '.eot', '.otf',
            # Media
            '.mp3', '.mp4', '.wav', '.avi', '.mov', '.webm',
            # Archives
            '.zip', '.rar', '.7z', '.tar', '.gz',
            # Documents (usually want markdown, not raw files)
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            # Other
            '.xml', '.json', '.rss', '.atom',
        ]

        for ext in skip_extensions:
            if url_lower.endswith(ext):
                return False

        return True

    async def disconnect(self) -> bool:
        """Disconnect from the website"""
        self.status = ConnectorStatus.DISCONNECTED
        self.visited_urls.clear()
        self.sitemap_urls.clear()
        self.robots_parser = None
        return True

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific document - not supported for web scraper"""
        return None

    async def test_connection(self) -> bool:
        """Test the connection"""
        return await self.connect()
