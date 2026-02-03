"""
Azure OpenAI Configuration
Centralized configuration for Azure OpenAI API access.
"""

import os
from openai import AzureOpenAI

# Azure OpenAI Configuration - READ FROM ENVIRONMENT VARIABLES
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://secondbrain-resource.openai.azure.com/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-05-01-preview")

# Deployment names (Azure uses deployment names instead of model names)
AZURE_CHAT_DEPLOYMENT = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-5-chat")
AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
AZURE_EMBEDDING_API_VERSION = os.getenv("AZURE_EMBEDDING_API_VERSION", "2024-05-01-preview")

def get_azure_client():
    """
    Get Azure OpenAI client configured for chat completions.
    """
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_API_VERSION
    )

def get_chat_completion(messages, temperature=0.7, max_tokens=1000):
    """
    Get chat completion from Azure OpenAI.

    Args:
        messages: List of message dicts with 'role' and 'content'
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        Response content string
    """
    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

    return response.choices[0].message.content

def get_embedding_client():
    """
    Get Azure OpenAI client configured for embeddings.
    Uses different API version for embeddings.
    """
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_EMBEDDING_API_VERSION
    )

def get_embedding(text):
    """
    Get embedding from Azure OpenAI.

    Args:
        text: Text to embed

    Returns:
        Embedding vector
    """
    client = get_embedding_client()

    response = client.embeddings.create(
        model=AZURE_EMBEDDING_DEPLOYMENT,
        input=text
    )

    return response.data[0].embedding

# Global client instance (lazy initialization)
_azure_client = None

def get_global_azure_client():
    """Get or create global Azure client (lazy initialization)"""
    global _azure_client
    if _azure_client is None:
        if AZURE_OPENAI_API_KEY:
            _azure_client = get_azure_client()
        else:
            raise ValueError("AZURE_OPENAI_API_KEY not set. Cannot create Azure client.")
    return _azure_client

# For backwards compatibility - only fails when accessed, not on import
class LazyAzureClient:
    def __getattr__(self, name):
        return getattr(get_global_azure_client(), name)

azure_client = LazyAzureClient()
