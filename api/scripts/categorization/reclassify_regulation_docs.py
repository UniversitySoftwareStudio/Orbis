"""
Reclassify misidentified regulation documents inside the 'document' category.

Strategy:
  1. Compute centroid of all 'regulation_document' embeddings (ground truth)
  2. Rank every 'document' row by cosine distance to that centroid
  3. Dry-run: show candidates with their distances at a given threshold
  4. Apply: update category = 'regulation_document', parent_category = 'regulation'

Usage:
  python reclassify_regulation_docs.py            # dry-run
  python reclassify_regulation_docs.py --apply    # write to DB

Env:
  DATABASE_URL — postgres connection string
"""

import os
import sys

import numpy as np
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

# Cosine distance threshold — rows below this get reclassified.
# Lower = stricter. Tune by inspecting dry-run output.
THRESHOLD = 0.25


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    return 1.0 - float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def main(apply: bool) -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    # ── Step 1: load regulation_document embeddings ──────────────────────────
    print("Loading regulation_document embeddings...")
    cur.execute(
        "SELECT id, embedding FROM knowledge_base "
        "WHERE category = 'regulation_document' AND embedding IS NOT NULL"
    )
    reg_rows = cur.fetchall()
    print(f"  {len(reg_rows)} regulation_document rows with embeddings")

    if not reg_rows:
        print("No regulation_document embeddings found. Aborting.")
        conn.close()
        return

    reg_embeddings = np.array([np.frombuffer(bytes(e), dtype=np.float32) for _, e in reg_rows])
    centroid = reg_embeddings.mean(axis=0)
    centroid /= np.linalg.norm(centroid)
    print(f"  Centroid computed (dim={centroid.shape[0]})")

    # ── Step 2: load document embeddings ──────────────────────────────────────
    print("\nLoading document embeddings...")
    cur.execute(
        "SELECT id, title, url, embedding FROM knowledge_base "
        "WHERE category = 'document' AND embedding IS NOT NULL"
    )
    doc_rows = cur.fetchall()
    print(f"  {len(doc_rows)} document rows with embeddings")

    if not doc_rows:
        print("No document embeddings found. Aborting.")
        conn.close()
        return

    # ── Step 3: rank by cosine distance to centroid ───────────────────────────
    print(f"\nRanking by cosine distance (threshold={THRESHOLD})...")
    candidates = []
    for doc_id, title, url, emb_raw in doc_rows:
        emb = np.frombuffer(bytes(emb_raw), dtype=np.float32)
        emb = emb / (np.linalg.norm(emb) + 1e-10)
        dist = cosine_distance(centroid, emb)
        if dist <= THRESHOLD:
            candidates.append((dist, doc_id, title, url))

    candidates.sort()
    print(f"  {len(candidates)} candidates within threshold {THRESHOLD}")

    if not candidates:
        print("No candidates found. Try raising THRESHOLD.")
        conn.close()
        return

    # ── Step 4: show dry-run output ───────────────────────────────────────────
    print(f"\n{'DIST':>6}  {'TITLE':<55}  URL")
    print("-" * 120)
    for dist, _, title, url in candidates[:50]:
        t = (title or "")[:55]
        print(f"  {dist:.4f}  {t:<55}  {url[:60]}")

    if len(candidates) > 50:
        print(f"  ... and {len(candidates) - 50} more")

    if not apply:
        print(f"\nDry-run complete. {len(candidates)} rows would be reclassified.")
        print("Run with --apply to write to DB.")
        conn.close()
        return

    # ── Step 5: apply updates ──────────────────────────────────────────────────
    ids = [doc_id for _, doc_id, _, _ in candidates]
    cur.execute(
        "UPDATE knowledge_base SET category = 'regulation_document', parent_category = 'regulation' "
        "WHERE id = ANY(%s::uuid[])",
        (ids,)
    )
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    print(f"\n✓ Updated {updated} rows → regulation_document / regulation")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    main(apply)
