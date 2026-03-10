import json
from json import JSONDecodeError
from typing import Any

from core.logging import get_logger
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
        logger.warning("Router parse failed, falling back to vector intent")
        return _default_intent(query)

    if isinstance(payload, dict) and isinstance(payload.get("intents"), list):
        return payload["intents"]
    if isinstance(payload, dict):
        return [payload]
    return _default_intent(query)
