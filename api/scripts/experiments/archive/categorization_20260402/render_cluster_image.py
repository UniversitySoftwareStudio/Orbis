"""
Render a static PNG image for cluster-vs-category validation.

Usage:
    python3 api/scripts/experiments/categorization/render_cluster_image.py \
      --assignments api/scripts/experiments/results/categorization/jina_v3_hierarchical_20260329_223811.assignments.jsonl \
      --level cluster_k64
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _load(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise RuntimeError(f"No rows in {path}")
    return pd.DataFrame(rows)


def _dominant_ratio(series: pd.Series) -> float:
    vc = series.value_counts()
    if vc.empty:
        return 0.0
    return float(vc.iloc[0] / len(series))


def main() -> int:
    ap = argparse.ArgumentParser(description="Render cluster/category image.")
    ap.add_argument("--assignments", type=Path, required=True)
    ap.add_argument("--level", type=str, default="cluster_k64")
    ap.add_argument("--top-categories", type=int, default=20)
    ap.add_argument("--top-clusters", type=int, default=30)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    df = _load(args.assignments)
    if args.level not in df.columns:
        raise RuntimeError(f"{args.level} missing in assignments file")

    df["category"] = df["category"].fillna("(none)").replace("", "(none)")
    df["cluster"] = df[args.level].astype(int)

    top_categories = df["category"].value_counts().head(args.top_categories).index.tolist()
    cluster_sizes = df["cluster"].value_counts()
    top_clusters = cluster_sizes.head(args.top_clusters).index.tolist()
    top_clusters_sorted = sorted(top_clusters)

    table = pd.crosstab(df["cluster"], df["category"])
    table = table.reindex(index=top_clusters_sorted, columns=top_categories, fill_value=0)

    by_cluster = (
        df[df["cluster"].isin(top_clusters_sorted)]
        .groupby("cluster")
        .agg(size=("cluster", "count"), purity=("category", _dominant_ratio))
        .reindex(top_clusters_sorted)
    )

    fig, axes = plt.subplots(2, 1, figsize=(22, 14), height_ratios=[3, 1.5])

    im = axes[0].imshow(table.values, aspect="auto")
    axes[0].set_title(f"{args.level}: Cluster x Category Heatmap (Top Clusters/Categories)")
    axes[0].set_ylabel("Cluster")
    axes[0].set_xlabel("Category")
    axes[0].set_yticks(np.arange(len(top_clusters_sorted)))
    axes[0].set_yticklabels([f"C{c}" for c in top_clusters_sorted], fontsize=8)
    axes[0].set_xticks(np.arange(len(top_categories)))
    axes[0].set_xticklabels(top_categories, rotation=45, ha="right", fontsize=8)
    fig.colorbar(im, ax=axes[0], fraction=0.015, pad=0.01, label="Doc Count")

    x = np.arange(len(top_clusters_sorted))
    size_vals = by_cluster["size"].to_numpy()
    purity_vals = by_cluster["purity"].to_numpy()

    axes[1].bar(x, size_vals, alpha=0.7, label="Cluster size")
    ax2 = axes[1].twinx()
    ax2.plot(x, purity_vals, color="crimson", marker="o", linewidth=1.5, label="Dominant category ratio")
    ax2.set_ylim(0, 1.0)
    ax2.set_ylabel("Purity (0-1)")
    axes[1].set_title("Cluster Size and Dominant-Category Purity")
    axes[1].set_xlabel("Cluster")
    axes[1].set_ylabel("Size")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"C{c}" for c in top_clusters_sorted], rotation=0, fontsize=8)

    lines1, labels1 = axes[1].get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    axes[1].legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    fig.tight_layout()

    out = args.output or args.assignments.with_suffix(f".{args.level}.image.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"[image] saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

