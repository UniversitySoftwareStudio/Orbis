#!/usr/bin/env python3
"""
Analyze umbrella URL groups for tail-depth diversity.

Goal:
- Detect groups where deeper URL segments carry semantic signal.
- Detect groups where deeper URL segments are too similar/dynamic (low semantic signal).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import func, select


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.models import KnowledgeBase  # noqa: E402
from database.session import SessionLocal  # noqa: E402


DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


def _parse_url(raw_url: str) -> tuple[str, list[str]]:
    p = urlparse((raw_url or "").strip())
    host = (p.netloc or "unknown").lower()
    segments = [s.lower() for s in (p.path or "").split("/") if s]
    return host, segments


def _is_dynamic(seg: str) -> bool:
    s = (seg or "").strip().lower()
    if not s:
        return False
    if s.isdigit():
        return True
    if re.fullmatch(r"\d{4}(-\d{1,2}){1,2}", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8,}", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", s):
        return True
    digits = sum(ch.isdigit() for ch in s)
    if len(s) >= 5 and digits / len(s) >= 0.6:
        return True
    return False


def _normalize_seg_for_pattern(seg: str) -> str:
    if _is_dynamic(seg):
        return "<id>"
    s = re.sub(r"\d+", "<n>", seg)
    return s


def _entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counter.values():
        p = c / total
        h -= p * math.log2(p)
    return h


def _fetch_url_map() -> dict[str, str]:
    db = SessionLocal()
    try:
        rows = list(
            db.execute(
                select(KnowledgeBase.id, func.coalesce(KnowledgeBase.url, ""))
                .where(KnowledgeBase.url.is_not(None))
            ).all()
        )
        return {str(r[0]): (r[1] or "") for r in rows}
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tail-depth diversity analyzer for umbrella URL groups")
    parser.add_argument(
        "--input-json",
        type=Path,
        required=True,
        help="Path to url_umbrella_parents dynamic output JSON.",
    )
    parser.add_argument("--run-name", type=str, default="url_parent_depth_diversity")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_json.exists():
        raise FileNotFoundError(f"Input not found: {args.input_json}")

    data = json.loads(args.input_json.read_text(encoding="utf-8"))
    depth_results = data.get("depth_results", {})
    if "dynamic" not in depth_results:
        raise RuntimeError("Input JSON does not contain depth_results.dynamic")

    clusters = depth_results["dynamic"].get("clusters", [])
    url_map = _fetch_url_map()

    group_rows = []
    for c in clusters:
        cluster_id = c["cluster_id"]
        first_counter: Counter[str] = Counter()
        tail_pattern_counter: Counter[str] = Counter()
        tail_raw_counter: Counter[str] = Counter()
        total_docs = 0
        no_tail_docs = 0
        dynamic_first_docs = 0
        semantic_first_docs = 0
        total_tail_tokens = 0
        dynamic_tail_tokens = 0
        semantic_tail_tokens = 0
        docs_with_tail = 0
        numeric_only_tail_docs = 0
        all_dynamic_tail_docs = 0
        semantic_tail_docs = 0

        for parent in c.get("parents", []):
            depth = int(parent.get("chosen_depth", 0) or 0)
            for doc_id in parent.get("doc_ids", []):
                raw_url = url_map.get(str(doc_id), "")
                _host, segments = _parse_url(raw_url)
                if depth <= 0:
                    tail = segments
                else:
                    tail = segments[depth:]
                total_docs += 1

                if not tail:
                    first_counter["__none__"] += 1
                    no_tail_docs += 1
                    continue

                first = tail[0]
                first_counter[first] += 1

                if _is_dynamic(first):
                    dynamic_first_docs += 1
                elif re.search(r"[a-z]", first):
                    semantic_first_docs += 1

                docs_with_tail += 1
                total_tail_tokens += len(tail)
                doc_has_dynamic = False
                doc_has_semantic = False
                doc_all_dynamic = True
                for token in tail:
                    if _is_dynamic(token):
                        dynamic_tail_tokens += 1
                        doc_has_dynamic = True
                    elif re.search(r"[a-z]", token):
                        semantic_tail_tokens += 1
                        doc_has_semantic = True
                        doc_all_dynamic = False
                    elif doc_all_dynamic and not _is_dynamic(token):
                        doc_all_dynamic = False

                if doc_has_semantic:
                    semantic_tail_docs += 1
                if doc_has_dynamic and not doc_has_semantic:
                    numeric_only_tail_docs += 1
                if doc_has_dynamic and doc_all_dynamic:
                    all_dynamic_tail_docs += 1

                normalized_tail = "/".join(_normalize_seg_for_pattern(s) for s in tail) or "__none__"
                raw_tail = "/".join(tail) or "__none__"
                tail_pattern_counter[normalized_tail] += 1
                tail_raw_counter[raw_tail] += 1

        if total_docs == 0:
            continue

        first_non_none = Counter({k: v for k, v in first_counter.items() if k != "__none__"})
        unique_first = len(first_non_none)
        dominant_first_share = max(first_counter.values()) / total_docs
        first_tail_entropy = _entropy(first_non_none)
        no_tail_ratio = no_tail_docs / total_docs
        dynamic_first_ratio = dynamic_first_docs / total_docs
        semantic_first_ratio = semantic_first_docs / total_docs

        unique_tail_patterns = len(tail_pattern_counter)
        dominant_tail_pattern_share = (
            max(tail_pattern_counter.values()) / max(1, docs_with_tail) if docs_with_tail > 0 else 1.0
        )
        tail_pattern_entropy = _entropy(tail_pattern_counter)
        dynamic_tail_ratio = dynamic_tail_tokens / max(1, total_tail_tokens)
        semantic_tail_ratio = semantic_tail_tokens / max(1, total_tail_tokens)
        avg_tail_len = total_tail_tokens / max(1, docs_with_tail)
        numeric_only_tail_ratio = numeric_only_tail_docs / max(1, docs_with_tail)
        all_dynamic_tail_doc_ratio = all_dynamic_tail_docs / max(1, docs_with_tail)
        semantic_tail_doc_ratio = semantic_tail_docs / max(1, docs_with_tail)

        # Minimal decision logic:
        # 1) numeric-only tails across full depth -> needs algorithm
        # 2) repetitive/similar tails -> needs algorithm
        # 3) diverse semantic tails -> URL-only categorization
        numeric_only_low_signal = (
            docs_with_tail > 0
            and all_dynamic_tail_doc_ratio >= 0.80
            and semantic_tail_doc_ratio <= 0.20
        )
        dynamic_dominant_low_signal = (
            docs_with_tail > 0
            and dynamic_tail_ratio >= 0.70
            and semantic_tail_ratio <= 0.30
        )
        repetitive_low_signal = (
            dominant_tail_pattern_share >= 0.60
            or tail_pattern_entropy <= 1.20
            or unique_tail_patterns <= 2
        )
        semantic_diverse = (
            semantic_tail_ratio >= 0.45
            and semantic_tail_doc_ratio >= 0.45
            and unique_tail_patterns >= 4
            and tail_pattern_entropy >= 1.50
            and dominant_tail_pattern_share <= 0.55
        )

        if no_tail_ratio >= 0.90:
            depth_signal = "shallow_only"
            decision = "url_only_parent"
        elif numeric_only_low_signal:
            depth_signal = "numeric_only_tail_low_signal"
            decision = "needs_algorithm"
        elif dynamic_dominant_low_signal:
            depth_signal = "numeric_dominant_tail_low_signal"
            decision = "needs_algorithm"
        elif repetitive_low_signal:
            depth_signal = "too_similar_repetitive"
            decision = "needs_algorithm"
        elif semantic_diverse:
            depth_signal = "diversified_semantic"
            decision = "url_only_categorize"
        else:
            depth_signal = "mixed"
            decision = "needs_algorithm"

        row = {
            "cluster_id": cluster_id,
            "doc_count": total_docs,
            "parent_count": c.get("parent_count", 0),
            "representative_parent": c.get("representative_parent", ""),
            "depth_signal": depth_signal,
            "decision": decision,
            "no_tail_ratio": round(no_tail_ratio, 6),
            "dynamic_first_ratio": round(dynamic_first_ratio, 6),
            "semantic_first_ratio": round(semantic_first_ratio, 6),
            "dynamic_tail_ratio": round(dynamic_tail_ratio, 6),
            "semantic_tail_ratio": round(semantic_tail_ratio, 6),
            "numeric_only_tail_ratio": round(numeric_only_tail_ratio, 6),
            "all_dynamic_tail_doc_ratio": round(all_dynamic_tail_doc_ratio, 6),
            "semantic_tail_doc_ratio": round(semantic_tail_doc_ratio, 6),
            "avg_tail_len": round(avg_tail_len, 6),
            "unique_first_tail_segments": unique_first,
            "unique_tail_patterns": unique_tail_patterns,
            "tail_entropy": round(first_tail_entropy, 6),
            "tail_pattern_entropy": round(tail_pattern_entropy, 6),
            "dominant_first_share": round(dominant_first_share, 6),
            "dominant_tail_pattern_share": round(dominant_tail_pattern_share, 6),
            "top_first_tail_segments": first_counter.most_common(8),
            "top_tail_patterns": tail_pattern_counter.most_common(8),
            "top_raw_tail_paths": tail_raw_counter.most_common(8),
        }
        group_rows.append(row)

    group_rows.sort(key=lambda x: (-x["doc_count"], x["cluster_id"]))
    summary = {
        "total_groups": len(group_rows),
        "url_only_parent": sum(1 for r in group_rows if r["decision"] == "url_only_parent"),
        "url_only_categorize": sum(1 for r in group_rows if r["decision"] == "url_only_categorize"),
        "needs_algorithm": sum(1 for r in group_rows if r["decision"] == "needs_algorithm"),
    }

    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_input": str(args.input_json),
        "summary": summary,
        "groups": group_rows,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_json = args.output_dir / f"{args.run_name}_{stamp}.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[depth-diversity] output: {out_json}")
    print(f"[depth-diversity] summary: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
