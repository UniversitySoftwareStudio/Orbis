import requests

from embedding.provider_base import EmbeddingProvider


class OllamaProvider(EmbeddingProvider):
    def __init__(self, api_url: str, model: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.dimension = 384
        self._validate_connection()

    def _validate_connection(self) -> None:
        try:
            requests.get(f"{self.api_url}/", timeout=5)
            response = requests.post(
                f"{self.api_url}/api/embeddings",
                json={"model": self.model, "prompt": "test"},
                timeout=10,
            )
            if response.status_code == 404:
                raise ValueError(f"Model {self.model} not found")
            response.raise_for_status()
            self.dimension = len(response.json().get("embedding"))
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(f"Could not connect to Ollama at {self.api_url}") from exc
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise ConnectionError(f"Ollama error: {exc}") from exc

    def embed_text(self, text: str) -> list[float]:
        response = requests.post(
            f"{self.api_url}/api/embeddings",
            json={"model": self.model, "prompt": text, "options": {"temperature": 0}},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    def get_dimension(self) -> int:
        return self.dimension
