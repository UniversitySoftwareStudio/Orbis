from typing import Any

from sqlalchemy.orm import Session


def normalize_filters(raw_filters: Any) -> dict[str, Any]:
    if not isinstance(raw_filters, dict):
        return {}

    normalized: dict[str, Any] = {}
    for key, value in raw_filters.items():
        if isinstance(value, dict):
            nested = next(iter(value.values()), "")
            normalized[key] = str(nested).replace("%", "")
        else:
            normalized[key] = value

    if "code" in normalized:
        normalized["type"] = "course"
    return normalized


def execute_sql_intent(repository: Any, session: Session, query: str, filters: dict[str, Any]) -> list[Any]:
    if not filters:
        return []

    repaired = dict(filters)
    if repaired.get("type") == "course" and "code" not in repaired and "title_like" not in repaired:
        if query and len(query) < 10:
            repaired["code"] = query
        else:
            return []

    return repository.sql_filter(session, repaired, limit=75)
