"""
embed_backfill.py — Backfill embedding columns for courses, documents, and chunks.

Usage:
    python -m ingest.embed_backfill                         # all tables
    python -m ingest.embed_backfill --only courses          # courses only
    python -m ingest.embed_backfill --only documents        # documents only
    python -m ingest.embed_backfill --only chunks           # chunks only
    python -m ingest.embed_backfill --only all              # all (same as no flag)
    python -m ingest.embed_backfill --batch-size 64         # custom batch size

Run from the api/ directory.
"""

import argparse
import os
import sys
import time

# Allow `python embed_backfill.py` from `api/ingest/` by making `api/` importable.
API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from dotenv import load_dotenv

# Load .env BEFORE any database / service imports
_env_file = os.path.join(os.path.dirname(__file__), os.pardir, ".env")
load_dotenv(_env_file)

from sqlalchemy import func, select
from database.session import SessionLocal
from database.models import Course, UniversityDocument, DocumentChunk
from services.embedding_service import get_embedding_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# all-MiniLM-L6-v2 has a 256 token limit. We keep this conservative to reduce 413s.
MAX_EMBED_CHARS = 320


def _truncate(text: str, max_chars: int = MAX_EMBED_CHARS) -> str:
    """Truncate text to max_chars to avoid 413 from the embedding server."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _build_course_text(course) -> str:
    """Build a single string to embed for a course row."""
    parts = [course.name or ""]
    if course.description:
        parts.append(course.description)
    if course.keywords:
        parts.append(course.keywords)
    return _truncate(" ".join(parts).strip())


def _build_document_text(doc) -> str:
    """Build a single string to embed for a university_document row."""
    parts = [doc.title or ""]
    if doc.keywords:
        parts.append(doc.keywords)
    if doc.summary:
        parts.append(doc.summary)
    return _truncate(" ".join(parts).strip())


# ---------------------------------------------------------------------------
# Backfill functions
# ---------------------------------------------------------------------------

def backfill_courses(batch_size: int = 32) -> int:
    """Embed courses that have a NULL embedding column."""
    svc = get_embedding_service()
    db = SessionLocal()
    try:
        total = db.query(func.count(Course.id)).filter(Course.embedding.is_(None)).scalar()
        if total == 0:
            print("  ✓ All courses already have embeddings.")
            return 0

        print(f"  📐 {total} courses need embeddings (batch={batch_size})")
        done = 0
        offset = 0

        while True:
            rows = (
                db.query(Course)
                .filter(Course.embedding.is_(None))
                .order_by(Course.id)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break

            texts = [_build_course_text(c) for c in rows]
            # Filter out empty texts
            valid = [(r, t) for r, t in zip(rows, texts) if t]
            if valid:
                embeddings = svc.embed_batch([t for _, t in valid])
                for (row, _), emb in zip(valid, embeddings):
                    row.embedding = emb

            db.commit()
            done += len(rows)
            print(f"    ... {done}/{total} courses embedded")

        return done
    finally:
        db.close()


def backfill_documents(batch_size: int = 32) -> int:
    """Embed university_documents that have a NULL keyword_embedding column."""
    svc = get_embedding_service()
    db = SessionLocal()
    try:
        total = db.query(func.count(UniversityDocument.id)).filter(
            UniversityDocument.keyword_embedding.is_(None)
        ).scalar()
        if total == 0:
            print("  ✓ All documents already have embeddings.")
            return 0

        print(f"  📐 {total} documents need embeddings (batch={batch_size})")
        done = 0

        while True:
            rows = (
                db.query(UniversityDocument)
                .filter(UniversityDocument.keyword_embedding.is_(None))
                .order_by(UniversityDocument.id)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break

            texts = [_build_document_text(d) for d in rows]
            valid = [(r, t) for r, t in zip(rows, texts) if t]
            if valid:
                embeddings = svc.embed_batch([t for _, t in valid])
                for (row, _), emb in zip(valid, embeddings):
                    row.keyword_embedding = emb

            db.commit()
            done += len(rows)
            print(f"    ... {done}/{total} documents embedded")

        return done
    finally:
        db.close()


def backfill_chunks(batch_size: int = 32) -> int:
    """Embed document_chunks that have a NULL embedding column."""
    svc = get_embedding_service()
    db = SessionLocal()
    try:
        total = db.query(func.count(DocumentChunk.id)).filter(
            DocumentChunk.embedding.is_(None)
        ).scalar()
        if total == 0:
            print("  ✓ All chunks already have embeddings.")
            return 0

        print(f"  📐 {total} chunks need embeddings (batch={batch_size})")
        done = 0

        while True:
            rows = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.embedding.is_(None))
                .order_by(DocumentChunk.id)
                .limit(batch_size)
                .all()
            )
            if not rows:
                break

            texts = [_truncate(r.content) for r in rows]
            valid = [(r, t) for r, t in zip(rows, texts) if t and t.strip()]
            if valid:
                embeddings = svc.embed_batch([t for _, t in valid])
                for (row, _), emb in zip(valid, embeddings):
                    row.embedding = emb

            db.commit()
            done += len(rows)
            if done % (batch_size * 10) == 0 or done == total:
                print(f"    ... {done}/{total} chunks embedded")

        # Final line if not already printed
        if done % (batch_size * 10) != 0 and done != total:
            print(f"    ... {done}/{total} chunks embedded")

        return done
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

TARGETS = {
    "courses": backfill_courses,
    "documents": backfill_documents,
    "chunks": backfill_chunks,
}

def main():
    parser = argparse.ArgumentParser(description="Backfill embeddings")
    parser.add_argument(
        "--only",
        choices=["courses", "documents", "chunks", "all"],
        default="all",
        help="Which table(s) to embed (default: all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding calls (default: 32)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  UniChatBot — Embedding Backfill")
    print("=" * 60)

    t0 = time.time()

    if args.only == "all":
        targets = list(TARGETS.keys())
    else:
        targets = [args.only]

    results = {}
    for name in targets:
        print(f"\n🔹 Backfilling {name} ...")
        try:
            count = TARGETS[name](batch_size=args.batch_size)
            results[name] = count
        except Exception as e:
            print(f"  ❌ Error embedding {name}: {e}")
            results[name] = -1

    elapsed = time.time() - t0

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    for name, count in results.items():
        status = f"{count} embedded" if count >= 0 else "FAILED"
        print(f"  {name:20s} {status}")
    print(f"  {'elapsed':20s} {elapsed:.1f}s")
    print("=" * 60)
    print("✅ Embedding backfill complete!")


if __name__ == "__main__":
    main()
