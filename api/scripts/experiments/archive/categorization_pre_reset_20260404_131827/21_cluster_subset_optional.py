"""
Cluster knowledge_base embeddings (Jina v3) into a hierarchy.

Pipeline:
1) Load embeddings for a model from `knowledge_base_embeddings`.
2) Reduce dimensions with PaCMAP (hierarchy-friendly geometry).
3) Build Ward hierarchical clustering (full dendrogram).
4) Cut tree at multiple depths (coarse/mid/fine).
5) Save assignments + run summary to results.

Example:
    python3 api/scripts/experiments/categorization/21_cluster_subset_optional.py \
      --sample-size 4000 \
      --levels 8,24,64 \
      --pacmap-dim 30 \
      --seed 42
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

import numpy as np
import pacmap
from dotenv import load_dotenv
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.metrics import silhouette_score
from sqlalchemy import select, text


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))

load_dotenv(API_ROOT / ".env")

from database.models import EmbeddingModel  # noqa: E402
from database.session import SessionLocal  # noqa: E402


RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


@dataclass
class Row:
    kb_id: str
    title: str
    type: str | None
    language: str | None
    category: str | None
    parent_category: str | None
    vector: np.ndarray


def _parse_levels(raw: str) -> list[int]:
    vals = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not vals:
        raise ValueError("--levels must contain at least one integer.")
    if any(v <= 1 for v in vals):
        raise ValueError("All cluster levels must be > 1.")
    return vals


def _vec_from_text(value: str) -> np.ndarray:
    # value is like: "[0.1,0.2,...]"
    arr = np.fromstring(value.strip("[]"), sep=",", dtype=np.float32)
    if arr.size == 0:
        raise ValueError("Empty vector parsed from DB.")
    return arr


def _normalize_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def _clean_rows(
    rows: list[Row],
    *,
    dedupe_embedding: bool,
    max_per_title: int,
) -> tuple[list[Row], dict[str, Any]]:
    out: list[Row] = []
    seen_embeddings: set[bytes] = set()
    seen_title_counts: dict[str, int] = {}
    dropped_dup_embedding = 0
    dropped_title_cap = 0

    for row in rows:
        if dedupe_embedding:
            emb_key = row.vector.tobytes()
            if emb_key in seen_embeddings:
                dropped_dup_embedding += 1
                continue
            seen_embeddings.add(emb_key)

        if max_per_title > 0:
            key = _normalize_title(row.title)
            seen = seen_title_counts.get(key, 0)
            if seen >= max_per_title:
                dropped_title_cap += 1
                continue
            seen_title_counts[key] = seen + 1

        out.append(row)

    stats = {
        "input_rows": len(rows),
        "output_rows": len(out),
        "dropped_duplicate_embedding": dropped_dup_embedding,
        "dropped_title_cap": dropped_title_cap,
        "dedupe_embedding": dedupe_embedding,
        "max_per_title": max_per_title,
    }
    return out, stats


def _active_or_named_model(db, model_name: str | None, model_id: int | None) -> EmbeddingModel:
    if model_id is not None:
        row = db.scalars(select(EmbeddingModel).where(EmbeddingModel.id == model_id).limit(1)).first()
        if row is None:
            raise RuntimeError(f"Model id={model_id} not found in embedding_models.")
        return row

    if model_name:
        row = db.scalars(
            select(EmbeddingModel).where(EmbeddingModel.name == model_name).order_by(EmbeddingModel.id.desc()).limit(1)
        ).first()
        if row is None:
            raise RuntimeError(f"Model name '{model_name}' not found in embedding_models.")
        return row

    row = db.scalars(
        select(EmbeddingModel).where(EmbeddingModel.is_active.is_(True)).limit(1)
    ).first()
    if row is None:
        raise RuntimeError("No active embedding model found.")
    return row


def _fetch_rows(
    db,
    *,
    model_id: int,
    sample_size: int,
    seed: int,
    languages: list[str],
    types: list[str],
) -> list[Row]:
    # Deterministic sampling order
    normalized_seed = ((seed % 2_000_001) / 1_000_000.0) - 1.0
    db.execute(text("SELECT setseed(:seed)"), {"seed": normalized_seed})

    where_parts = ["kbe.model_id = :model_id"]
    params: dict[str, Any] = {"model_id": model_id, "sample_size": sample_size}

    if languages:
        where_parts.append("kb.language = ANY(:languages)")
        params["languages"] = languages
    if types:
        where_parts.append("kb.type = ANY(:types)")
        params["types"] = types

    sql = f"""
        SELECT
            kbe.kb_id::text AS kb_id,
            kbe.embedding::text AS embedding_text,
            COALESCE(kb.title, '') AS title,
            kb.type,
            kb.language,
            kb.category,
            kb.parent_category
        FROM knowledge_base_embeddings kbe
        JOIN knowledge_base kb ON kb.id = kbe.kb_id
        WHERE {" AND ".join(where_parts)}
        ORDER BY random()
        LIMIT :sample_size
    """

    raw = list(db.execute(text(sql), params).all())
    rows: list[Row] = []
    for r in raw:
        rows.append(
            Row(
                kb_id=r[0],
                vector=_vec_from_text(r[1]),
                title=r[2] or "",
                type=r[3],
                language=r[4],
                category=r[5],
                parent_category=r[6],
            )
        )
    return rows


def _reduce_with_pacmap(vectors: np.ndarray, pacmap_dim: int, seed: int) -> np.ndarray:
    reducer = pacmap.PaCMAP(
        n_components=pacmap_dim,
        n_neighbors=15,
        MN_ratio=0.5,
        FP_ratio=2.0,
        random_state=seed,
    )
    return reducer.fit_transform(vectors, init="pca")


def _save_outputs(
    *,
    run_name: str,
    rows: list[Row],
    level_labels: dict[int, np.ndarray],
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
                "title": row.title[:220],
                "type": row.type,
                "language": row.language,
                "category": row.category,
                "parent_category": row.parent_category,
            }
            for level, labels in level_labels.items():
                item[f"cluster_k{level}"] = int(labels[i])
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    summary_path = base.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return assignments_path, summary_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hierarchical clustering for Jina KB embeddings.")
    p.add_argument("--sample-size", type=int, default=4000)
    p.add_argument(
        "--oversample-factor",
        type=float,
        default=1.0,
        help="Fetch factor before cleaning (e.g. 2.0 fetches 2x then cleans down).",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--levels", type=str, default="8,24,64")
    p.add_argument("--pacmap-dim", type=int, default=30)
    p.add_argument("--language", type=str, default="")
    p.add_argument("--type", dest="types", type=str, default="")
    p.add_argument(
        "--clean-dedupe-embedding",
        action="store_true",
        help="Drop rows with exact duplicate embedding vectors before clustering.",
    )
    p.add_argument(
        "--clean-max-per-title",
        type=int,
        default=0,
        help="Cap repeated normalized titles (0 disables title cap).",
    )
    p.add_argument("--model-id", type=int, default=None)
    p.add_argument("--model-name", type=str, default=None)
    p.add_argument("--run-name", type=str, default="jina_v3_hierarchical")
    p.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    return p.parse_args()


def main() -> int:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required (api/.env).")

    args = parse_args()
    if args.sample_size <= 2:
        raise ValueError("--sample-size must be > 2")
    if args.oversample_factor < 1.0:
        raise ValueError("--oversample-factor must be >= 1.0")
    if args.clean_max_per_title < 0:
        raise ValueError("--clean-max-per-title must be >= 0")
    levels = _parse_levels(args.levels)
    languages = [x.strip() for x in args.language.split(",") if x.strip()]
    types = [x.strip() for x in args.types.split(",") if x.strip()]

    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        model = _active_or_named_model(db, args.model_name, args.model_id)
        print(
            f"[cluster] model id={model.id} name={model.name} dim={model.dimension} active={model.is_active}"
        )

        fetch_size = int(round(args.sample_size * args.oversample_factor))
        fetch_size = max(args.sample_size, fetch_size)
        rows = _fetch_rows(
            db,
            model_id=model.id,
            sample_size=fetch_size,
            seed=args.seed,
            languages=languages,
            types=types,
        )
        if len(rows) < 3:
            raise RuntimeError("Not enough rows for clustering.")
        print(f"[cluster] fetched rows={len(rows)} (target={args.sample_size})")

        clean_stats: dict[str, Any] | None = None
        if args.clean_dedupe_embedding or args.clean_max_per_title > 0:
            rows, clean_stats = _clean_rows(
                rows,
                dedupe_embedding=args.clean_dedupe_embedding,
                max_per_title=args.clean_max_per_title,
            )
            print(
                "[cluster] cleaned rows "
                f"{clean_stats['input_rows']} -> {clean_stats['output_rows']} "
                f"(drop_dup_emb={clean_stats['dropped_duplicate_embedding']}, "
                f"drop_title_cap={clean_stats['dropped_title_cap']})"
            )

        if len(rows) < args.sample_size:
            print(
                "[cluster] warning: cleaned row count is below requested sample size: "
                f"{len(rows)} < {args.sample_size}"
            )
        rows = rows[: args.sample_size]
        if len(rows) < 3:
            raise RuntimeError("Not enough rows for clustering after cleaning.")

        vectors = np.vstack([r.vector for r in rows]).astype(np.float32)
        print(f"[cluster] vector matrix={vectors.shape}")

        reduced = _reduce_with_pacmap(vectors, pacmap_dim=args.pacmap_dim, seed=args.seed)
        print(f"[cluster] PaCMAP reduced shape={reduced.shape}")

        # Ward requires Euclidean geometry.
        z = linkage(reduced, method="ward", metric="euclidean")
        print("[cluster] linkage complete")

        level_labels: dict[int, np.ndarray] = {}
        sil_scores: dict[int, float] = {}
        for k in levels:
            labels = fcluster(z, t=k, criterion="maxclust")
            level_labels[k] = labels
            if 1 < len(np.unique(labels)) < len(labels):
                sil_scores[k] = float(silhouette_score(reduced, labels))
            else:
                sil_scores[k] = float("nan")
            print(f"[cluster] k={k} clusters={len(np.unique(labels))} silhouette={sil_scores[k]:.4f}")

        summary = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_id": model.id,
            "model_name": model.name,
            "model_dim": model.dimension,
            "sample_size": len(rows),
            "seed": args.seed,
            "levels": levels,
            "silhouette_by_level": sil_scores,
            "pacmap_dim": args.pacmap_dim,
            "language_filter": languages,
            "type_filter": types,
            "oversample_factor": args.oversample_factor,
            "clean_dedupe_embedding": args.clean_dedupe_embedding,
            "clean_max_per_title": args.clean_max_per_title,
            "clean_stats": clean_stats,
            "total_seconds": round(time.perf_counter() - t0, 3),
        }

        assignments_path, summary_path = _save_outputs(
            run_name=args.run_name,
            rows=rows,
            level_labels=level_labels,
            summary=summary,
            output_dir=args.output_dir,
        )
        print(f"[cluster] assignments: {assignments_path}")
        print(f"[cluster] summary: {summary_path}")
        print(f"[cluster] done in {summary['total_seconds']}s")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
