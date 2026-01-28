"""
Test Gamma API Integration
Quick test to verify Gamma service is working correctly.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.gamma_service import get_gamma_service, GAMMA_AVAILABLE


def test_gamma_availability():
    """Test if Gamma service is available"""
    print("="*70)
    print("TEST 1: Gamma Service Availability")
    print("="*70)

    if GAMMA_AVAILABLE:
        print("✓ Gamma service module loaded successfully")
    else:
        print("✗ Gamma service not available (import error)")
        return False

    try:
        service = get_gamma_service()
        print(f"✓ Gamma service initialized")
        print(f"  API Key: {'*' * 20}{service.api_key[-8:] if service.api_key else 'NOT SET'}")
        print(f"  Template ID: {service.template_id or 'NOT SET'}")
        print(f"  Theme ID: {service.theme_id or 'NOT SET'}")

        if not service.api_key:
            print("\n⚠ WARNING: GAMMA_API_KEY not set in .env file")
            return False

        return True

    except Exception as e:
        print(f"✗ Failed to initialize Gamma service: {e}")
        return False


def test_presentation_generation():
    """Test generating a simple presentation"""
    print("\n" + "="*70)
    print("TEST 2: Presentation Generation (No Export)")
    print("="*70)

    try:
        service = get_gamma_service()

        test_content = """
PRESENTATION TITLE: Test Presentation
SUBTITLE: Quick API Test

Create a 3-slide presentation:

## Slide 1: Introduction
Welcome to the test presentation. This is a simple test of the Gamma API integration.

## Slide 2: Features
- AI-powered presentation generation
- Professional design templates
- Export to PPTX format

## Slide 3: Conclusion
The Gamma API integration is working correctly. Thank you!
"""

        print("Generating presentation (without export)...")
        print(f"Content length: {len(test_content)} characters")

        result, error = service.generate_presentation(
            content=test_content,
            title="Test Presentation",
            export_format=None  # No export for quick test
        )

        if error:
            print(f"✗ Generation failed: {error}")
            return False

        if result:
            print("✓ Presentation generated successfully!")
            print(f"  Generation ID: {result.get('generationId', 'N/A')}")
            print(f"  URL: {result.get('url', 'N/A')}")
            print(f"  Status: {result.get('status', 'N/A')}")

            if 'url' in result:
                print(f"\n  View at: {result['url']}")

            return True
        else:
            print("✗ No result returned")
            return False

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pptx_export():
    """Test PPTX export (longer test)"""
    print("\n" + "="*70)
    print("TEST 3: PPTX Export (This may take 2-3 minutes)")
    print("="*70)

    try:
        service = get_gamma_service()

        test_content = """
PRESENTATION TITLE: Knowledge Transfer
SUBTITLE: Testing PPTX Export

Create a 5-slide business presentation:

## Slide 1: Overview
This is a test of the PPTX export functionality. We will verify that the Gamma API can export presentations in PowerPoint format.

## Slide 2: Technical Details
- Gamma API generates presentations
- Exports as PPTX file
- Downloads to local storage
- Parses slides and notes

## Slide 3: Use Cases
- Training videos from documents
- Knowledge base presentations
- Onboarding materials

## Slide 4: Integration
The PPTX files are parsed to extract:
- Slide titles
- Bullet points
- Speaker notes
- Content structure

## Slide 5: Next Steps
- Generate audio narration
- Create video from slides
- Store for portal viewing
"""

        print("Generating presentation with PPTX export...")
        print("⏱ This will take ~2-3 minutes (Gamma generation + export)")
        print()

        result, error = service.generate_presentation(
            content=test_content,
            title="PPTX Export Test",
            export_format='pptx'
        )

        if error:
            print(f"✗ Export failed: {error}")
            return False

        if result:
            print("✓ Presentation generated with export!")
            print(f"  Generation ID: {result.get('generationId', 'N/A')}")
            print(f"  URL: {result.get('url', 'N/A')}")
            print(f"  Status: {result.get('status', 'N/A')}")

            if 'exportUrl' in result:
                print(f"  Export URL: {result['exportUrl'][:60]}...")
                print("\n✓ PPTX export URL available!")
                print("  (Download test skipped - would download actual file)")
                return True
            else:
                print("⚠ No export URL in result")
                print(f"  Full result: {result}")
                return False
        else:
            print("✗ No result returned")
            return False

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("GAMMA API INTEGRATION TEST SUITE")
    print("="*70 + "\n")

    results = []

    # Test 1: Availability
    results.append(("Availability", test_gamma_availability()))

    if not results[-1][1]:
        print("\n⚠ Skipping remaining tests (service not available)")
        return

    # Test 2: Basic generation
    print("\nDo you want to test presentation generation? (y/n)")
    print("This will use 1 API call (~$0.30)")
    if input().lower().startswith('y'):
        results.append(("Generation", test_presentation_generation()))
    else:
        print("Skipped generation test")

    # Test 3: PPTX export
    print("\nDo you want to test PPTX export? (y/n)")
    print("This will take 2-3 minutes and use 1 API call (~$0.30)")
    if input().lower().startswith('y'):
        results.append(("PPTX Export", test_pptx_export()))
    else:
        print("Skipped PPTX export test")

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 All tests passed! Gamma integration is working correctly.")
    else:
        print("\n⚠ Some tests failed. Check the output above for details.")


if __name__ == '__main__':
    main()
