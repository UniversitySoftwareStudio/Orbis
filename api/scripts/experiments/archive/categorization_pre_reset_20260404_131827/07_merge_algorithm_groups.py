#!/usr/bin/env python3
"""
Merge `needs_algorithm` groups into the existing taxonomy tree.

Why this exists:
- Pass-1 URL taxonomy is already stable.
- We do NOT want to rerun pass-1 AI.
- We only process `needs_algorithm` groups, cluster them, then attach the
  resulting subclusters to the existing taxonomy leaves.

Method:
1) Build reference leaf centroids from pass-1 mapped URL groups.
2) Cluster each `needs_algorithm` source cluster into semantic subclusters.
3) Map each subcluster centroid to nearest reference leaf (cosine similarity).
4) Merge mapped subclusters into the existing taxonomy tree artifact.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from sklearn.cluster import MiniBatchKMeans
from sqlalchemy import bindparam, text


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.session import SessionLocal  # noqa: E402


DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


@dataclass
class DocRow:
    kb_id: str
    url: str
    title: str
    vector: np.ndarray


def _vec_from_text(value: str) -> np.ndarray:
    arr = np.fromstring((value or "").strip("[]"), sep=",", dtype=np.float32)
    if arr.size == 0:
        raise ValueError("Empty vector parsed from DB.")
    return arr


def _parse_cluster_doc_ids_from_umbrella(umbrella: dict[str, Any]) -> dict[int, list[str]]:
    clusters = (
        umbrella.get("depth_results", {})
        .get("dynamic", {})
        .get("clusters", [])
    )
    out: dict[int, list[str]] = {}
    for c in clusters:
        cluster_id = int(c.get("cluster_id", 0))
        ids: list[str] = []
        for p in c.get("parents", []):
            ids.extend([str(v) for v in p.get("doc_ids", [])])
        seen: set[str] = set()
        ordered: list[str] = []
        for kb_id in ids:
            if kb_id in seen:
                continue
            seen.add(kb_id)
            ordered.append(kb_id)
        out[cluster_id] = ordered
    return out


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return vec
    return vec / norm


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _chunked_ids(ids: list[str], chunk_size: int) -> list[list[str]]:
    return [ids[i: i + chunk_size] for i in range(0, len(ids), chunk_size)]


def _resolve_model_id(db, model_id: int | None) -> int:
    if model_id is not None and model_id > 0:
        row = db.execute(
            text("SELECT id FROM embedding_models WHERE id=:id LIMIT 1"),
            {"id": model_id},
        ).first()
        if row is None:
            raise RuntimeError(f"Model id={model_id} not found in embedding_models.")
        return int(model_id)

    row = db.execute(
        text("SELECT id FROM embedding_models WHERE is_active = true ORDER BY id DESC LIMIT 1")
    ).first()
    if row is None:
        raise RuntimeError("No active model found and --model-id was not provided.")
    return int(row[0])


def _fetch_doc_rows(
    db,
    *,
    model_id: int,
    ids: list[str],
    chunk_size: int,
    fetch_all_model_if_ids_ge: int,
) -> dict[str, DocRow]:
    if not ids:
        return {}
    # Keep UUID-typed predicates so PostgreSQL can use kb_id index.
    id_uuid_map: dict[uuid.UUID, str] = {}
    for raw in ids:
        try:
            uid = uuid.UUID(str(raw))
        except Exception:
            continue
        id_uuid_map[uid] = str(raw)
    ids_uuid = list(id_uuid_map.keys())
    if not ids_uuid:
        return {}

    out: dict[str, DocRow] = {}
    if fetch_all_model_if_ids_ge > 0 and len(ids_uuid) >= fetch_all_model_if_ids_ge:
        target_ids = set(ids_uuid)
        stmt_all = text(
            """
            SELECT
                kbe.kb_id AS kb_id,
                kbe.embedding::text AS embedding_text,
                COALESCE(kb.url, '') AS url,
                COALESCE(kb.title, '') AS title
            FROM knowledge_base_embeddings kbe
            JOIN knowledge_base kb ON kb.id = kbe.kb_id
            WHERE kbe.model_id = :model_id
            """
        )
        rows = list(db.execute(stmt_all, {"model_id": model_id}).all())
        for r in rows:
            kb_uuid = r[0]
            if kb_uuid not in target_ids:
                continue
            kb_id = id_uuid_map[kb_uuid]
            out[kb_id] = DocRow(
                kb_id=kb_id,
                vector=_vec_from_text(r[1]),
                url=r[2] or "",
                title=r[3] or "",
            )
        return out

    stmt = text(
        """
        SELECT
            kbe.kb_id AS kb_id,
            kbe.embedding::text AS embedding_text,
            COALESCE(kb.url, '') AS url,
            COALESCE(kb.title, '') AS title
        FROM knowledge_base_embeddings kbe
        JOIN knowledge_base kb ON kb.id = kbe.kb_id
        WHERE kbe.model_id = :model_id
          AND kbe.kb_id IN :ids
        """
    ).bindparams(bindparam("ids", expanding=True))

    for chunk in _chunked_ids(ids_uuid, chunk_size=chunk_size):
        rows = list(db.execute(stmt, {"model_id": model_id, "ids": chunk}).all())
        for r in rows:
            kb_uuid = r[0]
            kb_id = id_uuid_map[kb_uuid]
            out[kb_id] = DocRow(
                kb_id=kb_id,
                vector=_vec_from_text(r[1]),
                url=r[2] or "",
                title=r[3] or "",
            )
    return out


def _choose_k(
    *,
    n_docs: int,
    max_subclusters: int,
    min_docs_to_split: int,
    min_subcluster_size: int,
) -> int:
    if n_docs < min_docs_to_split:
        return 1

    # Scale slowly with group size; cap aggressively for readability.
    # k ~= sqrt(n/12), then constrained by min/max and minimum size rule.
    raw = int(round(math.sqrt(max(1.0, n_docs / 12.0))))
    k = max(2, raw)
    k = min(k, max_subclusters, n_docs)

    while k > 1 and (n_docs / k) < min_subcluster_size:
        k -= 1
    return max(1, k)


def _maybe_reduce_for_clustering(
    vectors: np.ndarray,
    *,
    pacmap_dim: int,
    seed: int,
) -> np.ndarray:
    if pacmap_dim <= 0:
        return vectors
    if len(vectors) <= 3:
        return vectors
    try:
        import pacmap
    except ImportError as exc:
        raise RuntimeError(
            "PaCMAP is not installed but --pacmap-dim > 0 was requested."
        ) from exc

    reduced_dim = min(pacmap_dim, vectors.shape[1], len(vectors) - 1)
    if reduced_dim < 2:
        return vectors

    reducer = pacmap.PaCMAP(
        n_components=reduced_dim,
        n_neighbors=min(15, len(vectors) - 1),
        MN_ratio=0.5,
        FP_ratio=2.0,
        random_state=seed,
    )
    return reducer.fit_transform(vectors, init="pca")


def _cluster_group(
    *,
    vectors: np.ndarray,
    k: int,
    pacmap_dim: int,
    seed: int,
) -> np.ndarray:
    if k <= 1:
        return np.ones(len(vectors), dtype=np.int32)

    cluster_space = _maybe_reduce_for_clustering(vectors, pacmap_dim=pacmap_dim, seed=seed)
    model = MiniBatchKMeans(
        n_clusters=k,
        random_state=seed,
        batch_size=min(4096, max(256, len(vectors))),
        n_init="auto",
        max_iter=300,
    )
    labels = model.fit_predict(cluster_space)
    return labels.astype(np.int32) + 1


def _leaf_key(top: str, sub: str, label: str) -> tuple[str, str, str]:
    return (str(top).strip().lower(), str(sub).strip().lower(), str(label).strip())


def _empty_leaf() -> dict[str, Any]:
    return {
        "category_count": 0,
        "doc_count": 0,
        "clusters": [],
        "representative_parents": [],
        "sample_urls": [],
        "algorithm_clusters": [],
    }


def _ensure_leaf(tree: dict[str, Any], top: str, sub: str, label: str) -> dict[str, Any]:
    top_node = tree.setdefault(
        top,
        {
            "category_count": 0,
            "doc_count": 0,
            "sub_levels": {},
        },
    )
    sub_node = top_node["sub_levels"].setdefault(
        sub,
        {
            "category_count": 0,
            "doc_count": 0,
            "leaves": {},
        },
    )
    leaf = sub_node["leaves"].setdefault(label, _empty_leaf())
    if "algorithm_clusters" not in leaf:
        leaf["algorithm_clusters"] = []
    return leaf


def _trim_leaf_examples(tree: dict[str, Any], max_examples: int) -> None:
    for top_node in tree.values():
        for sub_node in top_node.get("sub_levels", {}).values():
            for leaf in sub_node.get("leaves", {}).values():
                clusters = [v for v in leaf.get("clusters", [])]
                # keep URL clusters deterministic and compact
                int_clusters = sorted(set(int(v) for v in clusters if isinstance(v, int)))
                leaf["clusters"] = int_clusters

                rep_parents = [str(v) for v in leaf.get("representative_parents", []) if str(v).strip()]
                seen_p: set[str] = set()
                uniq_p: list[str] = []
                for p in rep_parents:
                    if p in seen_p:
                        continue
                    seen_p.add(p)
                    uniq_p.append(p)
                leaf["representative_parents"] = uniq_p[:max_examples]

                sample_urls = [str(v) for v in leaf.get("sample_urls", []) if str(v).strip()]
                seen_u: set[str] = set()
                uniq_u: list[str] = []
                for u in sample_urls:
                    if u in seen_u:
                        continue
                    seen_u.add(u)
                    uniq_u.append(u)
                leaf["sample_urls"] = uniq_u[:max_examples]

                algo = list(leaf.get("algorithm_clusters", []))
                algo.sort(
                    key=lambda x: (
                        int(x.get("source_cluster_id", 0)),
                        int(x.get("subcluster_local_id", 0)),
                    )
                )
                leaf["algorithm_clusters"] = algo


def _recompute_counts(tree: dict[str, Any]) -> None:
    for top_node in tree.values():
        top_categories = 0
        top_docs = 0
        for sub_node in top_node.get("sub_levels", {}).values():
            sub_categories = 0
            sub_docs = 0
            for leaf in sub_node.get("leaves", {}).values():
                sub_categories += int(leaf.get("category_count", 0))
                sub_docs += int(leaf.get("doc_count", 0))
            sub_node["category_count"] = sub_categories
            sub_node["doc_count"] = sub_docs
            top_categories += sub_categories
            top_docs += sub_docs
        top_node["category_count"] = top_categories
        top_node["doc_count"] = top_docs


def _sorted_tree(tree: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for top in sorted(tree.keys()):
        top_node = tree[top]
        sorted_sub: dict[str, Any] = {}
        for sub in sorted(top_node.get("sub_levels", {}).keys()):
            sub_node = top_node["sub_levels"][sub]
            sorted_leaves: dict[str, Any] = {}
            for label in sorted(sub_node.get("leaves", {}).keys()):
                sorted_leaves[label] = sub_node["leaves"][label]
            sorted_sub[sub] = {
                "category_count": int(sub_node.get("category_count", 0)),
                "doc_count": int(sub_node.get("doc_count", 0)),
                "leaves": sorted_leaves,
            }
        out[top] = {
            "category_count": int(top_node.get("category_count", 0)),
            "doc_count": int(top_node.get("doc_count", 0)),
            "sub_levels": sorted_sub,
        }
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge needs_algorithm clusters into existing taxonomy tree.")
    parser.add_argument("--depth-json", type=Path, required=True)
    parser.add_argument("--umbrella-json", type=Path, required=True)
    parser.add_argument("--pass1-ai-json", type=Path, required=True)
    parser.add_argument("--pass1-tree-json", type=Path, required=True)
    parser.add_argument("--model-id", type=int, default=0, help="0 means active embedding model.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pacmap-dim", type=int, default=0, help="0 disables PaCMAP before KMeans.")
    parser.add_argument("--max-subclusters", type=int, default=12)
    parser.add_argument("--min-docs-to-split", type=int, default=24)
    parser.add_argument("--min-subcluster-size", type=int, default=8)
    parser.add_argument("--min-similarity", type=float, default=0.20)
    parser.add_argument("--sample-urls-per-subcluster", type=int, default=3)
    parser.add_argument("--max-leaf-examples", type=int, default=6)
    parser.add_argument(
        "--reference-docs-per-pass1-cluster",
        type=int,
        default=80,
        help="How many docs per pass-1 cluster to use for reference centroids (0 means all).",
    )
    parser.add_argument(
        "--include-unresolved-in-tree",
        action="store_true",
        help="Attach unresolved algorithm subclusters under unknown/algorithm_unresolved.",
    )
    parser.add_argument(
        "--include-depth-signals",
        type=str,
        default="numeric_only_tail_low_signal,numeric_dominant_tail_low_signal,too_similar_repetitive,mixed",
        help="Comma-separated depth_signal filters for needs groups.",
    )
    parser.add_argument("--db-chunk-size", type=int, default=2000)
    parser.add_argument(
        "--fetch-all-model-if-ids-ge",
        type=int,
        default=0,
        help="If requested id count is >= this value, scan full model rows once and filter in memory.",
    )
    parser.add_argument("--run-name", type=str, default="pass2_algorithm_merge")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required (expected in api/.env).")

    args = parse_args()
    for p in [args.depth_json, args.umbrella_json, args.pass1_ai_json, args.pass1_tree_json]:
        if not p.exists():
            raise FileNotFoundError(f"Input not found: {p}")
    if args.max_subclusters <= 0:
        raise ValueError("--max-subclusters must be > 0")
    if args.min_docs_to_split <= 1:
        raise ValueError("--min-docs-to-split must be > 1")
    if args.min_subcluster_size <= 0:
        raise ValueError("--min-subcluster-size must be > 0")
    if not (0.0 <= args.min_similarity <= 1.0):
        raise ValueError("--min-similarity must be in [0, 1].")
    if args.sample_urls_per_subcluster <= 0:
        raise ValueError("--sample-urls-per-subcluster must be > 0")
    if args.max_leaf_examples <= 0:
        raise ValueError("--max-leaf-examples must be > 0")
    if args.reference_docs_per_pass1_cluster < 0:
        raise ValueError("--reference-docs-per-pass1-cluster must be >= 0")
    if args.db_chunk_size <= 0:
        raise ValueError("--db-chunk-size must be > 0")
    if args.fetch_all_model_if_ids_ge < 0:
        raise ValueError("--fetch-all-model-if-ids-ge must be >= 0")
    if args.pacmap_dim < 0:
        raise ValueError("--pacmap-dim must be >= 0")

    depth = json.loads(args.depth_json.read_text(encoding="utf-8"))
    umbrella = json.loads(args.umbrella_json.read_text(encoding="utf-8"))
    pass1_ai = json.loads(args.pass1_ai_json.read_text(encoding="utf-8"))
    pass1_tree_payload = json.loads(args.pass1_tree_json.read_text(encoding="utf-8"))

    cluster_doc_ids = _parse_cluster_doc_ids_from_umbrella(umbrella)
    depth_groups = list(depth.get("groups", []) or [])
    allowed_signals = set(_parse_csv(args.include_depth_signals))

    needs_groups = [
        g
        for g in depth_groups
        if str(g.get("decision", "")).strip() == "needs_algorithm"
        and str(g.get("depth_signal", "")).strip() in allowed_signals
    ]
    needs_groups.sort(key=lambda g: (-int(g.get("doc_count", 0)), int(g.get("cluster_id", 0))))

    pass1_results = list(pass1_ai.get("results", []) or [])
    pass1_cluster_to_leaf: dict[int, tuple[str, str, str]] = {}
    for row in pass1_results:
        ai = row.get("ai_taxonomy", {}) or {}
        if str(ai.get("status", "")).strip().lower() != "mapped":
            continue
        cid = int(row.get("cluster_id", 0))
        key = _leaf_key(
            str(ai.get("top_level", "unknown")),
            str(ai.get("sub_level", "unknown")),
            str(ai.get("canonical_label", "UNRESOLVED")),
        )
        pass1_cluster_to_leaf[cid] = key

    pass1_cluster_ids = sorted(pass1_cluster_to_leaf.keys())
    needs_cluster_ids = [int(g.get("cluster_id", 0)) for g in needs_groups]

    pass1_doc_ids: list[str] = []
    for cid in pass1_cluster_ids:
        doc_ids = cluster_doc_ids.get(cid, [])
        if args.reference_docs_per_pass1_cluster > 0:
            doc_ids = doc_ids[: args.reference_docs_per_pass1_cluster]
        pass1_doc_ids.extend(doc_ids)
    pass1_doc_ids = list(dict.fromkeys(pass1_doc_ids))

    needs_doc_ids: list[str] = []
    for cid in needs_cluster_ids:
        needs_doc_ids.extend(cluster_doc_ids.get(cid, []))
    needs_doc_ids = list(dict.fromkeys(needs_doc_ids))

    all_doc_ids = sorted(set(pass1_doc_ids) | set(needs_doc_ids))

    db = SessionLocal()
    try:
        model_id = _resolve_model_id(db, args.model_id if args.model_id > 0 else None)
        print(
            f"[algo-merge] model_id={model_id} "
            f"pass1_clusters={len(pass1_cluster_ids)} needs_clusters={len(needs_cluster_ids)} "
            f"pass1_docs={len(pass1_doc_ids)} needs_docs={len(needs_doc_ids)}"
        )
        if args.fetch_all_model_if_ids_ge > 0 and len(all_doc_ids) >= args.fetch_all_model_if_ids_ge:
            print(
                "[algo-merge] embedding fetch mode=full_model_scan "
                f"(requested_ids={len(all_doc_ids)} threshold={args.fetch_all_model_if_ids_ge})"
            )
        else:
            print(
                "[algo-merge] embedding fetch mode=chunked_in "
                f"(requested_ids={len(all_doc_ids)} chunk_size={args.db_chunk_size})"
            )

        doc_rows = _fetch_doc_rows(
            db,
            model_id=model_id,
            ids=all_doc_ids,
            chunk_size=args.db_chunk_size,
            fetch_all_model_if_ids_ge=args.fetch_all_model_if_ids_ge,
        )
    finally:
        db.close()

    print(f"[algo-merge] fetched_embeddings={len(doc_rows)} from requested_ids={len(all_doc_ids)}")

    # Build reference centroids from pass-1 mapped leaves.
    leaf_vec_sums: dict[tuple[str, str, str], np.ndarray] = {}
    leaf_vec_counts: defaultdict[tuple[str, str, str], int] = defaultdict(int)
    missing_pass1_docs = 0
    for cid in pass1_cluster_ids:
        key = pass1_cluster_to_leaf[cid]
        for kb_id in cluster_doc_ids.get(cid, []):
            row = doc_rows.get(kb_id)
            if row is None:
                missing_pass1_docs += 1
                continue
            if key not in leaf_vec_sums:
                leaf_vec_sums[key] = np.zeros_like(row.vector, dtype=np.float64)
            leaf_vec_sums[key] += row.vector.astype(np.float64)
            leaf_vec_counts[key] += 1

    leaf_keys = sorted(leaf_vec_sums.keys())
    if not leaf_keys:
        raise RuntimeError("No reference leaf centroids could be built from pass-1 mapped groups.")

    leaf_centroids = []
    for key in leaf_keys:
        centroid = leaf_vec_sums[key] / max(1, leaf_vec_counts[key])
        leaf_centroids.append(_normalize(centroid.astype(np.float32)))
    leaf_matrix = np.vstack(leaf_centroids).astype(np.float32)

    merged_tree = copy.deepcopy(pass1_tree_payload.get("tree", {}) or {})

    assignment_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []
    total_algo_subclusters = 0
    total_algo_docs = 0
    mapped_subclusters = 0
    mapped_docs = 0

    for group in needs_groups:
        source_cluster_id = int(group.get("cluster_id", 0))
        source_parent = str(group.get("representative_parent", ""))
        source_signal = str(group.get("depth_signal", ""))
        source_doc_count = int(group.get("doc_count", 0))
        ids = cluster_doc_ids.get(source_cluster_id, [])

        group_rows = [doc_rows[kb_id] for kb_id in ids if kb_id in doc_rows]
        if not group_rows:
            unresolved_rows.append(
                {
                    "source_cluster_id": source_cluster_id,
                    "source_doc_count": source_doc_count,
                    "source_representative_parent": source_parent,
                    "source_depth_signal": source_signal,
                    "reason": "missing_embeddings_for_group",
                }
            )
            continue

        vectors = np.vstack([r.vector for r in group_rows]).astype(np.float32)
        k = _choose_k(
            n_docs=len(group_rows),
            max_subclusters=args.max_subclusters,
            min_docs_to_split=args.min_docs_to_split,
            min_subcluster_size=args.min_subcluster_size,
        )
        labels = _cluster_group(
            vectors=vectors,
            k=k,
            pacmap_dim=args.pacmap_dim,
            seed=args.seed,
        )

        for subcluster_local_id in sorted(set(int(v) for v in labels.tolist())):
            idx = np.where(labels == subcluster_local_id)[0]
            sub_rows = [group_rows[int(i)] for i in idx]
            if not sub_rows:
                continue

            sub_docs = len(sub_rows)
            total_algo_subclusters += 1
            total_algo_docs += sub_docs

            sub_vectors = np.vstack([r.vector for r in sub_rows]).astype(np.float32)
            sub_centroid = _normalize(np.mean(sub_vectors, axis=0))
            sims = leaf_matrix @ sub_centroid
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])
            best_leaf = leaf_keys[best_idx]

            sample_urls: list[str] = []
            sample_doc_ids: list[str] = []
            for row in sub_rows[: args.sample_urls_per_subcluster]:
                sample_doc_ids.append(row.kb_id)
                sample_urls.append(row.url)

            mapping_status = "mapped" if best_sim >= args.min_similarity else "unresolved"
            mapped_top, mapped_sub, mapped_label = (
                (best_leaf[0], best_leaf[1], best_leaf[2]) if mapping_status == "mapped" else ("unknown", "unknown", "UNRESOLVED")
            )

            assignment = {
                "source_cluster_id": source_cluster_id,
                "source_representative_parent": source_parent,
                "source_depth_signal": source_signal,
                "source_doc_count": source_doc_count,
                "subcluster_local_id": subcluster_local_id,
                "subcluster_doc_count": sub_docs,
                "clustering_k_for_source_cluster": k,
                "mapping_status": mapping_status,
                "matched_top_level": mapped_top,
                "matched_sub_level": mapped_sub,
                "matched_canonical_label": mapped_label,
                "similarity_to_matched_leaf": round(best_sim, 6),
                "sample_doc_ids": sample_doc_ids,
                "sample_urls": sample_urls,
            }
            assignment_rows.append(assignment)

            if mapping_status == "mapped":
                mapped_subclusters += 1
                mapped_docs += sub_docs
                leaf = _ensure_leaf(merged_tree, mapped_top, mapped_sub, mapped_label)
                leaf["category_count"] = int(leaf.get("category_count", 0)) + 1
                leaf["doc_count"] = int(leaf.get("doc_count", 0)) + sub_docs

                rep_parents = list(leaf.get("representative_parents", []))
                if source_parent and source_parent not in rep_parents:
                    rep_parents.append(source_parent)
                leaf["representative_parents"] = rep_parents

                samples = list(leaf.get("sample_urls", []))
                for u in sample_urls:
                    if u and u not in samples:
                        samples.append(u)
                leaf["sample_urls"] = samples

                algo_clusters = list(leaf.get("algorithm_clusters", []))
                algo_clusters.append(
                    {
                        "source_cluster_id": source_cluster_id,
                        "subcluster_local_id": subcluster_local_id,
                        "doc_count": sub_docs,
                        "similarity": round(best_sim, 6),
                        "source_depth_signal": source_signal,
                        "source_representative_parent": source_parent,
                        "sample_urls": sample_urls,
                    }
                )
                leaf["algorithm_clusters"] = algo_clusters
            else:
                unresolved_rows.append(assignment)
                if args.include_unresolved_in_tree:
                    leaf = _ensure_leaf(merged_tree, "unknown", "algorithm_unresolved", "UNRESOLVED")
                    leaf["category_count"] = int(leaf.get("category_count", 0)) + 1
                    leaf["doc_count"] = int(leaf.get("doc_count", 0)) + sub_docs
                    samples = list(leaf.get("sample_urls", []))
                    for u in sample_urls:
                        if u and u not in samples:
                            samples.append(u)
                    leaf["sample_urls"] = samples

        print(
            f"[algo-merge] source_cluster={source_cluster_id} docs={len(group_rows)} "
            f"split_k={k} signal={source_signal}"
        )

    _recompute_counts(merged_tree)
    _trim_leaf_examples(merged_tree, max_examples=args.max_leaf_examples)
    merged_tree = _sorted_tree(merged_tree)

    pass1_summary = pass1_tree_payload.get("summary", {}) or {}
    pass1_category_count = int(pass1_summary.get("mapped_category_count", 0))
    pass1_doc_count = int(pass1_summary.get("mapped_doc_count", 0))
    merged_category_count = sum(int(v.get("category_count", 0)) for v in merged_tree.values())
    merged_doc_count = sum(int(v.get("doc_count", 0)) for v in merged_tree.values())

    top_level_algo_docs: defaultdict[str, int] = defaultdict(int)
    for row in assignment_rows:
        if row["mapping_status"] != "mapped":
            continue
        top_level_algo_docs[str(row["matched_top_level"])] += int(row["subcluster_doc_count"])

    out_summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_depth_json": str(args.depth_json),
        "source_umbrella_json": str(args.umbrella_json),
        "source_pass1_ai_json": str(args.pass1_ai_json),
        "source_pass1_tree_json": str(args.pass1_tree_json),
        "model_id": model_id,
        "seed": args.seed,
        "pacmap_dim": args.pacmap_dim,
        "reference_docs_per_pass1_cluster": args.reference_docs_per_pass1_cluster,
        "needs_algorithm_group_count": len(needs_groups),
        "needs_algorithm_doc_count": len(needs_doc_ids),
        "pass1_reference_cluster_count": len(pass1_cluster_ids),
        "pass1_reference_doc_count": len(pass1_doc_ids),
        "fetched_embedding_count": len(doc_rows),
        "missing_pass1_docs_for_centroids": missing_pass1_docs,
        "algorithm_subcluster_count": total_algo_subclusters,
        "algorithm_subcluster_doc_count": total_algo_docs,
        "mapped_algorithm_subcluster_count": mapped_subclusters,
        "mapped_algorithm_doc_count": mapped_docs,
        "unresolved_algorithm_subcluster_count": len(unresolved_rows),
        "unresolved_algorithm_doc_count": sum(int(r.get("subcluster_doc_count", 0)) for r in unresolved_rows),
        "min_similarity_threshold": args.min_similarity,
        "pass1_tree_category_count": pass1_category_count,
        "pass1_tree_doc_count": pass1_doc_count,
        "merged_tree_category_count": merged_category_count,
        "merged_tree_doc_count": merged_doc_count,
        "top_level_algorithm_doc_additions": dict(sorted(top_level_algo_docs.items(), key=lambda kv: (-kv[1], kv[0]))),
    }

    payload = {
        "summary": out_summary,
        "algorithm_assignments": assignment_rows,
        "unresolved_algorithm_assignments": unresolved_rows,
        "tree": merged_tree,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_json = args.output_dir / f"{args.run_name}_{stamp}.json"
    out_md = args.output_dir / f"{args.run_name}_{stamp}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# Algorithm Merge Into Taxonomy")
    lines.append("")
    lines.append(f"- model_id: `{model_id}`")
    lines.append(f"- needs_algorithm groups: `{out_summary['needs_algorithm_group_count']}`")
    lines.append(f"- needs_algorithm docs: `{out_summary['needs_algorithm_doc_count']}`")
    lines.append(f"- algorithm subclusters: `{out_summary['algorithm_subcluster_count']}`")
    lines.append(
        f"- mapped subclusters/docs: `{out_summary['mapped_algorithm_subcluster_count']}` / "
        f"`{out_summary['mapped_algorithm_doc_count']}`"
    )
    lines.append(
        f"- unresolved subclusters/docs: `{out_summary['unresolved_algorithm_subcluster_count']}` / "
        f"`{out_summary['unresolved_algorithm_doc_count']}`"
    )
    lines.append("")
    lines.append("## Top-Level Added Docs")
    lines.append("")
    lines.append("| Top Level | Added Docs |")
    lines.append("|---|---:|")
    for top, docs in out_summary["top_level_algorithm_doc_additions"].items():
        lines.append(f"| `{top}` | {docs} |")
    lines.append("")
    lines.append("## Sample Algorithm Assignments")
    lines.append("")
    lines.append("| Source Cluster | Subcluster | Docs | Status | Target Leaf | Similarity |")
    lines.append("|---:|---:|---:|---|---|---:|")
    for row in assignment_rows[:30]:
        target = (
            f"{row['matched_top_level']} / {row['matched_sub_level']} / {row['matched_canonical_label']}"
            if row["mapping_status"] == "mapped"
            else "UNRESOLVED"
        ).replace("|", "\\|")
        lines.append(
            f"| {row['source_cluster_id']} | {row['subcluster_local_id']} | {row['subcluster_doc_count']} | "
            f"`{row['mapping_status']}` | `{target}` | {row['similarity_to_matched_leaf']:.4f} |"
        )
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[algo-merge] output_json: {out_json}")
    print(f"[algo-merge] output_md: {out_md}")
    print(
        f"[algo-merge] pass1_docs={pass1_doc_count} merged_docs={merged_doc_count} "
        f"added_docs={mapped_docs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
