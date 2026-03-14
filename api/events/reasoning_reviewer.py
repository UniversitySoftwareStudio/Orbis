from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from core.logging import get_logger
from database.models import EventCandidateDecision
from llm.service import get_llm_service

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReviewedCandidate:
    decision: EventCandidateDecision
    reason_code: str
    normalized_text: str
    target_role: str


class ReasoningReviewer:
    """LLM-based candidate reviewer with strict JSON contract and safe fallback."""

    def __init__(self) -> None:
        enabled_flag = (os.getenv("EVENTS_ENABLE_REASONING_REVIEW", "1") or "1").strip().lower()
        self.enabled = enabled_flag in {"1", "true", "yes", "on"}
        default_batch_size = int((os.getenv("EVENTS_REASONING_BATCH_SIZE", "8") or "8").strip())
        self.batch_size = max(1, min(default_batch_size, 40))
        self._llm = None

        if not self.enabled:
            return
        try:
            self._llm = get_llm_service()
        except Exception as exc:  # pragma: no cover - fallback path
            logger.warning("Reasoning reviewer disabled, LLM init failed: %s", exc)
            self.enabled = False

    def review_batch(
        self,
        candidates: list[dict[str, str]],
    ) -> dict[int, ReviewedCandidate]:
        """
        Input items: {"idx": int, "text": str, "role": str, "url": str, "category": str}
        Returns map[idx] -> ReviewedCandidate.
        """
        if not self.enabled or not candidates:
            return {}

        outputs: dict[int, ReviewedCandidate] = {}
        pending_batches: list[list[dict[str, str]]] = [
            candidates[start : start + self.batch_size]
            for start in range(0, len(candidates), self.batch_size)
        ]

        while pending_batches:
            batch = pending_batches.pop(0)
            parsed_items = self._review_once(batch)

            reviewed_ids: set[int] = set()
            for item in parsed_items:
                idx = self._parse_idx(item.get("id"))
                if idx is None:
                    continue
                reviewed = self._parse_item(item)
                if reviewed is None:
                    continue
                outputs[idx] = reviewed
                reviewed_ids.add(idx)

            missing = [item for item in batch if int(item["idx"]) not in reviewed_ids]
            if not missing:
                continue

            if len(missing) == 1:
                fallback_item = missing[0]
                parsed_fallback = self._review_once([fallback_item])
                if parsed_fallback:
                    idx = self._parse_idx(parsed_fallback[0].get("id"))
                    reviewed = self._parse_item(parsed_fallback[0])
                    if idx is not None and reviewed is not None:
                        outputs[idx] = reviewed
                        continue
                logger.warning(
                    "Reasoning reviewer missing output for candidate idx=%s url=%s",
                    fallback_item.get("idx"),
                    fallback_item.get("url"),
                )
                continue

            split = max(1, len(missing) // 2)
            for start in range(0, len(missing), split):
                pending_batches.insert(0, missing[start : start + split])

        return outputs

    def _review_once(self, candidates: list[dict[str, str]]) -> list[dict[str, object]]:
        prompt = self._build_prompt(candidates)
        raw = "".join(self._llm.generate(prompt))
        return self._parse_json_array(raw)

    @staticmethod
    def _parse_idx(raw_id: object) -> int | None:
        if not isinstance(raw_id, str) or not raw_id.startswith("c"):
            return None
        try:
            return int(raw_id[1:])
        except ValueError:
            return None

    @staticmethod
    def _build_prompt(candidates: list[dict[str, str]]) -> str:
        payload = [
            {
                "id": f"c{item['idx']}",
                "text": item["text"],
                "target_role": item["role"],
                "source_url": item["url"],
                "category": item["category"],
            }
            for item in candidates
        ]

        instructions = (
            "You are a strict compliance quality gate for university regulations. "
            "Language can be Turkish or English.\n\n"
            "Goal: keep only explicit, person-assignable obligations.\n"
            "Reject aggressively.\n\n"
            "Decisions:\n"
            "- accept_pending: clear actor + strict obligation + concrete action + atomic sentence.\n"
            "- accept_review: probably obligation but still ambiguous/compound/long.\n"
            "- reject: definition, scope, policy narrative, article metadata, committee composition, contact info, OCR garbage, or non-assignable passive governance text.\n\n"
            "Non-assignable governance examples to reject:\n"
            "- 'shall be determined by the Academic Committee'\n"
            "- 'this regulation shall apply ...'\n"
            "- 'provisions of Article X shall apply ...'\n\n"
            "Normalization for accepted items:\n"
            "- one atomic sentence, <=180 chars,\n"
            "- remove article headers/numbers/footnotes,\n"
            "- preserve obligation meaning and key deadline/condition,\n"
            "- do not add facts not present in input.\n"
        )

        examples = (
            "Examples:\n"
            "Input: 'Students must submit the petition by Friday.' -> accept_pending\n"
            "Input: 'Students may submit additional documents.' -> accept_review\n"
            "Input: 'Aim Article 1: This directive defines principles...' -> reject\n"
            "Input: 'German Marshall Fund ... Supporters ...' -> reject\n"
            "Input: 'The Academic Committee shall determine ...' -> reject\n"
        )

        schema = (
            "Return ONLY JSON array. "
            "Each object keys: id, decision, reason_code, normalized_text, target_role.\n"
            "decision in {accept_pending, accept_review, reject}.\n"
            "reason_code in {strict, ambiguous_compound, non_assignable, missing_actor, missing_action, noisy_text, role_ambiguous, other}.\n"
            "target_role in {student, staff, admin, all}.\n"
            "For reject, normalized_text may be ''.\n"
            "For accept_*, normalized_text must be non-empty and <=180 chars.\n"
            "Include exactly one output object for every input id."
        )

        return (
            f"{instructions}\n"
            f"{examples}\n"
            f"{schema}\n"
            f"Candidates:\n{json.dumps(payload, ensure_ascii=False)}"
        )

    @staticmethod
    def _parse_json_array(raw: str) -> list[dict[str, object]]:
        text = (raw or "").strip()
        if not text:
            return []

        for candidate in (text,):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    return [x for x in parsed if isinstance(x, dict)]
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("items"), list):
                        return [x for x in parsed["items"] if isinstance(x, dict)]
                    if all(key in parsed for key in ("id", "decision")):
                        return [parsed]
            except Exception:
                pass

        left = text.find("[")
        right = text.rfind("]")
        if left == -1 or right == -1 or left >= right:
            return []
        try:
            parsed = json.loads(text[left : right + 1])
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
        except Exception:
            pass

        obj_left = text.find("{")
        obj_right = text.rfind("}")
        if obj_left != -1 and obj_right != -1 and obj_left < obj_right:
            try:
                parsed = json.loads(text[obj_left : obj_right + 1])
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("items"), list):
                        return [x for x in parsed["items"] if isinstance(x, dict)]
                    if all(key in parsed for key in ("id", "decision")):
                        return [parsed]
            except Exception:
                return []
        return []

    @staticmethod
    def _parse_item(item: dict[str, object]) -> ReviewedCandidate | None:
        decision_raw = str(item.get("decision") or "").strip().lower()
        reason_code = ReasoningReviewer._normalize_reason_code(str(item.get("reason_code") or "other"))
        normalized_text = str(item.get("normalized_text") or "").strip()
        target_role = str(item.get("target_role") or "all").strip().lower()

        if target_role not in {"student", "staff", "admin", "all"}:
            target_role = "all"

        if decision_raw == "accept_pending":
            decision = EventCandidateDecision.ACCEPT_PENDING
        elif decision_raw == "accept_review":
            decision = EventCandidateDecision.ACCEPT_REVIEW
        elif decision_raw == "reject":
            decision = EventCandidateDecision.REJECT_QUALITY
        else:
            return None

        if decision in {EventCandidateDecision.ACCEPT_PENDING, EventCandidateDecision.ACCEPT_REVIEW}:
            if not normalized_text:
                return None
            normalized_text = normalized_text[:180].strip()
            if not normalized_text:
                return None

            is_compound = bool(re.search(r"[;:]", normalized_text) or re.search(r"\b(and|or|ve|veya)\b", normalized_text, re.IGNORECASE))
            if decision == EventCandidateDecision.ACCEPT_PENDING and is_compound:
                decision = EventCandidateDecision.ACCEPT_REVIEW
                if reason_code == "strict":
                    reason_code = "ambiguous_compound"

        return ReviewedCandidate(
            decision=decision,
            reason_code=reason_code or "other",
            normalized_text=normalized_text,
            target_role=target_role,
        )

    @staticmethod
    def _normalize_reason_code(value: str) -> str:
        lowered = (value or "other").strip().lower()
        lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
        lowered = re.sub(r"_+", "_", lowered).strip("_")

        alias_map = {
            "strict_obligation": "strict",
            "strict_obligation_for_a_role": "strict",
            "single_obligation": "strict",
            "actionable_obligation": "strict",
            "likely_obligation": "ambiguous_compound",
            "ambiguous_compound_obligation": "ambiguous_compound",
            "not_actionable": "non_assignable",
            "not_assignable": "non_assignable",
            "non_actionable": "non_assignable",
            "missing_subject": "missing_actor",
            "missing_modal": "missing_action",
            "ocr_noise": "noisy_text",
            "role_conflict": "role_ambiguous",
        }
        normalized = alias_map.get(lowered, lowered)
        allowed = {
            "strict",
            "ambiguous_compound",
            "non_assignable",
            "missing_actor",
            "missing_action",
            "noisy_text",
            "role_ambiguous",
            "other",
        }
        return normalized if normalized in allowed else "other"
