#!/usr/bin/env python3
"""
Build processing shortlist from full-tail diversity output.

Simple rules:
- If decision == url_only_categorize -> URL is enough (not in shortlist)
- Else -> processing candidate
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build URL-parent processing shortlist")
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--p1-min-docs", type=int, default=20)
    parser.add_argument(
        "--include-all-candidates",
        action="store_true",
        help="Include full candidate list in JSON output (default: top_n only).",
    )
    parser.add_argument("--run-name", type=str, default="url_parent_shortlist")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_json.exists():
        raise FileNotFoundError(f"Input not found: {args.input_json}")
    if args.top_n <= 0:
        raise ValueError("--top-n must be > 0")
    if args.p1_min_docs <= 0:
        raise ValueError("--p1-min-docs must be > 0")

    src = json.loads(args.input_json.read_text(encoding="utf-8"))
    groups = src.get("groups", [])

    candidates = []
    for g in groups:
        decision = g.get("decision", "")
        if decision == "url_only_categorize":
            continue
        doc_count = int(g.get("doc_count", 0))
        priority = "P1" if doc_count >= args.p1_min_docs else "P2"
        candidates.append(
            {
                "cluster_id": g.get("cluster_id"),
                "parent": g.get("representative_parent"),
                "doc_count": doc_count,
                "decision": decision,
                "depth_signal": g.get("depth_signal"),
                "dynamic_tail_ratio": g.get("dynamic_tail_ratio"),
                "semantic_tail_ratio": g.get("semantic_tail_ratio"),
                "dominant_tail_pattern_share": g.get("dominant_tail_pattern_share"),
                "priority": priority,
            }
        )

    candidates.sort(key=lambda x: (x["priority"] != "P1", -x["doc_count"]))
    p1 = [r for r in candidates if r["priority"] == "P1"]
    p2 = [r for r in candidates if r["priority"] == "P2"]
    top_n = p1[: args.top_n]

    summary = {
        "source_input": str(args.input_json),
        "total_groups_in_input": len(groups),
        "candidate_groups": len(candidates),
        "candidate_docs": sum(r["doc_count"] for r in candidates),
        "p1_groups": len(p1),
        "p1_docs": sum(r["doc_count"] for r in p1),
        "p2_groups": len(p2),
        "p2_docs": sum(r["doc_count"] for r in p2),
        "top_n": args.top_n,
        "p1_min_docs": args.p1_min_docs,
    }

    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "top_n_groups": top_n,
    }
    if args.include_all_candidates:
        payload["candidates"] = candidates

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_json = args.output_dir / f"{args.run_name}_{stamp}.json"
    out_md = args.output_dir / f"{args.run_name}_{stamp}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("# URL Parent Shortlist")
    lines.append("")
    lines.append(f"Source: `{args.input_json}`")
    lines.append("")
    for k in [
        "candidate_groups",
        "candidate_docs",
        "p1_groups",
        "p1_docs",
        "p2_groups",
        "p2_docs",
        "top_n",
    ]:
        lines.append(f"- {k}: **{summary[k]}**")
    lines.append("")
    lines.append("## Top N (Work Now)")
    lines.append("")
    lines.append("| # | Cluster | Docs | Parent | Decision | Depth Signal |")
    lines.append("|---:|---:|---:|---|---|---|")
    for i, r in enumerate(top_n, 1):
        parent = (r["parent"] or "").replace("|", "\\|")
        lines.append(
            f"| {i} | {r['cluster_id']} | {r['doc_count']} | `{parent}` | `{r['decision']}` | `{r['depth_signal']}` |"
        )
    lines.append("")
    lines.append("Note: full candidate list is omitted for minimal output.")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[shortlist] json: {out_json}")
    print(f"[shortlist] md: {out_md}")
    print(f"[shortlist] summary: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
