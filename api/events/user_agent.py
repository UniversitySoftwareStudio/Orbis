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
from events.utils import normalize_text

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
    "Return only valid JSON. No explanation, no markdown."
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
    "reason": "one or two sentences explaining exactly why this rule applies to this person given their specific situation"
  }}
]

If no rules apply, return [].
Return ONLY the JSON array."""


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
        gpa = float(student.gpa) if student.gpa is not None else None
        if gpa is not None:
            lines.append(f"GPA: {gpa}")

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
        try:
            if eval(rule.sql_condition, {"__builtins__": {}}, context):  # noqa: S307
                matched.append(_rule_to_dict(rule, "sql",
                    f"Your profile matches the condition: {rule.sql_condition}"))
        except Exception:
            continue

    return matched


# ---------------------------------------------------------------------------
# Contextual rule matching — LLM-driven, any role
# ---------------------------------------------------------------------------

_CONTEXTUAL_BATCH_SIZE = 25


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
            idx = item.get("rule_index")
            if not isinstance(idx, int) or idx >= len(batch):
                continue
            if not item.get("applies"):
                continue
            rule = batch[idx]
            matched.append(_rule_to_dict(rule, "contextual",
                normalize_text(item.get("reason", ""))))

    return matched


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
