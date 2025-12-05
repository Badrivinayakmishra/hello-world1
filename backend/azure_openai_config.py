"""
Azure OpenAI Configuration
Centralized configuration for Azure OpenAI API access.
"""

import os
from openai import AzureOpenAI

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = "2025-01-01-preview"

# Deployment names (Azure uses deployment names instead of model names)
AZURE_CHAT_DEPLOYMENT = "gpt-5-chat"  # For chat completions
AZURE_EMBEDDING_DEPLOYMENT = "text-embedding-3-large"  # For embeddings
AZURE_EMBEDDING_API_VERSION = "2023-05-15"  # Embedding API version

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

# Global client instance
azure_client = get_azure_client()
