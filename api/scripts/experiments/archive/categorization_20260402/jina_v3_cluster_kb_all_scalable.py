"""
Scalable hierarchical clustering for full knowledge_base embeddings.

Method:
1) Fit MiniBatchKMeans on all embeddings for leaf clusters (default k=64).
2) Build Ward hierarchy on the leaf centroids (cheap: only 64 points).
3) Project parent levels (e.g. 24 and 8) back to all documents via leaf->parent mapping.

This is an approximation of full Ward HAC, designed for large datasets.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
from dotenv import load_dotenv
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score
from sqlalchemy import text


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))

load_dotenv(API_ROOT / ".env")

from database.session import SessionLocal  # noqa: E402


RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


@dataclass
class Row:
    kb_id: str
    url: str
    title: str
    type: str | None
    language: str | None
    category: str | None
    parent_category: str | None
    vector: np.ndarray


def _vec_from_text(value: str) -> np.ndarray:
    arr = np.fromstring(value.strip("[]"), sep=",", dtype=np.float32)
    if arr.size == 0:
        raise ValueError("Empty vector parsed from DB.")
    return arr


def _parse_levels(raw: str) -> list[int]:
    vals = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not vals:
        raise ValueError("--levels must contain at least one integer.")
    if any(v <= 1 for v in vals):
        raise ValueError("All cluster levels must be > 1.")
    return sorted(vals)


def _url_bucket(url: str, mode: str) -> str:
    parsed = urlparse(url or "")
    host = (parsed.netloc or "unknown").lower()
    path = (parsed.path or "").strip("/")
    if mode == "host":
        return host
    if mode == "host_path1":
        first = path.split("/")[0].lower() if path else "root"
        return f"{host}/{first}"
    if mode == "full":
        return (url or "").strip().lower() or "unknown"
    raise ValueError(f"Unsupported url bucket mode: {mode}")


def _maybe_reduce_centroids(
    centroids: np.ndarray,
    *,
    seed: int,
    pacmap_dim: int,
) -> np.ndarray:
    if pacmap_dim <= 0:
        return centroids
    if len(centroids) <= 3:
        return centroids
    try:
        import pacmap
    except ImportError as exc:
        raise RuntimeError(
            "PaCMAP is not installed but --centroid-pacmap-dim > 0 was requested."
        ) from exc

    reduced_dim = min(pacmap_dim, centroids.shape[1], len(centroids) - 1)
    if reduced_dim < 2:
        return centroids
    reducer = pacmap.PaCMAP(
        n_components=reduced_dim,
        n_neighbors=min(15, len(centroids) - 1),
        MN_ratio=0.5,
        FP_ratio=2.0,
        random_state=seed,
    )
    return reducer.fit_transform(centroids, init="pca")


def _fetch_rows(
    db,
    *,
    model_id: int,
    sample_size: int | None,
    languages: list[str],
    types: list[str],
) -> list[Row]:
    where_parts = ["kbe.model_id = :model_id"]
    params: dict[str, Any] = {"model_id": model_id}

    if languages:
        where_parts.append("kb.language = ANY(:languages)")
        params["languages"] = languages
    if types:
        where_parts.append("kb.type = ANY(:types)")
        params["types"] = types

    limit_sql = ""
    if sample_size is not None and sample_size > 0:
        limit_sql = "LIMIT :sample_size"
        params["sample_size"] = sample_size

    sql = f"""
        SELECT
            kbe.kb_id::text AS kb_id,
            kbe.embedding::text AS embedding_text,
            kb.url,
            COALESCE(kb.title, '') AS title,
            kb.type,
            kb.language,
            kb.category,
            kb.parent_category
        FROM knowledge_base_embeddings kbe
        JOIN knowledge_base kb ON kb.id = kbe.kb_id
        WHERE {" AND ".join(where_parts)}
        ORDER BY kbe.kb_id
        {limit_sql}
    """

    raw = list(db.execute(text(sql), params).all())
    rows: list[Row] = []
    for r in raw:
        rows.append(
            Row(
                kb_id=r[0],
                vector=_vec_from_text(r[1]),
                url=r[2] or "",
                title=r[3] or "",
                type=r[4],
                language=r[5],
                category=r[6],
                parent_category=r[7],
            )
        )
    return rows


def _save_outputs(
    *,
    run_name: str,
    rows: list[Row],
    level_labels: dict[int, np.ndarray],
    url_groups: list[str] | None,
    summary: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = output_dir / f"{run_name}_{stamp}"

    assignments_path = base.with_suffix(".assignments.jsonl")
    with assignments_path.open("w", encoding="utf-8") as f:
        for i, row in enumerate(rows):
            item = {
                "id": row.kb_id,
                "url": row.url,
                "title": row.title[:220],
                "type": row.type,
                "language": row.language,
                "category": row.category,
                "parent_category": row.parent_category,
            }
            if url_groups is not None:
                item["url_group"] = url_groups[i]
            for level, labels in level_labels.items():
                item[f"cluster_k{level}"] = int(labels[i])
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    summary_path = base.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return assignments_path, summary_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scalable full-data hierarchical clustering for KB embeddings.")
    p.add_argument("--model-id", type=int, required=True)
    p.add_argument("--sample-size", type=int, default=0, help="0 means all rows for model.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--levels", type=str, default="8,24,64")
    p.add_argument("--leaf-k", type=int, default=64, help="Leaf clusters for MiniBatchKMeans.")
    p.add_argument(
        "--centroid-pacmap-dim",
        type=int,
        default=0,
        help="Optional PaCMAP dim on centroids before Ward (0 disables).",
    )
    p.add_argument(
        "--doc-silhouette-sample-size",
        type=int,
        default=5000,
        help="Document-level silhouette sample size (0 disables).",
    )
    p.add_argument("--language", type=str, default="")
    p.add_argument("--type", dest="types", type=str, default="")
    p.add_argument(
        "--strict-url-first",
        action="store_true",
        help="First partition documents by URL bucket, then cluster inside each bucket.",
    )
    p.add_argument(
        "--url-bucket-mode",
        type=str,
        default="host_path1",
        choices=["host", "host_path1", "full"],
        help="How URL buckets are derived when --strict-url-first is enabled.",
    )
    p.add_argument("--run-name", type=str, default="jina_v3_hierarchical_all_scalable")
    p.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    return p.parse_args()


def main() -> int:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required (api/.env).")

    args = parse_args()
    levels = _parse_levels(args.levels)
    if args.leaf_k <= 1:
        raise ValueError("--leaf-k must be > 1")
    if args.centroid_pacmap_dim < 0:
        raise ValueError("--centroid-pacmap-dim must be >= 0")
    if args.doc_silhouette_sample_size < 0:
        raise ValueError("--doc-silhouette-sample-size must be >= 0")
    if max(levels) > args.leaf_k:
        print(
            "[cluster-all] warning: some requested levels are > leaf-k; "
            "effective clusters will be capped per URL group."
        )

    languages = [x.strip() for x in args.language.split(",") if x.strip()]
    types = [x.strip() for x in args.types.split(",") if x.strip()]

    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        rows = _fetch_rows(
            db,
            model_id=args.model_id,
            sample_size=args.sample_size if args.sample_size > 0 else None,
            languages=languages,
            types=types,
        )
        if len(rows) < 3:
            raise RuntimeError("Not enough rows for clustering.")
        print(f"[cluster-all] fetched rows={len(rows)}")

        vectors = np.vstack([r.vector for r in rows]).astype(np.float32)
        print(f"[cluster-all] vector matrix={vectors.shape}")

        # Stage 1 (optional): strict URL partition.
        if args.strict_url_first:
            group_map: dict[str, list[int]] = {}
            for i, row in enumerate(rows):
                bucket = _url_bucket(row.url, args.url_bucket_mode)
                group_map.setdefault(bucket, []).append(i)
            url_groups = [""] * len(rows)
            for bucket, idxs in group_map.items():
                for i in idxs:
                    url_groups[i] = bucket
            print(
                f"[cluster-all] strict URL-first enabled: groups={len(group_map)} "
                f"mode={args.url_bucket_mode}"
            )
        else:
            group_map = {"__all__": list(range(len(rows)))}
            url_groups = None

        level_labels: dict[int, np.ndarray] = {
            level: np.zeros(len(rows), dtype=np.int32) for level in levels
        }
        level_offsets: dict[int, int] = {level: 0 for level in levels}
        group_stats: list[dict[str, Any]] = []
        sil_sum: dict[int, float] = {level: 0.0 for level in levels}
        sil_weight: dict[int, int] = {level: 0 for level in levels}

        for group_idx, (group_name, global_indices) in enumerate(sorted(group_map.items()), start=1):
            idx = np.asarray(global_indices, dtype=np.int32)
            group_vectors = vectors[idx]
            group_n = len(idx)
            local_leaf_k = min(args.leaf_k, group_n)
            actual_by_level: dict[int, int] = {}
            if local_leaf_k <= 1:
                for level in levels:
                    level_labels[level][idx] = level_offsets[level] + 1
                    level_offsets[level] += 1
                    actual_by_level[level] = 1
                group_stats.append(
                    {
                        "group": group_name,
                        "rows": group_n,
                        "local_leaf_k": local_leaf_k,
                        "actual_clusters_by_level": {f"k{l}": actual_by_level[l] for l in levels},
                    }
                )
                print(f"[cluster-all] group {group_idx}: {group_name} n={group_n} trivial")
                continue

            kmeans = MiniBatchKMeans(
                n_clusters=local_leaf_k,
                random_state=args.seed,
                batch_size=4096,
                n_init="auto",
                max_iter=300,
                reassignment_ratio=0.01,
            )
            leaf0 = kmeans.fit_predict(group_vectors)
            centroids = kmeans.cluster_centers_.astype(np.float32)
            centroid_features = _maybe_reduce_centroids(
                centroids,
                seed=args.seed,
                pacmap_dim=args.centroid_pacmap_dim,
            )

            centroid_linkage = None
            if local_leaf_k > 2:
                centroid_linkage = linkage(centroid_features, method="ward", metric="euclidean")

            for level in levels:
                local_target = min(level, local_leaf_k)
                if local_target <= 1:
                    local_labels = np.ones(group_n, dtype=np.int32)
                    centroid_labels = np.ones(local_leaf_k, dtype=np.int32)
                elif local_target == local_leaf_k:
                    local_labels = leaf0 + 1
                    centroid_labels = np.arange(local_leaf_k, dtype=np.int32) + 1
                else:
                    assert centroid_linkage is not None
                    centroid_groups = fcluster(centroid_linkage, t=local_target, criterion="maxclust")
                    centroid_labels = np.asarray(centroid_groups, dtype=np.int32)
                    local_labels = np.asarray([centroid_labels[j] for j in leaf0], dtype=np.int32)

                offset = level_offsets[level]
                level_labels[level][idx] = local_labels + offset
                level_offsets[level] = offset + int(local_labels.max())
                actual_unique = int(np.unique(local_labels).size)
                actual_by_level[level] = actual_unique

                # Cheap quality signal on centroids.
                unique_cent = np.unique(centroid_labels).size
                if 1 < unique_cent < len(centroid_labels):
                    sil = float(silhouette_score(centroid_features, centroid_labels))
                    sil_sum[level] += sil * len(centroid_labels)
                    sil_weight[level] += len(centroid_labels)

            group_stats.append(
                {
                    "group": group_name,
                    "rows": group_n,
                    "local_leaf_k": local_leaf_k,
                    "actual_clusters_by_level": {f"k{l}": actual_by_level[l] for l in levels},
                }
            )
            if group_idx % 10 == 0 or group_idx == 1:
                print(
                    f"[cluster-all] group {group_idx}/{len(group_map)} "
                    f"n={group_n} local_leaf_k={local_leaf_k} "
                    f"actual={{{', '.join([f'k{l}:{actual_by_level[l]}' for l in levels])}}}"
                )

        centroid_silhouette_by_level = {
            str(level): (sil_sum[level] / sil_weight[level] if sil_weight[level] > 0 else None)
            for level in levels
        }
        if len(group_stats) > 500:
            group_stats_summary = sorted(group_stats, key=lambda g: g["rows"], reverse=True)[:500]
        else:
            group_stats_summary = group_stats

        doc_silhouette_by_level: dict[str, float | None] = {}
        for level in levels:
            print(f"[cluster-all] level k={level} unique={len(np.unique(level_labels[level]))}")
            print(
                f"[cluster-all] level k={level} centroid_silhouette="
                f"{centroid_silhouette_by_level[str(level)]}"
            )
            labels = level_labels[level]
            unique = np.unique(labels).size
            if args.doc_silhouette_sample_size == 0 or unique <= 1 or unique >= len(labels):
                doc_silhouette_by_level[str(level)] = None
                continue
            sample_size = min(args.doc_silhouette_sample_size, len(labels))
            try:
                doc_sil = float(
                    silhouette_score(
                        vectors,
                        labels,
                        sample_size=sample_size,
                        random_state=args.seed,
                    )
                )
                doc_silhouette_by_level[str(level)] = doc_sil
                print(
                    f"[cluster-all] level k={level} document_silhouette="
                    f"{doc_sil} (sample_size={sample_size})"
                )
            except Exception as exc:
                print(
                    f"[cluster-all] warning: document silhouette failed for k={level}: {exc}"
                )
                doc_silhouette_by_level[str(level)] = None

        summary = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_id": args.model_id,
            "sample_size": len(rows),
            "seed": args.seed,
            "levels": levels,
            "method": "minibatch_kmeans_leaf_plus_centroid_hac",
            "leaf_k": args.leaf_k,
            "centroid_pacmap_dim": args.centroid_pacmap_dim,
            "centroid_silhouette_by_level": centroid_silhouette_by_level,
            "doc_silhouette_sample_size": args.doc_silhouette_sample_size,
            "document_silhouette_by_level": doc_silhouette_by_level,
            "strict_url_first": args.strict_url_first,
            "url_bucket_mode": args.url_bucket_mode if args.strict_url_first else None,
            "url_group_count": len(group_map),
            "url_group_actual_clusters_by_level": group_stats_summary,
            "url_group_actual_clusters_truncated": len(group_stats_summary) != len(group_stats),
            "strict_url_note": (
                "When strict_url_first=true, clusters are isolated per URL bucket. "
                "Cross-bucket semantic grouping must be done downstream."
            ),
            "language_filter": languages,
            "type_filter": types,
            "total_seconds": round(time.perf_counter() - t0, 3),
        }

        assignments_path, summary_path = _save_outputs(
            run_name=args.run_name,
            rows=rows,
            level_labels=level_labels,
            url_groups=url_groups,
            summary=summary,
            output_dir=args.output_dir,
        )
        print(f"[cluster-all] assignments: {assignments_path}")
        print(f"[cluster-all] summary: {summary_path}")
        print(f"[cluster-all] done in {summary['total_seconds']}s")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
