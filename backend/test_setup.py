import os
"""
Quick Setup Test Script
Tests that all dependencies are installed and configuration is correct
"""

import sys
from pathlib import Path

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


def test_imports():
    """Test that all required packages can be imported"""
    print("Testing imports...")

    required_packages = [
        ('torch', 'PyTorch'),
        ('transformers', 'Transformers'),
        ('sentence_transformers', 'Sentence Transformers'),
        ('bertopic', 'BERTopic'),
        ('umap', 'UMAP'),
        ('hdbscan', 'HDBSCAN'),
        ('openai', 'OpenAI'),
        ('chromadb', 'ChromaDB'),
        ('pandas', 'Pandas'),
        ('numpy', 'NumPy'),
        ('sklearn', 'Scikit-learn'),
        ('pptx', 'python-pptx'),
        ('PIL', 'Pillow'),
        ('moviepy.editor', 'MoviePy'),
        ('gtts', 'gTTS'),
    ]

    failed = []

    for package, name in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {name}")
        except ImportError as e:
            print(f"  ✗ {name} - {e}")
            failed.append(name)

    if failed:
        print(f"\n❌ Failed to import: {', '.join(failed)}")
        print("\nRun: pip install -r requirements.txt")
        return False

    print("\n✅ All packages imported successfully!\n")
    return True


def test_config():
    """Test configuration"""
    print("Testing configuration...")

    try:
        from config.config import Config

        # Test directory creation
        Config.create_directories()
        print(f"  ✓ Directories created at {Config.BASE_DIR}")

        # Test environment variables
        if not Config.OPENAI_API_KEY:
            print(f"  ⚠ OPENAI_API_KEY not set in .env file")
            print(f"    Copy .env.template to .env and add your API key")
            return False
        else:
            print(f"  ✓ OpenAI API key found")

        # Test Enron path
        if not Path(Config.ENRON_MAILDIR).exists():
            print(f"  ⚠ ENRON_MAILDIR not found: {Config.ENRON_MAILDIR}")
            print(f"    Update ENRON_MAILDIR in .env to point to your maildir")
            return False
        else:
            print(f"  ✓ Enron maildir found at {Config.ENRON_MAILDIR}")

        print("\n✅ Configuration is valid!\n")
        return True

    except Exception as e:
        print(f"  ✗ Configuration error: {e}")
        return False


def test_embedding_model():
    """Test that embedding model can be loaded"""
    print("Testing embedding model...")

    try:
        from sentence_transformers import SentenceTransformer

        model_name = "sentence-transformers/all-mpnet-base-v2"
        print(f"  Loading {model_name}...")
        model = SentenceTransformer(model_name)

        # Test embedding
        test_text = "This is a test sentence."
        embedding = model.encode(test_text)

        print(f"  ✓ Model loaded successfully")
        print(f"  ✓ Generated embedding of dimension {len(embedding)}")
        print("\n✅ Embedding model works!\n")
        return True

    except Exception as e:
        print(f"  ✗ Embedding model error: {e}")
        return False


def test_openai():
    """Test OpenAI API connection"""
    print("Testing OpenAI API...")

    try:
        from openai import AzureOpenAI
        from config.config import Config

        if not Config.OPENAI_API_KEY:
            print("  ⚠ Skipping - API key not configured")
            return True

        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION
        )

        # Simple test call
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": "Say 'test successful' and nothing else."}],
            max_tokens=10,
        )

        result = response.choices[0].message.content.strip()
        print(f"  ✓ API connected successfully")
        print(f"  ✓ Response: {result}")
        print("\n✅ OpenAI API works!\n")
        return True

    except Exception as e:
        print(f"  ✗ OpenAI API error: {e}")
        print("  Check your API key in .env file")
        return False


def test_chromadb():
    """Test ChromaDB"""
    print("Testing ChromaDB...")

    try:
        import chromadb
        from chromadb.config import Settings
        import tempfile

        # Create temporary database
        temp_dir = tempfile.mkdtemp()
        client = chromadb.PersistentClient(
            path=temp_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        # Create test collection
        collection = client.create_collection(name="test")

        # Add test document
        collection.add(
            ids=["test1"],
            documents=["This is a test document"],
            metadatas=[{"source": "test"}]
        )

        # Query
        results = collection.query(
            query_texts=["test document"],
            n_results=1
        )

        print(f"  ✓ ChromaDB initialized successfully")
        print(f"  ✓ Test query returned {len(results['ids'][0])} results")
        print("\n✅ ChromaDB works!\n")

        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)

        return True

    except Exception as e:
        print(f"  ✗ ChromaDB error: {e}")
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("KNOWLEDGEVAULT SETUP TEST")
    print("="*60)
    print()

    tests = [
        ("Package Imports", test_imports),
        ("Configuration", test_config),
        ("Embedding Model", test_embedding_model),
        ("OpenAI API", test_openai),
        ("ChromaDB", test_chromadb),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} test crashed: {e}")
            results.append((name, False))

    # Summary
    print("="*60)
    print("TEST SUMMARY")
    print("="*60)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    all_passed = all(result for _, result in results)

    print()
    if all_passed:
        print("🎉 All tests passed! Your system is ready.")
        print()
        print("Next steps:")
        print("1. Run a test with small dataset:")
        print("   python main.py --limit 100 --skip-classification --skip-videos")
        print()
        print("2. Or read QUICKSTART.md for more options")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        print()
        print("Common fixes:")
        print("- Install packages: pip install -r requirements.txt")
        print("- Set API key: Copy .env.template to .env and add OPENAI_API_KEY")
        print("- Update paths in .env file")

    print("="*60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
