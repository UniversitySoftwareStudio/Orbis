from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import Event, EventCandidateDecision, EventCandidateLog, EventStatus, EventTargetRole
from events.reasoning_reviewer import ReviewedCandidate, ReasoningReviewer
from events.types import ObligationCandidate
from events.utils import hash_text, make_event_fingerprint, normalize_text


_STRICT_ACTION_PATTERNS = (
    re.compile(r"\bmust\b", re.IGNORECASE),
    re.compile(r"\bshall\b", re.IGNORECASE),
    re.compile(r"\brequired(?:\s+to)?\b", re.IGNORECASE),
    re.compile(r"\boblig(?:ed|ation)\b", re.IGNORECASE),
    re.compile(r"\bzorunlu(?:dur|)\b", re.IGNORECASE),
    re.compile(r"\bzorundad(?:ır|ir|ırlar|irler)\b", re.IGNORECASE),
    re.compile(r"\byükümlüdür(?:ler)?\b", re.IGNORECASE),
    re.compile(r"\bmecbur(?:dur|idir)\b", re.IGNORECASE),
    re.compile(r"\ben\s+geç\b", re.IGNORECASE),
    re.compile(r"\btarihine\s+kadar\b", re.IGNORECASE),
)

_STUDENT_ACTOR_PATTERNS = (
    re.compile(r"\bstudents?\b", re.IGNORECASE),
    re.compile(r"\böğrenc(?:i|iler)\b", re.IGNORECASE),
    re.compile(r"\bthe student\b", re.IGNORECASE),
)

_STAFF_ACTOR_PATTERNS = (
    re.compile(r"\bstaff\b", re.IGNORECASE),
    re.compile(r"\bpersonel\b", re.IGNORECASE),
    re.compile(r"\bemployees?\b", re.IGNORECASE),
    re.compile(r"\bakademik\b", re.IGNORECASE),
    re.compile(r"\bidari\b", re.IGNORECASE),
    re.compile(r"\bbuluş(?:çu|\s+sahibi)\b", re.IGNORECASE),
    re.compile(r"\baraştırmac(?:ı|ilar|ılar)\b", re.IGNORECASE),
)

_ADMIN_ACTOR_PATTERNS = (
    re.compile(r"\badmin\b", re.IGNORECASE),
    re.compile(r"\byönetim\b", re.IGNORECASE),
    re.compile(r"\brektörlük\b", re.IGNORECASE),
    re.compile(r"\bcommittee\b", re.IGNORECASE),
    re.compile(r"\bboard\b", re.IGNORECASE),
    re.compile(r"\bdean(?:'s)?\b", re.IGNORECASE),
    re.compile(r"\bfaculty executive board\b", re.IGNORECASE),
    re.compile(r"\byönetim kurulu\b", re.IGNORECASE),
)

_ACTOR_PATTERNS = (
    *_STUDENT_ACTOR_PATTERNS,
    *_STAFF_ACTOR_PATTERNS,
    *_ADMIN_ACTOR_PATTERNS,
)

_WEAK_MODAL_PATTERNS = (
    re.compile(r"\bcan\b", re.IGNORECASE),
    re.compile(r"\bmay\b", re.IGNORECASE),
    re.compile(r"yapabilir", re.IGNORECASE),
    re.compile(r"öner", re.IGNORECASE),
    re.compile(r"encourag", re.IGNORECASE),
)

_NON_ACTIONABLE_PATTERNS = (
    re.compile(r"for detailed information", re.IGNORECASE),
    re.compile(r"for more information", re.IGNORECASE),
    re.compile(r"\biletişim\b", re.IGNORECASE),
    re.compile(r"\bcontact\b", re.IGNORECASE),
    re.compile(r"@", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bwww\.", re.IGNORECASE),
    re.compile(r"\bwebsite\b", re.IGNORECASE),
    re.compile(r"\buniversity values\b", re.IGNORECASE),
    re.compile(r"\bdeğer verir\b", re.IGNORECASE),
)

_NON_ASSIGNABLE_GOVERNANCE_PATTERNS = (
    re.compile(r"\bshall be determined by\b", re.IGNORECASE),
    re.compile(r"\bshall apply\b", re.IGNORECASE),
    re.compile(r"\bshall be subject to\b", re.IGNORECASE),
    re.compile(r"\bshall be granted\b", re.IGNORECASE),
    re.compile(r"\bshall be finalized\b", re.IGNORECASE),
    re.compile(r"\bwill be determined by\b", re.IGNORECASE),
    re.compile(r"\bkarara bağlan(?:ır|acaktır)\b", re.IGNORECASE),
    re.compile(r"\bbelirlen(?:ir|ecektir)\b", re.IGNORECASE),
    re.compile(r"\buygulan(?:ır|acaktır)\b", re.IGNORECASE),
    re.compile(r"\bhükümleri uygulanır\b", re.IGNORECASE),
    re.compile(r"\btabidir\b", re.IGNORECASE),
    re.compile(r"\bçerçevesinde\b", re.IGNORECASE),
)

_HEADER_NOISE_PATTERNS = (
    re.compile(r"^\s*(article|madde|section|provisional article)\s+[0-9ivxlcdm]+[\s:.\-–]+", re.IGNORECASE),
    re.compile(r"^\s*[0-9]{1,3}\s+(article|madde|section)\b", re.IGNORECASE),
    re.compile(r"^\s*[0-9]{1,3}\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+", re.IGNORECASE),
)

_LEADING_CONNECTOR_PATTERNS = (
    re.compile(r"^\s*(and|or|ve|veya|ile)\b", re.IGNORECASE),
    re.compile(r"^\s*[,:;]", re.IGNORECASE),
)

_OCR_BREAK_RE = re.compile(r"(\w)-\s+(\w)")


@dataclass(frozen=True)
class PersistStats:
    created: int
    created_pending: int
    created_review: int
    skipped_quality: int
    skipped_duplicate: int
    rejection_reasons: dict[str, int]
    reviewed_by_llm: int


@dataclass(frozen=True)
class QualityDecision:
    decision: EventCandidateDecision
    reason_code: str
    status: EventStatus | None
    metrics: dict[str, int | float | bool | str]


class EventCreator:
    """Deterministic persistence with optional LLM reasoning review."""

    def __init__(self) -> None:
        self.reviewer = ReasoningReviewer()

    def persist_candidates(self, db: Session, run_id, candidates: list[ObligationCandidate]) -> PersistStats:
        created = 0
        created_pending = 0
        created_review = 0
        skipped_quality = 0
        skipped_duplicate = 0
        rejection_reasons: dict[str, int] = {}
        batch_seen: set[str] = set()

        base_decisions: dict[int, QualityDecision] = {}
        review_requests: list[dict[str, str]] = []
        reviewer_enabled = self.reviewer.enabled
        for idx, candidate in enumerate(candidates):
            decision = self._evaluate_candidate(candidate)
            base_decisions[idx] = decision
            if decision.decision != EventCandidateDecision.REJECT_QUALITY:
                review_requests.append(
                    {
                        "idx": idx,
                        "text": self._sanitize_text(candidate.obligation_text),
                        "role": (candidate.target_role or "all").lower(),
                        "url": candidate.source_url,
                        "category": candidate.category,
                    }
                )

        review_results: dict[int, ReviewedCandidate] = self.reviewer.review_batch(review_requests)
        reviewed_by_llm = len(review_results)

        for idx, candidate in enumerate(candidates):
            base = base_decisions[idx]
            normalized_text = self._sanitize_text(candidate.obligation_text)
            final_role = (candidate.target_role or "all").strip().lower()
            metrics = dict(base.metrics)
            metrics["base_reason_code"] = base.reason_code
            metrics["base_decision"] = base.decision.value
            metrics["llm_reviewed"] = False

            decision = base.decision
            decision_reason = base.reason_code
            decision_status = base.status

            review = review_results.get(idx)
            if review is not None:
                metrics["llm_reviewed"] = True
                metrics["llm_decision"] = review.decision.value
                metrics["llm_reason_code"] = review.reason_code
                if review.normalized_text:
                    normalized_text = self._sanitize_text(review.normalized_text)
                if review.target_role in {"student", "staff", "admin", "all"}:
                    final_role = review.target_role
                decision = review.decision
                decision_reason = f"llm_{review.reason_code}"
                if review.decision == EventCandidateDecision.ACCEPT_PENDING:
                    decision_status = EventStatus.PENDING
                elif review.decision == EventCandidateDecision.ACCEPT_REVIEW:
                    decision_status = EventStatus.NEEDS_REVIEW
                else:
                    decision_status = None
            elif reviewer_enabled and base.decision != EventCandidateDecision.REJECT_QUALITY:
                decision = EventCandidateDecision.REJECT_QUALITY
                decision_reason = "llm_missing_decision"
                decision_status = None

            # safety re-check after LLM normalization/role override
            safety_candidate = ObligationCandidate(
                source_key=candidate.source_key,
                source_url=candidate.source_url,
                parent_category=candidate.parent_category,
                category=candidate.category,
                source_chunk_ids=candidate.source_chunk_ids,
                obligation_text=normalized_text,
                evidence_excerpt=self._sanitize_text(candidate.evidence_excerpt),
                target_role=final_role,
                metrics=candidate.metrics,
            )
            safety = self._evaluate_candidate(safety_candidate)
            metrics["safety_reason_code"] = safety.reason_code
            metrics["safety_decision"] = safety.decision.value

            if safety.decision == EventCandidateDecision.REJECT_QUALITY:
                decision = EventCandidateDecision.REJECT_QUALITY
                decision_reason = f"safety_{safety.reason_code}"
                decision_status = None
            elif decision != EventCandidateDecision.REJECT_QUALITY:
                if decision == EventCandidateDecision.ACCEPT_PENDING and safety.decision == EventCandidateDecision.ACCEPT_REVIEW:
                    decision = EventCandidateDecision.ACCEPT_REVIEW
                    decision_status = EventStatus.NEEDS_REVIEW
                    decision_reason = f"{decision_reason}|safety_review"
                elif decision == EventCandidateDecision.ACCEPT_REVIEW and decision_status is None:
                    decision_status = EventStatus.NEEDS_REVIEW

            candidate_hash = hash_text(
                f"{candidate.source_key}|{final_role}|{normalized_text.lower()}"
            )

            if decision == EventCandidateDecision.REJECT_QUALITY:
                skipped_quality += 1
                rejection_reasons[decision_reason] = rejection_reasons.get(decision_reason, 0) + 1
                self._log_candidate(
                    db=db,
                    run_id=run_id,
                    candidate=candidate,
                    candidate_hash=candidate_hash,
                    normalized_text=normalized_text,
                    decision=EventCandidateDecision.REJECT_QUALITY,
                    reason_code=decision_reason,
                    metrics=metrics,
                    target_role=final_role,
                )
                continue

            fingerprint = make_event_fingerprint(
                obligation_text=normalized_text,
                target_role=final_role,
            )
            if fingerprint in batch_seen:
                skipped_duplicate += 1
                rejection_reasons["duplicate_in_batch"] = rejection_reasons.get("duplicate_in_batch", 0) + 1
                self._log_candidate(
                    db=db,
                    run_id=run_id,
                    candidate=candidate,
                    candidate_hash=candidate_hash,
                    normalized_text=normalized_text,
                    decision=EventCandidateDecision.REJECT_DUPLICATE,
                    reason_code="duplicate_in_batch",
                    metrics=metrics,
                    target_role=final_role,
                )
                continue
            batch_seen.add(fingerprint)

            exists = db.query(Event.id).filter(Event.fingerprint == fingerprint).first()
            if exists is not None:
                skipped_duplicate += 1
                rejection_reasons["duplicate_existing"] = rejection_reasons.get("duplicate_existing", 0) + 1
                self._log_candidate(
                    db=db,
                    run_id=run_id,
                    candidate=candidate,
                    candidate_hash=candidate_hash,
                    normalized_text=normalized_text,
                    decision=EventCandidateDecision.REJECT_DUPLICATE,
                    reason_code="duplicate_existing",
                    metrics=metrics,
                    target_role=final_role,
                )
                continue

            final_status = EventStatus.PENDING if decision == EventCandidateDecision.ACCEPT_PENDING else EventStatus.NEEDS_REVIEW
            event = Event(
                run_id=run_id,
                source_key=candidate.source_key,
                source_chunk_ids=[str(chunk_id) for chunk_id in candidate.source_chunk_ids],
                source_url=candidate.source_url,
                category=candidate.category,
                parent_category=candidate.parent_category,
                obligation_text=normalized_text,
                evidence_excerpt=self._sanitize_text(candidate.evidence_excerpt),
                target_role=self._map_role(final_role),
                status=final_status,
                fingerprint=fingerprint,
            )
            db.add(event)
            created += 1

            if final_status == EventStatus.PENDING:
                created_pending += 1
                final_decision = EventCandidateDecision.ACCEPT_PENDING
            else:
                created_review += 1
                final_decision = EventCandidateDecision.ACCEPT_REVIEW

            self._log_candidate(
                db=db,
                run_id=run_id,
                candidate=candidate,
                candidate_hash=candidate_hash,
                normalized_text=normalized_text,
                decision=final_decision,
                reason_code=decision_reason,
                metrics=metrics,
                target_role=final_role,
            )

        return PersistStats(
            created=created,
            created_pending=created_pending,
            created_review=created_review,
            skipped_quality=skipped_quality,
            skipped_duplicate=skipped_duplicate,
            rejection_reasons=rejection_reasons,
            reviewed_by_llm=reviewed_by_llm,
        )

    @staticmethod
    def _map_role(role: str) -> EventTargetRole:
        normalized = (role or "all").strip().lower()
        if normalized == "student":
            return EventTargetRole.STUDENT
        if normalized == "staff":
            return EventTargetRole.STAFF
        if normalized == "admin":
            return EventTargetRole.ADMIN
        return EventTargetRole.ALL

    def _evaluate_candidate(self, candidate: ObligationCandidate) -> QualityDecision:
        text = self._sanitize_text(candidate.obligation_text)
        excerpt = self._sanitize_text(candidate.evidence_excerpt)
        word_count = len(text.split())
        clause_count = len(re.findall(r"[;:]", text))
        sentence_markers = len(re.findall(r"[.!?]", text))
        action_marker_count = sum(1 for pattern in _STRICT_ACTION_PATTERNS if pattern.search(text))

        base_metrics: dict[str, int | float | bool | str] = {
            "length_chars": len(text),
            "length_words": word_count,
            "clause_count": clause_count,
            "sentence_markers": sentence_markers,
            "action_marker_count": action_marker_count,
        }

        if len(text) < 20 or len(excerpt) < 20:
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="too_short",
                status=None,
                metrics=base_metrics,
            )

        if any(pattern.search(text) for pattern in _HEADER_NOISE_PATTERNS):
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="header_noise",
                status=None,
                metrics=base_metrics,
            )

        if any(pattern.search(text) for pattern in _LEADING_CONNECTOR_PATTERNS):
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="fragment_leading_connector",
                status=None,
                metrics=base_metrics,
            )

        ratio = difflib.SequenceMatcher(None, text.lower(), excerpt.lower()).ratio()
        base_metrics["evidence_similarity"] = round(ratio, 4)
        if ratio < 0.75:
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="weak_evidence_match",
                status=None,
                metrics=base_metrics,
            )

        if any(pattern.search(text) for pattern in _NON_ACTIONABLE_PATTERNS):
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="non_actionable_statement",
                status=None,
                metrics=base_metrics,
            )

        if any(pattern.search(text) for pattern in _NON_ASSIGNABLE_GOVERNANCE_PATTERNS):
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="non_assignable_governance",
                status=None,
                metrics=base_metrics,
            )

        has_action = any(pattern.search(text) for pattern in _STRICT_ACTION_PATTERNS)
        base_metrics["has_strict_action"] = has_action
        if not has_action:
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="missing_action_marker",
                status=None,
                metrics=base_metrics,
            )

        role_hits = self._role_hits(text)
        base_metrics["role_hits"] = role_hits
        active_role_count = sum(1 for count in role_hits.values() if count > 0)
        if active_role_count == 0:
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="missing_actor",
                status=None,
                metrics=base_metrics,
            )

        has_actor = any(pattern.search(text) for pattern in _ACTOR_PATTERNS)
        base_metrics["has_actor"] = has_actor
        if not has_actor:
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="missing_actor",
                status=None,
                metrics=base_metrics,
            )

        if len(re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]{2,}", text)) < 6:
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="fragmented_text",
                status=None,
                metrics=base_metrics,
            )

        extreme_complexity = len(text) > 420 or clause_count > 3 or word_count > 95
        base_metrics["extreme_complexity"] = extreme_complexity
        if extreme_complexity:
            return QualityDecision(
                decision=EventCandidateDecision.REJECT_QUALITY,
                reason_code="too_complex",
                status=None,
                metrics=base_metrics,
            )

        has_weak_modal = any(pattern.search(text) for pattern in _WEAK_MODAL_PATTERNS)
        base_metrics["has_weak_modal"] = has_weak_modal
        high_complexity = len(text) > 260 or clause_count > 1 or word_count > 45 or sentence_markers > 1
        base_metrics["high_complexity"] = high_complexity

        if has_weak_modal:
            return QualityDecision(
                decision=EventCandidateDecision.ACCEPT_REVIEW,
                reason_code="weak_modal_review",
                status=EventStatus.NEEDS_REVIEW,
                metrics=base_metrics,
            )

        if active_role_count > 1:
            return QualityDecision(
                decision=EventCandidateDecision.ACCEPT_REVIEW,
                reason_code="role_ambiguous_review",
                status=EventStatus.NEEDS_REVIEW,
                metrics=base_metrics,
            )

        if action_marker_count > 1 and re.search(r"\b(and|or|ve|veya)\b", text, re.IGNORECASE):
            return QualityDecision(
                decision=EventCandidateDecision.ACCEPT_REVIEW,
                reason_code="multi_action_review",
                status=EventStatus.NEEDS_REVIEW,
                metrics=base_metrics,
            )

        if high_complexity:
            return QualityDecision(
                decision=EventCandidateDecision.ACCEPT_REVIEW,
                reason_code="complexity_review",
                status=EventStatus.NEEDS_REVIEW,
                metrics=base_metrics,
            )

        return QualityDecision(
            decision=EventCandidateDecision.ACCEPT_PENDING,
            reason_code="high_confidence",
            status=EventStatus.PENDING,
            metrics=base_metrics,
        )

    @staticmethod
    def _sanitize_text(value: str) -> str:
        text = normalize_text(value or "")
        text = _OCR_BREAK_RE.sub(r"\1\2", text)
        text = re.sub(
            r"^\s*(article|madde|section|provisional article)\s+[0-9ivxlcdm]+[\s:.\-–]+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"^\s*[0-9]{1,3}\s+", "", text)
        return normalize_text(text).strip(" -,:;")

    @staticmethod
    def _role_hits(text: str) -> dict[str, int]:
        return {
            "student": sum(1 for pattern in _STUDENT_ACTOR_PATTERNS if pattern.search(text)),
            "staff": sum(1 for pattern in _STAFF_ACTOR_PATTERNS if pattern.search(text)),
            "admin": sum(1 for pattern in _ADMIN_ACTOR_PATTERNS if pattern.search(text)),
        }

    @staticmethod
    def _log_candidate(
        db: Session,
        run_id,
        candidate: ObligationCandidate,
        candidate_hash: str,
        normalized_text: str,
        decision: EventCandidateDecision,
        reason_code: str,
        metrics: dict[str, int | float | bool | str],
        target_role: str,
    ) -> None:
        db.add(
            EventCandidateLog(
                run_id=run_id,
                source_key=candidate.source_key,
                source_url=candidate.source_url,
                category=candidate.category,
                parent_category=candidate.parent_category,
                target_role=target_role,
                candidate_hash=candidate_hash,
                candidate_text=normalize_text(candidate.obligation_text),
                normalized_text=normalized_text.lower(),
                decision=decision,
                reason_code=reason_code[:64],
                metrics=metrics,
            )
        )
