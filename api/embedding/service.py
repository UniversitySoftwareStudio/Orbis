import logging
import threading

from embedding.config import EMBEDDING_MODEL, EMBEDDING_URL
from embedding.providers import EmbeddingProvider, TEIProvider

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self) -> None:
        self.provider = self._create_provider()
        self.model_name = EMBEDDING_MODEL
        logger.info(
            "Embedding configured: url=%s model=%s dim=%s",
            EMBEDDING_URL,
            self.model_name,
            self.provider.get_dimension(),
        )

    def _create_provider(self) -> EmbeddingProvider:
        return TEIProvider(EMBEDDING_URL, model_name=EMBEDDING_MODEL)

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

    def get_model_name(self) -> str:
        return self.model_name

    def get_runtime_info(self) -> dict[str, str | int]:
        return {
            "embedding_url": EMBEDDING_URL,
            "model_name": self.model_name,
            "dimension": self.get_dimension(),
        }


_embedding_service: EmbeddingService | None = None
_embedding_service_lock = threading.Lock()


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        with _embedding_service_lock:
            if _embedding_service is None:
                _embedding_service = EmbeddingService()
    return _embedding_service
