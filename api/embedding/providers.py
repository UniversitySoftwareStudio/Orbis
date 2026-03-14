from embedding.ollama_provider import OllamaProvider
from embedding.provider_base import EmbeddingProvider
from embedding.tei_provider import TEIProvider
try:
    from embedding.local_provider import LocalProvider
except ModuleNotFoundError:  # Optional dependency: sentence_transformers
    LocalProvider = None

__all__ = ["EmbeddingProvider", "TEIProvider", "OllamaProvider"]
if LocalProvider is not None:
    __all__.append("LocalProvider")
