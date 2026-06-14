"""User rule matching agent — works for any user in the system.

Given a user (student, instructor, admin), builds their full context from the DB
and UserProfile, then finds which regulation rules apply to them.

Two matching paths:
  - SQL rules:       deterministic — evaluated directly against student attributes
                     (gpa, enrolled_credits, is_active). Non-students skip these.
  - Contextual rules: the LLM receives the full user context + all contextual rules
                      and decides which apply and why.

Assignments are persisted to user_rule_assignments, deduplicated by (user_id, rule_id).
Re-running updates the reason and urgency without creating duplicates.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any
from urllib import request as urlrequest

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import (
    AssignmentStatus,
    AssignmentUrgency,
    RegulationRule,
    RuleMatchType,
    RuleStatus,
    User,
    UserProfile,
    UserRuleAssignment,
)
from llm.service import LLMService, get_llm_service
from events.utils import normalize_text, safe_eval_condition

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM caller
# ---------------------------------------------------------------------------

def _call_llm(*, url: str, model: str, system: str, prompt: str, timeout: float) -> tuple[Any, str | None]:
    endpoint = url.rstrip("/") + "/chat/stream"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "systemMessage": system,
    }
    body = json.dumps(payload).encode()
    req = urlrequest.Request(endpoint, data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            raw_stream = r.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return None, f"connection_error: {exc}"

    parts: list[str] = []
    for line in raw_stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        msg = ev.get("message", {}) if isinstance(ev, dict) else {}
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            c = str(msg.get("content", ""))
            if c:
                parts.append(c)

    raw = "".join(parts).strip()
    try:
        return json.loads(raw), None
    except Exception:
        pass
    for ch in ("[", "{"):
        idx = raw.find(ch)
        if idx >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(raw[idx:])
                return obj, None
            except Exception:
                pass
    return None, f"malformed_json: {raw[:300]}"


SYSTEM = (
    "You are a university policy advisor. "
    "You decide which university regulations apply to a specific person based on their profile and role. "
    "Be precise — only say a rule applies if there is a clear reason given the person's situation. "
    "Return only valid JSON. No markdown. "
    "Do not reveal internal reasoning; write only short UI display text."
)

CONTEXTUAL_MATCH_PROMPT = """You are checking which university regulations apply to a specific person.

PERSON PROFILE:
{user_context}

CANDIDATE RULES (contextual — need your judgment):
{rules}

---

For each rule, decide if it applies to THIS specific person right now.
Consider their role, department, program, status flags, GPA, enrollment, and any other context provided.

Return a JSON array — include ONLY rules that apply:
[
  {{
    "rule_index": 0,
    "applies": true,
    "ui_reason": "Student fact + rule hook, max 90 chars. Example: GPA 2.60 meets threshold."
  }}
]

If no rules apply, return [].
Return ONLY the JSON array."""

CONTEXTUAL_TRACE_PROMPT = """{system}

You are checking which university regulations apply to a specific person.

PERSON PROFILE:
{user_context}

CANDIDATE RULES:
{rules}

For EVERY rule, decide if it applies to THIS person right now.
Use only the profile facts and the rule fields. Do not invent missing facts.
Return strict JSON only:
{{
  "decisions": [
    {{
      "rule_index": 0,
      "applies": true,
      "ui_reason": "Student fact + rule hook, max 90 chars. Example: GPA 2.60 meets threshold."
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# Context builder — works for any user role
# ---------------------------------------------------------------------------

def build_user_context(db: Session, user: User) -> str:
    role = user.user_type.value
    name = f"{user.first_name} {user.last_name}"
    profile: UserProfile | None = user.profile

    lines = [
        f"Name: {name}",
        f"Role: {role}",
        f"Active: {'yes' if user.is_active else 'no'}",
    ]

    if profile:
        if profile.department:
            lines.append(f"Department: {profile.department}")
        if profile.faculty:
            lines.append(f"Faculty: {profile.faculty}")
        if profile.program_level:
            lines.append(f"Program level: {profile.program_level}")
        if profile.academic_year:
            lines.append(f"Academic year: {profile.academic_year}")
        if profile.semester_number:
            lines.append(f"Semesters completed: {profile.semester_number}")
        if profile.total_credits_completed is not None:
            lines.append(f"Credits completed: {profile.total_credits_completed}")
        if profile.total_credits_enrolled is not None:
            lines.append(f"Credits enrolled this term: {profile.total_credits_enrolled}")
        if profile.title:
            lines.append(f"Title: {profile.title}")
        if profile.office:
            lines.append(f"Office: {profile.office}")
        if profile.responsibilities:
            lines.append(f"Responsibilities: {profile.responsibilities}")

        flags = []
        if profile.is_on_probation:
            flags.append("on academic probation")
        if profile.has_advisor_hold:
            flags.append("has advisor hold")
        if profile.has_financial_hold:
            flags.append("has financial hold")
        if profile.is_exchange_student:
            flags.append("exchange student")
        if profile.is_double_major:
            flags.append("double major")
        if profile.is_minor:
            flags.append("enrolled in minor")
        if flags:
            lines.append(f"Status flags: {', '.join(flags)}")

        if profile.extra_context:
            for k, v in profile.extra_context.items():
                lines.append(f"{k}: {v}")

    # For students — pull live enrollment and GPA from DB
    if role == "student" and user.student:
        student = user.student
        lines.append(f"Student ID: {student.student_id}")
        gpa = float(student.gpa) if student.gpa is not None else None
        if gpa is not None:
            lines.append(f"GPA: {gpa}")

        progress = db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE e.status = 'COMPLETED') AS completed_courses,
                COUNT(DISTINCT cs.term_id) FILTER (WHERE e.status = 'COMPLETED') AS completed_terms,
                COUNT(*) FILTER (WHERE e.status = 'ENROLLED') AS enrolled_courses
            FROM enrollments e
            LEFT JOIN course_sections cs ON cs.id = e.section_id
            WHERE e.student_id = :sid
        """), {"sid": student.id}).mappings().first()
        if progress:
            completed_courses = int(progress["completed_courses"] or 0)
            completed_terms = int(progress["completed_terms"] or 0)
            enrolled_courses = int(progress["enrolled_courses"] or 0)
            if completed_courses:
                lines.append(f"Completed courses: {completed_courses}")
                if not (profile and profile.total_credits_completed is not None):
                    lines.append(f"Estimated credits completed: {completed_courses * 3}")
            if completed_terms:
                lines.append(f"Completed academic terms: {completed_terms}")
                if not (profile and profile.semester_number):
                    lines.append(f"Estimated semesters completed: {completed_terms}")
            if enrolled_courses and not (profile and profile.total_credits_enrolled is not None):
                lines.append(f"Estimated credits enrolled this term: {enrolled_courses * 3}")

        enrollments = db.execute(text("""
            SELECT c.code, c.name, e.status
            FROM enrollments e
            JOIN course_sections cs ON cs.id = e.section_id
            JOIN courses c ON c.id = cs.course_id
            WHERE e.student_id = :sid AND e.status = 'ENROLLED'
            ORDER BY c.code
        """), {"sid": student.id}).all()

        course_list = [f"{r[0]} ({r[1]})" for r in enrollments]
        lines.append(f"Enrolled courses ({len(course_list)}): {', '.join(course_list) or 'none'}")

    # For instructors — pull sections they teach
    elif role == "instructor" and user.instructor:
        sections = db.execute(text("""
            SELECT c.code, c.name, cs.status
            FROM course_sections cs
            JOIN courses c ON c.id = cs.course_id
            WHERE cs.instructor_id = :iid AND cs.status IN ('SCHEDULED', 'ACTIVE')
            ORDER BY c.code
        """), {"iid": user.instructor.id}).all()

        section_list = [f"{r[0]} ({r[1]})" for r in sections]
        lines.append(f"Teaching ({len(section_list)} sections): {', '.join(section_list) or 'none'}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SQL rule matching — student-only, deterministic
# ---------------------------------------------------------------------------

def _match_sql_rules(db: Session, user: User) -> list[dict]:
    if user.user_type.value != "student" or not user.student:
        return []

    student = user.student
    rules = (
        db.query(RegulationRule)
        .filter(RegulationRule.match_type == RuleMatchType.SQL, RegulationRule.status == RuleStatus.ACTIVE)
        .all()
    )

    gpa = float(student.gpa) if student.gpa is not None else None
    enrolled_credits = db.execute(text("""
        SELECT COUNT(*) FROM enrollments WHERE student_id = :sid AND status = 'ENROLLED'
    """), {"sid": student.id}).scalar() or 0

    context = {
        "gpa": gpa,
        "enrolled_credits": int(enrolled_credits),
        "is_active": student.is_active,
    }

    matched: list[dict] = []
    for rule in rules:
        if not rule.sql_condition:
            continue
        if safe_eval_condition(rule.sql_condition, context):
            matched.append(_rule_to_dict(rule, "sql",
                _format_sql_reason(rule.sql_condition, context, True)))

    return matched


# ---------------------------------------------------------------------------
# Contextual rule matching — LLM-driven, any role
# ---------------------------------------------------------------------------

_CONTEXTUAL_BATCH_SIZE = 25
_CONTEXTUAL_MAX_WORKERS = 4
_UI_REASON_MAX_CHARS = 96
_CONDITION_SUMMARY_RE = re.compile(
    r"^\s*(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)\s*"
    r"(?P<op><=|>=|==|!=|<|>)\s*"
    r"(?P<value>-?\d+(?:\.\d+)?|true|false|none)\s*$",
    re.IGNORECASE,
)
_FIELD_LABELS = {
    "gpa": "GPA",
    "enrolled_credits": "enrolled credits",
    "is_active": "active status",
}


def _compact_reason(value: str, max_chars: int = _UI_REASON_MAX_CHARS) -> str:
    text = normalize_text(value or "")
    if not text:
        return "Matched profile."
    text = re.sub(r"^[\-*•]\s*", "", text)
    text = re.sub(r"\b(because|since|therefore|thus|so)\b[:,]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(this rule|the rule|regulation)\s+", "", text, flags=re.IGNORECASE)
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
    if sentence:
        text = sentence
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip(" ,.;:") + "..."


def _ui_reason_from_decision(item: dict[str, Any], fallback: str = "") -> str:
    """Prefer the model's display contract, then sanitize legacy reason output."""
    raw = item.get("ui_reason")
    if not raw:
        raw = item.get("reason")
    return _compact_reason(str(raw or fallback))


def _format_sql_reason(condition: str, context: dict, applies: bool | None) -> str:
    match = _CONDITION_SUMMARY_RE.match(condition or "")
    if not match:
        return "Profile matches." if applies else "Profile does not match."

    field = match.group("field")
    op = match.group("op")
    threshold = match.group("value")
    raw_value = context.get(field)
    label = _FIELD_LABELS.get(field, field.replace("_", " "))
    value = f"{raw_value:.2f}" if isinstance(raw_value, float) else str(raw_value)

    if applies:
        if op in {">", ">="}:
            return f"{label} {value} meets {threshold}."
        if op in {"<", "<="}:
            return f"{label} {value} is below {threshold}."
        return f"{label} matches."

    if op in {">", ">="}:
        return f"{label} {value} is below {threshold}."
    if op in {"<", "<="}:
        return f"{label} {value} is not below {threshold}."
    return f"{label} differs."


def _match_contextual_rules(
    db: Session,
    user: User,
    user_context: str,
    outlier_url: str,
    outlier_model: str,
    llm_timeout: float,
) -> list[dict]:
    rules = (
        db.query(RegulationRule)
        .filter(RegulationRule.match_type == RuleMatchType.CONTEXTUAL, RegulationRule.status == RuleStatus.ACTIVE)
        .all()
    )
    if not rules:
        return []

    matched: list[dict] = []

    # Send in batches to avoid 503 on large payloads
    for batch_start in range(0, len(rules), _CONTEXTUAL_BATCH_SIZE):
        batch = rules[batch_start: batch_start + _CONTEXTUAL_BATCH_SIZE]
        rules_payload = [
            {
                "rule_index": i,
                "index": i,
                "rule_text": r.rule_text,
                "applies_to": r.applies_to,
                "trigger": r.trigger,
                "deadline": r.deadline,
                "blocking": bool(r.blocking),
                "consequence": r.consequence,
                "exceptions": r.exceptions,
                "target_role": r.target_role.value,
            }
            for i, r in enumerate(batch)
        ]

        prompt = CONTEXTUAL_MATCH_PROMPT.format(
            user_context=user_context,
            rules=json.dumps(rules_payload, ensure_ascii=False, indent=2),
        )

        result, err = _call_llm(url=outlier_url, model=outlier_model,
                                system=SYSTEM, prompt=prompt, timeout=llm_timeout)

        if err or not isinstance(result, list):
            logger.warning("Contextual match LLM failed for user %s (batch %d): %s",
                           user.id, batch_start, err)
            continue

        for item in result:
            idx = _decision_index(item)
            if not isinstance(idx, int) or idx < 0 or idx >= len(batch):
                continue
            if not item.get("applies"):
                continue
            rule = batch[idx]
            matched.append(_rule_to_dict(rule, "contextual",
                _ui_reason_from_decision(item)))

    return matched


def _parse_llm_decisions(raw: str) -> list[dict[str, Any]]:
    cleaned = (raw or "").strip()
    for opener in ("{", "["):
        index = cleaned.find(opener)
        if index < 0:
            continue
        try:
            payload, _ = json.JSONDecoder().raw_decode(cleaned[index:])
        except Exception:
            continue
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("decisions"), list):
            return payload["decisions"]
    return []


def _decision_index(item: dict[str, Any]) -> int | None:
    """Accept both the requested key and the key shown in rule payloads."""
    for key in ("rule_index", "index"):
        value = item.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _rule_payload(rule: RegulationRule, index: int) -> dict[str, Any]:
    return {
        "rule_index": index,
        "index": index,
        "rule_id": str(rule.id),
        "rule_text": rule.rule_text,
        "applies_to": rule.applies_to,
        "trigger": rule.trigger,
        "deadline": rule.deadline,
        "blocking": bool(rule.blocking),
        "consequence": rule.consequence,
        "exceptions": rule.exceptions,
        "target_role": rule.target_role.value,
        "match_type": rule.match_type.value,
    }


def _decision_payload(
    rule: RegulationRule,
    match_type: str,
    applies: bool,
    reason: str,
    *,
    persistable: bool = True,
) -> dict[str, Any]:
    return {
        "rule_id": str(rule.id),
        "rule_text": rule.rule_text,
        "applies_to": rule.applies_to,
        "trigger": rule.trigger,
        "deadline": rule.deadline,
        "blocking": bool(rule.blocking),
        "consequence": rule.consequence,
        "authority": rule.authority,
        "source_url": rule.source_doc_url,
        "evidence_quote": rule.evidence_quote,
        "match_type": match_type,
        "applies": applies,
        "reason": _compact_reason(reason),
        "persistable": persistable,
        "_rule_obj": rule,
    }


def _sql_rule_decisions(db: Session, user: User) -> list[dict[str, Any]]:
    rules = (
        db.query(RegulationRule)
        .filter(RegulationRule.match_type == RuleMatchType.SQL, RegulationRule.status == RuleStatus.ACTIVE)
        .all()
    )
    if user.user_type.value != "student" or not user.student:
        return [
            _decision_payload(rule, "sql", False, "No student record.")
            for rule in rules
        ]

    student = user.student
    gpa = float(student.gpa) if student.gpa is not None else None
    enrolled_credits = db.execute(text("""
        SELECT COUNT(*) FROM enrollments WHERE student_id = :sid AND status = 'ENROLLED'
    """), {"sid": student.id}).scalar() or 0
    context = {"gpa": gpa, "enrolled_credits": int(enrolled_credits), "is_active": student.is_active}

    decisions: list[dict[str, Any]] = []
    for rule in rules:
        if not rule.sql_condition:
            decisions.append(_decision_payload(rule, "sql", False, "No condition."))
            continue
        result = safe_eval_condition(rule.sql_condition, context)
        if result is None:
            applies = False
            reason = "Condition unavailable."
        else:
            applies = result
            reason = _format_sql_reason(rule.sql_condition, context, applies)
        decisions.append(_decision_payload(rule, "sql", applies, reason))
    return decisions


def _contextual_batch_decisions(
    *,
    batch_start: int,
    batch: list[RegulationRule],
    user_context: str,
    llm: LLMService,
) -> list[dict[str, Any]]:
    prompt = CONTEXTUAL_TRACE_PROMPT.format(
        system=SYSTEM,
        user_context=user_context,
        rules=json.dumps([_rule_payload(rule, i) for i, rule in enumerate(batch)], ensure_ascii=False, indent=2),
    )
    try:
        raw = llm.complete(prompt)
    except Exception as exc:
        logger.warning("Contextual trace LLM failed for batch %d: %s", batch_start, exc)
        return [
            _decision_payload(
                rule,
                "contextual",
                False,
                "Check failed; unchanged.",
                persistable=False,
            )
            for rule in batch
        ]

    parsed = _parse_llm_decisions(raw)
    by_index: dict[int, dict[str, Any]] = {}
    by_rule_id: dict[str, dict[str, Any]] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        idx = _decision_index(item)
        if isinstance(idx, int):
            by_index[idx] = item
        rule_id = item.get("rule_id")
        if isinstance(rule_id, str) and rule_id:
            by_rule_id[rule_id] = item

    decisions: list[dict[str, Any]] = []
    for i, rule in enumerate(batch):
        item = by_index.get(i) or by_rule_id.get(str(rule.id))
        if item is None:
            decisions.append(
                _decision_payload(
                    rule,
                    "contextual",
                    False,
                    "No decision; unchanged.",
                    persistable=False,
                )
            )
            continue
        decisions.append(
            _decision_payload(
                rule,
                "contextual",
                bool(item.get("applies")),
                _ui_reason_from_decision(item, "Matched profile."),
            )
        )
    return decisions


def _contextual_rule_decisions(
    db: Session,
    user_context: str,
    llm_service: LLMService | None = None,
) -> list[dict[str, Any]]:
    rules = (
        db.query(RegulationRule)
        .filter(RegulationRule.match_type == RuleMatchType.CONTEXTUAL, RegulationRule.status == RuleStatus.ACTIVE)
        .all()
    )
    if not rules:
        return []

    llm = llm_service or get_llm_service()
    batches = [
        (batch_start, rules[batch_start: batch_start + _CONTEXTUAL_BATCH_SIZE])
        for batch_start in range(0, len(rules), _CONTEXTUAL_BATCH_SIZE)
    ]
    if len(batches) == 1:
        return _contextual_batch_decisions(
            batch_start=batches[0][0],
            batch=batches[0][1],
            user_context=user_context,
            llm=llm,
        )

    decisions: list[dict[str, Any]] = []
    workers = min(_CONTEXTUAL_MAX_WORKERS, len(batches))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _contextual_batch_decisions,
                batch_start=batch_start,
                batch=batch,
                user_context=user_context,
                llm=llm,
            )
            for batch_start, batch in batches
        ]
        for future in futures:
            decisions.extend(future.result())
    return decisions


def _persist_assignments_detailed(db: Session, user: User, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    effects: list[dict[str, Any]] = []
    for decision in decisions:
        rule: RegulationRule = decision["_rule_obj"]
        urgency = _compute_urgency(rule)
        match_type = RuleMatchType.SQL if decision["match_type"] == "sql" else RuleMatchType.CONTEXTUAL
        reason = normalize_text(decision.get("reason", ""))

        existing = (
            db.query(UserRuleAssignment)
            .filter(UserRuleAssignment.user_id == user.id, UserRuleAssignment.rule_id == rule.id)
            .first()
        )
        before_status = existing.status.value if existing else None
        before_reason = existing.reason if existing else None
        before_urgency = existing.urgency.value if existing else None

        if not decision.get("applies"):
            if not decision.get("persistable", True):
                continue
            if existing and existing.status == AssignmentStatus.ACTIVE:
                existing.status = AssignmentStatus.DISMISSED
                existing.reason = f"No longer matches: {reason}"
                db.flush()
                effects.append(
                    {
                        "assignment_id": str(existing.id),
                        "rule_id": str(rule.id),
                        "rule_text": rule.rule_text,
                        "urgency": existing.urgency.value,
                        "status": existing.status.value,
                        "before_status": before_status,
                        "action": "retired",
                        "reason": existing.reason,
                    }
                )
            continue

        if existing:
            action = "unchanged"
            existing.reason = reason
            existing.urgency = urgency
            existing.match_type = match_type
            if existing.status == AssignmentStatus.DISMISSED:
                existing.status = AssignmentStatus.ACTIVE
                action = "reactivated"
            elif before_reason != reason or before_urgency != urgency.value:
                action = "updated"
            db.flush()
            assignment = existing
        else:
            assignment = UserRuleAssignment(
                user_id=user.id,
                rule_id=rule.id,
                match_type=match_type,
                urgency=urgency,
                status=AssignmentStatus.ACTIVE,
                reason=reason,
            )
            db.add(assignment)
            db.flush()
            action = "created"

        effects.append(
            {
                "assignment_id": str(assignment.id),
                "rule_id": str(rule.id),
                "rule_text": rule.rule_text,
                "urgency": assignment.urgency.value,
                "status": assignment.status.value,
                "before_status": before_status,
                "action": action,
                "reason": assignment.reason,
            }
        )

    db.commit()
    return effects


def run_for_user_trace(db: Session, user: User):
    """Yield a transparent audit trail for a user-requested regulation check."""
    yield {"type": "step", "message": "Loading profile", "detail": f"{user.first_name} {user.last_name}"}
    user_context = build_user_context(db, user)
    yield {"type": "profile", "context": user_context}

    yield {"type": "step", "message": "Checking SQL", "detail": "profile rules"}
    sql_decisions = _sql_rule_decisions(db, user)
    yield {
        "type": "rule_decisions",
        "phase": "sql",
        "decisions": [{k: v for k, v in decision.items() if k != "_rule_obj"} for decision in sql_decisions],
    }

    yield {"type": "step", "message": "Checking LLM", "detail": "parallel batches"}
    contextual_decisions = _contextual_rule_decisions(db, user_context)
    yield {
        "type": "rule_decisions",
        "phase": "contextual",
        "decisions": [{k: v for k, v in decision.items() if k != "_rule_obj"} for decision in contextual_decisions],
    }

    all_decisions = sql_decisions + contextual_decisions
    applicable = [decision for decision in all_decisions if decision.get("applies")]
    yield {"type": "step", "message": "Saving matches", "detail": f"{len(applicable)} yes"}
    effects = _persist_assignments_detailed(db, user, all_decisions)
    yield {"type": "assignments", "assignments": effects}

    counts = {
        "rules_checked": len(all_decisions),
        "applicable": len(applicable),
        "created": sum(1 for item in effects if item["action"] == "created"),
        "updated": sum(1 for item in effects if item["action"] == "updated"),
        "reactivated": sum(1 for item in effects if item["action"] == "reactivated"),
        "retired": sum(1 for item in effects if item["action"] == "retired"),
        "unchanged": sum(1 for item in effects if item["action"] == "unchanged"),
    }
    yield {"type": "summary", **counts}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule_to_dict(rule: RegulationRule, match_type: str, reason: str) -> dict:
    return {
        "rule_id": str(rule.id),
        "rule_text": rule.rule_text,
        "applies_to": rule.applies_to,
        "trigger": rule.trigger,
        "deadline": rule.deadline,
        "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
        "valid_until": rule.valid_until.isoformat() if rule.valid_until else None,
        "blocking": bool(rule.blocking),
        "consequence": rule.consequence,
        "authority": rule.authority,
        "exceptions": rule.exceptions,
        "match_type": match_type,
        "reason": reason,
        "source_url": rule.source_doc_url,
        "evidence_quote": rule.evidence_quote,
        "_rule_obj": rule,
    }


def _compute_urgency(rule: RegulationRule) -> AssignmentUrgency:
    if rule.blocking:
        return AssignmentUrgency.HIGH
    if rule.deadline or rule.consequence or rule.valid_until:
        return AssignmentUrgency.MEDIUM
    return AssignmentUrgency.LOW


# ---------------------------------------------------------------------------
# Persist assignments — upsert on (user_id, rule_id)
# ---------------------------------------------------------------------------

def _persist_assignments(db: Session, user: User, matched: list[dict]) -> int:
    saved = 0
    for m in matched:
        rule: RegulationRule = m["_rule_obj"]
        urgency = _compute_urgency(rule)
        match_type = RuleMatchType.SQL if m["match_type"] == "sql" else RuleMatchType.CONTEXTUAL

        existing = (
            db.query(UserRuleAssignment)
            .filter(UserRuleAssignment.user_id == user.id,
                    UserRuleAssignment.rule_id == rule.id)
            .first()
        )
        if existing:
            existing.reason = m["reason"]
            existing.urgency = urgency
            existing.match_type = match_type
            if existing.status == AssignmentStatus.DISMISSED:
                existing.status = AssignmentStatus.ACTIVE
        else:
            db.add(UserRuleAssignment(
                user_id=user.id,
                rule_id=rule.id,
                match_type=match_type,
                urgency=urgency,
                status=AssignmentStatus.ACTIVE,
                reason=m["reason"],
            ))
            saved += 1

    db.commit()
    return saved


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_for_user(
    db: Session,
    user: User,
    outlier_url: str = "http://127.0.0.1:8080",
    outlier_model: str = "claude-opus-4-6",
    llm_timeout: float = 60.0,
    persist: bool = True,
) -> dict:
    """Match and optionally persist applicable rules for any user.

    Returns:
        {
            "user_id": int,
            "user_context": str,
            "sql_rules": [...],
            "contextual_rules": [...],
            "total_matched": int,
            "new_assignments": int,   # 0 if persist=False
        }
    """
    user_context = build_user_context(db, user)

    sql_matched = _match_sql_rules(db, user)
    contextual_matched = _match_contextual_rules(
        db, user, user_context,
        outlier_url=outlier_url,
        outlier_model=outlier_model,
        llm_timeout=llm_timeout,
    )

    all_matched = sql_matched + contextual_matched
    new_assignments = 0
    if persist:
        new_assignments = _persist_assignments(db, user, all_matched)

    return {
        "user_id": user.id,
        "user_context": user_context,
        "sql_rules": [{k: v for k, v in r.items() if k != "_rule_obj"} for r in sql_matched],
        "contextual_rules": [{k: v for k, v in r.items() if k != "_rule_obj"} for r in contextual_matched],
        "total_matched": len(all_matched),
        "new_assignments": new_assignments,
    }


def run_for_all_users(
    db: Session,
    outlier_url: str = "http://127.0.0.1:8080",
    outlier_model: str = "claude-opus-4-6",
    llm_timeout: float = 60.0,
) -> dict:
    """Run the agent for every active user in the system."""
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    total_matched = 0
    total_new = 0
    errors = 0

    for user in users:
        try:
            result = run_for_user(db, user,
                                  outlier_url=outlier_url,
                                  outlier_model=outlier_model,
                                  llm_timeout=llm_timeout,
                                  persist=True)
            total_matched += result["total_matched"]
            total_new += result["new_assignments"]
        except Exception as exc:
            logger.warning("User agent failed for user %s: %s", user.id, exc)
            errors += 1

    return {
        "users_processed": len(users),
        "total_matched": total_matched,
        "new_assignments": total_new,
        "errors": errors,
    }
