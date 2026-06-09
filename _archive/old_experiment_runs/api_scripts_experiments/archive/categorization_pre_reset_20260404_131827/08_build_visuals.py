#!/usr/bin/env python3
"""
Create presentation-ready visualizations for the categorization pipeline.

Outputs:
- PNG charts per pipeline step
- JSON summary
- Markdown report with chart list + literature mapping
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


API_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"

DECISION_COLORS = {
    "url_only_parent": "#4e79a7",
    "url_only_categorize": "#59a14f",
    "needs_algorithm": "#e15759",
}


def _resolve_latest(glob_pattern: str) -> Path | None:
    matches = sorted(DEFAULT_RESULTS_DIR.glob(glob_pattern))
    return matches[-1] if matches else None


def _truncate(text: str, max_len: int = 48) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _save(fig: plt.Figure, out_path: Path, dpi: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize categorization pipeline artifacts.")
    parser.add_argument("--umbrella-json", type=Path, default=None)
    parser.add_argument("--depth-json", type=Path, default=None)
    parser.add_argument("--shortlist-json", type=Path, default=None)
    parser.add_argument("--taxonomy-json", type=Path, default=None)
    parser.add_argument("--tree-json", type=Path, default=None)
    parser.add_argument("--run-name", type=str, default="pass1_pipeline_visual_pack")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--dpi", type=int, default=170)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        out = float(v)
        if out != out:
            return default
        return out
    except Exception:
        return default


def main() -> int:
    args = parse_args()

    umbrella_path = args.umbrella_json or _resolve_latest("pass1_url_umbrella_*.json")
    depth_path = args.depth_json or _resolve_latest("pass1_url_depth_diversity_*.json")
    shortlist_path = args.shortlist_json or _resolve_latest("pass1_url_shortlist_*.json")
    taxonomy_path = args.taxonomy_json or _resolve_latest("pass1_ai_taxonomy_outlier_full_*.json")
    tree_path = args.tree_json or _resolve_latest("pass1_taxonomy_tree_directional_*.json")

    missing = [
        name
        for name, p in {
            "umbrella": umbrella_path,
            "depth": depth_path,
            "shortlist": shortlist_path,
            "taxonomy": taxonomy_path,
            "tree": tree_path,
        }.items()
        if p is None or not p.exists()
    ]
    if missing:
        raise FileNotFoundError(f"Missing required artifacts: {missing}")

    output_dir = args.output_dir or (DEFAULT_RESULTS_DIR / f"{args.run_name}_assets")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    umbrella = _load_json(umbrella_path)
    depth = _load_json(depth_path)
    shortlist = _load_json(shortlist_path)
    taxonomy = _load_json(taxonomy_path)
    tree = _load_json(tree_path)

    sns.set_theme(style="whitegrid", context="talk")

    figures: list[dict[str, str]] = []

    # -----------------------------
    # Step 1: umbrella parent stage
    # -----------------------------
    dyn = umbrella["depth_results"]["dynamic"]
    clusters = dyn.get("clusters", [])
    cluster_df = pd.DataFrame(
        [
            {
                "cluster_id": _as_int(c.get("cluster_id")),
                "doc_count": _as_int(c.get("doc_count")),
                "parent_count": _as_int(c.get("parent_count")),
                "representative_parent": str(c.get("representative_parent", "")),
            }
            for c in clusters
        ]
    )
    depth_hist = dyn.get("dynamic_meta", {}).get("chosen_depth_hist_docs", {})
    depth_df = pd.DataFrame(
        [
            {"depth": str(k), "docs": _as_int(v)}
            for k, v in sorted(depth_hist.items(), key=lambda kv: int(kv[0]))
        ]
    )

    fig = plt.figure(figsize=(9, 5))
    ax = fig.add_subplot(111)
    ax.bar(depth_df["depth"], depth_df["docs"], color="#4e79a7")
    ax.set_title("Step 1: Chosen URL Depth Distribution")
    ax.set_xlabel("Chosen depth")
    ax.set_ylabel("Documents")
    out = output_dir / f"01_depth_distribution_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "1", "title": "Chosen URL Depth Distribution", "file": str(out)})

    top_clusters = cluster_df.sort_values("doc_count", ascending=False).head(args.top_k)
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111)
    ax.barh(
        [_truncate(v) for v in top_clusters["representative_parent"].tolist()[::-1]],
        top_clusters["doc_count"].tolist()[::-1],
        color="#76b7b2",
    )
    ax.set_title(f"Step 1: Largest Parent Clusters (Top {len(top_clusters)})")
    ax.set_xlabel("Documents in cluster")
    out = output_dir / f"02_top_parent_clusters_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "1", "title": "Largest Parent Clusters", "file": str(out)})

    # ---------------------------------
    # Step 2: depth-diversity decisions
    # ---------------------------------
    groups = depth.get("groups", [])
    grp_df = pd.DataFrame(groups)
    grp_df["decision"] = grp_df["decision"].astype(str)
    grp_df["doc_count"] = grp_df["doc_count"].map(_as_int)

    decision_counts = grp_df.groupby("decision")["doc_count"].sum().reset_index().sort_values("doc_count", ascending=False)
    fig = plt.figure(figsize=(8, 5))
    ax = fig.add_subplot(111)
    colors = [DECISION_COLORS.get(d, "#999999") for d in decision_counts["decision"]]
    ax.bar(decision_counts["decision"], decision_counts["doc_count"], color=colors)
    ax.set_title("Step 2: Decision Distribution (by documents)")
    ax.set_xlabel("Decision")
    ax.set_ylabel("Documents")
    out = output_dir / f"03_decision_distribution_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "2", "title": "Decision Distribution", "file": str(out)})

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    for decision, color in DECISION_COLORS.items():
        d = grp_df[grp_df["decision"] == decision]
        if d.empty:
            continue
        ax.scatter(
            d["dynamic_tail_ratio"].map(_as_float),
            d["semantic_tail_ratio"].map(_as_float),
            s=d["doc_count"].clip(lower=5).pow(0.5) * 8,
            alpha=0.65,
            c=color,
            label=decision,
            edgecolors="none",
        )
    # thresholds from algorithm.md
    ax.axvline(0.70, linestyle="--", color="#b55d60", linewidth=1)
    ax.axhline(0.30, linestyle="--", color="#b55d60", linewidth=1)
    ax.axhline(0.45, linestyle="--", color="#4f8a4f", linewidth=1)
    ax.set_title("Step 2: Tail Signal Scatter")
    ax.set_xlabel("dynamic_tail_ratio")
    ax.set_ylabel("semantic_tail_ratio")
    ax.legend(frameon=True, fontsize=9)
    out = output_dir / f"04_tail_signal_scatter_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "2", "title": "Tail Signal Scatter", "file": str(out)})

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    for decision, color in DECISION_COLORS.items():
        d = grp_df[grp_df["decision"] == decision]
        if d.empty:
            continue
        ax.scatter(
            d["tail_pattern_entropy"].map(_as_float),
            d["dominant_tail_pattern_share"].map(_as_float),
            s=d["doc_count"].clip(lower=5).pow(0.5) * 8,
            alpha=0.65,
            c=color,
            label=decision,
            edgecolors="none",
        )
    ax.axvline(1.20, linestyle="--", color="#b55d60", linewidth=1)
    ax.axhline(0.60, linestyle="--", color="#b55d60", linewidth=1)
    ax.axvline(1.50, linestyle="--", color="#4f8a4f", linewidth=1)
    ax.axhline(0.55, linestyle="--", color="#4f8a4f", linewidth=1)
    ax.set_title("Step 2: Entropy vs Dominance")
    ax.set_xlabel("tail_pattern_entropy")
    ax.set_ylabel("dominant_tail_pattern_share")
    ax.legend(frameon=True, fontsize=9)
    out = output_dir / f"05_entropy_dominance_scatter_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "2", "title": "Entropy vs Dominance", "file": str(out)})

    na = grp_df[grp_df["decision"] == "needs_algorithm"].copy()
    na = na.sort_values("doc_count", ascending=False).head(args.top_k)
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111)
    ax.barh([_truncate(x) for x in na["representative_parent"].tolist()[::-1]], na["doc_count"].tolist()[::-1], color="#e15759")
    ax.set_title(f"Step 2: Needs-Algorithm Groups (Top {len(na)})")
    ax.set_xlabel("Documents")
    out = output_dir / f"06_needs_algorithm_top_groups_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "2", "title": "Needs-Algorithm Top Groups", "file": str(out)})

    # ----------------------------
    # Step 3: shortlist diagnostic
    # ----------------------------
    ssum = shortlist.get("summary", {})
    pr_df = pd.DataFrame(
        [
            {"priority": "P1", "groups": _as_int(ssum.get("p1_groups")), "docs": _as_int(ssum.get("p1_docs"))},
            {"priority": "P2", "groups": _as_int(ssum.get("p2_groups")), "docs": _as_int(ssum.get("p2_docs"))},
        ]
    )
    fig = plt.figure(figsize=(8, 5))
    ax = fig.add_subplot(111)
    ax.bar(pr_df["priority"], pr_df["docs"], color=["#4e79a7", "#f28e2b"])
    ax.set_title("Step 3: Shortlist Priority Load")
    ax.set_xlabel("Priority")
    ax.set_ylabel("Documents")
    out = output_dir / f"07_shortlist_priority_docs_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "3", "title": "Shortlist Priority Load", "file": str(out)})

    # -----------------------------------
    # Step 4: taxonomy mapping outcomes
    # -----------------------------------
    rows = taxonomy.get("results", [])
    tax_df = pd.DataFrame(
        [
            {
                "decision": str(r.get("decision", "")),
                "doc_count": _as_int(r.get("doc_count")),
                "top_level": str((r.get("ai_taxonomy") or {}).get("top_level", "unknown")),
                "sub_level": str((r.get("ai_taxonomy") or {}).get("sub_level", "unknown")),
                "label": str((r.get("ai_taxonomy") or {}).get("canonical_label", "unknown")),
                "mapping_source": str((r.get("validation") or {}).get("mapping_source", "unknown")),
                "status": str((r.get("ai_taxonomy") or {}).get("status", "unknown")),
            }
            for r in rows
        ]
    )

    ms = tax_df.groupby("mapping_source")["doc_count"].sum().reset_index().sort_values("doc_count", ascending=False)
    fig = plt.figure(figsize=(8, 5))
    ax = fig.add_subplot(111)
    ax.bar(ms["mapping_source"], ms["doc_count"], color="#59a14f")
    ax.set_title("Step 4: Mapping Source Contribution")
    ax.set_xlabel("Mapping source")
    ax.set_ylabel("Documents")
    out = output_dir / f"08_mapping_source_docs_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "4", "title": "Mapping Source Contribution", "file": str(out)})

    tl_docs = tax_df.groupby("top_level")["doc_count"].sum().reset_index().sort_values("doc_count", ascending=False)
    fig = plt.figure(figsize=(11, 6))
    ax = fig.add_subplot(111)
    ax.barh(tl_docs["top_level"].tolist()[::-1], tl_docs["doc_count"].tolist()[::-1], color="#edc948")
    ax.set_title("Step 4: Top-Level Taxonomy Load (Docs)")
    ax.set_xlabel("Documents")
    out = output_dir / f"09_top_level_docs_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "4", "title": "Top-Level Taxonomy Load", "file": str(out)})

    decision_top = pd.pivot_table(
        tax_df,
        index="decision",
        columns="top_level",
        values="doc_count",
        aggfunc="sum",
        fill_value=0,
    )
    fig = plt.figure(figsize=(12, 5))
    ax = fig.add_subplot(111)
    sns.heatmap(decision_top, cmap="YlGnBu", annot=True, fmt=".0f", cbar=True, ax=ax)
    ax.set_title("Step 4: Decision -> Top-Level Flow (Doc Heatmap)")
    out = output_dir / f"10_decision_top_level_heatmap_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "4", "title": "Decision to Top-Level Heatmap", "file": str(out)})

    # -----------------------------------
    # Step 5: directional tree (counts)
    # -----------------------------------
    top_counts = []
    for top, node in (tree.get("tree") or {}).items():
        top_counts.append((top, _as_int(node.get("category_count")), _as_int(node.get("doc_count"))))
    top_count_df = pd.DataFrame(top_counts, columns=["top_level", "category_count", "doc_count"]).sort_values(
        "category_count", ascending=False
    )
    fig = plt.figure(figsize=(11, 6))
    ax = fig.add_subplot(111)
    ax.barh(top_count_df["top_level"].tolist()[::-1], top_count_df["category_count"].tolist()[::-1], color="#b07aa1")
    ax.set_title("Step 5: Directional Tree Coverage (Category Count)")
    ax.set_xlabel("Categories")
    out = output_dir / f"11_tree_top_level_category_counts_{stamp}.png"
    _save(fig, out, args.dpi)
    figures.append({"step": "5", "title": "Directional Tree Coverage", "file": str(out)})

    # ----------------------------
    # Summary + report generation
    # ----------------------------
    metrics = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "umbrella_json": str(umbrella_path),
            "depth_json": str(depth_path),
            "shortlist_json": str(shortlist_path),
            "taxonomy_json": str(taxonomy_path),
            "tree_json": str(tree_path),
        },
        "core_counts": {
            "umbrella_clusters": _as_int(dyn.get("parent_cluster_count")),
            "depth_total_groups": _as_int(depth.get("summary", {}).get("total_groups")),
            "depth_url_only_parent": _as_int(depth.get("summary", {}).get("url_only_parent")),
            "depth_url_only_categorize": _as_int(depth.get("summary", {}).get("url_only_categorize")),
            "depth_needs_algorithm": _as_int(depth.get("summary", {}).get("needs_algorithm")),
            "taxonomy_selected_count": _as_int(taxonomy.get("summary", {}).get("selected_count")),
            "taxonomy_mapped_count": _as_int(taxonomy.get("summary", {}).get("mapped_count")),
            "taxonomy_unresolved_count": _as_int(taxonomy.get("summary", {}).get("unresolved_count")),
            "tree_top_level_count": _as_int(tree.get("summary", {}).get("top_level_count")),
        },
        "figures": figures,
    }

    metrics_json = output_dir / f"visualization_metrics_{stamp}.json"
    metrics_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    # literature map for presentation framing
    literature_lines = [
        "## Literature Mapping",
        "- **Entropy diagnostics**: Shannon, C. E. (1948), *A Mathematical Theory of Communication*.",
        "- **Hierarchical clustering**: Ward, J. H. (1963), minimum-variance agglomerative clustering.",
        "- **Cluster quality**: Rousseeuw, P. J. (1987), silhouette width for cluster validation.",
        "- **Scalable centroid clustering**: Sculley, D. (2010), Web-scale K-Means / MiniBatchKMeans.",
        "- **Manifold learning stage**: PaCMAP (Pairwise Controlled Manifold Approximation Projection) for structure-preserving projection.",
        "- **URL-text similarity foundation**: character n-gram TF-IDF + cosine neighborhood graph + connected components.",
        "- **Decision gate design**: rule-based interpretable thresholds for traceable taxonomy assignment.",
    ]

    report_lines = [
        "# Categorization Visualization Pack",
        "",
        "## Pipeline Snapshot",
        f"- umbrella clusters: `{metrics['core_counts']['umbrella_clusters']}`",
        f"- total URL groups: `{metrics['core_counts']['depth_total_groups']}`",
        f"- `needs_algorithm` groups: `{metrics['core_counts']['depth_needs_algorithm']}`",
        f"- taxonomy mapped: `{metrics['core_counts']['taxonomy_mapped_count']}` / `{metrics['core_counts']['taxonomy_selected_count']}`",
        f"- taxonomy unresolved: `{metrics['core_counts']['taxonomy_unresolved_count']}`",
        f"- top-level categories in directional tree: `{metrics['core_counts']['tree_top_level_count']}`",
        "",
        "## Figure Index",
    ]
    for i, f in enumerate(figures, start=1):
        report_lines.append(f"{i}. Step {f['step']} - {f['title']}: `{Path(f['file']).name}`")
    report_lines.extend(["", *literature_lines, ""])

    report_md = output_dir / f"visualization_report_{stamp}.md"
    report_md.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"[viz] output_dir: {output_dir}")
    print(f"[viz] metrics_json: {metrics_json}")
    print(f"[viz] report_md: {report_md}")
    print(f"[viz] figures: {len(figures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
