import argparse
import concurrent.futures
import json
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv
from psycopg2.extras import execute_values
import requests
from sqlalchemy import and_, func, or_, select, text
import yaml

from database.models import EmbeddingModel, KnowledgeBase, KnowledgeBaseEmbedding
from database.session import SessionLocal
from services.embedding_service import get_embedding_service


def _build_text(
    metadata: dict | None,
    title: str | None,
    char_limit: int | None = None,
) -> str:
    metadata_part = ""
    if metadata:
        metadata_part = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    value = (
        f"{metadata_part}\n"
        f"{(title or '').strip()}\n"
    ).strip()
    final = value if value else "[empty]"
    if char_limit is not None and char_limit > 0:
        final = final[:char_limit]
    return final


def _active_model(db) -> EmbeddingModel:
    model = db.scalars(select(EmbeddingModel).where(EmbeddingModel.is_active.is_(True)).limit(1)).first()
    if model is None:
        raise RuntimeError(
            "[EMBEDDING_BACKFILL_FAILED] No active embedding model found "
            "(embedding_models.is_active=true)."
        )
    return model


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _compose_service_for_model(model_name: str) -> str:
    compose_path = _repo_root() / "docker-compose.yml"
    with compose_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    services = (data.get("services") or {})
    for svc_name, svc in services.items():
        if svc_name == "embedding-lb" or not svc_name.startswith("embedding-"):
            continue
        command = (svc or {}).get("command")
        command_text = " ".join(command) if isinstance(command, list) else str(command or "")
        if f"--model-id {model_name}" in command_text or f"--model-id={model_name}" in command_text:
            return svc_name
    raise RuntimeError(
        "[EMBEDDING_BACKFILL_FAILED] "
        f"No docker-compose embedding service found for active model '{model_name}'."
    )


def _ensure_active_model_service_running(model_name: str) -> None:
    service = _compose_service_for_model(model_name)
    root = _repo_root()

    running = subprocess.run(
        ["docker", "compose", "ps", "--services", "--status", "running"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    running_services = {line.strip() for line in running.stdout.splitlines() if line.strip()}

    # Keep routing deterministic: only active embedding service + lb should be running.
    other_embedding_services = [
        svc for svc in running_services
        if svc.startswith("embedding-") and svc not in {"embedding-lb", service}
    ]
    if other_embedding_services:
        print(
            "[EMBEDDING_BACKFILL] stopping non-active embedding services: "
            + ", ".join(sorted(other_embedding_services))
        )
        subprocess.run(
            ["docker", "compose", "stop", *sorted(other_embedding_services)],
            cwd=root,
            check=True,
        )

    if service not in running_services:
        print(f"[EMBEDDING_BACKFILL] starting docker services: embedding-lb + {service}")
        subprocess.run(
            ["docker", "compose", "up", "-d", "embedding-lb", service],
            cwd=root,
            check=True,
        )

    for _ in range(90):
        health = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:7860/health"],
            check=False,
            capture_output=True,
            text=True,
        )
        if health.stdout.strip() == "200":
            print(f"[EMBEDDING_BACKFILL] embedding service ready: {service}")
            return
        time.sleep(2)

    raise RuntimeError(
        "[EMBEDDING_BACKFILL_FAILED] Embedding service did not become ready at http://localhost:7860/health."
    )


def _verify_counts(db, model_id: int) -> tuple[int, int]:
    kb_count = db.scalar(select(func.count()).select_from(KnowledgeBase)) or 0
    emb_count = (
        db.scalar(
            select(func.count(func.distinct(KnowledgeBaseEmbedding.kb_id))).where(
                KnowledgeBaseEmbedding.model_id == model_id
            )
        )
        or 0
    )
    return kb_count, emb_count


def _chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def _embed_concurrently(
    svc,
    texts: list[str],
    request_batch_size: int,
    embed_workers: int,
) -> list[list[float]]:
    chunks = _chunked(texts, request_batch_size)
    if len(chunks) == 1:
        return svc.embed_batch(chunks[0])

    out: list[list[list[float]] | None] = [None] * len(chunks)
    def _embed_chunk_safe(chunk: list[str]) -> list[list[float]]:
        max_retries = 8
        for attempt in range(max_retries):
            try:
                return svc.embed_batch(chunk)
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else None
                if code == 413 and len(chunk) > 1:
                    mid = len(chunk) // 2
                    left = _embed_chunk_safe(chunk[:mid])
                    right = _embed_chunk_safe(chunk[mid:])
                    return left + right
                if code in {429, 502, 503, 504} and attempt < max_retries - 1:
                    time.sleep(min(0.2 * (2**attempt), 3.0))
                    continue
                raise RuntimeError(
                    f"[EMBEDDING_BACKFILL_FAILED] embed request failed status={code} "
                    f"chunk_size={len(chunk)} retries={attempt + 1}/{max_retries}"
                ) from exc
            except requests.exceptions.RequestException as exc:
                if attempt < max_retries - 1:
                    time.sleep(min(0.2 * (2**attempt), 3.0))
                    continue
                raise RuntimeError(
                    f"[EMBEDDING_BACKFILL_FAILED] embed request network error "
                    f"chunk_size={len(chunk)} retries={attempt + 1}/{max_retries}: {exc}"
                ) from exc
        raise RuntimeError(
            f"[EMBEDDING_BACKFILL_FAILED] embed retries exhausted chunk_size={len(chunk)}."
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=embed_workers) as executor:
        futures = {
            executor.submit(_embed_chunk_safe, chunk): idx
            for idx, chunk in enumerate(chunks)
        }
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            out[idx] = future.result()

    vectors: list[list[float]] = []
    for part in out:
        if part is None:
            raise RuntimeError("[EMBEDDING_BACKFILL_FAILED] Missing embedding chunk result.")
        vectors.extend(part)
    return vectors


def _bulk_upsert_embeddings(db, model_id: int, ids: list, vectors: list[list[float]]) -> None:
    rows = [(str(kb_id), model_id, str(vec)) for kb_id, vec in zip(ids, vectors)]
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


def run(
    batch_size: int,
    request_batch_size: int,
    embed_workers: int,
    char_limit: int | None,
    max_rows: int | None,
) -> int:
    db = SessionLocal()
    try:
        started_at = time.perf_counter()
        t0 = time.perf_counter()
        model = _active_model(db)
        print(f"[EMBEDDING_BACKFILL_PROFILE] active_model_lookup_sec={time.perf_counter() - t0:.3f}")

        t0 = time.perf_counter()
        _ensure_active_model_service_running(model.name)
        print(f"[EMBEDDING_BACKFILL_PROFILE] docker_ensure_sec={time.perf_counter() - t0:.3f}")

        t0 = time.perf_counter()
        svc = get_embedding_service()
        print(f"[EMBEDDING_BACKFILL_PROFILE] embedding_service_init_sec={time.perf_counter() - t0:.3f}")
        print(
            f"[EMBEDDING_BACKFILL] active_model={model.name} version={model.version} "
            f"dim={model.dimension} db_batch_size={batch_size} "
            f"request_batch_size={request_batch_size} embed_workers={embed_workers} "
            f"char_limit={char_limit or 'none'}"
        )

        t0 = time.perf_counter()
        total = db.scalar(select(func.count()).select_from(KnowledgeBase)) or 0
        print(f"[EMBEDDING_BACKFILL_PROFILE] source_count_sec={time.perf_counter() - t0:.3f}")
        target_total = min(total, max_rows) if max_rows is not None else total
        print(f"[EMBEDDING_BACKFILL] source_rows={total} target_rows={target_total}")

        processed = 0
        last_created_at = None
        last_id = None
        while processed < target_total:
            remaining = target_total - processed
            take = min(batch_size, remaining)

            fetch_started_at = time.perf_counter()
            q = (
                select(
                    KnowledgeBase.id,
                    KnowledgeBase.metadata_,
                    KnowledgeBase.title,
                    KnowledgeBase.content,
                    KnowledgeBase.created_at,
                )
                .order_by(KnowledgeBase.created_at, KnowledgeBase.id)
                .limit(take)
            )
            if last_created_at is not None and last_id is not None:
                q = q.where(
                    or_(
                        KnowledgeBase.created_at > last_created_at,
                        and_(
                            KnowledgeBase.created_at == last_created_at,
                            KnowledgeBase.id > last_id,
                        ),
                    )
                )
            rows = list(db.execute(q).all())
            fetch_elapsed = time.perf_counter() - fetch_started_at
            if not rows:
                break

            build_started_at = time.perf_counter()
            ids = [row[0] for row in rows]
            texts = [_build_text(row[1], row[2], char_limit=char_limit) for row in rows]
            build_elapsed = time.perf_counter() - build_started_at
            last_created_at = rows[-1][4]
            last_id = rows[-1][0]

            batch_started_at = time.perf_counter()
            embed_started_at = batch_started_at
            vectors = _embed_concurrently(
                svc=svc,
                texts=texts,
                request_batch_size=request_batch_size,
                embed_workers=embed_workers,
            )
            embed_elapsed = time.perf_counter() - embed_started_at

            db_started_at = time.perf_counter()
            _bulk_upsert_embeddings(db, model.id, ids, vectors)

            db.commit()
            db_elapsed = time.perf_counter() - db_started_at
            processed += len(rows)
            batch_elapsed = time.perf_counter() - batch_started_at
            total_elapsed = time.perf_counter() - started_at
            batch_rps = (len(rows) / batch_elapsed) if batch_elapsed > 0 else 0.0
            avg_rps = (processed / total_elapsed) if total_elapsed > 0 else 0.0
            remaining = max(target_total - processed, 0)
            eta_sec = (remaining / avg_rps) if avg_rps > 0 else 0.0
            print(
                "[EMBEDDING_BACKFILL] "
                f"progress={processed}/{target_total} "
                f"batch_rows={len(rows)} "
                f"fetch_sec={fetch_elapsed:.3f} "
                f"build_sec={build_elapsed:.3f} "
                f"batch_sec={batch_elapsed:.3f} "
                f"embed_sec={embed_elapsed:.3f} "
                f"db_sec={db_elapsed:.3f} "
                f"batch_rps={batch_rps:.1f} "
                f"avg_rps={avg_rps:.1f} "
                f"eta_sec={eta_sec:.1f}"
            )

        if max_rows is None:
            verify_started_at = time.perf_counter()
            kb_count, emb_count = _verify_counts(db, model.id)
            verify_elapsed = time.perf_counter() - verify_started_at
            if kb_count != emb_count:
                missing = kb_count - emb_count
                raise RuntimeError(
                    "[EMBEDDING_BACKFILL_FAILED] "
                    f"active_model={model.name} kb_count={kb_count} embedding_count={emb_count} "
                    f"missing={missing}. Backfill incomplete."
                )
            print(
                "[EMBEDDING_BACKFILL_OK] "
                f"active_model={model.name} kb_count={kb_count} embedding_count={emb_count} "
                f"verify_sec={verify_elapsed:.3f} "
                f"total_sec={time.perf_counter() - started_at:.2f} "
                f"avg_rps={(processed / max(time.perf_counter() - started_at, 1e-9)):.1f}"
            )
        else:
            total_elapsed = time.perf_counter() - started_at
            avg_rps = (processed / total_elapsed) if total_elapsed > 0 else 0.0
            print(
                "[EMBEDDING_BACKFILL_OK] partial run finished (max_rows mode). "
                f"total_sec={total_elapsed:.2f} avg_rps={avg_rps:.1f}"
            )

        return 0
    finally:
        db.close()


def main() -> int:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)

    parser = argparse.ArgumentParser(description="Backfill active model embeddings for knowledge_base")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Number of knowledge_base rows per DB batch/commit.",
    )
    parser.add_argument(
        "--request-batch-size",
        type=int,
        default=8,
        help="Texts per /embed request (best stable from tests: 8).",
    )
    parser.add_argument(
        "--embed-workers",
        type=int,
        default=12,
        help="Parallel embedding requests per DB batch.",
    )
    parser.add_argument(
        "--char-limit",
        type=int,
        default=80,
        help="Max chars per row text before embedding. Lower is faster.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap for partial test runs. Omit for full backfill + strict verify.",
    )
    args = parser.parse_args()
    return run(
        batch_size=args.batch_size,
        request_batch_size=args.request_batch_size,
        embed_workers=args.embed_workers,
        char_limit=args.char_limit,
        max_rows=args.max_rows,
    )


if __name__ == "__main__":
    raise SystemExit(main())
