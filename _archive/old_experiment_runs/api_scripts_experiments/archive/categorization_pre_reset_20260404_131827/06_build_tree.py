#!/usr/bin/env python3
"""
Build a directional taxonomy tree from AI taxonomy classification output.

Input:
- Output JSON from 05_run_ai_mapping.py

Output:
- Tree JSON (top_level -> sub_level -> canonical_label)
- Markdown summary with examples per leaf
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build directional taxonomy tree artifact.")
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--examples-per-leaf", type=int, default=3)
    parser.add_argument("--run-name", type=str, default="taxonomy_tree_directional")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def _empty_leaf() -> dict[str, Any]:
    return {
        "category_count": 0,
        "doc_count": 0,
        "clusters": [],
        "representative_parents": [],
        "sample_urls": [],
    }


def main() -> int:
    args = parse_args()
    if not args.input_json.exists():
        raise FileNotFoundError(f"Input JSON not found: {args.input_json}")
    if args.examples_per_leaf <= 0:
        raise ValueError("--examples-per-leaf must be > 0")

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    summary = payload.get("summary", {}) or {}
    rows = list(payload.get("results", []) or [])

    unresolved: list[dict[str, Any]] = []
    tree: dict[str, Any] = {}

    for row in rows:
        ai = row.get("ai_taxonomy", {}) or {}
        status = str(ai.get("status", "unresolved")).strip().lower()
        if status != "mapped":
            unresolved.append(
                {
                    "cluster_id": row.get("cluster_id"),
                    "representative_parent": row.get("representative_parent"),
                    "status": status,
                    "reason": ai.get("reason", ""),
                }
            )
            continue

        top = str(ai.get("top_level", "unknown")).strip().lower() or "unknown"
        sub = str(ai.get("sub_level", "unknown")).strip().lower() or "unknown"
        label = str(ai.get("canonical_label", "UNRESOLVED")).strip() or "UNRESOLVED"
        doc_count = int(row.get("doc_count", 0))
        cluster_id = int(row.get("cluster_id", 0))
        parent = str(row.get("representative_parent", ""))
        sample_urls = [str(u) for u in (row.get("sample_urls", []) or []) if str(u).strip()]

        top_node = tree.setdefault(
            top,
            {
                "category_count": 0,
                "doc_count": 0,
                "sub_levels": {},
            },
        )
        top_node["category_count"] += 1
        top_node["doc_count"] += doc_count

        sub_node = top_node["sub_levels"].setdefault(
            sub,
            {
                "category_count": 0,
                "doc_count": 0,
                "leaves": {},
            },
        )
        sub_node["category_count"] += 1
        sub_node["doc_count"] += doc_count

        leaf = sub_node["leaves"].setdefault(label, _empty_leaf())
        leaf["category_count"] += 1
        leaf["doc_count"] += doc_count
        leaf["clusters"].append(cluster_id)
        if parent and parent not in leaf["representative_parents"]:
            leaf["representative_parents"].append(parent)
        for url in sample_urls:
            if url not in leaf["sample_urls"]:
                leaf["sample_urls"].append(url)

    # trim arrays for readability
    for top_node in tree.values():
        for sub_node in top_node["sub_levels"].values():
            for leaf in sub_node["leaves"].values():
                leaf["clusters"] = sorted(set(int(v) for v in leaf["clusters"]))
                leaf["representative_parents"] = leaf["representative_parents"][: args.examples_per_leaf]
                leaf["sample_urls"] = leaf["sample_urls"][: args.examples_per_leaf]

    # sort tree deterministically
    sorted_tree: dict[str, Any] = {}
    for top in sorted(tree.keys()):
        top_node = tree[top]
        sorted_sub = {}
        for sub in sorted(top_node["sub_levels"].keys()):
            sub_node = top_node["sub_levels"][sub]
            sorted_leaves = {}
            for label in sorted(sub_node["leaves"].keys()):
                sorted_leaves[label] = sub_node["leaves"][label]
            sorted_sub[sub] = {
                "category_count": sub_node["category_count"],
                "doc_count": sub_node["doc_count"],
                "leaves": sorted_leaves,
            }
        sorted_tree[top] = {
            "category_count": top_node["category_count"],
            "doc_count": top_node["doc_count"],
            "sub_levels": sorted_sub,
        }

    tree_summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_input_json": str(args.input_json),
        "source_summary": summary,
        "top_level_count": len(sorted_tree),
        "mapped_category_count": sum(v["category_count"] for v in sorted_tree.values()),
        "mapped_doc_count": sum(v["doc_count"] for v in sorted_tree.values()),
        "unresolved_count": len(unresolved),
    }

    out_payload = {
        "summary": tree_summary,
        "tree": sorted_tree,
        "unresolved": unresolved,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_json = args.output_dir / f"{args.run_name}_{stamp}.json"
    out_md = args.output_dir / f"{args.run_name}_{stamp}.md"
    out_json.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# Directional Taxonomy Tree")
    lines.append("")
    lines.append(f"- source: `{args.input_json}`")
    lines.append(f"- mapped categories: `{tree_summary['mapped_category_count']}`")
    lines.append(f"- mapped docs: `{tree_summary['mapped_doc_count']}`")
    lines.append(f"- unresolved categories: `{tree_summary['unresolved_count']}`")
    lines.append("")
    for top, top_node in sorted_tree.items():
        lines.append(f"## {top} ({top_node['category_count']} categories, {top_node['doc_count']} docs)")
        for sub, sub_node in top_node["sub_levels"].items():
            lines.append(f"- `{sub}` ({sub_node['category_count']} categories, {sub_node['doc_count']} docs)")
            for label, leaf in sub_node["leaves"].items():
                lines.append(
                    f"  - `{label}` | categories={leaf['category_count']} docs={leaf['doc_count']} "
                    f"clusters={len(leaf['clusters'])}"
                )
                if leaf["representative_parents"]:
                    lines.append(f"    - parents: {', '.join(leaf['representative_parents'])}")
                if leaf["sample_urls"]:
                    lines.append(f"    - sample_urls: {', '.join(leaf['sample_urls'])}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[taxonomy-tree] output_json: {out_json}")
    print(f"[taxonomy-tree] output_md: {out_md}")
    print(
        f"[taxonomy-tree] top_levels={tree_summary['top_level_count']} "
        f"mapped_categories={tree_summary['mapped_category_count']} "
        f"unresolved={tree_summary['unresolved_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
