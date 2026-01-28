"""
OpenAI Client Wrapper
Supports both Azure OpenAI and regular OpenAI APIs
"""
import os
from typing import Optional
from openai import OpenAI, AzureOpenAI


class OpenAIClientWrapper:
    """Wrapper that works with both Azure OpenAI and regular OpenAI"""

    def __init__(self):
        self.use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"

        if self.use_azure:
            # Azure OpenAI configuration
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            # Handle Azure AI Services project endpoints
            if "/api/projects/" in endpoint:
                # Remove trailing path for SDK compatibility
                base_endpoint = endpoint.split("/api/projects/")[0]
                self.client = AzureOpenAI(
                    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                    api_version=os.getenv("AZURE_API_VERSION", "2024-12-01-preview"),
                    azure_endpoint=base_endpoint,
                    default_headers={"api-project": endpoint.split("/api/projects/")[1]}
                )
            else:
                self.client = AzureOpenAI(
                    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                    api_version=os.getenv("AZURE_API_VERSION", "2024-12-01-preview"),
                    azure_endpoint=endpoint
                )
            self.chat_model = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4")
            self.embedding_model = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
        else:
            # Regular OpenAI configuration
            self.client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )
            self.chat_model = "gpt-4o-mini"  # More cost-effective for development
            self.embedding_model = "text-embedding-3-large"

    def chat_completion(self, messages, temperature=0.7, max_tokens=None, **kwargs):
        """Create a chat completion"""
        params = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        params.update(kwargs)

        return self.client.chat.completions.create(**params)

    def create_embedding(self, text, dimensions=1536):
        """Create embeddings"""
        return self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
            dimensions=dimensions
        )

    def get_chat_model(self):
        """Get the chat model name"""
        return self.chat_model

    def get_embedding_model(self):
        """Get the embedding model name"""
        return self.embedding_model


# Singleton instance
_client = None

def get_openai_client() -> OpenAIClientWrapper:
    """Get or create the OpenAI client singleton"""
    global _client
    if _client is None:
        _client = OpenAIClientWrapper()
    return _client
