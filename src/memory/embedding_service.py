"""Azure OpenAI embedding service for pgvector."""

from openai import AzureOpenAI
from typing import List
import asyncio


class AzureEmbeddingService:
    """Azure OpenAI embedding service for pgvector."""
    
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str = "2023-05-15"
    ):
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        self.deployment = deployment
    
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # Run sync OpenAI call in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.embeddings.create(
                input=text,
                model=self.deployment
            )
        )
        return response.data[0].embedding
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.embeddings.create(
                input=texts,
                model=self.deployment
            )
        )
        return [item.embedding for item in response.data]
