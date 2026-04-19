"""
Validate hierarchical clustering assignments against existing KB categories.

Input:
- assignments jsonl produced by `jina_v3_cluster_kb.py`

Output:
- prints validation metrics
- writes a JSON report next to the assignments file

Usage:
    python3 api/scripts/experiments/categorization/validate_cluster_categories.py \
      --assignments api/scripts/experiments/results/categorization/jina_v3_hierarchical_20260329_223811.assignments.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score


def _purity(rows: list[dict[str, Any]], cluster_field: str, label_field: str) -> tuple[float, int, list[dict[str, Any]]]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for r in rows:
        label = r.get(label_field)
        if not label:
            continue
        grouped[int(r[cluster_field])].append(str(label))

    total = 0
    correct = 0
    stats: list[dict[str, Any]] = []
    for cluster_id, labels in grouped.items():
        cnt = Counter(labels)
        n = len(labels)
        top_label, top_n = cnt.most_common(1)[0]
        total += n
        correct += top_n
        stats.append(
            {
                "cluster_id": cluster_id,
                "size": n,
                "top_label": top_label,
                "top_ratio": top_n / n,
                "top3": cnt.most_common(3),
            }
        )
    stats.sort(key=lambda x: x["size"], reverse=True)
    return (correct / total if total else float("nan")), total, stats


def _level_report(rows: list[dict[str, Any]], level: str) -> dict[str, Any]:
    sizes = Counter(int(r[level]) for r in rows)
    report: dict[str, Any] = {
        "level": level,
        "cluster_count": len(sizes),
        "size_min": min(sizes.values()),
        "size_max": max(sizes.values()),
        "size_avg": sum(sizes.values()) / len(sizes),
        "labels": {},
    }

    for label_field in ("category", "parent_category"):
        purity, total, stats = _purity(rows, level, label_field)
        labels = [r[label_field] for r in rows if r.get(label_field)]
        clusters = [r[level] for r in rows if r.get(label_field)]
        nmi = normalized_mutual_info_score(labels, clusters)
        ari = adjusted_rand_score(labels, clusters)

        report["labels"][label_field] = {
            "purity": purity,
            "docs_counted": total,
            "nmi": nmi,
            "ari": ari,
            "top_clusters_by_size": stats[:10],
            "most_mixed_clusters": sorted(stats, key=lambda x: x["top_ratio"])[:10],
            "most_pure_clusters": sorted(stats, key=lambda x: (-x["top_ratio"], -x["size"]))[:10],
        }

    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate found clusters against KB categories.")
    ap.add_argument("--assignments", type=Path, required=True)
    args = ap.parse_args()

    rows = [json.loads(line) for line in args.assignments.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise RuntimeError("Assignments file is empty.")

    level_fields = [k for k in rows[0].keys() if k.startswith("cluster_k")]
    level_fields.sort(key=lambda s: int(s.split("k", 1)[1]))

    report = {
        "assignments_file": str(args.assignments),
        "rows": len(rows),
        "levels": [],
    }
    for level in level_fields:
        report["levels"].append(_level_report(rows, level))

    out = args.assignments.with_suffix(".validation.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[validate] rows={report['rows']}")
    for lvl in report["levels"]:
        print(
            f"[validate] {lvl['level']} "
            f"clusters={lvl['cluster_count']} "
            f"category_purity={lvl['labels']['category']['purity']:.4f} "
            f"parent_purity={lvl['labels']['parent_category']['purity']:.4f}"
        )
    print(f"[validate] report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

