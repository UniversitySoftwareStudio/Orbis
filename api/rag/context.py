import os
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rag.helpers import doc_meta

console = Console()
RAG_DEBUG = os.getenv("RAG_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def deduplicate_docs(docs: list[Any]) -> list[Any]:
    unique: dict[Any, Any] = {}
    for doc in docs:
        if doc.id not in unique:
            unique[doc.id] = doc
    return list(unique.values())


def render_debug_table(intents: list[dict[str, Any]], docs: list[Any]) -> None:
    if not RAG_DEBUG:
        return

    items = [
        f"{index + 1}. [{str(intent.get('tool', 'vector')).upper()}] {intent.get('query') or intent.get('filters')}"
        for index, intent in enumerate(intents)
    ]
    console.print(
        Panel(
            "\n".join(items) if items else "No intents",
            title=f"Router: {len(intents)} intent(s)",
            border_style="cyan",
            box=box.SIMPLE,
        )
    )

    table = Table(title=f"Merged Context ({len(docs)} docs)", box=box.SIMPLE)
    table.add_column("Score", style="magenta", width=7)
    table.add_column("Type", style="cyan", width=10)
    table.add_column("Title", style="green")
    table.add_column("Snippet", style="white", no_wrap=True)

    for doc in docs:
        score = f"{getattr(doc, 'score', 0.0):.3f}" if hasattr(doc, "score") else "-"
        snippet = ((doc.content or "")[:60].replace("\n", " ") + "...") if getattr(doc, "content", None) else ""
        table.add_row(score, str(getattr(doc, "type", "")).upper(), str(getattr(doc, "title", "")), snippet)
    console.print(table)


def build_context(intents: list[dict[str, Any]], docs: list[Any]) -> str:
    if not docs:
        return ""

    has_sql = any(str(intent.get("tool", "")).lower() == "sql" for intent in intents)
    compact_mode = (has_sql and len(docs) > 5) or len(docs) > 40

    if compact_mode:
        course_docs = [doc for doc in docs if getattr(doc, "type", None) == "course"]
        if len(course_docs) > len(docs) / 2:
            lines = ["The user asked for a list of courses. CSV Format:\n", "ID, Code, Title, ECTS, Info"]
            for doc in docs:
                meta = doc_meta(doc)
                code = meta.get("course_code", "N/A")
                ects = meta.get("ects", "-")
                snippet = ((doc.content or "")[:50].replace("\n", " ") + "...") if getattr(doc, "content", None) else ""
                lines.append(f"{doc.id}, {code}, {doc.title}, {ects}, {snippet}")
            return "\n".join(lines)

        lines = ["The user asked for a list. CSV Format:\n", "ID, Type, Title, URL, Snippet"]
        for doc in docs:
            meta = doc_meta(doc)
            source_ref = getattr(doc, "url", None) if getattr(doc, "type", "") == "web_page" else meta.get("course_code", "N/A")
            snippet = ((doc.content or "")[:100].replace("\n", " ") + "...") if getattr(doc, "content", None) else ""
            lines.append(f"{doc.id}, {doc.type}, {doc.title}, {source_ref}, {snippet}")
        return "\n".join(lines)

    sections: list[str] = []
    for doc in docs:
        text = f"Source: {doc.title}\nURL: {getattr(doc, 'url', 'N/A')}\nContent: {doc.content}"
        meta = doc_meta(doc)
        if meta:
            attrs = ", ".join(
                f"{key.upper()}: {value}"
                for key, value in meta.items()
                if isinstance(value, (str, int, float))
            )
            if attrs:
                text += f"\nAttributes: {attrs}"
        sections.append(text)
    return "\n\n".join(sections)
