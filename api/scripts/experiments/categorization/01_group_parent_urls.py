#!/usr/bin/env python3
"""Step 01: group parent URLs with rule-first + AI-on-ambiguous decisions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import func, select


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.models import KnowledgeBase  # noqa: E402
from database.session import SessionLocal  # noqa: E402


DEFAULT_OUTPUT_DIR = (
    API_ROOT / "scripts" / "experiments" / "results" / "categorization" / "flow" / "01_group_parent_urls"
)


def _parse_url(raw_url: str) -> tuple[str, list[str]]:
    text = (raw_url or "").strip()
    if not text:
        return "unknown", []
    if "://" not in text:
        text = f"https://{text.lstrip('/')}"
    parsed = urlparse(text)
    host = (parsed.netloc or "unknown").lower().strip()
    if not host:
        host = "unknown"
    segments = [s.lower() for s in (parsed.path or "").split("/") if s]
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


def _is_semantic_segment(seg: str) -> bool:
    s = (seg or "").strip().lower()
    if not s:
        return False
    if s in {"tr", "en", "www"}:
        return False
    if _is_dynamic_segment(s):
        return False
    return bool(re.search(r"[a-z]", s))


def _extract_json_obj(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    first = text.find("{")
    if first >= 0:
        decoder = json.JSONDecoder()
        try:
            obj, _idx = decoder.raw_decode(text[first:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return {}


def _call_ollama(*, url: str, model: str, timeout_seconds: float, prompt: str) -> tuple[dict[str, Any], str, str | None]:
    endpoint = url.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
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
        return {}, "", f"ollama_error:{exc}"
    raw = str(parsed.get("response", "")).strip()
    obj = _extract_json_obj(raw)
    if not obj:
        return {}, raw, "malformed_model_output"
    return obj, raw, None


def _call_outlier(
    *,
    url: str,
    model: str,
    timeout_seconds: float,
    prompt: str,
    system_message: str,
) -> tuple[dict[str, Any], str, str | None]:
    endpoint = url.rstrip("/") + "/chat/stream"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_message.strip():
        payload["systemMessage"] = system_message.strip()

    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=timeout_seconds) as resp:
            raw_stream = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return {}, "", f"outlier_error:{exc}"

    assistant_parts: list[str] = []
    for line in raw_stream.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            event = json.loads(text)
        except Exception:
            continue
        if isinstance(event, dict) and isinstance(event.get("error"), str) and event["error"].strip():
            return {}, raw_stream[:500], f"outlier_stream_error:{event['error'].strip()}"
        msg = event.get("message", {}) if isinstance(event, dict) else {}
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = str(msg.get("content", ""))
            if content:
                assistant_parts.append(content)

    raw = "".join(assistant_parts).strip()
    obj = _extract_json_obj(raw)
    if not obj:
        return {}, raw, "malformed_model_output"
    return obj, raw, None


def _call_llm(
    *,
    provider: str,
    ollama_url: str,
    ollama_model: str,
    outlier_url: str,
    outlier_model: str,
    outlier_system_message: str,
    timeout_seconds: float,
    prompt: str,
) -> tuple[dict[str, Any], str, str | None]:
    if provider == "outlier":
        return _call_outlier(
            url=outlier_url,
            model=outlier_model,
            timeout_seconds=timeout_seconds,
            prompt=prompt,
            system_message=outlier_system_message,
        )
    return _call_ollama(url=ollama_url, model=ollama_model, timeout_seconds=timeout_seconds, prompt=prompt)


def _fetch_docs(sample_size: int) -> list[tuple[str, str]]:
    db = SessionLocal()
    try:
        stmt = (
            select(KnowledgeBase.id, func.coalesce(KnowledgeBase.url, ""))
            .where(KnowledgeBase.url.is_not(None))
            .order_by(KnowledgeBase.id)
        )
        if sample_size > 0:
            stmt = stmt.limit(sample_size)
        rows = list(db.execute(stmt).all())
        return [(str(r[0]), str(r[1] or "")) for r in rows]
    finally:
        db.close()


def _candidate_metrics(counter: Counter[str]) -> dict[str, Any]:
    non_none = Counter({k: v for k, v in counter.items() if k != "__none__"})
    child_docs = int(sum(non_none.values()))
    distinct_children = int(len(non_none))
    dynamic_docs = int(sum(v for k, v in non_none.items() if _is_dynamic_segment(k)))
    semantic_docs = int(sum(v for k, v in non_none.items() if _is_semantic_segment(k)))
    return {
        "child_docs": child_docs,
        "distinct_children": distinct_children,
        "dynamic_ratio": round(dynamic_docs / max(1, child_docs), 6),
        "semantic_ratio": round(semantic_docs / max(1, child_docs), 6),
        "top_children": non_none.most_common(12),
    }


def _ai_prompt(*, parent_key: str, depth: int, doc_count: int, metrics: dict[str, Any], sample_urls: list[str]) -> str:
    top_children_text = "\n".join([f"- {k}: {v}" for k, v in metrics["top_children"]])
    sample_urls_text = "\n".join([f"- {u}" for u in sample_urls]) if sample_urls else "- none"
    return (
        "You decide if a URL prefix should be an explicit taxonomy parent.\n"
        "Answer with strict JSON only.\n"
        "\n"
        f"Candidate parent: {parent_key}\n"
        f"Depth: {depth}\n"
        f"Documents under candidate: {doc_count}\n"
        f"Distinct child segments: {metrics['distinct_children']}\n"
        f"Semantic child ratio: {metrics['semantic_ratio']}\n"
        f"Dynamic child ratio: {metrics['dynamic_ratio']}\n"
        "Top child segments:\n"
        f"{top_children_text}\n"
        "Sample URLs:\n"
        f"{sample_urls_text}\n"
        "\n"
        "Decision rules:\n"
        "1) PARENT if this prefix is a stable semantic branch with meaningful child structure.\n"
        "2) NOT_PARENT if this prefix is mostly IDs, dates, file shards, or noisy technical paths.\n"
        "\n"
        "Return JSON with keys:\n"
        '{"decision":"PARENT|NOT_PARENT","confidence":0.0,"reason":"short reason"}'
    )


def _safe_str(v: Any) -> str:
    return str(v) if v is not None else ""


def _semantic_segments_in_parent(parent_key: str) -> int:
    raw = (parent_key or "").strip().strip("/")
    if not raw:
        return 0
    tokens = raw.split("/")
    if len(tokens) <= 1:
        return 0
    segments = tokens[1:]
    return sum(1 for s in segments if _is_semantic_segment(s))


def _last_segment(parent_key: str) -> str:
    raw = (parent_key or "").strip().strip("/")
    if not raw:
        return ""
    tokens = raw.split("/")
    if len(tokens) <= 1:
        return ""
    return tokens[-1].strip().lower()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step 01: group parent URLs")
    parser.add_argument("--sample-size", type=int, default=0, help="0 means all docs")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--min-docs", type=int, default=5)
    parser.add_argument("--min-distinct-children", type=int, default=2)

    parser.add_argument("--strong-min-docs", type=int, default=25)
    parser.add_argument("--strong-min-distinct-children", type=int, default=3)
    parser.add_argument("--strong-min-semantic-ratio", type=float, default=0.40)
    parser.add_argument("--strong-max-dynamic-ratio", type=float, default=0.55)

    parser.add_argument("--weak-max-semantic-ratio", type=float, default=0.15)
    parser.add_argument("--weak-min-dynamic-ratio", type=float, default=0.80)
    parser.add_argument(
        "--large-group-doc-threshold",
        type=int,
        default=1000,
        help="Accept very large semantic groups even when normal weak rules would reject.",
    )
    parser.add_argument(
        "--large-group-min-semantic-segments",
        type=int,
        default=1,
        help="Minimum semantic segments in parent path for large-group override.",
    )

    parser.add_argument("--ai-mode", choices=["off", "ambiguous", "all"], default="ambiguous")
    parser.add_argument("--max-ai-candidates", type=int, default=200)
    parser.add_argument("--llm-provider", choices=["outlier", "ollama"], default="outlier")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434")
    parser.add_argument("--ollama-model", type=str, default="qwen:4b")
    parser.add_argument("--outlier-url", type=str, default="http://127.0.0.1:8080")
    parser.add_argument("--outlier-model", type=str, default="claude-opus-4-6")
    parser.add_argument("--outlier-system-message", type=str, default="")
    parser.add_argument("--llm-timeout-seconds", type=float, default=30.0)

    parser.add_argument("--sample-urls-per-candidate", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.sample_size < 0:
        raise ValueError("--sample-size must be >= 0")
    if args.max_depth <= 0:
        raise ValueError("--max-depth must be > 0")
    if args.min_docs <= 0:
        raise ValueError("--min-docs must be > 0")
    if args.min_distinct_children <= 0:
        raise ValueError("--min-distinct-children must be > 0")
    if args.max_ai_candidates < 0:
        raise ValueError("--max-ai-candidates must be >= 0")
    if args.sample_urls_per_candidate <= 0:
        raise ValueError("--sample-urls-per-candidate must be > 0")
    if args.llm_timeout_seconds <= 0:
        raise ValueError("--llm-timeout-seconds must be > 0")
    if args.large_group_doc_threshold <= 0:
        raise ValueError("--large-group-doc-threshold must be > 0")
    if args.large_group_min_semantic_segments < 0:
        raise ValueError("--large-group-min-semantic-segments must be >= 0")

    print("[01] fetching docs...")
    docs = _fetch_docs(sample_size=args.sample_size)
    if not docs:
        raise RuntimeError("No docs found in knowledge_base.url")
    print(f"[01] docs={len(docs)}")

    parsed_docs: list[dict[str, Any]] = []
    parent_doc_counts: dict[tuple[int, str], int] = defaultdict(int)
    next_counts: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)
    sample_urls_by_candidate: dict[tuple[int, str], list[str]] = defaultdict(list)
    parent_link: dict[tuple[int, str], str] = {}

    for doc_id, raw_url in docs:
        host, segments = _parse_url(raw_url)
        parsed_docs.append(
            {
                "doc_id": doc_id,
                "url": raw_url,
                "host": host,
                "segments": segments,
            }
        )
        upto = min(len(segments), args.max_depth)
        if upto <= 0:
            continue
        for depth in range(1, upto + 1):
            key = _parent_key(host, segments, depth)
            parent_doc_counts[(depth, key)] += 1

            samples = sample_urls_by_candidate[(depth, key)]
            if raw_url and len(samples) < args.sample_urls_per_candidate:
                samples.append(raw_url)

            if depth > 1:
                parent_link[(depth, key)] = _parent_key(host, segments, depth - 1)

            nxt = segments[depth] if len(segments) > depth else "__none__"
            next_counts[(depth, key)][nxt] += 1

    accepted_by_depth: dict[int, set[str]] = defaultdict(set)
    decisions: list[dict[str, Any]] = []
    ai_calls = 0
    ai_errors = 0

    for depth in range(1, args.max_depth + 1):
        keys = [k for d, k in parent_doc_counts.keys() if d == depth]
        keys.sort(key=lambda k: (-parent_doc_counts[(depth, k)], k))

        for key in keys:
            doc_count = int(parent_doc_counts[(depth, key)])
            metrics = _candidate_metrics(next_counts[(depth, key)])
            distinct_children = int(metrics["distinct_children"])
            semantic_ratio = float(metrics["semantic_ratio"])
            dynamic_ratio = float(metrics["dynamic_ratio"])
            tail_segment = _last_segment(key)

            parent_required = depth > 1
            linked_parent = parent_link.get((depth, key), "")
            if parent_required and linked_parent not in accepted_by_depth[depth - 1]:
                decisions.append(
                    {
                        "depth": depth,
                        "parent_key": key,
                        "doc_count": doc_count,
                        "distinct_children": distinct_children,
                        "semantic_ratio": semantic_ratio,
                        "dynamic_ratio": dynamic_ratio,
                        "decision": "reject",
                        "decision_source": "parent_not_accepted",
                        "reason": f"parent_not_accepted:{linked_parent}",
                        "top_children": metrics["top_children"],
                    }
                )
                continue

            if tail_segment and _is_dynamic_segment(tail_segment):
                decisions.append(
                    {
                        "depth": depth,
                        "parent_key": key,
                        "doc_count": doc_count,
                        "distinct_children": distinct_children,
                        "semantic_ratio": semantic_ratio,
                        "dynamic_ratio": dynamic_ratio,
                        "decision": "reject",
                        "decision_source": "rule_invalid_parent_tail",
                        "reason": "parent_ends_with_dynamic_segment",
                        "top_children": metrics["top_children"],
                        "sample_urls": sample_urls_by_candidate[(depth, key)],
                        "llm_raw_excerpt": "",
                        "large_group_override": False,
                    }
                )
                continue

            strong = (
                doc_count >= args.strong_min_docs
                and distinct_children >= args.strong_min_distinct_children
                and semantic_ratio >= args.strong_min_semantic_ratio
                and dynamic_ratio <= args.strong_max_dynamic_ratio
            )
            weak = (
                doc_count < args.min_docs
                or distinct_children < args.min_distinct_children
                or (semantic_ratio <= args.weak_max_semantic_ratio and dynamic_ratio >= args.weak_min_dynamic_ratio)
            )
            large_group_override = (
                doc_count >= args.large_group_doc_threshold
                and _semantic_segments_in_parent(key) >= args.large_group_min_semantic_segments
                and not _is_dynamic_segment(_last_segment(key))
            )

            decision = "reject"
            source = "rule_weak"
            reason = "weak_signal"
            llm_raw = ""

            if strong:
                decision = "accept"
                source = "rule_strong"
                reason = "strong_signal"
            elif large_group_override:
                decision = "accept"
                source = "rule_large_group"
                reason = "large_group_keep_together"
            elif weak:
                decision = "reject"
                source = "rule_weak"
                reason = "weak_signal"
            else:
                should_call_ai = args.ai_mode in {"ambiguous", "all"}
                if should_call_ai and ai_calls < args.max_ai_candidates:
                    ai_calls += 1
                    prompt = _ai_prompt(
                        parent_key=key,
                        depth=depth,
                        doc_count=doc_count,
                        metrics=metrics,
                        sample_urls=sample_urls_by_candidate[(depth, key)],
                    )
                    ai_obj, raw_response, err = _call_llm(
                        provider=args.llm_provider,
                        ollama_url=args.ollama_url,
                        ollama_model=args.ollama_model,
                        outlier_url=args.outlier_url,
                        outlier_model=args.outlier_model,
                        outlier_system_message=args.outlier_system_message,
                        timeout_seconds=args.llm_timeout_seconds,
                        prompt=prompt,
                    )
                    llm_raw = raw_response[:250]

                    if err:
                        ai_errors += 1
                        fallback_accept = (
                            doc_count >= args.min_docs
                            and distinct_children >= args.min_distinct_children
                            and semantic_ratio >= 0.30
                            and dynamic_ratio <= 0.70
                        )
                        decision = "accept" if fallback_accept else "reject"
                        source = "ai_error_fallback_rule"
                        reason = err
                    else:
                        raw_decision = _safe_str(ai_obj.get("decision", "")).strip().upper()
                        if raw_decision == "PARENT":
                            decision = "accept"
                            source = "ai"
                            reason = _safe_str(ai_obj.get("reason", "ai_parent"))[:180]
                        elif raw_decision == "NOT_PARENT":
                            decision = "reject"
                            source = "ai"
                            reason = _safe_str(ai_obj.get("reason", "ai_not_parent"))[:180]
                        else:
                            ai_errors += 1
                            fallback_accept = (
                                doc_count >= args.min_docs
                                and distinct_children >= args.min_distinct_children
                                and semantic_ratio >= 0.30
                                and dynamic_ratio <= 0.70
                            )
                            decision = "accept" if fallback_accept else "reject"
                            source = "ai_invalid_fallback_rule"
                            reason = "ai_invalid_decision"
                else:
                    fallback_accept = (
                        doc_count >= args.min_docs
                        and distinct_children >= args.min_distinct_children
                        and semantic_ratio >= 0.30
                        and dynamic_ratio <= 0.70
                    )
                    decision = "accept" if fallback_accept else "reject"
                    source = "middle_rule"
                    reason = "ai_skipped"

            if decision == "accept":
                accepted_by_depth[depth].add(key)

            decisions.append(
                {
                    "depth": depth,
                    "parent_key": key,
                    "doc_count": doc_count,
                    "distinct_children": distinct_children,
                    "semantic_ratio": semantic_ratio,
                    "dynamic_ratio": dynamic_ratio,
                    "decision": decision,
                    "decision_source": source,
                    "reason": reason,
                    "top_children": metrics["top_children"],
                    "sample_urls": sample_urls_by_candidate[(depth, key)],
                    "llm_raw_excerpt": llm_raw,
                    "large_group_override": large_group_override,
                }
            )

    parent_depth_map: dict[str, int] = {}
    for depth, keys in accepted_by_depth.items():
        for key in keys:
            parent_depth_map[key] = depth

    group_doc_ids: dict[str, list[str]] = defaultdict(list)
    group_sample_urls: dict[str, list[str]] = defaultdict(list)
    fallback_root_docs = 0

    for row in parsed_docs:
        host = str(row["host"])
        segments = list(row["segments"])
        url = str(row["url"])
        best = f"{host}/"
        best_depth = 0

        upto = min(len(segments), args.max_depth)
        for depth in range(1, upto + 1):
            key = _parent_key(host, segments, depth)
            if key in accepted_by_depth[depth]:
                best = key
                best_depth = depth

        if best_depth == 0:
            fallback_root_docs += 1

        group_doc_ids[best].append(str(row["doc_id"]))
        samples = group_sample_urls[best]
        if url and len(samples) < 3 and url not in samples:
            samples.append(url)

    parent_groups: list[dict[str, Any]] = []
    for idx, key in enumerate(sorted(group_doc_ids.keys(), key=lambda k: (-len(group_doc_ids[k]), k)), start=1):
        parent_groups.append(
            {
                "group_id": idx,
                "parent_key": key,
                "chosen_depth": int(parent_depth_map.get(key, 0)),
                "doc_count": len(group_doc_ids[key]),
                "doc_ids": group_doc_ids[key],
                "sample_urls": group_sample_urls.get(key, []),
            }
        )

    accepted_total = sum(len(v) for v in accepted_by_depth.values())
    decision_counter = Counter((d["depth"], d["decision"]) for d in decisions)
    large_group_accept_count = sum(
        1 for d in decisions if d.get("decision") == "accept" and d.get("decision_source") == "rule_large_group"
    )

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_docs": len(parsed_docs),
        "candidate_count": len(decisions),
        "accepted_parent_candidates": accepted_total,
        "final_parent_groups": len(parent_groups),
        "fallback_root_docs": fallback_root_docs,
        "ai_calls": ai_calls,
        "ai_errors": ai_errors,
        "large_group_doc_threshold": args.large_group_doc_threshold,
        "large_group_accept_count": large_group_accept_count,
        "accepted_by_depth": {str(d): len(v) for d, v in sorted(accepted_by_depth.items())},
        "decisions_by_depth": {
            f"depth_{d}": {
                "accept": int(decision_counter.get((d, "accept"), 0)),
                "reject": int(decision_counter.get((d, "reject"), 0)),
            }
            for d in range(1, args.max_depth + 1)
        },
    }

    payload = {
        "config": {
            "sample_size": args.sample_size,
            "max_depth": args.max_depth,
            "min_docs": args.min_docs,
            "min_distinct_children": args.min_distinct_children,
            "strong_min_docs": args.strong_min_docs,
            "strong_min_distinct_children": args.strong_min_distinct_children,
            "strong_min_semantic_ratio": args.strong_min_semantic_ratio,
            "strong_max_dynamic_ratio": args.strong_max_dynamic_ratio,
            "weak_max_semantic_ratio": args.weak_max_semantic_ratio,
            "weak_min_dynamic_ratio": args.weak_min_dynamic_ratio,
            "large_group_doc_threshold": args.large_group_doc_threshold,
            "large_group_min_semantic_segments": args.large_group_min_semantic_segments,
            "ai_mode": args.ai_mode,
            "max_ai_candidates": args.max_ai_candidates,
            "llm_provider": args.llm_provider,
            "ollama_url": args.ollama_url,
            "ollama_model": args.ollama_model,
            "outlier_url": args.outlier_url,
            "outlier_model": args.outlier_model,
            "llm_timeout_seconds": args.llm_timeout_seconds,
        },
        "summary": summary,
        "candidate_decisions": decisions,
        "parent_groups": parent_groups,
    }

    ranked_decisions = sorted(decisions, key=lambda r: (-int(r["doc_count"]), int(r["depth"]), str(r["parent_key"])))
    accepted_ranked = [r for r in ranked_decisions if str(r["decision"]) == "accept"]
    rejected_ranked = [r for r in ranked_decisions if str(r["decision"]) == "reject"]

    def _candidate_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "depth": int(row["depth"]),
            "parent_key": str(row["parent_key"]),
            "doc_count": int(row["doc_count"]),
            "distinct_children": int(row["distinct_children"]),
            "semantic_ratio": float(row["semantic_ratio"]),
            "dynamic_ratio": float(row["dynamic_ratio"]),
            "decision_source": str(row["decision_source"]),
            "reason": str(row["reason"]),
        }

    payload["investigation"] = {
        "top_accepted_candidates": [_candidate_row(r) for r in accepted_ranked[:30]],
        "top_rejected_candidates": [_candidate_row(r) for r in rejected_ranked[:30]],
        "top_parent_groups": [
            {
                "parent_key": str(r["parent_key"]),
                "chosen_depth": int(r["chosen_depth"]),
                "doc_count": int(r["doc_count"]),
            }
            for r in parent_groups[:30]
        ],
    }

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    result_json_path = out_dir / "parent_groups_result.json"
    quick_json_path = out_dir / "investigation_quick.json"
    report_quick_path = out_dir / "investigation_quick.md"
    report_trace_path = out_dir / "investigation_trace.md"

    result_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    quick_json_payload = {
        "summary": summary,
        "top_parent_groups": payload["investigation"]["top_parent_groups"][:20],
        "top_accepted_candidates": payload["investigation"]["top_accepted_candidates"][:20],
        "top_rejected_candidates": payload["investigation"]["top_rejected_candidates"][:20],
        "large_group_candidates": [
            _candidate_row(r)
            for r in ranked_decisions
            if int(r["doc_count"]) >= args.large_group_doc_threshold
        ],
        "blocked_by_parent_not_accepted": [
            _candidate_row(r)
            for r in ranked_decisions
            if str(r.get("decision_source")) == "parent_not_accepted"
            and int(r["doc_count"]) >= max(1, args.large_group_doc_threshold // 2)
        ],
    }
    quick_json_path.write_text(json.dumps(quick_json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    quick_lines: list[str] = []
    quick_lines.append("# Step 01 - Quick Investigation")
    quick_lines.append("")
    quick_lines.append("## One Minute Summary")
    quick_lines.append("")
    quick_lines.append(f"- docs scanned: `{summary['total_docs']}`")
    quick_lines.append(f"- parent candidates seen: `{summary['candidate_count']}`")
    quick_lines.append(f"- accepted parent candidates: `{summary['accepted_parent_candidates']}`")
    quick_lines.append(f"- final parent groups: `{summary['final_parent_groups']}`")
    quick_lines.append(f"- fallback root docs: `{summary['fallback_root_docs']}`")
    quick_lines.append(f"- AI calls/errors: `{summary['ai_calls']}` / `{summary['ai_errors']}`")
    quick_lines.append("")
    quick_lines.append("## Top Final Parent Groups")
    quick_lines.append("")
    quick_lines.append("| # | Parent | Depth | Docs |")
    quick_lines.append("|---:|---|---:|---:|")
    for i, row in enumerate(parent_groups[:20], start=1):
        p = str(row["parent_key"]).replace("|", "\\|")
        quick_lines.append(f"| {i} | `{p}` | {row['chosen_depth']} | {row['doc_count']} |")
    quick_lines.append("")
    quick_lines.append("## Biggest Rejected Candidates To Review")
    quick_lines.append("")
    quick_lines.append("| # | Parent | Depth | Docs | Source | Reason |")
    quick_lines.append("|---:|---|---:|---:|---|---|")
    for i, row in enumerate(rejected_ranked[:20], start=1):
        p = str(row["parent_key"]).replace("|", "\\|")
        reason_txt = str(row["reason"]).replace("|", "\\|")
        quick_lines.append(
            f"| {i} | `{p}` | {row['depth']} | {row['doc_count']} | `{row['decision_source']}` | {reason_txt} |"
        )

    trace_lines: list[str] = []
    trace_lines.append("# Step 01 - Investigation Trace")
    trace_lines.append("")
    trace_lines.append("## Config")
    trace_lines.append("")
    for k, v in payload["config"].items():
        trace_lines.append(f"- {k}: `{v}`")
    trace_lines.append("")
    trace_lines.append("## Summary")
    trace_lines.append("")
    for k, v in summary.items():
        trace_lines.append(f"- {k}: `{v}`")
    trace_lines.append("")
    trace_lines.append("## Candidate Decisions (Top 120 by docs)")
    trace_lines.append("")
    trace_lines.append("| Depth | Parent | Docs | Children | Semantic | Dynamic | Decision | Source | Reason |")
    trace_lines.append("|---:|---|---:|---:|---:|---:|---|---|---|")
    for row in ranked_decisions[:120]:
        parent_txt = str(row["parent_key"]).replace("|", "\\|")
        reason_txt = str(row["reason"]).replace("|", "\\|")
        trace_lines.append(
            "| "
            f"{row['depth']} | `{parent_txt}` | {row['doc_count']} | {row['distinct_children']} | "
            f"{row['semantic_ratio']:.3f} | {row['dynamic_ratio']:.3f} | "
            f"`{row['decision']}` | `{row['decision_source']}` | {reason_txt} |"
        )

    report_quick_path.write_text("\n".join(quick_lines) + "\n", encoding="utf-8")
    report_trace_path.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")

    print(f"[01] result_json={result_json_path}")
    print(f"[01] quick_json={quick_json_path}")
    print(f"[01] report_quick={report_quick_path}")
    print(f"[01] report_trace={report_trace_path}")
    print(
        "[01] summary "
        f"docs={summary['total_docs']} candidates={summary['candidate_count']} "
        f"accepted_candidates={summary['accepted_parent_candidates']} groups={summary['final_parent_groups']} "
        f"ai_calls={summary['ai_calls']} ai_errors={summary['ai_errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
