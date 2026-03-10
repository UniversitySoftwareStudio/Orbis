import json
from json import JSONDecodeError
from typing import Any

from rich import box
from rich.panel import Panel
from rich.table import Table

from core.logging import get_logger
from rag.console import RAG_DEBUG, console
from rag.constants import ROUTER_PROMPT

logger = get_logger(__name__)


def _default_intent(query: str) -> list[dict[str, Any]]:
    return [{"tool": "vector", "query": query}]


def route_query(llm_service: Any, query: str) -> list[dict[str, Any]]:
    raw = "".join(llm_service.generate(f"{ROUTER_PROMPT}\nUser: {query}"))
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        payload = json.loads(cleaned)
    except JSONDecodeError:
        logger.warning("Router parse failed, falling back to vector intent. Raw: %.120s", raw)
        return _default_intent(query)

    if isinstance(payload, dict) and isinstance(payload.get("intents"), list):
        intents = payload["intents"]
    elif isinstance(payload, dict):
        intents = [payload]
    else:
        intents = _default_intent(query)

    if RAG_DEBUG:
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Tool", style="bold cyan", width=8)
        table.add_column("Detail", style="white")
        for i, intent in enumerate(intents):
            tool = intent.get("tool", "vector").upper()
            detail = str(intent.get("query") or intent.get("filters") or "")
            table.add_row(str(i + 1), tool, detail)
        console.print(Panel(
            table,
            title=f"[cyan]Router[/cyan] → [bold]{len(intents)} intent(s)[/bold] for: [italic]{query[:80]}[/italic]",
            border_style="cyan",
            box=box.SIMPLE,
        ))

    return intents