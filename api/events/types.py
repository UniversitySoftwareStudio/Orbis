from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SourceDocument:
    source_key: str
    content_hash: str
    canonical_url: str
    parent_category: str
    category: str
    chunk_ids: list[UUID]
    chunk_count: int
    full_text: str
    should_process: bool = True
    skip_reason: str | None = None
    regulatory_signal_score: int = 0


@dataclass(frozen=True)
class ObligationCandidate:
    source_key: str
    source_url: str
    parent_category: str
    category: str
    source_chunk_ids: list[UUID]
    obligation_text: str
    evidence_excerpt: str
    target_role: str
    metrics: dict[str, int] | None = None
