import threading

from embedding.config import EMBEDDING_PROVIDER, OLLAMA_MODEL, OLLAMA_URL, select_tei_url
from embedding.providers import EmbeddingProvider, OllamaProvider, TEIProvider


class EmbeddingService:
    def __init__(self) -> None:
        self.provider = self._create_provider()

    @staticmethod
    def _create_provider() -> EmbeddingProvider:
        if EMBEDDING_PROVIDER == "ollama":
            return OllamaProvider(OLLAMA_URL, OLLAMA_MODEL)
        if EMBEDDING_PROVIDER == "tei":
            return TEIProvider(select_tei_url())
        raise ValueError(f"Unknown embedding provider: {EMBEDDING_PROVIDER}")

    def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        return self.provider.embed_text(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("Texts list cannot be empty")
        return self.provider.embed_batch(texts)

    def get_dimension(self) -> int:
        return self.provider.get_dimension()


_embedding_service: EmbeddingService | None = None
_embedding_service_lock = threading.Lock()


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        with _embedding_service_lock:
            if _embedding_service is None:
                _embedding_service = EmbeddingService()
    return _embedding_service
