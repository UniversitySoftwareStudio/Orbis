from __future__ import annotations

from collections import defaultdict
from sqlalchemy.orm import Session

from database.models import KnowledgeBase
from events.types import SourceDocument
from events.utils import canonicalize_url, hash_text, make_source_key, normalize_text


class SearchAgent:
    """Stateless source loader for regulation categories."""

    _REGULATION_SIGNAL_MARKERS = (
        "rule",
        "regulation",
        "regulations",
        "rules-and-regulations",
        "procedure",
        "procedures",
        "directive",
        "directives",
        "ethic",
        "conduct",
        "policy",
        "yonerge",
        "yönerge",
        "yonetmelik",
        "yönetmelik",
        "mevzuat",
        "handbook",
        "el-kitabi",
        "el-kitabı",
        "staj",
        "sinav",
        "sınav",
        "disciplin",
        "disiplin",
        "ibraz",
        "code-of-conduct",
        "information-security-policy",
        "bilgi-guvenligi",
        "bilgi-güvenliği",
    )
    _REGULATION_NOISE_MARKERS = (
        "community-services",
        "supporters",
        "projects",
        "lectures",
        "sustainability",
        "topluma-hizmet",
        "projeler",
        "social-responsibility",
    )

    def fetch_regulation_sources(self, db: Session) -> list[SourceDocument]:
        rows = list(
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.category.in_(["regulation", "regulation_document"]))
            .order_by(KnowledgeBase.category.asc(), KnowledgeBase.url.asc(), KnowledgeBase.id.asc())
            .all()
        )

        groups: dict[tuple[str, str], list[KnowledgeBase]] = defaultdict(list)
        for row in rows:
            groups[(row.category or "", canonicalize_url(row.url))].append(row)

        sources: list[SourceDocument] = []
        for (category, canonical_url), grouped in groups.items():
            ordered = sorted(grouped, key=lambda item: (item.url, str(item.id)))
            text_parts = [normalize_text(item.content or "") for item in ordered if (item.content or "").strip()]
            if not text_parts:
                continue

            full_text = "\n\n".join(text_parts)
            content_hash = hash_text(full_text)
            source_key = make_source_key(ordered[0].url, content_hash)
            chunk_ids = [item.id for item in ordered]
            representative_url = ordered[0].url
            signal_score = self._signal_score(representative_url)
            lowered_url = canonicalize_url(representative_url).lower()
            has_noise = any(marker in lowered_url for marker in self._REGULATION_NOISE_MARKERS)
            should_process = category == "regulation_document" or (signal_score > 0 and not has_noise)
            skip_reason = None if should_process else "low_regulatory_signal"
            sources.append(
                SourceDocument(
                    source_key=source_key,
                    content_hash=content_hash,
                    canonical_url=representative_url,
                    parent_category=ordered[0].parent_category or "regulation",
                    category=category,
                    chunk_ids=chunk_ids,
                    chunk_count=len(chunk_ids),
                    full_text=full_text,
                    should_process=should_process,
                    skip_reason=skip_reason,
                    regulatory_signal_score=signal_score,
                )
            )

        sources.sort(key=lambda item: (item.parent_category, item.category, canonicalize_url(item.canonical_url)))
        return sources

    def _signal_score(self, url: str) -> int:
        value = canonicalize_url(url).lower()
        score = sum(1 for marker in self._REGULATION_SIGNAL_MARKERS if marker in value)
        if value.endswith(".pdf"):
            score += 1
        return score
