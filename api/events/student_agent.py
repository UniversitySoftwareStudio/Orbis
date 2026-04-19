"""Student rule matching agent.

Given a student, builds their context blob from the DB and finds which
regulation rules apply to them.

Two paths:
  - SQL rules:        fired directly by querying regulation_rules with simple conditions
                      matched against the student's attributes (gpa, enrolled credits, etc.)
  - Contextual rules: the LLM receives the student context blob + all contextual rules
                      and decides which ones apply and why.

Returns a list of applicable rules with a plain-language reason for each.
"""
from __future__ import annotations

import json
from typing import Any
from urllib import request as urlrequest

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import RegulationRule, RuleMatchType, RuleStatus, Student
from events.utils import normalize_text

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# LLM caller (same pattern)
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
    "You are a university advisor assistant. "
    "You decide which university regulations apply to a specific student based on their profile. "
    "Be precise — only say a rule applies if there is a clear reason given the student's situation. "
    "Return only valid JSON."
)

CONTEXTUAL_MATCH_PROMPT = """You are checking which university regulations apply to a specific student.

STUDENT PROFILE:
{student_context}

CANDIDATE ACTIONS (contextual — need your judgment):
{rules}

---

For each action, decide if it applies to THIS specific student right now.
Consider: their program, GPA, enrollment status, current courses, and any other relevant context.

Return a JSON array — include ONLY rules that apply:
[
  {{
    "rule_index": 0,
    "applies": true,
    "reason": "short plain-language reason why this applies to this student"
  }},
  ...
]

If no rules apply, return an empty array [].
Return ONLY the JSON array."""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def build_student_context(db: Session, student: Student) -> str:
    """Build a plain-text context blob for a student from their DB records."""
    user = student.user
    name = f"{user.first_name} {user.last_name}"

    # enrolled courses this term
    enrollments = db.execute(text("""
        SELECT c.code, c.name, e.status, e.final_grade_letter
        FROM enrollments e
        JOIN course_sections cs ON cs.id = e.section_id
        JOIN courses c ON c.id = cs.course_id
        WHERE e.student_id = :sid AND e.status = 'enrolled'
        ORDER BY c.code
    """), {"sid": student.id}).all()

    enrolled_courses = [f"{r[0]} ({r[1]})" for r in enrollments]
    enrolled_credits = len(enrollments)  # rough proxy

    lines = [
        f"Name: {name}",
        f"Student ID: {student.student_id}",
        f"GPA: {float(student.gpa) if student.gpa is not None else 'unknown'}",
        f"Active: {'yes' if student.is_active else 'no'}",
        f"Enrolled courses this term ({enrolled_credits} courses): {', '.join(enrolled_courses) or 'none'}",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SQL rule matching
# ---------------------------------------------------------------------------

def match_sql_rules(db: Session, student: Student) -> list[dict]:
    """Fire deterministic SQL rules against student attributes.

    Each rule has a sql_condition like "gpa < 1.80" or "enrolled_credits < 12".
    We evaluate these in Python against the student's attributes.
    """
    rules = (
        db.query(RegulationRule)
        .filter(
            RegulationRule.match_type == RuleMatchType.SQL,
            RegulationRule.status == RuleStatus.ACTIVE,
        )
        .all()
    )

    gpa = float(student.gpa) if student.gpa is not None else None
    enrolled_credits = db.execute(text("""
        SELECT COUNT(*) FROM enrollments
        WHERE student_id = :sid AND status = 'enrolled'
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
                matched.append({
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
                    "match_type": "sql",
                    "reason": f"Your profile matches: {rule.sql_condition}",
                    "source_url": rule.source_doc_url,
                })
        except Exception:
            continue  # bad condition expression — skip silently

    return matched


# ---------------------------------------------------------------------------
# Contextual rule matching
# ---------------------------------------------------------------------------

def match_contextual_rules(
    db: Session,
    student: Student,
    student_context: str,
    outlier_url: str = "http://127.0.0.1:8080",
    outlier_model: str = "claude-opus-4-6",
    llm_timeout: float = 60.0,
) -> list[dict]:
    rules = (
        db.query(RegulationRule)
        .filter(
            RegulationRule.match_type == RuleMatchType.CONTEXTUAL,
            RegulationRule.status == RuleStatus.ACTIVE,
        )
        .all()
    )

    if not rules:
        return []

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
        }
        for i, r in enumerate(rules)
    ]

    prompt = CONTEXTUAL_MATCH_PROMPT.format(
        student_context=student_context,
        rules=json.dumps(rules_payload, ensure_ascii=False, indent=2),
    )

    result, err = _call_llm(
        url=outlier_url, model=outlier_model,
        system=SYSTEM, prompt=prompt, timeout=llm_timeout,
    )

    if err or not isinstance(result, list):
        logger.warning("Contextual match LLM failed: %s", err)
        return []

    matched: list[dict] = []
    for item in result:
        idx = item.get("rule_index")
        if not isinstance(idx, int) or idx >= len(rules):
            continue
        if not item.get("applies"):
            continue
        rule = rules[idx]
        matched.append({
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
            "match_type": "contextual",
            "reason": normalize_text(item.get("reason", "")),
            "source_url": rule.source_doc_url,
        })

    return matched


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_rules_for_student(
    db: Session,
    student: Student,
    outlier_url: str = "http://127.0.0.1:8080",
    outlier_model: str = "claude-opus-4-6",
    llm_timeout: float = 60.0,
) -> dict:
    """Return all rules that apply to this student.

    Returns:
        {
            "student_id": "...",
            "context": "...",         # the text blob used for matching
            "sql_rules": [...],       # fired deterministically
            "contextual_rules": [...],# fired by LLM reasoning
            "total": N
        }
    """
    student_context = build_student_context(db, student)

    sql_matched = match_sql_rules(db, student)
    contextual_matched = match_contextual_rules(
        db, student, student_context,
        outlier_url=outlier_url,
        outlier_model=outlier_model,
        llm_timeout=llm_timeout,
    )

    return {
        "student_id": student.student_id,
        "context": student_context,
        "sql_rules": sql_matched,
        "contextual_rules": contextual_matched,
        "total": len(sql_matched) + len(contextual_matched),
    }
