from typing import Any


def doc_meta(doc: Any) -> dict[str, Any]:
    return getattr(doc, "metadata_", getattr(doc, "metadata", {})) or {}


def build_rerank_text(doc: Any, include_language: bool = False) -> str:
    meta = doc_meta(doc)
    safe_meta = ", ".join(
        f"{key}: {value}" for key, value in meta.items() if isinstance(value, (str, int, float))
    )
    parts = [
        f"Title: {getattr(doc, 'title', '')}",
        f"URL: {getattr(doc, 'url', 'N/A')}",
    ]
    if include_language:
        parts.append(f"Language: {getattr(doc, 'language', 'N/A')}")
    if safe_meta:
        parts.append(f"Metadata: {safe_meta}")
    parts.append(f"Content: {getattr(doc, 'content', '')}")
    return "\n".join(parts)
