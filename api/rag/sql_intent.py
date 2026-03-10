from typing import Any

from rich import box
from rich.table import Table

from core.logging import get_logger
from rag.console import RAG_DEBUG, console
from sqlalchemy.orm import Session

logger = get_logger(__name__)


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

    results = repository.sql_filter(session, repaired, limit=75)

    if RAG_DEBUG:
        status_color = "green" if results else "yellow"
        status = f"[{status_color}]{len(results)} doc(s)[/{status_color}]"
        if not results:
            status += " [yellow]→ will fallback to vector[/yellow]"
        console.print(f"  [bold]SQL intent[/bold]  filters=[cyan]{repaired}[/cyan]  →  {status}")

    return results