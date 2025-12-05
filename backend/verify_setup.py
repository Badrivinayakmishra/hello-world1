"""Verify all external service configurations for KnowledgeVault"""
import os
import sys
from dotenv import load_dotenv

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"


# Load environment
load_dotenv("/Users/rishitjain/Downloads/knowledgevault_backend/.env")

def check_env_var(name: str, placeholder_check: str = None) -> tuple:
    """Check if environment variable is set and not a placeholder"""
    value = os.getenv(name)
    if not value:
        return False, "Not set"
    if placeholder_check and placeholder_check in value.lower():
        return False, f"Still placeholder: {value[:30]}..."
    return True, f"Configured: {value[:20]}..." if len(value) > 20 else f"Configured: {value}"

def verify_pinecone():
    """Verify Pinecone connection"""
    print("\n🔷 PINECONE VECTOR DATABASE")
    print("-" * 40)

    ok, msg = check_env_var("PINECONE_API_KEY", "your_")
    print(f"  API Key: {'✅' if ok else '❌'} {msg}")

    ok, msg = check_env_var("PINECONE_INDEX")
    print(f"  Index Name: {'✅' if ok else '❌'} {msg}")

    if os.getenv("PINECONE_API_KEY") and "your_" not in os.getenv("PINECONE_API_KEY", "").lower():
        try:
            from pinecone import Pinecone
            pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            indexes = [idx.name for idx in pc.list_indexes()]
            index_name = os.getenv("PINECONE_INDEX", "knowledgevault")
            if index_name in indexes:
                index = pc.Index(index_name)
                stats = index.describe_index_stats()
                print(f"  Connection: ✅ Connected")
                print(f"  Vectors: {stats.total_vector_count}")
                print(f"  Dimension: {stats.dimension}")
                return True
            else:
                print(f"  Connection: ❌ Index '{index_name}' not found")
                print(f"  Available: {indexes}")
        except Exception as e:
            print(f"  Connection: ❌ {str(e)[:50]}")
    return False

def verify_auth0():
    """Verify Auth0 configuration"""
    print("\n🔐 AUTH0 AUTHENTICATION")
    print("-" * 40)

    ok1, msg1 = check_env_var("AUTH0_DOMAIN", "your-tenant")
    print(f"  Domain: {'✅' if ok1 else '❌'} {msg1}")

    ok2, msg2 = check_env_var("AUTH0_CLIENT_ID", "your_")
    print(f"  Client ID: {'✅' if ok2 else '❌'} {msg2}")

    ok3, msg3 = check_env_var("AUTH0_CLIENT_SECRET", "your_")
    print(f"  Client Secret: {'✅' if ok3 else '❌'} {msg3}")

    ok4, msg4 = check_env_var("AUTH0_API_AUDIENCE")
    print(f"  API Audience: {'✅' if ok4 else '❌'} {msg4}")

    if all([ok1, ok2, ok3]):
        # Try to fetch JWKS
        try:
            import urllib.request
            import json
            domain = os.getenv("AUTH0_DOMAIN")
            url = f"https://{domain}/.well-known/jwks.json"
            with urllib.request.urlopen(url, timeout=5) as response:
                jwks = json.loads(response.read())
                if "keys" in jwks:
                    print(f"  JWKS: ✅ Found {len(jwks['keys'])} keys")
                    return True
        except Exception as e:
            print(f"  JWKS: ❌ Cannot fetch - {str(e)[:40]}")
    return False

def verify_google():
    """Verify Google/Gmail OAuth configuration"""
    print("\n📧 GOOGLE/GMAIL OAUTH")
    print("-" * 40)

    ok1, msg1 = check_env_var("GOOGLE_CLIENT_ID", "your_")
    print(f"  Client ID: {'✅' if ok1 else '❌'} {msg1}")

    ok2, msg2 = check_env_var("GOOGLE_CLIENT_SECRET", "your_")
    print(f"  Client Secret: {'✅' if ok2 else '❌'} {msg2}")

    ok3, msg3 = check_env_var("GOOGLE_REDIRECT_URI")
    print(f"  Redirect URI: {'✅' if ok3 else '❌'} {msg3}")

    if all([ok1, ok2]):
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        if client_id.endswith(".apps.googleusercontent.com"):
            print(f"  Format: ✅ Valid Google Client ID format")
            return True
        else:
            print(f"  Format: ❌ Should end with .apps.googleusercontent.com")
    return False

def verify_openai():
    """Verify OpenAI configuration"""
    print("\n🤖 OPENAI API")
    print("-" * 40)

    ok, msg = check_env_var("OPENAI_API_KEY", "your_")
    print(f"  API Key: {'✅' if ok else '❌'} {msg}")

    if ok:
        try:
            from openai import AzureOpenAI
            client = OpenAI()
            # Quick test with minimal tokens
            response = client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": "Say 'OK'"}],
                max_tokens=5
            )
            print(f"  Connection: ✅ Working (tested gpt-4o-mini)")
            return True
        except Exception as e:
            print(f"  Connection: ❌ {str(e)[:50]}")
    return False

def main():
    print("=" * 50)
    print("KNOWLEDGEVAULT - CONFIGURATION VERIFICATION")
    print("=" * 50)

    results = {}

    results["openai"] = verify_openai()
    results["pinecone"] = verify_pinecone()
    results["auth0"] = verify_auth0()
    results["google"] = verify_google()

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    all_ok = True
    for service, ok in results.items():
        status = "✅ Ready" if ok else "⚠️  Needs Setup"
        print(f"  {service.upper()}: {status}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("🎉 All services configured and ready!")
    else:
        print("📋 Some services need configuration. Update .env file with credentials.")
        print("\nSetup guides:")
        if not results["auth0"]:
            print("  Auth0: https://auth0.com → Create tenant → APIs → Create API")
        if not results["google"]:
            print("  Google: https://console.cloud.google.com → APIs → Gmail API → OAuth")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
