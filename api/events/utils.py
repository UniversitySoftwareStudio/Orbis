from __future__ import annotations

import hashlib
import operator
import re
from urllib.parse import urlparse


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip())


def canonicalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")
    return f"{host}{path}"


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_source_key(url: str, content_hash: str) -> str:
    return hash_text(f"{canonicalize_url(url)}:{content_hash}")


def make_event_fingerprint(obligation_text: str, target_role: str) -> str:
    normalized = normalize_text(obligation_text).lower()
    role = (target_role or "").strip().lower()
    return hash_text(f"{normalized}|{role}")


# --- Safe evaluation of stored rule SQL-conditions -------------------------
#
# Rule rows carry a `sql_condition` string authored upstream (e.g. "gpa < 1.80",
# "enrolled_credits < 12", "is_active", "not is_active"). These were previously
# run through Python `eval()` against a student-attribute context, which is a
# code-execution surface on database-sourced text. `safe_eval_condition`
# replaces that with a tiny grammar: a single comparison `field OP literal`, or
# a bare/negated boolean `[not] field`. Anything outside the grammar returns
# None so callers can treat it as "could not evaluate" rather than risk
# executing arbitrary code.

_COMPARATORS = {
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    ">": operator.gt,
}

# Longer operators first so "<=" is matched before "<".
_CONDITION_RE = re.compile(
    r"^\s*(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)\s*"
    r"(?P<op><=|>=|==|!=|<|>)\s*"
    r"(?P<value>-?\d+(?:\.\d+)?|true|false|none)\s*$",
    re.IGNORECASE,
)
_BOOL_RE = re.compile(r"^\s*(?P<neg>not\s+)?(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)\s*$", re.IGNORECASE)


def _coerce_literal(raw: str):
    lowered = raw.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "none":
        return None
    if "." in raw:
        return float(raw)
    return int(raw)


def safe_eval_condition(condition: str, context: dict) -> bool | None:
    """Evaluate a stored rule condition without `eval`.

    Returns the boolean result, or None when the condition is empty, malformed,
    references an unknown field, or compares incomparable types (e.g. a missing
    GPA of None against a number). None means "skip this rule", never "applies".
    """
    text = (condition or "").strip()
    if not text:
        return None

    match = _CONDITION_RE.match(text)
    if match:
        field = match.group("field")
        if field not in context:
            return None
        left = context[field]
        right = _coerce_literal(match.group("value"))
        compare = _COMPARATORS[match.group("op")]
        if compare in (operator.eq, operator.ne):
            try:
                return bool(compare(left, right))
            except TypeError:
                return None
        # ordered comparisons require comparable, non-None operands
        if left is None or right is None or isinstance(left, bool):
            return None
        try:
            return bool(compare(left, right))
        except TypeError:
            return None

    bool_match = _BOOL_RE.match(text)
    if bool_match:
        field = bool_match.group("field")
        if field not in context:
            return None
        value = bool(context[field])
        return (not value) if bool_match.group("neg") else value

    return None
