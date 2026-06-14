"""Single source of truth for obligation/actor/noise regexes.

Both the extractor (`events/reasoning_agent.py`) and the quality gate
(`events/event_creator.py`) need to recognise the same things: strict
obligation markers ("must", "shall", "zorunludur"...), actors (students,
staff, admin), and various noise/governance patterns. These used to be
copy-pasted into both files with subtly different regexes — including a buggy
`\bzorunlu(?:dur|)\b` empty-alternation that matched the bare stem "zorunlu"
spuriously. Drift between the two copies meant the extractor and the gate could
disagree about what counts as an obligation. They now both import from here.
"""
from __future__ import annotations

import re

# --- Strict obligation markers (English + Turkish) -------------------------
# Note: every alternation is non-empty; "zorunludur"/"zorunludurlar" are
# matched explicitly rather than via an empty-alternative stem match.
ACTION_PATTERNS = (
    re.compile(r"\bmust\b", re.IGNORECASE),
    re.compile(r"\bshall\b", re.IGNORECASE),
    re.compile(r"\brequired(?:\s+to)?\b", re.IGNORECASE),
    re.compile(r"\boblig(?:ed|ation)\b", re.IGNORECASE),
    re.compile(r"\bzorunlu(?:dur|durlar)\b", re.IGNORECASE),
    re.compile(r"\bzorundad(?:ır|ir|ırlar|irler)\b", re.IGNORECASE),
    re.compile(r"\byükümlüdür(?:ler)?\b", re.IGNORECASE),
    re.compile(r"\bmecbur(?:dur|idir)\b", re.IGNORECASE),
    re.compile(r"\ben\s+geç\b", re.IGNORECASE),
    re.compile(r"\btarihine\s+kadar\b", re.IGNORECASE),
)

# --- Actors, split by role so callers can both detect and disambiguate -----
STUDENT_ACTOR_PATTERNS = (
    re.compile(r"\bstudents?\b", re.IGNORECASE),
    re.compile(r"\böğrenc(?:i|iler)\b", re.IGNORECASE),
    re.compile(r"\bthe student\b", re.IGNORECASE),
)

STAFF_ACTOR_PATTERNS = (
    re.compile(r"\bstaff\b", re.IGNORECASE),
    re.compile(r"\bpersonel\b", re.IGNORECASE),
    re.compile(r"\bemployees?\b", re.IGNORECASE),
    re.compile(r"\binstructor\b", re.IGNORECASE),
    re.compile(r"\bakademik\b", re.IGNORECASE),
    re.compile(r"\bidari\b", re.IGNORECASE),
    re.compile(r"\bbuluş(?:çu|\s+sahibi)\b", re.IGNORECASE),
    re.compile(r"\baraştırmac(?:ı|ilar|ılar)\b", re.IGNORECASE),
)

ADMIN_ACTOR_PATTERNS = (
    re.compile(r"\badmin\b", re.IGNORECASE),
    re.compile(r"\byönetim\b", re.IGNORECASE),
    re.compile(r"\brektörlük\b", re.IGNORECASE),
    re.compile(r"\bcommittee\b", re.IGNORECASE),
    re.compile(r"\bboard\b", re.IGNORECASE),
    re.compile(r"\bdean(?:'s)?\b", re.IGNORECASE),
    re.compile(r"\brectorate\b", re.IGNORECASE),
    re.compile(r"\bfaculty executive board\b", re.IGNORECASE),
    re.compile(r"\byönetim kurulu\b", re.IGNORECASE),
)

ACTOR_PATTERNS = (
    *STUDENT_ACTOR_PATTERNS,
    *STAFF_ACTOR_PATTERNS,
    *ADMIN_ACTOR_PATTERNS,
)

# --- Tokens used for the coarse role label on an extracted candidate -------
STUDENT_ROLE_TOKENS = ("öğrenci", "students", "student")
STAFF_ROLE_TOKENS = ("personel", "staff", "instructor", "employee", "akademik", "idari", "buluşçu", "araştırmacı")
ADMIN_ROLE_TOKENS = ("admin", "yönetim", "dean", "rektörlük", "rectorate")


def detect_role(text: str) -> str:
    """Coarse role label for a candidate sentence."""
    lowered = text.lower()
    if any(token in lowered for token in STUDENT_ROLE_TOKENS):
        return "student"
    if any(token in lowered for token in STAFF_ROLE_TOKENS):
        return "staff"
    if any(token in lowered for token in ADMIN_ROLE_TOKENS):
        return "admin"
    return "all"


def has_action(text: str) -> bool:
    return any(pattern.search(text) for pattern in ACTION_PATTERNS)


def action_count(text: str) -> int:
    return sum(1 for pattern in ACTION_PATTERNS if pattern.search(text))


def has_actor(text: str) -> bool:
    return any(pattern.search(text) for pattern in ACTOR_PATTERNS)


def role_hits(text: str) -> dict[str, int]:
    return {
        "student": sum(1 for p in STUDENT_ACTOR_PATTERNS if p.search(text)),
        "staff": sum(1 for p in STAFF_ACTOR_PATTERNS if p.search(text)),
        "admin": sum(1 for p in ADMIN_ACTOR_PATTERNS if p.search(text)),
    }
