"""Backward-compatible embedding runtime exports.

Prefer importing from `embedding.service` in new code.
"""

from embedding.config import EMBEDDING_MODEL, EMBEDDING_URL
from embedding.providers import EmbeddingProvider, TEIProvider
from embedding.service import EmbeddingService, get_embedding_service

__all__ = [
    "EMBEDDING_URL",
    "EMBEDDING_MODEL",
    "EmbeddingProvider",
    "TEIProvider",
    "EmbeddingService",
    "get_embedding_service",
]
