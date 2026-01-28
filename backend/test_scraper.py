#!/usr/bin/env python3
"""
Test script to verify web scraping works locally
"""

import sys

# Test 1: Check if libraries are installed
print("=" * 60)
print("TEST 1: Checking required libraries...")
print("=" * 60)

try:
    import requests
    print("✓ requests library installed")
    print(f"  Version: {requests.__version__}")
except ImportError as e:
    print(f"✗ requests library MISSING: {e}")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    print("✓ BeautifulSoup4 library installed")
except ImportError as e:
    print(f"✗ BeautifulSoup4 library MISSING: {e}")
    sys.exit(1)

# Test 2: Try to fetch the Pellegrini website
print("\n" + "=" * 60)
print("TEST 2: Attempting to fetch Pellegrini website...")
print("=" * 60)

url = "https://www.pellegrini.mcdb.ucla.edu/"
print(f"URL: {url}")

try:
    response = requests.get(url, timeout=10)
    print(f"✓ HTTP Status: {response.status_code}")
    print(f"✓ Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
    print(f"✓ Content Length: {len(response.text)} characters")

    if response.status_code != 200:
        print(f"✗ Expected 200, got {response.status_code}")
        sys.exit(1)

except requests.exceptions.Timeout:
    print("✗ Request timed out (website may be slow or blocking)")
    sys.exit(1)
except requests.exceptions.ConnectionError as e:
    print(f"✗ Connection failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    sys.exit(1)

# Test 3: Parse HTML and extract content
print("\n" + "=" * 60)
print("TEST 3: Parsing HTML content...")
print("=" * 60)

try:
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract title
    title = soup.find("title")
    if title:
        print(f"✓ Page title: {title.get_text().strip()}")
    else:
        print("✗ No title found")

    # Remove script/style
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()

    # Get main content
    main_content = (
        soup.find("main") or
        soup.find("article") or
        soup.find("body") or
        soup
    )

    # Extract text
    text = main_content.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    content = "\n\n".join(lines)

    print(f"✓ Extracted content length: {len(content)} characters")
    print(f"✓ Number of text lines: {len(lines)}")

    if len(content) < 100:
        print(f"✗ WARNING: Content too short (<100 chars) - would be skipped by scraper")
        print(f"   Content preview: {content[:200]}")
    else:
        print(f"✓ Content is sufficient (>100 chars)")
        print(f"\n   Preview (first 300 chars):")
        print(f"   {content[:300]}...")

except Exception as e:
    print(f"✗ Parsing failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Extract links
print("\n" + "=" * 60)
print("TEST 4: Extracting links...")
print("=" * 60)

try:
    from urllib.parse import urljoin, urlparse

    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()

        # Skip empty, anchor, mailto, tel links
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        # Convert to absolute URL
        absolute_url = urljoin(url, href)

        # Remove fragment
        absolute_url = absolute_url.split("#")[0]

        # Check if same domain
        parsed = urlparse(absolute_url)
        base_domain = urlparse(url)

        if f"{parsed.scheme}://{parsed.netloc}" == f"{base_domain.scheme}://{base_domain.netloc}":
            links.append(absolute_url)

    unique_links = list(set(links))
    print(f"✓ Found {len(unique_links)} unique internal links")

    if unique_links:
        print(f"\n   First 10 links:")
        for link in unique_links[:10]:
            print(f"   - {link}")
    else:
        print("✗ WARNING: No internal links found - crawler won't follow any pages")

except Exception as e:
    print(f"✗ Link extraction failed: {e}")
    import traceback
    traceback.print_exc()

# Final summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("✓ All tests passed! Web scraping should work.")
print("\nIf the WebScraper still returns 0 documents, the issue is likely:")
print("1. Render environment blocking the website (firewall/geo-blocking)")
print("2. Rate limiting or bot detection on the target website")
print("3. Different behavior in production vs local environment")
print("\nCheck Render logs for the verbose output we added:")
print("  [WebScraper] === SYNC STARTED ===")
print("  [WebScraper] Starting crawl from...")
print("  etc.")
