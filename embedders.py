from abc import ABC, abstractmethod
from typing import List, Optional
import requests


class Embedder(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        pass

    def embed_query(self, text: str) -> List[float]:
        return self.embed([text])[0]


class VoyageAIEmbedder(Embedder):
    DIMENSIONS = {
        "voyage-3": 1024,
        "voyage-3-lite": 512,
        "voyage-large-2": 1536,
    }

    def __init__(self, api_key: str, model: str = "voyage-3"):
        try:
            import voyageai
        except ImportError:
            raise ImportError("pip install voyageai")

        if model not in self.DIMENSIONS:
            raise ValueError(f"Unknown model: {model}. Choose from: {list(self.DIMENSIONS.keys())}")

        self.client = voyageai.Client(api_key=api_key)
        self.model = model
        self._dimension = self.DIMENSIONS[model]

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        all_embeddings = []
        batch_size = 128

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            result = self.client.embed(batch, model=self.model)
            all_embeddings.extend(result.embeddings)

        return all_embeddings


class OpenRouterEmbedder(Embedder):
    DIMENSIONS = {
        "openai/text-embedding-3-small": 1536,
        "openai/text-embedding-3-large": 3072,
        "openai/text-embedding-ada-002": 1536,
    }

    def __init__(self, api_key: str, model: str = "openai/text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        self._dimension = self.DIMENSIONS.get(model, 1536)

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        response = requests.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": texts,
            },
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        return [item["embedding"] for item in data["data"]]


def create_embedder(
    provider: str = "voyage",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Embedder:
    import os

    if provider == "voyage":
        key = api_key or os.getenv("VOYAGE_API_KEY")
        if not key:
            raise ValueError("Voyage AI API key required. Set VOYAGE_API_KEY env var.")
        return VoyageAIEmbedder(key, model or "voyage-3")

    elif provider == "openrouter":
        key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise ValueError("OpenRouter API key required. Set OPENROUTER_API_KEY env var.")
        return OpenRouterEmbedder(key, model or "openai/text-embedding-3-small")

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'voyage' or 'openrouter'")


EmbedderInterface = Embedder
