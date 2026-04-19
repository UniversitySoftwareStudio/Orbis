"""Embedding provider exports.

This module intentionally exposes only the active provider interface and TEI
implementation used by the application.
"""

from embedding.provider_base import EmbeddingProvider
from embedding.tei_provider import TEIProvider

__all__ = ["EmbeddingProvider", "TEIProvider"]
