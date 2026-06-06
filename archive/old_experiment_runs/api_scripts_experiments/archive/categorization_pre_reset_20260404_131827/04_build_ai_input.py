#!/usr/bin/env python3
"""
Prepare AI taxonomy input from depth-diversity output.

Default behavior is intentionally safe:
- include only URL-resolved groups:
  - url_only_parent
  - url_only_categorize
- exclude needs_algorithm groups

This script is the "count gate" before any AI run:
it prints how many categories will be sent to AI.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import bindparam, text


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.session import SessionLocal  # noqa: E402


DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _cluster_to_doc_ids_from_umbrella(umbrella: dict[str, object]) -> dict[int, list[str]]:
    clusters = (
        umbrella.get("depth_results", {})
        .get("dynamic", {})
        .get("clusters", [])
    )
    out: dict[int, list[str]] = {}
    for cluster in clusters:
        cluster_id = int(cluster.get("cluster_id", 0))
        all_ids: list[str] = []
        for parent in cluster.get("parents", []):
            all_ids.extend([str(v) for v in parent.get("doc_ids", [])])
        # preserve order + dedupe
        seen: set[str] = set()
        ordered: list[str] = []
        for doc_id in all_ids:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            ordered.append(doc_id)
        out[cluster_id] = ordered
    return out


def _fetch_urls(ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    db = SessionLocal()
    try:
        stmt = text(
            """
            SELECT id::text AS id, COALESCE(url, '') AS url
            FROM knowledge_base
            WHERE id::text IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
        rows = list(db.execute(stmt, {"ids": ids}).all())
        return {r[0]: (r[1] or "") for r in rows}
    finally:
        db.close()


def _path_hint(parent: str) -> dict[str, object]:
    parsed = urlparse((parent or "").strip())
    # parent is usually host/path without protocol, so keep robust fallback
    raw = (parent or "").strip().strip("/")
    if "://" in raw:
        host = (parsed.netloc or "").lower()
        parts = [p for p in (parsed.path or "").split("/") if p]
    else:
        tokens = raw.split("/") if raw else []
        host = tokens[0].lower() if tokens else "unknown"
        parts = tokens[1:] if len(tokens) > 1 else []
    return {
        "host": host,
        "segments": parts,
        "path_depth": len(parts),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare AI taxonomy input and category-count gate.")
    parser.add_argument("--depth-json", type=Path, required=True)
    parser.add_argument("--umbrella-json", type=Path, default=None)
    parser.add_argument(
        "--include-decisions",
        type=str,
        default="url_only_parent,url_only_categorize",
        help="Comma-separated decisions to include in AI input.",
    )
    parser.add_argument("--sample-urls-per-category", type=int, default=3)
    parser.add_argument("--run-name", type=str, default="ai_taxonomy_pass1_input")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.depth_json.exists():
        raise FileNotFoundError(f"Depth JSON not found: {args.depth_json}")
    if args.umbrella_json is not None and not args.umbrella_json.exists():
        raise FileNotFoundError(f"Umbrella JSON not found: {args.umbrella_json}")
    if args.sample_urls_per_category <= 0:
        raise ValueError("--sample-urls-per-category must be > 0")

    include_decisions = set(_parse_csv(args.include_decisions))
    if not include_decisions:
        raise ValueError("--include-decisions must contain at least one decision.")

    depth = json.loads(args.depth_json.read_text(encoding="utf-8"))
    groups = list(depth.get("groups", []))

    included = [g for g in groups if str(g.get("decision", "")) in include_decisions]
    included.sort(key=lambda g: (-int(g.get("doc_count", 0)), int(g.get("cluster_id", 0))))
    excluded_counter = Counter(str(g.get("decision", "unknown")) for g in groups if g not in included)

    cluster_doc_ids: dict[int, list[str]] = {}
    if args.umbrella_json is not None:
        umbrella = json.loads(args.umbrella_json.read_text(encoding="utf-8"))
        cluster_doc_ids = _cluster_to_doc_ids_from_umbrella(umbrella)

    # collect ids needed for sample URL lookup in one DB query
    sample_ids: list[str] = []
    for g in included:
        cid = int(g.get("cluster_id", 0))
        ids = cluster_doc_ids.get(cid, [])
        sample_ids.extend(ids[: args.sample_urls_per_category])
    url_map = _fetch_urls(sorted(set(sample_ids))) if sample_ids else {}

    categories: list[dict[str, object]] = []
    for g in included:
        cid = int(g.get("cluster_id", 0))
        parent = str(g.get("representative_parent", ""))
        category = {
            "cluster_id": cid,
            "decision": str(g.get("decision", "")),
            "depth_signal": str(g.get("depth_signal", "")),
            "doc_count": int(g.get("doc_count", 0)),
            "representative_parent": parent,
            "path_hint": _path_hint(parent),
            "metrics": {
                "no_tail_ratio": g.get("no_tail_ratio"),
                "dynamic_tail_ratio": g.get("dynamic_tail_ratio"),
                "semantic_tail_ratio": g.get("semantic_tail_ratio"),
                "numeric_only_tail_ratio": g.get("numeric_only_tail_ratio"),
                "all_dynamic_tail_doc_ratio": g.get("all_dynamic_tail_doc_ratio"),
                "semantic_tail_doc_ratio": g.get("semantic_tail_doc_ratio"),
                "tail_pattern_entropy": g.get("tail_pattern_entropy"),
                "dominant_tail_pattern_share": g.get("dominant_tail_pattern_share"),
                "unique_tail_patterns": g.get("unique_tail_patterns"),
            },
            "sample_urls": [],
        }
        ids = cluster_doc_ids.get(cid, [])
        for doc_id in ids[: args.sample_urls_per_category]:
            url = url_map.get(doc_id, "")
            if url:
                category["sample_urls"].append(url)
        categories.append(category)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_depth_json": str(args.depth_json),
        "source_umbrella_json": str(args.umbrella_json) if args.umbrella_json else None,
        "include_decisions": sorted(include_decisions),
        "total_groups_in_depth": len(groups),
        "categories_for_ai_count": len(categories),
        "categories_for_ai_docs": sum(int(c["doc_count"]) for c in categories),
        "excluded_by_decision": dict(excluded_counter),
    }

    payload = {
        "summary": summary,
        "categories_for_ai": categories,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_json = args.output_dir / f"{args.run_name}_{stamp}.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ai-input] output: {out_json}")
    print(
        "[ai-input] categories_for_ai_count="
        f"{summary['categories_for_ai_count']} "
        f"docs={summary['categories_for_ai_docs']}"
    )
    print(f"[ai-input] included_decisions={summary['include_decisions']}")
    print(f"[ai-input] excluded_by_decision={summary['excluded_by_decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

