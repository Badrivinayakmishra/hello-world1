"""
Test Azure OpenAI Configuration
Run this locally to verify your Azure settings work
"""
import os
from openai import AzureOpenAI

# Your config
endpoint = "https://secondbrain-resource.services.ai.azure.com/api/projects/Secondbrain"
api_key = "7vb1fWJykGyS3rz82TqieFWA2JyiQtqQaJzUa0hh-Fqqc1S54ghmKJQQJ99CAACHYHv6XJ3w3AAAAACO-GORVD"
api_version = "2024-12-01-preview"

# Extract base endpoint for SDK
base_endpoint = endpoint.split("/api/projects/")[0]
project_name = endpoint.split("/api/projects/")[1]

print(f"Testing Azure OpenAI Configuration:")
print(f"  Base Endpoint: {base_endpoint}")
print(f"  Project: {project_name}")
print(f"  API Version: {api_version}")
print()

try:
    # Test 1: Embedding
    print("Test 1: Creating embedding...")
    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=base_endpoint,
        default_headers={"api-project": project_name}
    )

    response = client.embeddings.create(
        model="text-embedding-3-large",  # Your deployment name
        input="Hello, this is a test",
        dimensions=1536
    )

    print(f"✅ SUCCESS! Embedding created: {len(response.data[0].embedding)} dimensions")
    print()

except Exception as e:
    print(f"❌ FAILED: {e}")
    print()
    print("Common fixes:")
    print("  1. Check deployment name in Azure Portal")
    print("  2. Verify API key is correct and active")
    print("  3. Ensure endpoint format is correct")
    print()
