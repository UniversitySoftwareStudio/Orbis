#!/usr/bin/env python3
"""
Group documents by pure URL-character similarity (no LLM, no content semantics).

Purpose:
- Build URL groups using only URL string similarity.
- Keep full membership visibility for each group (all URLs + doc IDs).
- Flag low-similarity members as candidates for downstream algorithmic reprocessing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
from dotenv import load_dotenv
from scipy.sparse import eye
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
from sqlalchemy import func, select


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))

load_dotenv(API_ROOT / ".env")

from database.models import KnowledgeBase  # noqa: E402
from database.session import SessionLocal  # noqa: E402


DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


def _normalize_url(raw: str) -> str:
    parsed = urlparse((raw or "").strip())
    host = (parsed.netloc or "unknown").lower()
    path = (parsed.path or "/").strip().lower()
    if not path.startswith("/"):
        path = "/" + path
    path = path.rstrip("/") or "/"
    return f"{host}{path}"


def _fetch_docs(db, sample_size: int) -> list[tuple[str, str]]:
    stmt = (
        select(KnowledgeBase.id, func.coalesce(KnowledgeBase.url, ""))
        .where(KnowledgeBase.url.is_not(None))
        .order_by(KnowledgeBase.id)
    )
    if sample_size > 0:
        stmt = stmt.limit(sample_size)
    rows = list(db.execute(stmt).all())
    return [(str(r[0]), r[1] or "") for r in rows]


def _threshold_range(start: float, end: float, step: float) -> list[float]:
    values: list[float] = []
    cur = start
    while cur <= end + 1e-12:
        values.append(round(cur, 6))
        cur += step
    return values


def _build_labels(x, similarity_threshold: float) -> tuple[int, np.ndarray]:
    radius = 1.0 - similarity_threshold
    nn = NearestNeighbors(radius=radius, metric="cosine", algorithm="brute", n_jobs=-1)
    nn.fit(x)
    graph = nn.radius_neighbors_graph(x, mode="connectivity")
    graph = graph + eye(graph.shape[0], format="csr")
    n_groups, labels = connected_components(csgraph=graph, directed=False, return_labels=True)
    return int(n_groups), labels.astype(int) + 1


def _score_threshold(
    labels: np.ndarray,
    doc_counts_per_url: list[int],
    *,
    overmerge_url_count: int,
) -> dict[str, Any]:
    group_url_counts: dict[int, int] = defaultdict(int)
    group_doc_counts: dict[int, int] = defaultdict(int)
    for idx, group_id in enumerate(labels):
        gid = int(group_id)
        group_url_counts[gid] += 1
        group_doc_counts[gid] += doc_counts_per_url[idx]

    total_docs = sum(doc_counts_per_url)
    total_groups = len(group_url_counts)
    singleton_groups = sum(1 for c in group_url_counts.values() if c == 1)
    multi_groups = total_groups - singleton_groups
    singleton_docs = sum(group_doc_counts[g] for g, c in group_url_counts.items() if c == 1)
    multi_docs = total_docs - singleton_docs

    overmerge_docs = sum(
        group_doc_counts[g]
        for g, c in group_url_counts.items()
        if c >= overmerge_url_count
    )
    largest_group_docs = max(group_doc_counts.values()) if group_doc_counts else 0
    largest_group_urls = max(group_url_counts.values()) if group_url_counts else 0

    multi_docs_ratio = multi_docs / max(1, total_docs)
    multi_groups_ratio = multi_groups / max(1, total_groups)
    overmerge_docs_ratio = overmerge_docs / max(1, total_docs)
    largest_group_docs_ratio = largest_group_docs / max(1, total_docs)

    # Sweet-spot objective:
    # - reward parent coverage (docs in multi-URL groups)
    # - reward having non-trivial number of parent groups
    # - penalize over-merged giant groups
    score = (
        (0.70 * multi_docs_ratio)
        + (0.20 * multi_groups_ratio)
        - (0.45 * overmerge_docs_ratio)
        - (0.25 * largest_group_docs_ratio)
    )

    return {
        "url_group_count": total_groups,
        "singleton_group_count": singleton_groups,
        "multi_group_count": multi_groups,
        "multi_docs_ratio": round(multi_docs_ratio, 6),
        "multi_groups_ratio": round(multi_groups_ratio, 6),
        "overmerge_docs_ratio": round(overmerge_docs_ratio, 6),
        "largest_group_docs_ratio": round(largest_group_docs_ratio, 6),
        "largest_group_urls": int(largest_group_urls),
        "score": round(float(score), 6),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pure URL-character grouping with candidate flags")
    parser.add_argument("--sample-size", type=int, default=0, help="0 means all docs")
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.78,
        help="Minimum cosine similarity between URL-char vectors to connect URLs into the same group.",
    )
    parser.add_argument(
        "--candidate-similarity-threshold",
        type=float,
        default=0.60,
        help="Within-group URLs below this centroid similarity are flagged for downstream processing.",
    )
    parser.add_argument("--ngram-min", type=int, default=3)
    parser.add_argument("--ngram-max", type=int, default=5)
    parser.add_argument("--min-df", type=int, default=1)
    parser.add_argument(
        "--auto-sweet-spot",
        action="store_true",
        help="Sweep thresholds and auto-select best parent threshold before final grouping.",
    )
    parser.add_argument("--threshold-start", type=float, default=0.64)
    parser.add_argument("--threshold-end", type=float, default=0.90)
    parser.add_argument("--threshold-step", type=float, default=0.02)
    parser.add_argument(
        "--overmerge-url-count",
        type=int,
        default=120,
        help="Group URL-count at/above this is treated as potentially over-merged during sweet-spot scoring.",
    )
    parser.add_argument("--run-name", type=str, default="url_char_grouping")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_size < 0:
        raise ValueError("--sample-size must be >= 0")
    if not (0.0 < args.similarity_threshold <= 1.0):
        raise ValueError("--similarity-threshold must be in (0, 1]")
    if not (0.0 <= args.candidate_similarity_threshold <= 1.0):
        raise ValueError("--candidate-similarity-threshold must be in [0, 1]")
    if args.ngram_min <= 0 or args.ngram_max <= 0:
        raise ValueError("--ngram-min and --ngram-max must be > 0")
    if args.ngram_min > args.ngram_max:
        raise ValueError("--ngram-min must be <= --ngram-max")
    if args.min_df <= 0:
        raise ValueError("--min-df must be > 0")
    if args.overmerge_url_count <= 1:
        raise ValueError("--overmerge-url-count must be > 1")
    if not (0.0 < args.threshold_start <= 1.0):
        raise ValueError("--threshold-start must be in (0, 1]")
    if not (0.0 < args.threshold_end <= 1.0):
        raise ValueError("--threshold-end must be in (0, 1]")
    if args.threshold_start > args.threshold_end:
        raise ValueError("--threshold-start must be <= --threshold-end")
    if args.threshold_step <= 0:
        raise ValueError("--threshold-step must be > 0")

    t0 = time.perf_counter()
    db = SessionLocal()
    try:
        print("[url-char] fetching docs...")
        rows = _fetch_docs(db, sample_size=args.sample_size)
        if not rows:
            raise RuntimeError("No docs found.")
        print(f"[url-char] docs fetched: {len(rows)}")

        url_to_docs: dict[str, list[str]] = defaultdict(list)
        for doc_id, raw_url in rows:
            url_key = _normalize_url(raw_url)
            url_to_docs[url_key].append(doc_id)

        unique_urls = sorted(url_to_docs.keys())
        print(f"[url-char] unique normalized urls: {len(unique_urls)}")

        print("[url-char] vectorizing urls (char n-grams)...")
        vec = TfidfVectorizer(
            analyzer="char",
            ngram_range=(args.ngram_min, args.ngram_max),
            lowercase=False,
            min_df=args.min_df,
        )
        x = vec.fit_transform(unique_urls)
        print(f"[url-char] tfidf shape: {x.shape}")

        doc_counts_per_url = [len(url_to_docs[u]) for u in unique_urls]
        sweep_results: list[dict[str, Any]] = []
        selected_threshold = args.similarity_threshold

        if args.auto_sweet_spot:
            thresholds = _threshold_range(args.threshold_start, args.threshold_end, args.threshold_step)
            print(f"[url-char] sweeping thresholds: {thresholds[0]:.2f}..{thresholds[-1]:.2f} step={args.threshold_step}")
            best_score = float("-inf")
            for thr in thresholds:
                n_thr_groups, thr_labels = _build_labels(x, similarity_threshold=thr)
                metrics = _score_threshold(
                    thr_labels,
                    doc_counts_per_url,
                    overmerge_url_count=args.overmerge_url_count,
                )
                metrics["threshold"] = round(thr, 6)
                metrics["url_group_count"] = n_thr_groups
                sweep_results.append(metrics)
                if metrics["score"] > best_score:
                    best_score = metrics["score"]
                    selected_threshold = thr
            print(f"[url-char] sweet spot threshold selected: {selected_threshold:.3f}")

        radius = 1.0 - selected_threshold
        print(
            f"[url-char] building final URL similarity graph "
            f"(cosine >= {selected_threshold:.3f}, radius <= {radius:.3f})..."
        )
        n_groups, labels = _build_labels(x, similarity_threshold=selected_threshold)
        print(f"[url-char] url groups discovered: {n_groups}")

        group_to_url_idxs: dict[int, list[int]] = defaultdict(list)
        for idx, group_id in enumerate(labels):
            group_to_url_idxs[int(group_id)].append(idx)

        doc_assignments: dict[str, dict[str, Any]] = {}
        group_details: list[dict[str, Any]] = []
        candidate_doc_ids: list[str] = []

        for group_id, idxs in group_to_url_idxs.items():
            sub = x[idxs]
            if len(idxs) == 1:
                sims = [1.0]
            else:
                centroid = np.asarray(sub.mean(axis=0)).reshape(1, -1)
                sims_arr = cosine_similarity(sub, centroid).reshape(-1)
                sims = [float(v) for v in sims_arr]

            members = []
            doc_count = 0
            candidate_doc_count = 0
            for local_i, url_idx in enumerate(idxs):
                url_key = unique_urls[url_idx]
                sim_val = sims[local_i]
                docs = url_to_docs[url_key]
                is_candidate = sim_val < args.candidate_similarity_threshold
                if is_candidate:
                    candidate_doc_ids.extend(docs)
                    candidate_doc_count += len(docs)

                members.append(
                    {
                        "url": url_key,
                        "doc_count": len(docs),
                        "doc_ids": docs,
                        "similarity_to_group_centroid": round(sim_val, 6),
                        "candidate_for_algorithm": is_candidate,
                    }
                )
                doc_count += len(docs)
                for doc_id in docs:
                    doc_assignments[doc_id] = {
                        "group_id": group_id,
                        "url": url_key,
                        "candidate_for_algorithm": is_candidate,
                    }

            members.sort(key=lambda x: x["doc_count"], reverse=True)
            group_details.append(
                {
                    "group_id": group_id,
                    "url_count": len(members),
                    "doc_count": doc_count,
                    "candidate_url_count": sum(1 for m in members if m["candidate_for_algorithm"]),
                    "candidate_doc_count": candidate_doc_count,
                    "members": members,
                }
            )

        group_details.sort(key=lambda x: x["doc_count"], reverse=True)
        candidate_doc_ids = sorted(set(candidate_doc_ids))

        source_domain_counts = Counter(url.split("/")[0] for url in unique_urls)
        output = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "config": {
                "sample_size": args.sample_size,
                "similarity_threshold": args.similarity_threshold,
                "selected_similarity_threshold": selected_threshold,
                "candidate_similarity_threshold": args.candidate_similarity_threshold,
                "ngram_min": args.ngram_min,
                "ngram_max": args.ngram_max,
                "min_df": args.min_df,
                "auto_sweet_spot": args.auto_sweet_spot,
                "threshold_start": args.threshold_start,
                "threshold_end": args.threshold_end,
                "threshold_step": args.threshold_step,
                "overmerge_url_count": args.overmerge_url_count,
            },
            "summary": {
                "total_docs": len(rows),
                "total_unique_urls": len(unique_urls),
                "url_group_count": int(n_groups),
                "candidate_doc_count": len(candidate_doc_ids),
                "candidate_doc_ratio": round(len(candidate_doc_ids) / max(1, len(rows)), 6),
                "top_domains": source_domain_counts.most_common(20),
            },
            "threshold_sweep": sorted(sweep_results, key=lambda r: r["threshold"]),
            "groups": group_details,
            "candidate_doc_ids": candidate_doc_ids,
            "doc_assignments": doc_assignments,
            "total_seconds": round(time.perf_counter() - t0, 3),
        }

        args.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = args.output_dir / f"{args.run_name}_{stamp}.json"
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[url-char] output: {output_path}")
        print(f"[url-char] done in {output['total_seconds']}s")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
