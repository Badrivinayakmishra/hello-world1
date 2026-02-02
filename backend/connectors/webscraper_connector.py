"""
Website Scraper Connector - Pure Playwright Implementation
Advanced web scraping with JavaScript rendering, hidden data extraction,
and PDF/screenshot capture for human-readable document viewing.

Features:
- Stealth browser mode (anti-detection)
- JavaScript rendering for dynamic pages
- Hidden API data interception (XHR/fetch)
- Hidden JS state extraction (__NEXT_DATA__, etc.)
- Screenshot capture (PNG)
- PDF capture (full page, human-viewable)
- Lazy loading trigger
- Robots.txt compliance
- Sitemap discovery
- Smart link extraction
"""

import os
import asyncio
import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Set, Any
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import hashlib

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

# Import Playwright
try:
    from playwright.async_api import async_playwright, Page, Response
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[WebScraper] Playwright not installed. Run: pip install playwright && playwright install chromium")

# Check if Playwright browsers are installed
PLAYWRIGHT_BROWSERS_INSTALLED = False
PLAYWRIGHT_BROWSER_PATH = None
if PLAYWRIGHT_AVAILABLE:
    try:
        import glob

        # Check for Playwright managed chromium directories
        cache_paths = [
            os.path.expanduser("~/.cache/ms-playwright/"),
            "/root/.cache/ms-playwright/"
        ]

        for cache_path in cache_paths:
            if os.path.exists(cache_path):
                try:
                    contents = os.listdir(cache_path)
                    # If we find chromium directory, mark as installed
                    for item in contents:
                        if item.startswith('chromium'):
                            PLAYWRIGHT_BROWSERS_INSTALLED = True
                            PLAYWRIGHT_BROWSER_PATH = os.path.join(cache_path, item)
                            print(f"[WebScraper] Found Chromium at: {PLAYWRIGHT_BROWSER_PATH}")
                            break
                    if PLAYWRIGHT_BROWSERS_INSTALLED:
                        break
                except Exception as e:
                    print(f"[WebScraper] Could not list cache {cache_path}: {e}")

        if not PLAYWRIGHT_BROWSERS_INSTALLED:
            print("[WebScraper] WARNING: Playwright browsers not found. Will attempt to use system browser.")
    except Exception as e:
        print(f"[WebScraper] Error checking Playwright browsers: {e}")

# Fallback imports
try:
    import requests
    from bs4 import BeautifulSoup
    FALLBACK_AVAILABLE = True
except ImportError:
    FALLBACK_AVAILABLE = False


class WebScraperConnector(BaseConnector):
    """
    Advanced website scraper using pure Playwright.

    Features:
    - Stealth mode to avoid detection
    - JavaScript rendering for SPAs (React, Vue, Angular)
    - Hidden API/XHR data interception
    - Hidden JS state extraction (__NEXT_DATA__, __INITIAL_STATE__)
    - Full-page PDF capture (human-viewable)
    - Screenshot capture
    - Lazy loading support
    - Robots.txt compliance
    """

    CONNECTOR_TYPE = "webscraper"
    REQUIRED_CREDENTIALS = []
    OPTIONAL_SETTINGS = {
        "start_url": "",
        "max_depth": 2,
        "max_pages": 20,
        "wait_for_js": True,
        "screenshot": True,
        "pdf_capture": True,  # Capture full-page PDF for human viewing
        "capture_api_data": True,  # Intercept XHR/fetch responses
        "respect_robots_txt": True,
        "use_sitemap": True,
        "crawl_delay": 1.0,
        "timeout": 60,  # Longer timeout for JS-heavy sites
        "exclude_patterns": [
            "#", "mailto:", "tel:", "javascript:", "data:", "file:",
            "login", "signin", "signup", "register", "logout", "signout",
            "/auth/", "/account/", "/user/", "/profile/", "/dashboard/",
            "/admin/", "/password", "/forgot", "/reset", "/verify",
            "cart", "checkout", "/basket", "/order", "/payment",
            "/search", "?search=", "?q=", "?query=", "?sort=", "?filter=",
            "?utm_", "?fbclid=", "?gclid=", "?ref=", "?session",
            "/api/", "/v1/", "/v2/", "/graphql", "/webhook",
        ],
    }

    # Stealth user agent
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

    def __init__(self, config: ConnectorConfig, tenant_id: Optional[str] = None):
        super().__init__(config)
        self.tenant_id = tenant_id
        self.visited_urls: Set[str] = set()
        self.base_domain = None
        self.robots_parser: Optional[RobotFileParser] = None
        self.sitemap_urls: List[str] = []
        self.error_count = 0
        self.success_count = 0
        self.captured_api_data: List[Dict] = []

    def _get_storage_dir(self, subdir: str = "screenshots") -> str:
        """Get directory for storing files"""
        base_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tenant_data",
            self.tenant_id or "default",
            subdir
        )
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        return f"page_{url_hash}"

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to prevent duplicates"""
        if not url:
            return ""
        parsed = urlparse(url)
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()
        if netloc.endswith(":80") and scheme == "http":
            netloc = netloc[:-3]
        elif netloc.endswith(":443") and scheme == "https":
            netloc = netloc[:-4]
        path = parsed.path
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return f"{scheme}://{netloc}{path}"

    async def _handle_response(self, response: Response):
        """Intercept API responses to capture hidden data"""
        try:
            if response.request.resource_type in ["fetch", "xhr"]:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        data = await response.json()
                        self.captured_api_data.append({
                            "url": response.url,
                            "data": data
                        })
                        print(f"[WebScraper] Captured API data from: {response.url[:80]}...")
                    except:
                        pass
        except:
            pass

    async def _load_robots_txt(self) -> bool:
        """Load and parse robots.txt"""
        if not self.config.settings.get("respect_robots_txt", True):
            return True
        try:
            robots_url = f"{self.base_domain}/robots.txt"
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()

            if FALLBACK_AVAILABLE:
                response = requests.get(robots_url, timeout=10, headers={"User-Agent": self.USER_AGENT})
                if response.status_code == 200:
                    for line in response.text.splitlines():
                        if line.lower().startswith("sitemap:"):
                            sitemap_url = line.split(":", 1)[1].strip()
                            self.sitemap_urls.append(sitemap_url)
            print(f"[WebScraper] Loaded robots.txt")
            return True
        except Exception as e:
            print(f"[WebScraper] Could not load robots.txt: {e}")
            return True

    def _is_allowed_by_robots(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        if not self.robots_parser:
            return True
        try:
            return self.robots_parser.can_fetch(self.USER_AGENT, url)
        except:
            return True

    async def _discover_sitemap_urls(self) -> List[str]:
        """Discover URLs from sitemap.xml"""
        if not self.config.settings.get("use_sitemap", True):
            return []
        urls = []
        if not self.sitemap_urls:
            self.sitemap_urls = [f"{self.base_domain}/sitemap.xml"]

        for sitemap_url in self.sitemap_urls[:3]:
            try:
                if not FALLBACK_AVAILABLE:
                    continue
                response = requests.get(sitemap_url, timeout=10, headers={"User-Agent": self.USER_AGENT})
                if response.status_code != 200:
                    continue
                soup = BeautifulSoup(response.content, "xml")
                for url_tag in soup.find_all("url"):
                    loc = url_tag.find("loc")
                    if loc and loc.text:
                        normalized = self._normalize_url(loc.text)
                        if normalized.startswith(self.base_domain):
                            urls.append(normalized)
                print(f"[WebScraper] Found {len(urls)} URLs in sitemap")
            except Exception as e:
                print(f"[WebScraper] Could not parse sitemap: {e}")
        return urls[:100]

    async def connect(self) -> bool:
        """Test website connection"""
        if not PLAYWRIGHT_AVAILABLE and not FALLBACK_AVAILABLE:
            self._set_error("Neither Playwright nor fallback libraries installed")
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
                response = requests.head(start_url, timeout=10, allow_redirects=True,
                                        headers={"User-Agent": self.USER_AGENT})
                if response.status_code >= 400:
                    self._set_error(f"Failed to connect: HTTP {response.status_code}")
                    return False

            await self._load_robots_txt()

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print(f"[WebScraper] Connected to {start_url}")
            return True

        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Crawl website using Playwright"""
        print(f"[WebScraper] === SYNC STARTED ===")

        if self.status != ConnectorStatus.CONNECTED:
            if not await self.connect():
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []
        self.error_count = 0
        self.success_count = 0
        self.captured_api_data = []

        start_url = self.config.settings["start_url"]
        max_depth = self.config.settings.get("max_depth", 2)
        max_pages = self.config.settings.get("max_pages", 20)
        exclude_patterns = self.config.settings.get("exclude_patterns", [])

        print(f"[WebScraper] Starting crawl from {start_url}")
        print(f"[WebScraper] Max depth: {max_depth}, Max pages: {max_pages}")
        print(f"[WebScraper] Using Playwright: {PLAYWRIGHT_AVAILABLE}")

        self.visited_urls.clear()

        # Discover sitemap URLs
        sitemap_urls = await self._discover_sitemap_urls()
        if sitemap_urls:
            print(f"[WebScraper] Using {len(sitemap_urls)} URLs from sitemap")

        if PLAYWRIGHT_AVAILABLE:
            try:
                documents = await self._crawl_with_playwright(
                    start_url, max_depth, max_pages, exclude_patterns, sitemap_urls
                )
            except Exception as e:
                print(f"[WebScraper] FATAL ERROR in Playwright crawl: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise  # Re-raise to let the caller handle it
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

    async def _crawl_with_playwright(
        self,
        start_url: str,
        max_depth: int,
        max_pages: int,
        exclude_patterns: List[str],
        sitemap_urls: List[str] = None
    ) -> List[Document]:
        """Crawl using pure Playwright with stealth mode"""
        documents = []
        screenshots_dir = self._get_storage_dir("screenshots")
        pdfs_dir = self._get_storage_dir("pdfs")
        crawl_delay = self.config.settings.get("crawl_delay", 1.0)
        timeout = self.config.settings.get("timeout", 60) * 1000  # ms
        take_screenshot = self.config.settings.get("screenshot", True)
        capture_pdf = self.config.settings.get("pdf_capture", True)
        capture_api = self.config.settings.get("capture_api_data", True)

        # Initialize URL queue
        urls_to_crawl = []
        if sitemap_urls:
            for url in sitemap_urls[:max_pages]:
                urls_to_crawl.append((url, 0))
        urls_to_crawl.append((start_url, 0))

        print(f"[WebScraper] Attempting to launch Playwright browser...")

        async with async_playwright() as p:
            # Try to launch with various fallback options
            browser = None
            launch_error = None

            # Attempt 1: Standard headless with stealth args
            try:
                print(f"[WebScraper] Attempting standard launch...")
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-setuid-sandbox",
                        "--single-process",  # May help on memory-constrained systems
                    ]
                )
                print(f"[WebScraper] Browser launched successfully!")
            except Exception as e:
                launch_error = e
                print(f"[WebScraper] Standard launch failed: {type(e).__name__}: {e}")

            # Attempt 2: Try with channel=chromium (system chromium)
            if not browser:
                try:
                    print(f"[WebScraper] Attempting launch with channel=chromium...")
                    browser = await p.chromium.launch(
                        headless=True,
                        channel="chromium",
                        args=["--no-sandbox", "--disable-dev-shm-usage"]
                    )
                    print(f"[WebScraper] Browser launched with channel=chromium!")
                except Exception as e:
                    print(f"[WebScraper] Channel launch failed: {type(e).__name__}: {e}")

            # Attempt 3: Minimal args launch
            if not browser:
                try:
                    print(f"[WebScraper] Attempting minimal launch...")
                    browser = await p.chromium.launch(headless=True)
                    print(f"[WebScraper] Browser launched with minimal config!")
                except Exception as e:
                    print(f"[WebScraper] Minimal launch failed: {type(e).__name__}: {e}")

            if not browser:
                error_msg = f"Failed to launch browser after all attempts. Last error: {launch_error}"
                print(f"[WebScraper] FATAL: {error_msg}")
                raise RuntimeError(error_msg)

            context = await browser.new_context(
                user_agent=self.USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
            )

            page = await context.new_page()

            # Listen for API calls if enabled
            if capture_api:
                page.on("response", self._handle_response)

            try:
                while urls_to_crawl and len(documents) < max_pages:
                    url, depth = urls_to_crawl.pop(0)

                    # Normalize and validate URL
                    url = self._normalize_url(url)
                    if not url or url in self.visited_urls:
                        continue
                    if not self._is_valid_url(url, exclude_patterns):
                        continue
                    if not self._is_allowed_by_robots(url):
                        print(f"[WebScraper] Blocked by robots.txt: {url}")
                        continue

                    self.visited_urls.add(url)
                    print(f"[WebScraper] Crawling ({len(documents)+1}/{max_pages}): {url}")

                    # Reset API data for this page
                    page_api_data = []

                    try:
                        # Navigate with timeout
                        await page.goto(url, wait_until="networkidle", timeout=timeout)

                        # Trigger lazy loading - scroll to bottom
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(1.5)  # Wait for animations

                        # Scroll back up for proper screenshot
                        await page.evaluate("window.scrollTo(0, 0)")
                        await asyncio.sleep(0.5)

                        # Extract DOM content
                        dom_data = await page.evaluate("""() => {
                            // Remove unwanted elements
                            const remove = ['script', 'style', 'noscript', 'iframe'];
                            remove.forEach(tag => {
                                document.querySelectorAll(tag).forEach(el => el.remove());
                            });

                            // Get title
                            const title = document.title || '';

                            // Get main content text
                            const mainEl = document.querySelector('main') ||
                                          document.querySelector('article') ||
                                          document.querySelector('[role="main"]') ||
                                          document.body;

                            // Extract text from content elements
                            const contentElements = mainEl.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, td, th, span, div');
                            const textParts = [];
                            contentElements.forEach(el => {
                                const text = el.innerText?.trim();
                                if (text && text.length > 10) {
                                    textParts.push(text);
                                }
                            });

                            // Get all links
                            const links = Array.from(document.querySelectorAll('a[href]'))
                                .map(a => a.href)
                                .filter(href => href && href.startsWith('http'));

                            return {
                                title: title,
                                text: textParts.join('\\n\\n'),
                                links: [...new Set(links)]
                            };
                        }""")

                        # Extract hidden JS state (React/Next.js/Vue data)
                        hidden_state = await page.evaluate("""() => {
                            const states = {};
                            if (window.__NEXT_DATA__) states.nextData = window.__NEXT_DATA__;
                            if (window.__INITIAL_STATE__) states.initialState = window.__INITIAL_STATE__;
                            if (window.__NUXT__) states.nuxt = window.__NUXT__;
                            if (window.__APP_CONFIG__) states.appConfig = window.__APP_CONFIG__;
                            if (window.__PRELOADED_STATE__) states.preloadedState = window.__PRELOADED_STATE__;
                            return Object.keys(states).length > 0 ? states : null;
                        }""")

                        # Build content
                        content_parts = []
                        if dom_data.get("title"):
                            content_parts.append(f"# {dom_data['title']}\n")
                        if dom_data.get("text"):
                            content_parts.append(dom_data["text"])

                        # Add hidden state content if available
                        if hidden_state:
                            try:
                                state_text = self._extract_text_from_state(hidden_state)
                                if state_text:
                                    content_parts.append(f"\n\n## Additional Content\n{state_text}")
                            except:
                                pass

                        content = "\n\n".join(content_parts)

                        if len(content.strip()) < 50:
                            print(f"[WebScraper] Skipping {url} - too little content")
                            continue

                        # Capture screenshot
                        screenshot_path = None
                        if take_screenshot:
                            screenshot_path = os.path.join(screenshots_dir, f"{self._url_to_filename(url)}.png")
                            try:
                                await page.screenshot(path=screenshot_path, full_page=True)
                                print(f"[WebScraper] Screenshot saved: {screenshot_path}")
                            except Exception as e:
                                print(f"[WebScraper] Screenshot failed: {e}")
                                screenshot_path = None

                        # Capture PDF (human-viewable document)
                        pdf_path = None
                        if capture_pdf:
                            pdf_path = os.path.join(pdfs_dir, f"{self._url_to_filename(url)}.pdf")
                            try:
                                await page.pdf(path=pdf_path, format="A4", print_background=True)
                                print(f"[WebScraper] PDF saved: {pdf_path}")
                            except Exception as e:
                                print(f"[WebScraper] PDF failed: {e}")
                                pdf_path = None

                        # Create document
                        doc = Document(
                            doc_id=f"webscraper_{self._url_to_filename(url)}",
                            source="webscraper",
                            content=content,
                            title=dom_data.get("title", url),
                            metadata={
                                "url": url,
                                "depth": depth,
                                "word_count": len(content.split()),
                                "links_found": len(dom_data.get("links", [])),
                                "screenshot_path": screenshot_path,
                                "pdf_path": pdf_path,
                                "has_hidden_state": hidden_state is not None,
                                "api_calls_captured": len(self.captured_api_data),
                            },
                            timestamp=datetime.now(),
                            url=url,
                            doc_type="webpage"
                        )
                        documents.append(doc)
                        self.success_count += 1
                        print(f"[WebScraper] ✓ Extracted {len(content)} chars from {url}")

                        # Queue internal links
                        if depth < max_depth:
                            for link in dom_data.get("links", [])[:50]:
                                link = self._normalize_url(link)
                                if link and link.startswith(self.base_domain):
                                    if link not in self.visited_urls:
                                        if self._is_valid_url(link, exclude_patterns):
                                            urls_to_crawl.append((link, depth + 1))

                        # Crawl delay
                        if crawl_delay > 0:
                            await asyncio.sleep(crawl_delay)

                    except asyncio.TimeoutError:
                        print(f"[WebScraper] Timeout: {url}")
                        self.error_count += 1
                    except Exception as e:
                        print(f"[WebScraper] Error crawling {url}: {type(e).__name__}: {e}")
                        self.error_count += 1

            finally:
                await browser.close()

        return documents

    def _extract_text_from_state(self, state: Dict) -> str:
        """Extract readable text from hidden JS state"""
        texts = []

        def extract_recursive(obj, depth=0):
            if depth > 5:  # Limit recursion
                return
            if isinstance(obj, str) and len(obj) > 20:
                # Filter out base64, URLs, etc.
                if not obj.startswith(('data:', 'http', '/static', '/api')):
                    if not re.match(r'^[A-Za-z0-9+/=]+$', obj):  # Not base64
                        texts.append(obj)
            elif isinstance(obj, dict):
                for v in obj.values():
                    extract_recursive(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj[:20]:  # Limit list items
                    extract_recursive(item, depth + 1)

        extract_recursive(state)
        return "\n".join(texts[:50])  # Limit total extracted text

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

        urls_to_crawl = []
        if sitemap_urls:
            for url in sitemap_urls[:max_pages]:
                urls_to_crawl.append((url, 0))
        urls_to_crawl.append((start_url, 0))

        while urls_to_crawl and len(documents) < max_pages:
            url, depth = urls_to_crawl.pop(0)

            url = self._normalize_url(url)
            if not url or url in self.visited_urls:
                continue
            if not self._is_valid_url(url, exclude_patterns):
                continue
            if not self._is_allowed_by_robots(url):
                continue

            self.visited_urls.add(url)
            print(f"[WebScraper] Crawling ({len(documents)+1}/{max_pages}): {url}")

            try:
                response = requests.get(url, timeout=30, headers={"User-Agent": self.USER_AGENT})
                if response.status_code != 200:
                    self.error_count += 1
                    continue

                soup = BeautifulSoup(response.text, "html.parser")

                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                    tag.decompose()

                title = soup.title.string if soup.title else url
                main = soup.find("main") or soup.find("article") or soup.find("body")
                content = main.get_text(separator="\n", strip=True) if main else ""

                if len(content) < 50:
                    continue

                # Extract links
                links = []
                for a in soup.find_all("a", href=True):
                    link = a["href"]
                    if link.startswith("/"):
                        link = self.base_domain + link
                    elif not link.startswith("http"):
                        link = urljoin(url, link)
                    link = self._normalize_url(link)
                    if link and link.startswith(self.base_domain):
                        links.append(link)

                doc = Document(
                    doc_id=f"webscraper_{self._url_to_filename(url)}",
                    source="webscraper",
                    content=content,
                    title=title,
                    metadata={
                        "url": url,
                        "depth": depth,
                        "word_count": len(content.split()),
                        "links_found": len(links),
                        "fallback_mode": True,
                    },
                    timestamp=datetime.now(),
                    url=url,
                    doc_type="webpage"
                )
                documents.append(doc)
                self.success_count += 1
                print(f"[WebScraper] ✓ Extracted {len(content)} chars from {url}")

                # Queue links
                if depth < max_depth:
                    for link in links[:50]:
                        if link not in self.visited_urls:
                            if self._is_valid_url(link, exclude_patterns):
                                urls_to_crawl.append((link, depth + 1))

                if crawl_delay > 0:
                    await asyncio.sleep(crawl_delay)

            except Exception as e:
                print(f"[WebScraper] Error: {type(e).__name__}: {e}")
                self.error_count += 1

        return documents

    def _is_valid_url(self, url: str, exclude_patterns: List[str]) -> bool:
        """Check if URL should be crawled"""
        if not url or not url.startswith(self.base_domain):
            return False

        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern.lower() in url_lower:
                return False

        skip_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',
            '.css', '.js', '.map', '.woff', '.woff2', '.ttf', '.eot',
            '.mp3', '.mp4', '.wav', '.avi', '.mov', '.webm',
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.xml', '.json', '.rss', '.atom',
        ]
        for ext in skip_extensions:
            if url_lower.endswith(ext):
                return False

        return True

    async def disconnect(self) -> bool:
        """Disconnect"""
        self.status = ConnectorStatus.DISCONNECTED
        self.visited_urls.clear()
        self.sitemap_urls.clear()
        self.robots_parser = None
        self.captured_api_data = []
        return True

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific document - not supported"""
        return None

    async def test_connection(self) -> bool:
        """Test the connection"""
        return await self.connect()
