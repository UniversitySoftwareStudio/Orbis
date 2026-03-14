from __future__ import annotations

import re

from events.types import ObligationCandidate, SourceDocument
from events.utils import normalize_text


_BOUNDARY_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")
_ENUM_SPLIT_RE = re.compile(r"\s*\(\d+\)\s*|\s*[a-zA-Z]\)\s*")
_CLAUSE_SPLIT_RE = re.compile(r"\s*;\s*|\s*:\s*")
_FOOTNOTE_RE = re.compile(r"\[[0-9]+\]")
_ARTICLE_HEADER_RE = re.compile(
    r"^(article|madde|section|bölüm)\s+[0-9ivxlcdm]+[\-–:]*\s*",
    flags=re.IGNORECASE,
)


class ReasoningAgent:
    """Deterministic extractor focused on strict actionable statements."""

    _ACTION_PATTERNS = (
        re.compile(r"\bmust\b", re.IGNORECASE),
        re.compile(r"\bshall\b", re.IGNORECASE),
        re.compile(r"\brequired(?:\s+to)?\b", re.IGNORECASE),
        re.compile(r"\boblig(?:ed|ation)\b", re.IGNORECASE),
        re.compile(r"\bzorunlu(?:dur|dur\.|d?r|)\b", re.IGNORECASE),
        re.compile(r"\bzorundad(?:ır|ir|ırlar|irler)\b", re.IGNORECASE),
        re.compile(r"\byükümlüdür(?:ler)?\b", re.IGNORECASE),
        re.compile(r"\bmecbur(?:dur|idir)\b", re.IGNORECASE),
        re.compile(r"\ben\s+geç\b", re.IGNORECASE),
        re.compile(r"\btarihine\s+kadar\b", re.IGNORECASE),
    )

    _ACTOR_PATTERNS = (
        re.compile(r"\bstudents?\b", re.IGNORECASE),
        re.compile(r"\böğrenc(?:i|iler)\b", re.IGNORECASE),
        re.compile(r"\bstaff\b", re.IGNORECASE),
        re.compile(r"\bpersonel\b", re.IGNORECASE),
        re.compile(r"\bemployees?\b", re.IGNORECASE),
        re.compile(r"\bakademik\b", re.IGNORECASE),
        re.compile(r"\bidari\b", re.IGNORECASE),
        re.compile(r"\badmin\b", re.IGNORECASE),
        re.compile(r"\byönetim\b", re.IGNORECASE),
        re.compile(r"\brektörlük\b", re.IGNORECASE),
        re.compile(r"\bbuluş(?:çu| sahibi)\b", re.IGNORECASE),
        re.compile(r"\baraştırmac(?:ı|ilar|ılar)\b", re.IGNORECASE),
    )

    _BLOCKLIST_PATTERNS = (
        re.compile(r"for detailed information", re.IGNORECASE),
        re.compile(r"for more information", re.IGNORECASE),
        re.compile(r"\biletişim\b", re.IGNORECASE),
        re.compile(r"\bcontact us\b", re.IGNORECASE),
        re.compile(r"@", re.IGNORECASE),
        re.compile(r"https?://", re.IGNORECASE),
        re.compile(r"\bwww\.", re.IGNORECASE),
        re.compile(r"\buniversity values\b", re.IGNORECASE),
        re.compile(r"\büniversitemiz\b", re.IGNORECASE),
    )

    def extract(self, source: SourceDocument) -> list[ObligationCandidate]:
        obligations: list[ObligationCandidate] = []
        seen: set[str] = set()

        for segment in self._iter_atomic_segments(source.full_text):
            if self._is_blocklisted(segment):
                continue
            if not self._has_action(segment):
                continue
            if not self._looks_assignable(segment):
                continue

            role = self._detect_role(segment)
            normalized_segment = normalize_text(segment)
            key = f"{role}|{normalized_segment.lower()}"
            if key in seen:
                continue
            seen.add(key)

            metrics = {
                "length_chars": len(normalized_segment),
                "length_words": len(normalized_segment.split()),
                "clause_markers": len(re.findall(r"[;:]", normalized_segment)),
                "strict_marker_count": self._action_count(normalized_segment),
            }

            obligations.append(
                ObligationCandidate(
                    source_key=source.source_key,
                    source_url=source.canonical_url,
                    parent_category=source.parent_category,
                    category=source.category,
                    source_chunk_ids=source.chunk_ids,
                    obligation_text=normalized_segment,
                    evidence_excerpt=normalized_segment,
                    target_role=role,
                    metrics=metrics,
                )
            )

        return obligations

    @staticmethod
    def _cleanup(segment: str) -> str:
        value = _FOOTNOTE_RE.sub(" ", segment)
        value = _ARTICLE_HEADER_RE.sub("", value)
        value = normalize_text(value)
        return value

    def _iter_atomic_segments(self, text: str):
        prepared = normalize_text((text or "").replace("\n\n", ". "))
        for base in _BOUNDARY_SPLIT_RE.split(prepared):
            base = self._cleanup(base)
            if not base:
                continue

            enum_parts = [self._cleanup(p) for p in _ENUM_SPLIT_RE.split(base) if self._cleanup(p)]
            if not enum_parts:
                enum_parts = [base]

            for enum_part in enum_parts:
                clause_parts = [self._cleanup(p) for p in _CLAUSE_SPLIT_RE.split(enum_part) if self._cleanup(p)]
                if not clause_parts:
                    continue
                for clause in clause_parts:
                    if len(clause) < 35:
                        continue
                    if len(clause) > 420 and "," in clause:
                        comma_parts = [self._cleanup(p) for p in clause.split(",") if self._cleanup(p)]
                        for sub in comma_parts:
                            if len(sub) >= 35:
                                yield sub
                        continue
                    yield clause

    def _has_action(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self._ACTION_PATTERNS)

    def _action_count(self, text: str) -> int:
        return sum(1 for pattern in self._ACTION_PATTERNS if pattern.search(text))

    def _looks_assignable(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self._ACTOR_PATTERNS)

    def _is_blocklisted(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self._BLOCKLIST_PATTERNS)

    @staticmethod
    def _detect_role(text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("öğrenci", "students", "student")):
            return "student"
        if any(token in lowered for token in ("personel", "staff", "instructor", "employee", "akademik", "idari", "buluşçu", "araştırmacı")):
            return "staff"
        if any(token in lowered for token in ("admin", "yönetim", "dean", "rektörlük", "rectorate")):
            return "admin"
        return "all"


class NoopReasoningAgent(ReasoningAgent):
    def extract(self, source: SourceDocument) -> list[ObligationCandidate]:
        return []
