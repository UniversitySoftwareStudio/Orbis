"""
Visualize discovered clusters versus existing KB categories.

Creates an interactive HTML dashboard with:
1) Sankey: cluster -> category flows
2) Heatmap: cluster x category counts
3) Bar: cluster sizes + dominant-category purity
4) Sunburst: parent_category -> category distribution

Usage:
    python3 api/scripts/experiments/categorization/visualize_cluster_vs_category.py \
      --assignments api/scripts/experiments/results/categorization/jina_v3_hierarchical_20260329_223811.assignments.jsonl \
      --level cluster_k64
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _load_assignments(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if not rows:
        raise RuntimeError(f"No rows found in {path}")
    return pd.DataFrame(rows)


def _cluster_sort_key(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 10**9


def _build_cluster_profile(df: pd.DataFrame, level: str) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for cluster_id, g in df.groupby(level):
        c = g["category"].value_counts(dropna=False)
        p = g["parent_category"].value_counts(dropna=False)
        top_cat = c.index[0]
        top_cat_n = int(c.iloc[0])
        size = int(len(g))
        profiles.append(
            {
                "cluster_id": int(cluster_id),
                "size": size,
                "dominant_category": str(top_cat),
                "dominant_category_ratio": top_cat_n / size if size else 0.0,
                "top_categories": [(str(k), int(v)) for k, v in c.head(5).items()],
                "top_parent_categories": [(str(k), int(v)) for k, v in p.head(5).items()],
                "sample_titles": [str(x) for x in g["title"].dropna().head(5).tolist()],
            }
        )
    profiles.sort(key=lambda x: x["cluster_id"])
    return profiles


def build_dashboard(
    df: pd.DataFrame,
    *,
    level: str,
    top_sankey_categories: int,
    top_heatmap_categories: int,
) -> go.Figure:
    # Normalize missing values for clean visuals.
    df = df.copy()
    df["category"] = df["category"].fillna("(none)").replace("", "(none)")
    df["parent_category"] = df["parent_category"].fillna("(none)").replace("", "(none)")

    clusters = sorted(df[level].unique().tolist(), key=_cluster_sort_key)
    cluster_labels = [f"Cluster {int(c)}" for c in clusters]

    # Top categories for display.
    category_counts = df["category"].value_counts()
    top_cats = category_counts.head(top_sankey_categories).index.tolist()

    df_sankey = df.copy()
    df_sankey["category_sankey"] = df_sankey["category"].where(df_sankey["category"].isin(top_cats), "Other")
    flow = (
        df_sankey.groupby([level, "category_sankey"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )

    # Sankey nodes
    cat_nodes = sorted(flow["category_sankey"].unique().tolist())
    node_labels = cluster_labels + [f"Category: {c}" for c in cat_nodes]
    cluster_to_idx = {c: i for i, c in enumerate(clusters)}
    cat_to_idx = {c: len(clusters) + i for i, c in enumerate(cat_nodes)}

    sources = [cluster_to_idx[r[level]] for _, r in flow.iterrows()]
    targets = [cat_to_idx[r["category_sankey"]] for _, r in flow.iterrows()]
    values = [int(r["count"]) for _, r in flow.iterrows()]

    # Heatmap
    heat_cats = category_counts.head(top_heatmap_categories).index.tolist()
    heat = pd.crosstab(df[level], df["category"])[heat_cats]
    heat = heat.reindex(index=clusters, fill_value=0)

    # Cluster purity + size
    by_cluster = df.groupby(level)
    cluster_size = by_cluster.size().reindex(clusters)
    dominant_ratio = by_cluster["category"].apply(lambda s: s.value_counts().iloc[0] / len(s)).reindex(clusters)

    # Sunburst
    sun = (
        df.groupby(["parent_category", "category"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )

    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "domain"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "domain"}],
        ],
        subplot_titles=(
            "Cluster -> Category Flow (Sankey)",
            "Cluster x Category Heatmap",
            "Cluster Size and Dominant-Category Purity",
            "Parent Category -> Category Distribution",
        ),
        horizontal_spacing=0.08,
        vertical_spacing=0.12,
    )

    fig.add_trace(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=node_labels,
                pad=12,
                thickness=12,
                color=["#4c78a8"] * len(clusters) + ["#72b7b2"] * len(cat_nodes),
            ),
            link=dict(source=sources, target=targets, value=values),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Heatmap(
            z=heat.values,
            x=[str(c) for c in heat.columns],
            y=[f"C{int(c)}" for c in heat.index],
            colorscale="YlGnBu",
            colorbar=dict(title="Count"),
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Bar(
            x=[f"C{int(c)}" for c in clusters],
            y=cluster_size.values,
            name="Cluster size",
            marker=dict(color=dominant_ratio.values, colorscale="Viridis", colorbar=dict(title="Purity")),
            text=[f"{r:.2f}" for r in dominant_ratio.values],
            textposition="outside",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Sunburst(
            labels=sun["category"],
            parents=sun["parent_category"],
            values=sun["count"],
            branchvalues="total",
        ),
        row=2,
        col=2,
    )

    fig.update_layout(
        title=f"Cluster Validation Dashboard ({level})",
        template="plotly_white",
        height=1200,
        width=1800,
        showlegend=False,
        margin=dict(l=20, r=20, t=70, b=20),
    )
    fig.update_yaxes(title_text="Cluster", row=1, col=2)
    fig.update_xaxes(title_text="Category", row=1, col=2)
    fig.update_yaxes(title_text="Docs", row=2, col=1)
    fig.update_xaxes(title_text="Cluster", row=2, col=1)
    return fig


def main() -> int:
    p = argparse.ArgumentParser(description="Visualize found clusters vs existing categories.")
    p.add_argument("--assignments", type=Path, required=True)
    p.add_argument("--level", type=str, default="cluster_k64")
    p.add_argument("--top-sankey-categories", type=int, default=20)
    p.add_argument("--top-heatmap-categories", type=int, default=20)
    p.add_argument("--output-html", type=Path, default=None)
    p.add_argument("--output-profile-json", type=Path, default=None)
    args = p.parse_args()

    df = _load_assignments(args.assignments)
    if args.level not in df.columns:
        raise RuntimeError(f"{args.level} not found in assignments columns.")

    fig = build_dashboard(
        df,
        level=args.level,
        top_sankey_categories=args.top_sankey_categories,
        top_heatmap_categories=args.top_heatmap_categories,
    )

    out_html = args.output_html or args.assignments.with_suffix(f".{args.level}.dashboard.html")
    out_profile = args.output_profile_json or args.assignments.with_suffix(f".{args.level}.cluster_profiles.json")

    fig.write_html(str(out_html), include_plotlyjs="cdn")
    profiles = _build_cluster_profile(df, args.level)
    out_profile.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[viz] dashboard: {out_html}")
    print(f"[viz] profiles:  {out_profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

