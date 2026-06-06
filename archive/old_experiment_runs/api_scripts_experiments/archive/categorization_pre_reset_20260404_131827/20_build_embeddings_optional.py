"""
Experiment: local (non-container) Jina v3 embeddings for knowledge_base rows.

Why this exists:
- Uses `jinaai/jina-embeddings-v3` directly (no TEI/docker embedding server).
- Supports random subset runs for fast quality checks.
- Registers/updates the embedding model in `embedding_models`.
- Upserts vectors into `knowledge_base_embeddings`.

Examples:
    # 1) Fast random subset experiment (recommended first run)
    python3 api/scripts/experiments/categorization/20_build_embeddings_optional.py \
      --sample-size 500 \
      --seed 42 \
      --task separation \
      --truncate-dim 512 \
      --batch-size 16 \
      --content-chars 2400

    # 2) Turkish-only subset
    python3 api/scripts/experiments/categorization/20_build_embeddings_optional.py \
      --sample-size 300 \
      --language tr \
      --seed 7

    # 3) Only register the model row (no embedding write)
    python3 api/scripts/experiments/categorization/20_build_embeddings_optional.py \
      --register-only \
      --truncate-dim 1024
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from dotenv import load_dotenv
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
from sqlalchemy import and_, func, select, text


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))

# Load env before importing database.session (engine is initialized on import).
load_dotenv(API_ROOT / ".env")

from database.models import EmbeddingModel, KnowledgeBase  # noqa: E402
from database.session import SessionLocal  # noqa: E402


DEFAULT_MODEL_NAME = "jinaai/jina-embeddings-v3"
DEFAULT_MODEL_VERSION = "v3"
DEFAULT_TASK = "separation"
DEFAULT_NATIVE_DIM = 1024
DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


@dataclass
class SampleRow:
    id: str
    title: str
    content: str
    metadata: dict[str, Any]
    type: str | None
    language: str | None
    category: str | None
    parent_category: str | None


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _stable_pg_seed(seed: int | None) -> float | None:
    """
    Convert any integer seed to PostgreSQL setseed range [-1, 1].
    """
    if seed is None:
        return None
    # deterministic mapping with good spread
    return ((seed % 2_000_001) / 1_000_000.0) - 1.0


def _to_pgvector_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in vec.tolist()) + "]"


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return vectors / norms


def _build_embed_text(
    row: SampleRow,
    content_chars: int,
    metadata_exclude_keys: set[str],
) -> str:
    title = (row.title or "").strip()
    content = (row.content or "").strip()
    if content_chars > 0:
        content = content[:content_chars]

    parts: list[str] = []
    if title:
        parts.append(f"Title: {title}")
    if row.metadata:
        metadata_clean = {
            str(k): v
            for k, v in row.metadata.items()
            if str(k).lower() not in metadata_exclude_keys
        }
        if metadata_clean:
            metadata_text = json.dumps(metadata_clean, ensure_ascii=False, sort_keys=True)
            parts.append(f"Metadata: {metadata_text}")
    if row.type:
        parts.append(f"Type: {row.type}")
    if row.language:
        parts.append(f"Language: {row.language}")
    if content:
        parts.append("Content:")
        parts.append(content)

    joined = "\n".join(parts).strip()
    return joined if joined else "[empty]"


def _upsert_embedding_model(
    db,
    *,
    name: str,
    version: str,
    dimension: int,
    description: str,
    set_active: bool,
) -> EmbeddingModel:
    model = db.scalars(
        select(EmbeddingModel).where(
            and_(
                EmbeddingModel.name == name,
                EmbeddingModel.version == version,
            )
        )
    ).first()

    if model is None:
        model = EmbeddingModel(
            name=name,
            version=version,
            dimension=dimension,
            description=description,
            is_active=False,
        )
        db.add(model)
        db.flush()
    else:
        model.dimension = dimension
        model.description = description

    if set_active:
        for row in db.scalars(select(EmbeddingModel)).all():
            row.is_active = row.id == model.id

    db.commit()
    db.refresh(model)
    return model


def _fetch_random_rows(
    db,
    *,
    sample_size: int,
    seed: int | None,
    languages: list[str],
    types: list[str],
) -> list[SampleRow]:
    pg_seed = _stable_pg_seed(seed)
    if pg_seed is not None:
        db.execute(text("SELECT setseed(:seed)"), {"seed": pg_seed})

    stmt = (
        select(
            KnowledgeBase.id,
            KnowledgeBase.title,
            KnowledgeBase.content,
            KnowledgeBase.metadata_,
            KnowledgeBase.type,
            KnowledgeBase.language,
            KnowledgeBase.category,
            KnowledgeBase.parent_category,
        )
        .where(KnowledgeBase.content.is_not(None))
        .where(func.length(func.trim(KnowledgeBase.content)) > 0)
    )

    if languages:
        stmt = stmt.where(KnowledgeBase.language.in_(languages))
    if types:
        stmt = stmt.where(KnowledgeBase.type.in_(types))

    stmt = stmt.order_by(func.random()).limit(sample_size)
    rows = list(db.execute(stmt).all())
    return [
        SampleRow(
            id=str(r[0]),
            title=r[1] or "",
            content=r[2] or "",
            metadata=r[3] or {},
            type=r[4],
            language=r[5],
            category=r[6],
            parent_category=r[7],
        )
        for r in rows
    ]


def _embed_texts(
    *,
    texts: list[str],
    embedder: SentenceTransformer,
    task: str,
    batch_size: int,
    truncate_dim: int | None,
    normalize: bool,
) -> np.ndarray:
    vectors = embedder.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=False,
        task=task,
    )
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2:
        raise RuntimeError(f"Unexpected embedding shape: {vectors.shape}")

    if truncate_dim is not None:
        if truncate_dim <= 0 or truncate_dim > vectors.shape[1]:
            raise ValueError(
                f"--truncate-dim must be in range [1, {vectors.shape[1]}], got {truncate_dim}"
            )
        vectors = vectors[:, :truncate_dim]

    if normalize:
        vectors = _l2_normalize(vectors)
    return vectors


def _is_oom_error(exc: Exception) -> bool:
    return "out of memory" in str(exc).lower()


def _load_embedder(model_name: str, device: str | None) -> SentenceTransformer:
    # Jina v3 relies on remote code with relative imports from
    # `jinaai/xlm-roberta-flash-implementation`. In some environments,
    # dynamic import cache can miss a subset of files. Pre-warm snapshots
    # to avoid intermittent FileNotFoundError on modules like rotary.py.
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=model_name)
        dep_snapshot = Path(snapshot_download(repo_id="jinaai/xlm-roberta-flash-implementation"))

        module_root = (
            Path.home()
            / ".cache"
            / "huggingface"
            / "modules"
            / "transformers_modules"
            / "jinaai"
            / "xlm-roberta-flash-implementation"
        )
        module_root.mkdir(parents=True, exist_ok=True)
        commit_dirs = [
            p for p in module_root.iterdir()
            if p.is_dir() and p.name != "__pycache__"
        ]
        if not commit_dirs:
            commit_dir = module_root / dep_snapshot.name
            commit_dir.mkdir(parents=True, exist_ok=True)
            commit_dirs = [commit_dir]

        dep_py_files = list(dep_snapshot.glob("*.py"))
        for commit_dir in commit_dirs:
            for src in dep_py_files:
                dst = commit_dir / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
            init_file = commit_dir / "__init__.py"
            if not init_file.exists():
                init_file.write_text("", encoding="utf-8")
    except Exception as exc:
        # Soft-fail: we still attempt normal model loading.
        print(f"[jina-v3] warning: snapshot prewarm failed: {exc}")

    try:
        return SentenceTransformer(
            model_name,
            trust_remote_code=True,
            device=device,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Failed to load jina-embeddings-v3 dependencies. "
            "Install missing packages (at minimum: `einops`) and retry."
        ) from exc


def _upsert_model_embeddings(
    db,
    *,
    kb_ids: list[str],
    vectors: np.ndarray,
    model_id: int,
) -> None:
    rows = [
        (kb_id, model_id, _to_pgvector_literal(vec))
        for kb_id, vec in zip(kb_ids, vectors, strict=True)
    ]
    sql = """
        INSERT INTO knowledge_base_embeddings (kb_id, model_id, embedding)
        VALUES %s
        ON CONFLICT (kb_id, model_id)
        DO UPDATE SET embedding = EXCLUDED.embedding, created_at = NOW()
    """
    conn = db.connection().connection
    with conn.cursor() as cur:
        execute_values(
            cur,
            sql,
            rows,
            template="(%s::uuid, %s::int, %s::vector)",
            page_size=1000,
        )
    db.commit()


def _save_run_artifacts(
    *,
    output_dir: Path,
    run_name: str,
    rows: list[SampleRow],
    vectors: np.ndarray | None,
    config: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = output_dir / f"{run_name}_{stamp}"

    manifest = {
        "run_name": run_name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "rows": [
            {
                "id": row.id,
                "title": row.title[:180],
                "type": row.type,
                "language": row.language,
                "category": row.category,
                "parent_category": row.parent_category,
                "content_chars": len(row.content or ""),
            }
            for row in rows
        ],
    }
    manifest_path = base.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if vectors is not None:
        npy_path = base.with_suffix(".embeddings.npy")
        ids_path = base.with_suffix(".ids.json")
        np.save(npy_path, vectors)
        ids_path.write_text(json.dumps([row.id for row in rows], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[jina-v3] saved manifest: {manifest_path}")
    if vectors is not None:
        print(f"[jina-v3] saved vectors:   {base.with_suffix('.embeddings.npy')}")
        print(f"[jina-v3] saved ids:       {base.with_suffix('.ids.json')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed random knowledge_base subsets with local jina-embeddings-v3."
    )
    parser.add_argument("--sample-size", type=int, default=500, help="How many random rows to embed.")
    parser.add_argument(
        "--resume-at",
        type=int,
        default=0,
        help="Skip the first N sampled rows (useful to resume an interrupted seeded run).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed used for DB sampling.")
    parser.add_argument("--language", type=str, default="", help="Comma-separated languages filter (e.g. tr,en).")
    parser.add_argument("--type", dest="types", type=str, default="", help="Comma-separated types filter (e.g. pdf,web_page).")
    parser.add_argument(
        "--content-chars",
        type=int,
        default=0,
        help="Per-row content truncation before embedding. Use 0 for full content.",
    )
    parser.add_argument(
        "--metadata-exclude-keys",
        type=str,
        default="category,parent_category,breadcrumbs",
        help=(
            "Comma-separated metadata keys to exclude from embedding text to avoid "
            "label leakage."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size for model.encode().")
    parser.add_argument(
        "--upsert-batch-size",
        type=int,
        default=512,
        help="Rows processed per encode->upsert chunk.",
    )
    parser.add_argument("--device", type=str, default=None, help="Torch device override, e.g. cpu, cuda.")

    parser.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME)
    parser.add_argument("--model-version", type=str, default=DEFAULT_MODEL_VERSION)
    parser.add_argument(
        "--task",
        type=str,
        default=DEFAULT_TASK,
        choices=["retrieval.query", "retrieval.passage", "separation", "classification", "text-matching"],
        help="Jina v3 task LoRA adapter.",
    )
    parser.add_argument(
        "--truncate-dim",
        type=int,
        default=DEFAULT_NATIVE_DIM,
        help="Matryoshka truncation dimension (<=1024).",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Disable L2 normalization after embedding/truncation.",
    )

    parser.add_argument(
        "--set-active",
        action="store_true",
        help="Mark this model row as active in embedding_models.",
    )
    parser.add_argument(
        "--register-only",
        action="store_true",
        help="Only upsert embedding_models row, skip embedding generation.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory for experiment artifacts.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default="jina_v3_subset",
        help="Prefix for saved artifact files.",
    )
    parser.add_argument(
        "--no-save-artifacts",
        action="store_true",
        help="Skip saving .manifest.json / .npy / .ids.json files.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_size <= 0:
        raise ValueError("--sample-size must be > 0")
    if args.resume_at < 0:
        raise ValueError("--resume-at must be >= 0")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    if args.upsert_batch_size <= 0:
        raise ValueError("--upsert-batch-size must be > 0")

    load_dotenv(API_ROOT / ".env")
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required (expected in api/.env).")

    normalize = not args.no_normalize
    truncate_dim = args.truncate_dim if args.truncate_dim is not None else DEFAULT_NATIVE_DIM
    target_dim = truncate_dim or DEFAULT_NATIVE_DIM
    description = (
        "Local jina-embeddings-v3 experiment "
        f"(task={args.task}, truncate_dim={target_dim}, normalize={normalize})"
    )

    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        model_row = _upsert_embedding_model(
            db,
            name=args.model_name,
            version=args.model_version,
            dimension=target_dim,
            description=description,
            set_active=args.set_active,
        )
        print(
            "[jina-v3] model registered "
            f"id={model_row.id} name={model_row.name} version={model_row.version} "
            f"dim={model_row.dimension} active={model_row.is_active}"
        )

        if args.register_only:
            print("[jina-v3] register-only mode complete.")
            return 0

        rows = _fetch_random_rows(
            db,
            sample_size=args.sample_size,
            seed=args.seed,
            languages=_parse_csv(args.language),
            types=_parse_csv(args.types),
        )
        if not rows:
            print("[jina-v3] no rows matched the filters; nothing to embed.")
            return 0
        print(f"[jina-v3] sampled rows: {len(rows)}")
        if args.resume_at > 0:
            if args.resume_at >= len(rows):
                print(
                    "[jina-v3] resume-at is >= sampled rows; "
                    "nothing left to process."
                )
                return 0
            rows = rows[args.resume_at :]
            print(
                f"[jina-v3] resumed run: skipped first {args.resume_at} rows; "
                f"remaining {len(rows)}"
            )

        metadata_exclude_keys = {
            key.strip().lower()
            for key in (args.metadata_exclude_keys or "").split(",")
            if key.strip()
        }
        embedder = _load_embedder(args.model_name, args.device)
        total = len(rows)
        vectors_for_artifact: list[np.ndarray] = []
        processed = 0
        effective_batch_size = args.batch_size
        cpu_embedder: SentenceTransformer | None = None
        for start in range(0, total, args.upsert_batch_size):
            chunk = rows[start : start + args.upsert_batch_size]
            used_cpu_fallback = False
            texts = [
                _build_embed_text(
                    row,
                    content_chars=args.content_chars,
                    metadata_exclude_keys=metadata_exclude_keys,
                )
                for row in chunk
            ]
            while True:
                try:
                    chunk_vectors = _embed_texts(
                        texts=texts,
                        embedder=embedder,
                        task=args.task,
                        batch_size=effective_batch_size,
                        truncate_dim=truncate_dim,
                        normalize=normalize,
                    )
                    break
                except (torch.OutOfMemoryError, RuntimeError) as exc:
                    is_oom = _is_oom_error(exc)
                    if not is_oom or effective_batch_size <= 1:
                        if not is_oom:
                            raise
                        print(
                            "[jina-v3] warning: OOM at batch_size=1; "
                            "falling back to CPU encode for this chunk"
                        )
                        if cpu_embedder is None:
                            cpu_embedder = _load_embedder(args.model_name, "cpu")
                        used_cpu_fallback = True
                        chunk_vectors = _embed_texts(
                            texts=texts,
                            embedder=cpu_embedder,
                            task=args.task,
                            batch_size=1,
                            truncate_dim=truncate_dim,
                            normalize=normalize,
                        )
                        break
                    next_batch_size = max(1, effective_batch_size // 2)
                    print(
                        "[jina-v3] warning: CUDA OOM at batch_size="
                        f"{effective_batch_size}; retrying with {next_batch_size}"
                    )
                    effective_batch_size = next_batch_size
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
            _upsert_model_embeddings(
                db,
                kb_ids=[row.id for row in chunk],
                vectors=chunk_vectors,
                model_id=model_row.id,
            )
            processed += len(chunk)
            if not args.no_save_artifacts:
                vectors_for_artifact.append(chunk_vectors)
            print(
                "[jina-v3] upsert progress: "
                f"{processed}/{total} rows ({processed / total:.1%}) "
                f"model_id={model_row.id} batch_size={effective_batch_size}"
            )
            if not used_cpu_fallback and effective_batch_size < args.batch_size:
                next_probe = min(args.batch_size, effective_batch_size * 2)
                if next_probe != effective_batch_size:
                    effective_batch_size = next_probe

        if args.no_save_artifacts:
            print("[jina-v3] artifact saving disabled.")
        else:
            vectors = np.concatenate(vectors_for_artifact, axis=0)
            _save_run_artifacts(
                output_dir=args.output_dir,
                run_name=args.run_name,
                rows=rows,
                vectors=vectors,
                config={
                    "sample_size": args.sample_size,
                    "resume_at": args.resume_at,
                    "seed": args.seed,
                    "language": args.language,
                    "types": args.types,
                    "content_chars": args.content_chars,
                    "metadata_exclude_keys": args.metadata_exclude_keys,
                    "batch_size": args.batch_size,
                    "upsert_batch_size": args.upsert_batch_size,
                    "model_name": args.model_name,
                    "model_version": args.model_version,
                    "task": args.task,
                    "truncate_dim": truncate_dim,
                    "normalize": normalize,
                    "device": args.device,
                    "model_id": model_row.id,
                },
            )

        elapsed = time.perf_counter() - t0
        print(f"[jina-v3] done in {elapsed:.2f}s")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
