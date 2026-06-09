#!/usr/bin/env python3
"""
Find umbrella URL parents at shallow depth (2-3 levels) using URL-char similarity.

This keeps things intentionally simple:
- truncate URLs to shallow parent depth
- cluster those parent strings by char similarity
- output a flat parent list (no deep nesting)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.parse import urlparse

from dotenv import load_dotenv
from scipy.sparse import eye
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from sqlalchemy import func, select


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.models import KnowledgeBase  # noqa: E402
from database.session import SessionLocal  # noqa: E402


DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


def _normalize_parent(raw_url: str, depth: int) -> str:
    p = urlparse((raw_url or "").strip())
    host = (p.netloc or "unknown").lower()
    segments = [s for s in (p.path or "").split("/") if s]
    parent_segments = segments[: max(0, depth)]
    if not parent_segments:
        return f"{host}/"
    return f"{host}/" + "/".join(parent_segments).lower()


def _parse_url_parts(raw_url: str) -> tuple[str, list[str]]:
    p = urlparse((raw_url or "").strip())
    host = (p.netloc or "unknown").lower()
    segments = [s.lower() for s in (p.path or "").split("/") if s]
    return host, segments


def _parent_key(host: str, segments: list[str], depth: int) -> str:
    if depth <= 0 or not segments:
        return f"{host}/"
    return f"{host}/" + "/".join(segments[:depth])


def _is_dynamic_segment(seg: str) -> bool:
    s = (seg or "").strip().lower()
    if not s:
        return False
    if s.isdigit():
        return True
    if re.fullmatch(r"\d{4}(-\d{1,2}){1,2}", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8,}", s):
        return True
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        s,
    ):
        return True
    digits = sum(ch.isdigit() for ch in s)
    if len(s) >= 5 and digits / len(s) >= 0.6:
        return True
    return False


def _is_semantic_segment(seg: str) -> bool:
    s = (seg or "").strip().lower()
    return bool(s) and not _is_dynamic_segment(s) and bool(re.search(r"[a-z]", s))


def _extract_json_obj(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    first = raw.find("{")
    if first >= 0:
        decoder = json.JSONDecoder()
        try:
            obj, _idx = decoder.raw_decode(raw[first:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return {}


def _ollama_decide_deepen(
    *,
    ollama_url: str,
    ollama_model: str,
    timeout_seconds: float,
    parent_key: str,
    parent_depth: int,
    doc_count: int,
    next_counter: Counter[str],
) -> tuple[bool, dict[str, Any]]:
    non_none = {k: v for k, v in next_counter.items() if k != "__none__"}
    total = sum(non_none.values())
    if total <= 0:
        return False, {"source": "fastpath", "reason": "no_next_segments"}

    dynamic_docs = sum(v for k, v in non_none.items() if _is_dynamic_segment(k))
    semantic_docs = sum(v for k, v in non_none.items() if _is_semantic_segment(k))
    dynamic_ratio = dynamic_docs / max(1, total)
    semantic_ratio = semantic_docs / max(1, total)
    unique_semantic = sum(1 for k in non_none if _is_semantic_segment(k))
    dominant_share = max(non_none.values()) / max(1, total)

    top_items = sorted(non_none.items(), key=lambda x: x[1], reverse=True)[:12]
    top_lines = "\n".join(f"- {k}: {v}" for k, v in top_items)
    prompt = (
        "You are deciding URL taxonomy depth.\n"
        f"Current parent: {parent_key}\n"
        f"Current depth: {parent_depth}\n"
        f"Documents under parent: {doc_count}\n"
        f"Child-segment stats: total_child_docs={total}, unique_children={len(non_none)}, "
        f"unique_semantic={unique_semantic}, semantic_ratio={semantic_ratio:.3f}, "
        f"dynamic_ratio={dynamic_ratio:.3f}, dominant_child_share={dominant_share:.3f}\n"
        "Top child segments (segment: count):\n"
        f"{top_lines}\n\n"
        "Decision rules:\n"
        "1) If children are mostly IDs/files/codes/repetitive tokens, STOP.\n"
        "2) If children are multiple meaningful category words, DEEPEN.\n"
        "Return strict JSON only with this schema:\n"
        '{"decision":"DEEPEN","confidence":0.0,"reason":"short reason"}\n'
        'The "decision" value must be exactly "DEEPEN" or "STOP".'
    )

    endpoint = ollama_url.rstrip("/") + "/api/generate"
    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=timeout_seconds) as resp:
            parsed = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        return False, {"source": "error", "reason": f"ollama_error:{exc}"}

    raw = str(parsed.get("response", "")).strip()
    obj = _extract_json_obj(raw)
    decision_raw = str(obj.get("decision", "")).strip().upper()
    if decision_raw not in {"DEEPEN", "STOP"}:
        # Fallback: shallow by default when output is malformed.
        return False, {"source": "fallback", "reason": "malformed_model_output", "raw": raw[:240]}

    decision = decision_raw == "DEEPEN"
    return decision, {
        "source": "ollama",
        "decision": decision_raw,
        "confidence": obj.get("confidence"),
        "reason": obj.get("reason", ""),
    }


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


def _cluster_parent_strings(parent_keys: list[str], similarity_threshold: float) -> tuple[int, list[int]]:
    if not parent_keys:
        return 0, []
    if len(parent_keys) == 1:
        return 1, [1]
    vec = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), lowercase=False, min_df=1)
    x = vec.fit_transform(parent_keys)
    nn = NearestNeighbors(
        radius=(1.0 - similarity_threshold),
        metric="cosine",
        algorithm="brute",
        n_jobs=-1,
    )
    nn.fit(x)
    graph = nn.radius_neighbors_graph(x, mode="connectivity")
    graph = graph + eye(graph.shape[0], format="csr")
    n_groups, labels = connected_components(csgraph=graph, directed=False, return_labels=True)
    return int(n_groups), [int(v) + 1 for v in labels]


def _build_dynamic_parent_map(
    docs: list[tuple[str, str]],
    *,
    min_depth: int,
    max_depth: int,
    min_parent_docs: int,
    depth_decider: str = "heuristic",
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "qwen:4b",
    ollama_timeout_seconds: float = 30.0,
) -> tuple[dict[str, list[str]], dict[str, int], dict[str, Any]]:
    parsed: list[tuple[str, str, list[str]]] = []
    counts_by_depth: dict[int, Counter[str]] = defaultdict(Counter)
    next_by_prefix: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)

    for doc_id, raw_url in docs:
        host, segments = _parse_url_parts(raw_url)
        parsed.append((doc_id, host, segments))
        if not segments:
            continue
        for d in range(1, min(max_depth, len(segments)) + 1):
            counts_by_depth[d][_parent_key(host, segments, d)] += 1
        for d in range(min_depth, min(max_depth, len(segments) + 1)):
            k = _parent_key(host, segments, d)
            nxt = segments[d] if len(segments) > d else "__none__"
            next_by_prefix[(d, k)][nxt] += 1

    parent_to_doc_ids: dict[str, list[str]] = defaultdict(list)
    parent_depths: dict[str, int] = {}
    chosen_depth_hist = Counter()
    decision_cache: dict[tuple[int, str], tuple[bool, dict[str, Any]]] = {}
    decider_meta = {
        "depth_decider": depth_decider,
        "ollama_url": ollama_url,
        "ollama_model": ollama_model,
        "prefixes_considered": 0,
        "ollama_calls": 0,
        "ollama_deepen": 0,
        "ollama_stop": 0,
        "ollama_errors": 0,
    }

    def _decide_deepen(prefix_depth: int, prefix_key: str) -> bool:
        key = (prefix_depth, prefix_key)
        if key in decision_cache:
            return decision_cache[key][0]

        decider_meta["prefixes_considered"] += 1
        next_counter = next_by_prefix.get(key, Counter())
        non_none = {k: v for k, v in next_counter.items() if k != "__none__"}
        total_non_none = sum(non_none.values())
        if total_non_none <= 0:
            decision_cache[key] = (False, {"source": "fastpath", "reason": "no_children"})
            return False

        # Heuristic fallback used directly in heuristic mode and as guardrails around LLM mode.
        dynamic_docs = sum(v for k, v in non_none.items() if _is_dynamic_segment(k))
        semantic_docs = sum(v for k, v in non_none.items() if _is_semantic_segment(k))
        semantic_ratio = semantic_docs / max(1, total_non_none)
        dynamic_ratio = dynamic_docs / max(1, total_non_none)
        unique_semantic = sum(1 for k in non_none if _is_semantic_segment(k))
        dominant_share = max(non_none.values()) / max(1, total_non_none)
        heuristic_deepen = (
            unique_semantic >= 2
            and semantic_ratio >= 0.40
            and dynamic_ratio <= 0.50
            and dominant_share <= 0.80
        )

        if depth_decider == "heuristic":
            decision_cache[key] = (heuristic_deepen, {"source": "heuristic"})
            return heuristic_deepen

        # Fast-path obvious non-semantic groups before calling Ollama.
        if unique_semantic == 0 or dynamic_ratio >= 0.80:
            decision_cache[key] = (False, {"source": "fastpath", "reason": "dynamic_or_nonsemantic"})
            return False

        decider_meta["ollama_calls"] += 1
        llm_deepen, llm_meta = _ollama_decide_deepen(
            ollama_url=ollama_url,
            ollama_model=ollama_model,
            timeout_seconds=ollama_timeout_seconds,
            parent_key=prefix_key,
            parent_depth=prefix_depth,
            doc_count=counts_by_depth[prefix_depth][prefix_key],
            next_counter=next_counter,
        )

        source = str(llm_meta.get("source", ""))
        if source in {"error", "fallback"}:
            decider_meta["ollama_errors"] += 1
            decision = heuristic_deepen
        else:
            decision = llm_deepen

        if decision:
            decider_meta["ollama_deepen"] += 1
        else:
            decider_meta["ollama_stop"] += 1

        decision_cache[key] = (decision, llm_meta)
        return decision

    for doc_id, host, segments in parsed:
        if not segments:
            parent = _parent_key(host, segments, 0)
            parent_to_doc_ids[parent].append(doc_id)
            parent_depths[parent] = 0
            chosen_depth_hist[0] += 1
            continue

        max_allowed = min(max_depth, len(segments))
        min_d = min(min_depth, max_allowed)
        depth = max_allowed

        # Step 1: never end at dynamic tokens and enforce minimum parent support.
        while depth > min_d and _is_dynamic_segment(segments[depth - 1]):
            depth -= 1
        while depth > min_d:
            key_at_depth = _parent_key(host, segments, depth)
            if counts_by_depth[depth][key_at_depth] >= min_parent_docs:
                break
            depth -= 1

        # Step 2: in Ollama mode, stop early when parent should remain umbrella.
        if depth_decider in {"heuristic", "ollama"} and max_allowed > min_d:
            candidate = min_d
            while candidate < depth:
                candidate_key = _parent_key(host, segments, candidate)
                next_key = _parent_key(host, segments, candidate + 1)
                if _is_dynamic_segment(segments[candidate]):
                    break
                if counts_by_depth[candidate + 1][next_key] < min_parent_docs:
                    break
                if _decide_deepen(candidate, candidate_key):
                    candidate += 1
                    continue
                break
            depth = candidate

        parent = _parent_key(host, segments, depth)
        parent_to_doc_ids[parent].append(doc_id)
        parent_depths[parent] = depth
        chosen_depth_hist[depth] += 1

    meta = {
        "chosen_depth_hist_docs": dict(chosen_depth_hist),
        "min_depth": min_depth,
        "max_depth": max_depth,
        "min_parent_docs": min_parent_docs,
        "depth_decider": depth_decider,
        "decider_meta": decider_meta,
    }
    return parent_to_doc_ids, parent_depths, meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shallow umbrella URL parent finder (depth 2-3)")
    parser.add_argument("--sample-size", type=int, default=0, help="0 means all docs")
    parser.add_argument("--depths", type=str, default="2,3", help='Comma-separated depths, e.g. "2,3"')
    parser.set_defaults(dynamic_depth=True)
    parser.add_argument(
        "--dynamic-depth",
        dest="dynamic_depth",
        action="store_true",
        help="Choose depth per URL dynamically between min/max depth (default on).",
    )
    parser.add_argument(
        "--no-dynamic-depth",
        dest="dynamic_depth",
        action="store_false",
        help="Use fixed depths only from --depths.",
    )
    parser.add_argument("--min-depth", type=int, default=2)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument(
        "--min-parent-docs",
        type=int,
        default=6,
        help="When dynamic depth is on, back off depth until parent has at least this many docs.",
    )
    parser.add_argument(
        "--depth-decider",
        type=str,
        choices=["heuristic", "ollama"],
        default="heuristic",
        help="How to decide whether to go deeper within dynamic depth range.",
    )
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434")
    parser.add_argument("--ollama-model", type=str, default="qwen:4b")
    parser.add_argument("--ollama-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--similarity-threshold", type=float, default=0.85)
    parser.add_argument("--run-name", type=str, default="url_umbrella_parents")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_size < 0:
        raise ValueError("--sample-size must be >= 0")
    if not (0.0 < args.similarity_threshold <= 1.0):
        raise ValueError("--similarity-threshold must be in (0, 1]")
    if args.min_depth <= 0 or args.max_depth <= 0:
        raise ValueError("--min-depth and --max-depth must be > 0")
    if args.min_depth > args.max_depth:
        raise ValueError("--min-depth must be <= --max-depth")
    if args.min_parent_docs <= 0:
        raise ValueError("--min-parent-docs must be > 0")
    if args.ollama_timeout_seconds <= 0:
        raise ValueError("--ollama-timeout-seconds must be > 0")

    depths = []
    for raw in args.depths.split(","):
        raw = raw.strip()
        if not raw:
            continue
        d = int(raw)
        if d <= 0:
            raise ValueError("Depth must be > 0")
        depths.append(d)
    if not depths:
        raise ValueError("--depths produced no valid values")

    t0 = time.perf_counter()
    db = SessionLocal()
    try:
        print("[umbrella] fetching docs...")
        docs = _fetch_docs(db, sample_size=args.sample_size)
        if not docs:
            raise RuntimeError("No docs found")
        print(f"[umbrella] docs fetched: {len(docs)}")

        def _build_depth_result(
            parent_to_doc_ids: dict[str, list[str]],
            parent_depths: dict[str, int] | None = None,
        ) -> tuple[int, dict[str, Any]]:
            parent_keys = sorted(parent_to_doc_ids.keys())
            n_groups, labels = _cluster_parent_strings(parent_keys, args.similarity_threshold)
            cluster_to_parent_idxs: dict[int, list[int]] = defaultdict(list)
            for idx, cluster_id in enumerate(labels):
                cluster_to_parent_idxs[cluster_id].append(idx)

            clusters = []
            for cluster_id, idxs in cluster_to_parent_idxs.items():
                parent_members = []
                total_docs = 0
                for idx in idxs:
                    key = parent_keys[idx]
                    count = len(parent_to_doc_ids[key])
                    total_docs += count
                    row = {
                        "parent_key": key,
                        "doc_count": count,
                        "doc_ids": parent_to_doc_ids[key],
                    }
                    if parent_depths is not None:
                        row["chosen_depth"] = parent_depths.get(key)
                    parent_members.append(row)
                parent_members.sort(key=lambda x: x["doc_count"], reverse=True)
                clusters.append(
                    {
                        "cluster_id": cluster_id,
                        "doc_count": total_docs,
                        "parent_count": len(parent_members),
                        "representative_parent": parent_members[0]["parent_key"],
                        "parents": parent_members,
                    }
                )
            clusters.sort(key=lambda x: x["doc_count"], reverse=True)
            return n_groups, {
                "unique_parent_count": len(parent_keys),
                "parent_cluster_count": n_groups,
                "clusters": clusters,
            }

        depth_results = {}
        dynamic_meta: dict[str, Any] | None = None

        if args.dynamic_depth:
            parent_to_doc_ids, parent_depths, dynamic_meta = _build_dynamic_parent_map(
                docs,
                min_depth=args.min_depth,
                max_depth=args.max_depth,
                min_parent_docs=args.min_parent_docs,
                depth_decider=args.depth_decider,
                ollama_url=args.ollama_url,
                ollama_model=args.ollama_model,
                ollama_timeout_seconds=args.ollama_timeout_seconds,
            )
            n_groups, result = _build_depth_result(parent_to_doc_ids, parent_depths=parent_depths)
            result["mode"] = "dynamic"
            result["depth_range"] = [args.min_depth, args.max_depth]
            result["dynamic_meta"] = dynamic_meta
            depth_results["dynamic"] = result
            print(
                f"[umbrella] dynamic depth range={args.min_depth}-{args.max_depth} "
                f"unique_parents={result['unique_parent_count']} clusters={n_groups}"
            )
        else:
            for depth in depths:
                parent_to_doc_ids: dict[str, list[str]] = defaultdict(list)
                for doc_id, raw_url in docs:
                    parent = _normalize_parent(raw_url, depth=depth)
                    parent_to_doc_ids[parent].append(doc_id)
                n_groups, result = _build_depth_result(parent_to_doc_ids)
                result["mode"] = "fixed"
                result["depth"] = depth
                depth_results[str(depth)] = result
                print(
                    f"[umbrella] depth={depth} unique_parents={result['unique_parent_count']} "
                    f"clusters={n_groups}"
                )

        output = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "config": {
                "sample_size": args.sample_size,
                "depths": depths,
                "dynamic_depth": args.dynamic_depth,
                "min_depth": args.min_depth,
                "max_depth": args.max_depth,
                "min_parent_docs": args.min_parent_docs,
                "depth_decider": args.depth_decider,
                "ollama_url": args.ollama_url,
                "ollama_model": args.ollama_model,
                "ollama_timeout_seconds": args.ollama_timeout_seconds,
                "similarity_threshold": args.similarity_threshold,
            },
            "summary": {
                "total_docs": len(docs),
                "depths": depths,
            },
            "depth_results": depth_results,
            "total_seconds": round(time.perf_counter() - t0, 3),
        }

        args.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = args.output_dir / f"{args.run_name}_{stamp}.json"
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[umbrella] output: {output_path}")
        print(f"[umbrella] done in {output['total_seconds']}s")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
