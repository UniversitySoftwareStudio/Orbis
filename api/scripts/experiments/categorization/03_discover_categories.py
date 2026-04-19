#!/usr/bin/env python3
"""Step 03: semantic clustering of unknown URL groups to discover new category candidates.

Pipeline:
  1) Load doc_ids for groups with target decisions (default: "unknown") from step 01 + 02 outputs.
  2) Fetch embeddings from DB for those docs.
  3) L2-normalize vectors; run MiniBatchKMeans for leaf clusters (auto-k).
  4) Ward HAC on leaf centroids to cut at 3 levels: coarse, mid, fine.
  5) Label each cluster: TF-IDF on titles, top URL path segments, representative titles.
  6) Write discovery_result.json + discovery_quick.md.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
from dotenv import load_dotenv
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import bindparam, text


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.session import SessionLocal  # noqa: E402


DEFAULT_GROUPS_JSON = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "01_group_parent_urls"
    / "parent_groups_result.json"
)
DEFAULT_CLASSIFY_JSON = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "02_classify_unknowns"
    / "group_classification_result.json"
)
DEFAULT_OUTPUT_DIR = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "03_discover_categories"
)

# ---------------------------------------------------------------------------
# Combined stopwords for TF-IDF labeling
# ---------------------------------------------------------------------------
TR_STOPWORDS: set[str] = {
    "ve", "bir", "bu", "da", "de", "ile", "için", "olan", "gibi", "daha", "en",
    "her", "şu", "o", "biz", "siz", "onlar", "ben", "sen", "ki", "mi", "mı",
    "mu", "mü", "ise", "ya", "veya", "hem", "ne", "nasıl", "neden", "niçin",
    "hangi", "kaç", "olan",
}
EN_STOPWORDS: set[str] = {
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "are", "was",
    "were", "with", "at", "by", "from", "on", "as", "it", "its", "that", "this",
    "be", "have", "has", "had", "will", "not", "but", "if", "then", "so",
    "about", "into", "up", "out", "do",
}
COMBINED_STOPWORDS: list[str] = sorted(TR_STOPWORDS | EN_STOPWORDS)


# ---------------------------------------------------------------------------
# URL / segment helpers  (copied from step 01 — no cross-import dependency)
# ---------------------------------------------------------------------------

def _is_dynamic_segment(seg: str) -> bool:
    s = (seg or "").strip().lower()
    if not s:
        return False
    if s.isdigit():
        return True
    if re.fullmatch(r"\d{4}([-_/]\d{1,2}){1,2}", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8,}", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{13,}", s):
        return True
    digits = sum(ch.isdigit() for ch in s)
    if len(s) >= 5 and digits / len(s) >= 0.60:
        return True
    return False


def _path_segments(url: str) -> list[str]:
    """Return non-dynamic, non-empty path segments (host stripped)."""
    raw = (url or "").strip()
    if not raw:
        return []
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    parsed = urlparse(raw)
    segs = [s.lower() for s in (parsed.path or "").split("/") if s]
    return [s for s in segs if s not in {"tr", "en", "www"} and not _is_dynamic_segment(s)]


def _vec_from_text(value: str) -> np.ndarray:
    arr = np.fromstring(value.strip("[]"), sep=",", dtype=np.float32)
    if arr.size == 0:
        raise ValueError("Empty vector parsed from DB.")
    return arr


# ---------------------------------------------------------------------------
# Auto k formula
# ---------------------------------------------------------------------------

def _auto_leaf_k(n: int) -> int:
    return min(300, max(20, int(round(math.sqrt(n / 8.0)))))


def _auto_coarse_k(n: int) -> int:
    """~1 cluster per 2500 docs, range 6–20."""
    return min(20, max(6, int(round(n / 2500.0))))


def _auto_mid_k(n: int) -> int:
    """~1 cluster per 1000 docs, range 12–45."""
    return min(45, max(12, int(round(n / 1000.0))))


def _auto_fine_k(n: int) -> int:
    """~1 cluster per 400 docs, range 20–80."""
    return min(80, max(20, int(round(n / 400.0))))


# ---------------------------------------------------------------------------
# DB fetch helpers
# ---------------------------------------------------------------------------

def _chunked(items: list[str], chunk_size: int) -> list[list[str]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _fetch_doc_meta(doc_ids: list[str], chunk_size: int) -> dict[str, dict[str, str]]:
    """Return {kb_id: {url, title, language}} for given doc_ids."""
    if not doc_ids:
        return {}
    db = SessionLocal()
    try:
        stmt = text(
            """
            SELECT id::text, COALESCE(url,'') AS url,
                   COALESCE(title,'') AS title,
                   COALESCE(language,'') AS language
            FROM knowledge_base
            WHERE id::text IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
        out: dict[str, dict[str, str]] = {}
        for chunk in _chunked(doc_ids, chunk_size):
            rows = list(db.execute(stmt, {"ids": chunk}).all())
            for row in rows:
                out[str(row[0])] = {
                    "url": str(row[1]),
                    "title": str(row[2]),
                    "language": str(row[3]),
                }
        return out
    finally:
        db.close()


def _fetch_embeddings(doc_ids: list[str], model_id: int, chunk_size: int) -> dict[str, np.ndarray]:
    """Return {kb_id: vector} for given doc_ids and model."""
    if not doc_ids:
        return {}
    db = SessionLocal()
    try:
        if model_id == 0:
            # active model: join with embedding_models to find active
            model_clause = """
                JOIN embedding_models em ON em.id = kbe.model_id AND em.is_active = TRUE
            """
        else:
            model_clause = ""

        stmt_sql = f"""
            SELECT kbe.kb_id::text, kbe.embedding::text
            FROM knowledge_base_embeddings kbe
            {model_clause}
            WHERE kbe.kb_id::text IN :ids
            {"" if model_id == 0 else "AND kbe.model_id = :model_id"}
        """
        params: dict[str, Any] = {}
        if model_id != 0:
            params["model_id"] = model_id

        stmt = text(stmt_sql).bindparams(bindparam("ids", expanding=True))
        out: dict[str, np.ndarray] = {}
        for chunk in _chunked(doc_ids, chunk_size):
            p = {**params, "ids": chunk}
            rows = list(db.execute(stmt, p).all())
            for row in rows:
                try:
                    out[str(row[0])] = _vec_from_text(str(row[1]))
                except Exception:
                    pass
        return out
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Cluster labeling
# ---------------------------------------------------------------------------

def _label_cluster(
    kb_ids: list[str],
    meta: dict[str, dict[str, str]],
    vectors: np.ndarray,
    centroid: np.ndarray,
) -> dict[str, Any]:
    """Compute TF-IDF label tokens, top URL segments, representative titles, lang dist."""
    titles = [meta[k]["title"] for k in kb_ids if k in meta and meta[k]["title"]]
    urls = [meta[k]["url"] for k in kb_ids if k in meta]

    # Language distribution
    lang_dist: Counter[str] = Counter()
    for k in kb_ids:
        lang = meta.get(k, {}).get("language", "") or ""
        bucket = lang if lang in {"tr", "en"} else "other"
        lang_dist[bucket] += 1

    # TF-IDF on titles
    label_tokens: list[str] = []
    if titles:
        try:
            vec = TfidfVectorizer(
                max_features=500,
                stop_words=COMBINED_STOPWORDS,
                min_df=1,
                ngram_range=(1, 1),
            )
            tfidf_mat = vec.fit_transform(titles)
            feature_names = vec.get_feature_names_out()
            mean_scores = np.asarray(tfidf_mat.mean(axis=0)).ravel()
            top_idx = mean_scores.argsort()[::-1][:6]
            label_tokens = [feature_names[i] for i in top_idx if mean_scores[i] > 0]
        except Exception:
            pass

    # Top URL path segments
    seg_counter: Counter[str] = Counter()
    for url in urls:
        for seg in _path_segments(url):
            if len(seg) >= 3:
                seg_counter[seg] += 1
    top_url_segments = [seg for seg, _ in seg_counter.most_common(3)]

    # Representative titles: closest to centroid
    representative_titles: list[str] = []
    if len(kb_ids) > 0 and vectors is not None and len(vectors) > 0:
        centroid_norm = centroid / (np.linalg.norm(centroid) + 1e-9)
        sims = vectors @ centroid_norm
        top_n = min(5, len(kb_ids))
        top_idx_rep = sims.argsort()[::-1][:top_n]
        for idx in top_idx_rep:
            kid = kb_ids[idx]
            t = meta.get(kid, {}).get("title", "")
            if t and t not in representative_titles:
                representative_titles.append(t)

    return {
        "label_tokens": label_tokens,
        "top_url_segments": top_url_segments,
        "representative_titles": representative_titles[:5],
        "language_dist": {
            "tr": int(lang_dist.get("tr", 0)),
            "en": int(lang_dist.get("en", 0)),
            "other": int(lang_dist.get("other", 0)),
        },
    }


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step 03: discover categories from unknown groups via semantic clustering.")
    parser.add_argument("--groups-json", type=Path, default=DEFAULT_GROUPS_JSON,
                        help="Step 01 output: parent_groups_result.json")
    parser.add_argument("--classify-json", type=Path, default=DEFAULT_CLASSIFY_JSON,
                        help="Step 02 output: group_classification_result.json")
    parser.add_argument("--include-decisions", type=str, default="unknown",
                        help="Comma-separated step-02 decisions to cluster (default: unknown)")
    parser.add_argument("--model-id", type=int, default=0,
                        help="Embedding model_id (0 = active model)")
    parser.add_argument("--db-chunk-size", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--coarse-k", type=int, default=0, help="0 = auto")
    parser.add_argument("--mid-k", type=int, default=0, help="0 = auto")
    parser.add_argument("--fine-k", type=int, default=0, help="0 = auto")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    if not args.groups_json.exists():
        raise FileNotFoundError(f"groups-json not found: {args.groups_json}")
    if not args.classify_json.exists():
        raise FileNotFoundError(f"classify-json not found: {args.classify_json}")
    if args.db_chunk_size <= 0:
        raise ValueError("--db-chunk-size must be > 0")

    include_decisions = {d.strip() for d in args.include_decisions.split(",") if d.strip()}
    print(f"[03-disc] include_decisions={include_decisions}")

    # ------------------------------------------------------------------
    # Load step-01 groups (for doc_id → group_id mapping)
    # ------------------------------------------------------------------
    groups_src = json.loads(args.groups_json.read_text(encoding="utf-8"))
    parent_groups: list[dict[str, Any]] = list(groups_src.get("parent_groups", []))
    group_by_id: dict[int, dict[str, Any]] = {int(g["group_id"]): g for g in parent_groups}
    print(f"[03-disc] step-01 parent_groups={len(parent_groups)}")

    # ------------------------------------------------------------------
    # Load step-02 classification; collect group_ids with target decisions
    # ------------------------------------------------------------------
    classify_src = json.loads(args.classify_json.read_text(encoding="utf-8"))
    classify_groups: list[dict[str, Any]] = list(classify_src.get("groups", []))

    target_group_ids: list[int] = []
    group_id_to_decision: dict[int, str] = {}
    for cg in classify_groups:
        decision = str(cg.get("decision", ""))
        gid = int(cg.get("group_id", 0))
        group_id_to_decision[gid] = decision
        if decision in include_decisions:
            target_group_ids.append(gid)

    print(f"[03-disc] target group_ids={len(target_group_ids)}")
    if not target_group_ids:
        raise RuntimeError(f"No groups with decisions in {include_decisions} found.")

    # Collect doc_ids from step-01 for these groups
    all_doc_ids: list[str] = []
    doc_id_to_group_id: dict[str, int] = {}
    for gid in target_group_ids:
        g = group_by_id.get(gid)
        if g is None:
            continue
        for did in g.get("doc_ids", []):
            sid = str(did)
            all_doc_ids.append(sid)
            doc_id_to_group_id[sid] = gid

    all_doc_ids = list(dict.fromkeys(all_doc_ids))  # dedup, preserve order
    print(f"[03-disc] total doc_ids to cluster={len(all_doc_ids)}")

    if len(all_doc_ids) < 10:
        raise RuntimeError("Too few documents for clustering (<10).")

    # ------------------------------------------------------------------
    # Fetch metadata + embeddings
    # ------------------------------------------------------------------
    print("[03-disc] fetching document metadata...")
    meta = _fetch_doc_meta(all_doc_ids, chunk_size=args.db_chunk_size)
    print(f"[03-disc] metadata fetched for {len(meta)} docs")

    print(f"[03-disc] fetching embeddings (model_id={args.model_id})...")
    emb_map = _fetch_embeddings(all_doc_ids, model_id=args.model_id, chunk_size=args.db_chunk_size)
    print(f"[03-disc] embeddings fetched for {len(emb_map)} docs")

    # Keep only docs that have embeddings
    valid_ids = [d for d in all_doc_ids if d in emb_map]
    if len(valid_ids) < 10:
        raise RuntimeError(f"Too few docs with embeddings: {len(valid_ids)}")
    print(f"[03-disc] valid docs (have embedding)={len(valid_ids)}")

    vectors_raw = np.vstack([emb_map[d] for d in valid_ids]).astype(np.float32)

    # L2 normalize
    norms = np.linalg.norm(vectors_raw, axis=1, keepdims=True)
    norms = np.where(norms < 1e-9, 1.0, norms)
    vectors = vectors_raw / norms
    n = len(valid_ids)

    # ------------------------------------------------------------------
    # Determine k values
    # ------------------------------------------------------------------
    leaf_k = _auto_leaf_k(n)
    leaf_k = min(leaf_k, n)
    coarse_k = args.coarse_k if args.coarse_k > 0 else _auto_coarse_k(n)
    mid_k = args.mid_k if args.mid_k > 0 else _auto_mid_k(n)
    fine_k = args.fine_k if args.fine_k > 0 else _auto_fine_k(n)

    # Clamp to reasonable values
    coarse_k = max(2, min(coarse_k, leaf_k))
    mid_k = max(coarse_k + 1, min(mid_k, leaf_k))
    fine_k = max(mid_k + 1, min(fine_k, leaf_k))

    print(
        f"[03-disc] n={n} leaf_k={leaf_k} "
        f"coarse_k={coarse_k} mid_k={mid_k} fine_k={fine_k}"
    )

    # ------------------------------------------------------------------
    # Stage 1: MiniBatchKMeans leaf clusters
    # ------------------------------------------------------------------
    print("[03-disc] running MiniBatchKMeans...")
    kmeans = MiniBatchKMeans(
        n_clusters=leaf_k,
        random_state=args.seed,
        batch_size=min(4096, n),
        n_init="auto",
        max_iter=300,
        reassignment_ratio=0.01,
    )
    leaf_labels = kmeans.fit_predict(vectors)
    centroids = kmeans.cluster_centers_.astype(np.float32)
    # L2-normalize centroids too
    c_norms = np.linalg.norm(centroids, axis=1, keepdims=True)
    c_norms = np.where(c_norms < 1e-9, 1.0, c_norms)
    centroids = centroids / c_norms

    # ------------------------------------------------------------------
    # Stage 2: Ward HAC on leaf centroids
    # ------------------------------------------------------------------
    print("[03-disc] running Ward HAC on centroids...")
    Z = linkage(centroids, method="ward", metric="euclidean")

    def _cut(k: int) -> np.ndarray:
        k_clamped = min(k, leaf_k)
        if k_clamped <= 1:
            return np.ones(leaf_k, dtype=np.int32)
        centroid_groups = fcluster(Z, t=k_clamped, criterion="maxclust")
        return np.asarray(centroid_groups, dtype=np.int32)

    coarse_centroid_labels = _cut(coarse_k)
    mid_centroid_labels = _cut(mid_k)
    fine_centroid_labels = _cut(fine_k)

    # Map doc-level
    doc_coarse = np.array([int(coarse_centroid_labels[leaf_labels[i]]) for i in range(n)], dtype=np.int32)
    doc_mid = np.array([int(mid_centroid_labels[leaf_labels[i]]) for i in range(n)], dtype=np.int32)
    doc_fine = np.array([int(fine_centroid_labels[leaf_labels[i]]) for i in range(n)], dtype=np.int32)

    actual_coarse = int(np.unique(doc_coarse).size)
    actual_mid = int(np.unique(doc_mid).size)
    actual_fine = int(np.unique(doc_fine).size)
    print(f"[03-disc] actual clusters: coarse={actual_coarse} mid={actual_mid} fine={actual_fine}")

    # ------------------------------------------------------------------
    # Stage 3: Compute centroids per level and label clusters
    # ------------------------------------------------------------------
    def _compute_level_centroids(level_labels_arr: np.ndarray) -> dict[int, np.ndarray]:
        out: dict[int, np.ndarray] = {}
        unique = np.unique(level_labels_arr)
        for cid in unique:
            mask = level_labels_arr == cid
            out[int(cid)] = vectors[mask].mean(axis=0)
        return out

    coarse_centroids = _compute_level_centroids(doc_coarse)
    mid_centroids = _compute_level_centroids(doc_mid)
    fine_centroids = _compute_level_centroids(doc_fine)

    # Group docs by (level, cluster_id)
    def _group_docs(level_labels_arr: np.ndarray) -> dict[int, list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        for i, cid in enumerate(level_labels_arr):
            out[int(cid)].append(i)
        return dict(out)

    coarse_groups = _group_docs(doc_coarse)
    mid_groups = _group_docs(doc_mid)
    fine_groups = _group_docs(doc_fine)

    # Build per-cluster metadata
    print("[03-disc] labeling clusters...")

    def _build_cluster_entries(
        level: str,
        groups: dict[int, list[int]],
        level_centroids: dict[int, np.ndarray],
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for cid, indices in sorted(groups.items()):
            kid_list = [valid_ids[i] for i in indices]
            cluster_vecs = vectors[np.array(indices)]
            centroid = level_centroids.get(cid, cluster_vecs.mean(axis=0))

            label_info = _label_cluster(
                kb_ids=kid_list,
                meta=meta,
                vectors=cluster_vecs,
                centroid=centroid,
            )

            # Source group_ids that contributed to this cluster
            source_gids = sorted(set(
                doc_id_to_group_id[k] for k in kid_list if k in doc_id_to_group_id
            ))

            entries.append({
                "cluster_id": int(cid),
                "level": level,
                "doc_count": len(kid_list),
                "label_tokens": label_info["label_tokens"],
                "top_url_segments": label_info["top_url_segments"],
                "representative_titles": label_info["representative_titles"],
                "language_dist": label_info["language_dist"],
                "source_group_ids": source_gids,
            })
        return entries

    coarse_entries = _build_cluster_entries("coarse", coarse_groups, coarse_centroids)
    mid_entries = _build_cluster_entries("mid", mid_groups, mid_centroids)
    fine_entries = _build_cluster_entries("fine", fine_groups, fine_centroids)

    all_cluster_entries = coarse_entries + mid_entries + fine_entries

    # ------------------------------------------------------------------
    # Build doc assignments
    # ------------------------------------------------------------------
    doc_assignments: list[dict[str, Any]] = []
    for i, kb_id in enumerate(valid_ids):
        m = meta.get(kb_id, {})
        doc_assignments.append({
            "kb_id": kb_id,
            "url": m.get("url", ""),
            "title": m.get("title", ""),
            "cluster_coarse": int(doc_coarse[i]),
            "cluster_mid": int(doc_mid[i]),
            "cluster_fine": int(doc_fine[i]),
            "source_group_id": doc_id_to_group_id.get(kb_id, 0),
        })

    # ------------------------------------------------------------------
    # Build summary
    # ------------------------------------------------------------------
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_docs": n,
        "docs_with_embeddings": len(valid_ids),
        "include_decisions": sorted(include_decisions),
        "target_groups": len(target_group_ids),
        "model_id": args.model_id,
        "seed": args.seed,
        "leaf_k": leaf_k,
        "coarse_k_requested": coarse_k,
        "mid_k_requested": mid_k,
        "fine_k_requested": fine_k,
        "actual_coarse_clusters": actual_coarse,
        "actual_mid_clusters": actual_mid,
        "actual_fine_clusters": actual_fine,
    }

    config = {
        "groups_json": str(args.groups_json),
        "classify_json": str(args.classify_json),
        "include_decisions": sorted(include_decisions),
        "model_id": args.model_id,
        "db_chunk_size": args.db_chunk_size,
        "seed": args.seed,
        "coarse_k_override": args.coarse_k,
        "mid_k_override": args.mid_k,
        "fine_k_override": args.fine_k,
    }

    result_payload: dict[str, Any] = {
        "summary": summary,
        "config": config,
        "clusters": all_cluster_entries,
        "doc_assignments": doc_assignments,
    }

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    result_json = out_dir / "discovery_result.json"
    quick_md = out_dir / "discovery_quick.md"

    result_json.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Quick markdown
    lines: list[str] = ["# Step 03 — Category Discovery", ""]
    lines += ["## Summary", ""]
    lines += [f"- total_docs: `{summary['total_docs']}`"]
    lines += [f"- docs_with_embeddings: `{summary['docs_with_embeddings']}`"]
    lines += [f"- target_groups (step-02 decisions): `{summary['target_groups']}`"]
    lines += [f"- include_decisions: `{summary['include_decisions']}`"]
    lines += [f"- leaf_k: `{summary['leaf_k']}`"]
    lines += [f"- coarse clusters: `{summary['actual_coarse_clusters']}`"]
    lines += [f"- mid clusters: `{summary['actual_mid_clusters']}`"]
    lines += [f"- fine clusters: `{summary['actual_fine_clusters']}`"]
    lines += [""]

    for level_name, entries in [("coarse", coarse_entries), ("mid", mid_entries), ("fine", fine_entries)]:
        lines += [f"## {level_name.capitalize()} Clusters ({len(entries)})", ""]
        lines += ["| # | cluster_id | docs | label_tokens | top_url_segments | top_titles |"]
        lines += ["|---:|---:|---:|---|---|---|"]
        for i, e in enumerate(sorted(entries, key=lambda x: -x["doc_count"]), start=1):
            tokens = ", ".join(e["label_tokens"][:4])
            segs = ", ".join(e["top_url_segments"][:3])
            title = (e["representative_titles"][0][:60] if e["representative_titles"] else "").replace("|", "\\|")
            lines += [f"| {i} | {e['cluster_id']} | {e['doc_count']} | {tokens} | {segs} | {title} |"]
        lines += [""]

    quick_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[03-disc] result_json={result_json}")
    print(f"[03-disc] quick_md={quick_md}")
    print(
        f"[03-disc] DONE — docs={n} leaf_k={leaf_k} "
        f"coarse={actual_coarse} mid={actual_mid} fine={actual_fine}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
