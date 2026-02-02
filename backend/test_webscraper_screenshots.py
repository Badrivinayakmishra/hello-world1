"""
Test script for WebScraper screenshot/PDF capture functionality.
Demonstrates how to use the webscraper with screenshot capture.
"""

import asyncio
from connectors.webscraper_connector import WebScraperConnector
from connectors.base_connector import ConnectorConfig


async def test_webscraper_with_screenshots():
    """Test webscraper with screenshot capture enabled."""
    print("\n" + "="*60)
    print("WebScraper Screenshot Capture Test")
    print("="*60 + "\n")

    # Example 1: Test with screenshots enabled (default)
    print("[TEST 1] WebScraper with screenshots ENABLED")
    print("-" * 60)

    config = ConnectorConfig(
        connector_type="webscraper",
        user_id="test_user",
        settings={
            "start_url": "https://example.com",
            "max_depth": 1,
            "max_pages": 2,
            "capture_screenshots": True,  # Enable screenshot capture
            "screenshot_timeout": 30,
            "rate_limit_delay": 0.5,
        }
    )

    connector = WebScraperConnector(config, tenant_id="tenant_123")

    print(f"Connector initialized with:")
    print(f"  - Start URL: {config.settings['start_url']}")
    print(f"  - Max depth: {config.settings['max_depth']}")
    print(f"  - Max pages: {config.settings['max_pages']}")
    print(f"  - Screenshots enabled: {config.settings['capture_screenshots']}")
    print(f"  - Screenshots dir: {connector.screenshots_dir}")
    print()

    # Test connection
    print("Testing connection...")
    connected = await connector.connect()
    print(f"Connection result: {connected}\n")

    if connected:
        # Run sync
        print("Starting crawl with screenshot capture...")
        documents = await connector.sync()
        print(f"\nCrawl completed!")
        print(f"Documents created: {len(documents)}")
        print()

        # Show document details
        for i, doc in enumerate(documents, 1):
            print(f"Document {i}:")
            print(f"  - Title: {doc.title}")
            print(f"  - URL: {doc.url}")
            print(f"  - Doc Type: {doc.doc_type}")
            print(f"  - Content length: {len(doc.content)} chars")

            # Check for PDF screenshot
            if "pdf_path" in doc.metadata:
                print(f"  - PDF Screenshot: {doc.metadata['pdf_path']} ✓")
            else:
                print(f"  - PDF Screenshot: Not captured")

            # Show other metadata
            if "description" in doc.metadata:
                print(f"  - Description: {doc.metadata['description'][:50]}...")
            if "depth" in doc.metadata:
                print(f"  - Depth: {doc.metadata['depth']}")
            print()

        await connector.disconnect()

    # Example 2: Test with screenshots disabled
    print("\n" + "="*60)
    print("[TEST 2] WebScraper with screenshots DISABLED")
    print("-" * 60 + "\n")

    config_no_screenshots = ConnectorConfig(
        connector_type="webscraper",
        user_id="test_user",
        settings={
            "start_url": "https://example.com",
            "max_depth": 1,
            "max_pages": 1,
            "capture_screenshots": False,  # Disable screenshot capture
            "rate_limit_delay": 0.5,
        }
    )

    connector2 = WebScraperConnector(config_no_screenshots, tenant_id="tenant_456")
    print(f"Connector initialized with screenshots DISABLED")
    print(f"  - Screenshots dir: {connector2.screenshots_dir}")
    print()

    connected2 = await connector2.connect()
    if connected2:
        print("Starting crawl WITHOUT screenshot capture...")
        documents2 = await connector2.sync()
        print(f"\nCrawl completed!")
        print(f"Documents created: {len(documents2)}")

        if documents2:
            doc = documents2[0]
            print(f"\nFirst document:")
            print(f"  - Title: {doc.title}")
            if "pdf_path" in doc.metadata:
                print(f"  - PDF Screenshot: {doc.metadata['pdf_path']}")
            else:
                print(f"  - PDF Screenshot: Not captured (disabled)")

        await connector2.disconnect()

    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)


if __name__ == "__main__":
    print("\nBefore running this test:")
    print("1. Install Playwright: pip install playwright")
    print("2. Install Chromium: playwright install chromium")
    print("3. Update requirements.txt (already done)")
    print()

    # Note: This test uses example.com which may not work
    # For real testing, use your actual website
    print("Note: This test uses https://example.com for demonstration.")
    print("Replace with your actual website URL for real testing.\n")

    # Run the async test
    # Uncomment to run:
    # asyncio.run(test_webscraper_with_screenshots())
