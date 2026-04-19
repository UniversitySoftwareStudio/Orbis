#!/usr/bin/env python3
"""Step 02: classify detected parent URL groups as known or unknown."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import bindparam, text


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.session import SessionLocal  # noqa: E402


DEFAULT_INPUT_JSON = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "01_group_parent_urls"
    / "parent_groups_result.json"
)
DEFAULT_OUTPUT_DIR = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "02_classify_unknowns"
)


def _parse_url(raw_url: str) -> tuple[str, list[str]]:
    text = (raw_url or "").strip()
    if not text:
        return "unknown", []
    if "://" not in text:
        text = f"https://{text.lstrip('/')}"
    parsed = urlparse(text)
    host = (parsed.netloc or "unknown").lower().strip() or "unknown"
    segments = [s.lower() for s in (parsed.path or "").split("/") if s]
    return host, segments


def _is_dynamic(seg: str) -> bool:
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


def _is_semantic(seg: str) -> bool:
    s = (seg or "").strip().lower()
    if not s:
        return False
    if s in {"tr", "en", "www"}:
        return False
    if _is_dynamic(s):
        return False
    return bool(re.search(r"[a-z]", s))


def _normalize_tail_token(seg: str) -> str:
    if _is_dynamic(seg):
        return "<id>"
    return re.sub(r"\d+", "<n>", seg)


def _entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    out = 0.0
    for count in counter.values():
        p = count / total
        out -= p * math.log2(p)
    return out


def _chunked(items: list[str], chunk_size: int) -> list[list[str]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _build_reason_text(
    *,
    reason_code: str,
    no_tail_ratio: float,
    dynamic_tail_ratio: float,
    semantic_tail_ratio: float,
    unique_tail_patterns: int,
    tail_pattern_entropy: float,
    dominant_tail_pattern_share: float,
) -> str:
    if reason_code == "parent_explains_group_no_tail":
        return (
            "Known: most URLs end at parent depth, so this parent already explains the group "
            f"(no_tail_ratio={no_tail_ratio:.2f})."
        )
    if reason_code == "semantic_tail_signal":
        return (
            "Known: tail URLs carry clear semantic structure and variety "
            f"(semantic_tail_ratio={semantic_tail_ratio:.2f}, unique_tail_patterns={unique_tail_patterns}, "
            f"tail_entropy={tail_pattern_entropy:.2f}, dominant_pattern_share={dominant_tail_pattern_share:.2f})."
        )
    if reason_code == "dynamic_tail_low_signal":
        return (
            "Unknown: tail URLs are mostly dynamic/id-like and weak in semantic signal "
            f"(dynamic_tail_ratio={dynamic_tail_ratio:.2f}, semantic_tail_ratio={semantic_tail_ratio:.2f})."
        )
    if reason_code == "repetitive_tail_low_signal":
        return (
            "Unknown: tail URLs are repetitive with low information gain "
            f"(dominant_pattern_share={dominant_tail_pattern_share:.2f}, tail_entropy={tail_pattern_entropy:.2f})."
        )
    return (
        "Unknown: tail signals are mixed or weak and do not meet known-group thresholds "
        f"(semantic_tail_ratio={semantic_tail_ratio:.2f}, dynamic_tail_ratio={dynamic_tail_ratio:.2f}, "
        f"unique_tail_patterns={unique_tail_patterns})."
    )


def _fetch_url_map(doc_ids: list[str], chunk_size: int) -> dict[str, str]:
    if not doc_ids:
        return {}
    db = SessionLocal()
    try:
        stmt = text(
            """
            SELECT id::text AS id, COALESCE(url, '') AS url
            FROM knowledge_base
            WHERE id::text IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
        out: dict[str, str] = {}
        for chunk in _chunked(doc_ids, chunk_size=chunk_size):
            rows = list(db.execute(stmt, {"ids": chunk}).all())
            for row in rows:
                out[str(row[0])] = str(row[1] or "")
        return out
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step 02: classify parent URL groups as known/unknown.")
    parser.add_argument("--input-json", type=Path, default=DEFAULT_INPUT_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--db-chunk-size", type=int, default=2000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_json.exists():
        raise FileNotFoundError(f"Input not found: {args.input_json}")
    if args.db_chunk_size <= 0:
        raise ValueError("--db-chunk-size must be > 0")

    src = json.loads(args.input_json.read_text(encoding="utf-8"))
    groups = list(src.get("parent_groups", []))
    if not groups:
        raise RuntimeError("No parent_groups found in input JSON.")

    all_doc_ids: list[str] = []
    for group in groups:
        all_doc_ids.extend([str(v) for v in group.get("doc_ids", [])])
    all_doc_ids = sorted(set(all_doc_ids))
    url_map = _fetch_url_map(all_doc_ids, chunk_size=args.db_chunk_size)

    rows: list[dict[str, Any]] = []
    for group in groups:
        group_id = int(group.get("group_id", 0))
        parent_key = str(group.get("parent_key", ""))
        chosen_depth = int(group.get("chosen_depth", 0))
        doc_ids = [str(v) for v in group.get("doc_ids", [])]
        doc_count = len(doc_ids)

        first_counter: Counter[str] = Counter()
        tail_pattern_counter: Counter[str] = Counter()
        dynamic_tail_tokens = 0
        semantic_tail_tokens = 0
        total_tail_tokens = 0
        no_tail_docs = 0
        docs_with_tail = 0

        for doc_id in doc_ids:
            url = url_map.get(doc_id, "")
            _host, segments = _parse_url(url)
            tail = segments[chosen_depth:] if chosen_depth > 0 else segments

            if not tail:
                no_tail_docs += 1
                first_counter["__none__"] += 1
                continue

            docs_with_tail += 1
            first_counter[tail[0]] += 1

            normalized_tail = "/".join(_normalize_tail_token(token) for token in tail) or "__none__"
            tail_pattern_counter[normalized_tail] += 1

            for token in tail:
                total_tail_tokens += 1
                if _is_dynamic(token):
                    dynamic_tail_tokens += 1
                elif _is_semantic(token):
                    semantic_tail_tokens += 1

        no_tail_ratio = no_tail_docs / max(1, doc_count)
        dynamic_tail_ratio = dynamic_tail_tokens / max(1, total_tail_tokens)
        semantic_tail_ratio = semantic_tail_tokens / max(1, total_tail_tokens)
        unique_tail_patterns = len(tail_pattern_counter)
        dominant_tail_pattern_share = (
            max(tail_pattern_counter.values()) / max(1, docs_with_tail) if docs_with_tail > 0 else 1.0
        )
        tail_pattern_entropy = _entropy(tail_pattern_counter)

        if no_tail_ratio >= 0.85:
            decision = "known"
            reason_code = "parent_explains_group_no_tail"
        elif (
            semantic_tail_ratio >= 0.45
            and unique_tail_patterns >= 4
            and tail_pattern_entropy >= 1.50
            and dominant_tail_pattern_share <= 0.55
        ):
            decision = "known"
            reason_code = "semantic_tail_signal"
        elif dynamic_tail_ratio >= 0.70 and semantic_tail_ratio <= 0.30:
            decision = "unknown"
            reason_code = "dynamic_tail_low_signal"
        elif dominant_tail_pattern_share >= 0.60 or tail_pattern_entropy <= 1.20:
            decision = "unknown"
            reason_code = "repetitive_tail_low_signal"
        else:
            decision = "unknown"
            reason_code = "mixed_or_weak_signal"

        reason_text = _build_reason_text(
            reason_code=reason_code,
            no_tail_ratio=no_tail_ratio,
            dynamic_tail_ratio=dynamic_tail_ratio,
            semantic_tail_ratio=semantic_tail_ratio,
            unique_tail_patterns=unique_tail_patterns,
            tail_pattern_entropy=tail_pattern_entropy,
            dominant_tail_pattern_share=dominant_tail_pattern_share,
        )

        rows.append(
            {
                "group_id": group_id,
                "parent_key": parent_key,
                "chosen_depth": chosen_depth,
                "doc_count": doc_count,
                "decision": decision,
                "reason_code": reason_code,
                "reason_text": reason_text,
                "no_tail_ratio": round(no_tail_ratio, 6),
                "dynamic_tail_ratio": round(dynamic_tail_ratio, 6),
                "semantic_tail_ratio": round(semantic_tail_ratio, 6),
                "unique_tail_patterns": unique_tail_patterns,
                "tail_pattern_entropy": round(tail_pattern_entropy, 6),
                "dominant_tail_pattern_share": round(dominant_tail_pattern_share, 6),
                "top_first_tail_segments": first_counter.most_common(8),
                "top_tail_patterns": tail_pattern_counter.most_common(8),
                "sample_urls": group.get("sample_urls", []),
            }
        )

    rows.sort(key=lambda r: (-int(r["doc_count"]), int(r["group_id"])))
    known_rows = [r for r in rows if r["decision"] == "known"]
    unknown_rows = [r for r in rows if r["decision"] == "unknown"]

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_input_json": str(args.input_json),
        "total_groups": len(rows),
        "total_docs": sum(int(r["doc_count"]) for r in rows),
        "known_groups": len(known_rows),
        "known_docs": sum(int(r["doc_count"]) for r in known_rows),
        "unknown_groups": len(unknown_rows),
        "unknown_docs": sum(int(r["doc_count"]) for r in unknown_rows),
    }

    result_payload = {
        "summary": summary,
        "groups": rows,
    }
    quick_payload = {
        "summary": summary,
        "known_top_groups": [
            {
                "group_id": int(r["group_id"]),
                "parent_key": str(r["parent_key"]),
                "doc_count": int(r["doc_count"]),
                "reason_code": str(r["reason_code"]),
                "reason_text": str(r["reason_text"]),
            }
            for r in known_rows[:20]
        ],
        "unknown_top_groups": [
            {
                "group_id": int(r["group_id"]),
                "parent_key": str(r["parent_key"]),
                "doc_count": int(r["doc_count"]),
                "reason_code": str(r["reason_code"]),
                "reason_text": str(r["reason_text"]),
            }
            for r in unknown_rows[:20]
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_json = args.output_dir / "group_classification_result.json"
    quick_json = args.output_dir / "group_classification_quick.json"
    quick_md = args.output_dir / "classification_quick.md"

    result_json.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    quick_json.write_text(json.dumps(quick_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# Step 02 - Group Classification")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- total_groups: `{summary['total_groups']}`")
    lines.append(f"- total_docs: `{summary['total_docs']}`")
    lines.append(f"- known_groups / known_docs: `{summary['known_groups']}` / `{summary['known_docs']}`")
    lines.append(f"- unknown_groups / unknown_docs: `{summary['unknown_groups']}` / `{summary['unknown_docs']}`")
    lines.append("")
    lines.append("## Largest Unknown Groups")
    lines.append("")
    lines.append("| # | Group | Parent | Docs | Reason |")
    lines.append("|---:|---:|---|---:|---|")
    for i, row in enumerate(unknown_rows[:20], start=1):
        p = str(row["parent_key"]).replace("|", "\\|")
        reason = str(row["reason_text"]).replace("|", "\\|")
        lines.append(f"| {i} | {row['group_id']} | `{p}` | {row['doc_count']} | {reason} |")
    quick_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[02] result_json={result_json}")
    print(f"[02] quick_json={quick_json}")
    print(f"[02] quick_md={quick_md}")
    print(
        "[02] summary "
        f"groups={summary['total_groups']} known={summary['known_groups']} unknown={summary['unknown_groups']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
