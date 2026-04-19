#!/usr/bin/env python3
"""
URL-first categorization experiment.

Phases:
1) Group by URL structure (domain-specific natural depth).
2) Validate each URL group with LLM (YES/NO + category).
3) Sub-cluster rejected groups with embeddings (MiniBatchKMeans) and label sub-clusters with LLM.

Output:
- Single JSON artifact containing doc_id -> category mapping, source, and stats.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
from dotenv import load_dotenv
from sklearn.cluster import MiniBatchKMeans
from sqlalchemy import bindparam, func, select, text


API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))

load_dotenv(API_ROOT / ".env")

from database.models import KnowledgeBase  # noqa: E402
from database.session import SessionLocal  # noqa: E402
from llm.service import LLMService  # noqa: E402


DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"


@dataclass
class DocRecord:
    id: str
    url: str
    title: str
    preview: str
    domain: str
    segments: list[str]


@dataclass
class UrlGroup:
    id: str
    domain: str
    depth: int
    prefix: str
    doc_ids: list[str]


PLACEHOLDER_LABEL_PATTERNS = [
    r"^\d+\s*-\s*\d+\s*words?$",
    r"^\d+\s*words?$",
    r"^words?$",
    r"^category$",
    r"^url\s+group$",
    r"^concrete\s+category$",
    r"^concrete\s+cluster$",
    r"^misc(?:ellaneous)?(?:\s+category)?$",
    r"^general(?:\s+category)?$",
    r"^other(?:\s+category)?$",
    r"^(?:media|course|tr)\s*\d+$",
    r"^subcluster\s*\d+$",
]

GENERIC_LABEL_PATTERNS = [
    r"^www\b.*",
    r".*\bedu\b.*",
    r".*\btopic$",
    r"^site\s+media$",
]


def _patch_openai_compat_for_httpx_028() -> None:
    """
    Runtime compatibility shim:
    openai==1.51.0 + httpx==0.28.x can fail in default OpenAI constructor path
    used by llm.providers.OpenAICompatProvider. We patch provider init to pass an
    explicit http_client, while still using the existing LLM module.
    """
    import httpx
    from openai import OpenAI
    import llm.providers as llm_providers

    def _init(self, model: str, api_key: str, base_url: str | None = None) -> None:
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.Client(
                timeout=httpx.Timeout(120.0, connect=20.0),
                trust_env=False,
            ),
        )

    llm_providers.OpenAICompatProvider.__init__ = _init


def _normalize_space(text_value: str) -> str:
    return " ".join((text_value or "").split())


def _safe_prefix(segments: list[str], depth: int) -> str:
    if not segments:
        return "root"
    return "/".join(segments[: min(depth, len(segments))]).lower() or "root"


def _parse_url(url: str) -> tuple[str, list[str]]:
    parsed = urlparse((url or "").strip())
    domain = (parsed.netloc or "unknown").lower()
    segments = [seg for seg in (parsed.path or "").split("/") if seg]
    return domain, segments


def _vector_from_text(value: str) -> np.ndarray:
    arr = np.fromstring(value.strip("[]"), sep=",", dtype=np.float32)
    if arr.size == 0:
        raise ValueError("Failed to parse vector from pgvector text.")
    return arr


def _extract_json_obj(raw: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_category_name(name: str, fallback: str) -> str:
    cleaned = _normalize_space(re.sub(r"[\[\]{}()#*`\"']", " ", name or ""))
    if not cleaned:
        cleaned = fallback
    words = cleaned.split()
    if len(words) > 4:
        words = words[:4]
    if len(words) < 2:
        fb_words = _normalize_space(re.sub(r"[\[\]{}()#*`\"']", " ", fallback or "")).split()
        fb_words = fb_words[:4]
        if len(fb_words) >= 2:
            words = fb_words
        elif len(words) == 1:
            words = [words[0], "Topic"]
        else:
            words = ["General", "Topic"]
    return " ".join(words)


def _is_placeholder_label(name: str) -> bool:
    s = _normalize_space((name or "").lower())
    if not s:
        return True
    for pattern in PLACEHOLDER_LABEL_PATTERNS:
        if re.fullmatch(pattern, s):
            return True
    parts = s.split()
    if len(parts) <= 2 and s.endswith(" category"):
        return True
    return False


def _needs_label_repair(name: str) -> bool:
    s = _normalize_space((name or "").lower())
    if _is_placeholder_label(s):
        return True
    for pattern in GENERIC_LABEL_PATTERNS:
        if re.fullmatch(pattern, s):
            return True
    return False


def _humanize_prefix(prefix: str, fallback: str) -> str:
    tokens: list[str] = []
    for segment in (prefix or "").split("/"):
        cleaned = re.sub(r"[-_]+", " ", segment)
        cleaned = re.sub(r"\d+", " ", cleaned)
        cleaned = _normalize_space(cleaned)
        if not cleaned:
            continue
        for tok in cleaned.split():
            low = tok.lower()
            if low in {"tr", "en", "www", "index", "page", "default"}:
                continue
            tokens.append(tok.capitalize())
            if len(tokens) >= 4:
                break
        if len(tokens) >= 4:
            break
    if not tokens:
        cleaned_fb = _normalize_space(re.sub(r"[-_.]+", " ", fallback or ""))
        tokens = [t.capitalize() for t in cleaned_fb.split() if t]
    candidate = " ".join(tokens) if tokens else "General Topic"
    return _normalize_category_name(candidate, fallback=fallback)


def _choose_domain_depth(
    docs: list[DocRecord],
    *,
    min_group_size: int,
    max_group_size: int,
    max_url_depth: int,
) -> tuple[int, list[dict[str, Any]]]:
    """
    Choose depth by balancing:
    - too-big groups (under-segmentation)
    - too-small groups (over-segmentation)
    - usable mid-size groups
    - heterogeneity at next URL level (semantic impurity proxy)
    """
    n = len(docs)
    if n <= max(2, min_group_size * 2):
        return 1, []

    observed_depth = max([len(d.segments) for d in docs] + [1])
    max_depth = max(1, min(max_url_depth, observed_depth))

    best_depth = 1
    best_score = float("-inf")
    diagnostics: list[dict[str, Any]] = []

    for depth in range(1, max_depth + 1):
        counts = Counter(_safe_prefix(d.segments, depth) for d in docs)
        sizes = list(counts.values())
        docs_mid = sum(s for s in sizes if min_group_size <= s <= max_group_size)
        docs_big = sum(s for s in sizes if s > max_group_size)
        docs_small = sum(s for s in sizes if s < min_group_size)

        mid_ratio = docs_mid / n
        big_ratio = docs_big / n
        small_ratio = docs_small / n
        groups = len(sizes)

        hetero_docs = 0
        if depth < max_depth:
            buckets: dict[str, list[DocRecord]] = defaultdict(list)
            for doc in docs:
                buckets[_safe_prefix(doc.segments, depth)].append(doc)
            for bucket_docs in buckets.values():
                if len(bucket_docs) < min_group_size:
                    continue
                child_counts = Counter(_safe_prefix(d.segments, depth + 1) for d in bucket_docs)
                if len(child_counts) <= 1:
                    continue
                dominant_share = max(child_counts.values()) / len(bucket_docs)
                if dominant_share < 0.85:
                    hetero_docs += len(bucket_docs)
        hetero_ratio = hetero_docs / n

        score = mid_ratio - (0.95 * big_ratio) - (0.45 * small_ratio) - (0.35 * hetero_ratio)
        score -= 0.002 * max(0, groups - (n // max(1, min_group_size)))

        diagnostics.append(
            {
                "depth": depth,
                "groups": groups,
                "mid_ratio": round(mid_ratio, 4),
                "big_ratio": round(big_ratio, 4),
                "small_ratio": round(small_ratio, 4),
                "hetero_ratio": round(hetero_ratio, 4),
                "score": round(score, 6),
            }
        )

        if score > best_score + 1e-12 or (abs(score - best_score) <= 1e-12 and depth < best_depth):
            best_score = score
            best_depth = depth

    return best_depth, diagnostics


def _build_url_groups(
    docs: list[DocRecord],
    *,
    min_group_size: int,
    max_group_size: int,
    max_url_depth: int,
) -> tuple[dict[str, UrlGroup], dict[str, int], dict[str, list[dict[str, Any]]]]:
    by_domain: dict[str, list[DocRecord]] = defaultdict(list)
    for doc in docs:
        by_domain[doc.domain].append(doc)

    domain_depths: dict[str, int] = {}
    diagnostics: dict[str, list[dict[str, Any]]] = {}
    groups: dict[str, UrlGroup] = {}

    for domain, domain_docs in by_domain.items():
        depth, scores = _choose_domain_depth(
            domain_docs,
            min_group_size=min_group_size,
            max_group_size=max_group_size,
            max_url_depth=max_url_depth,
        )
        domain_depths[domain] = depth
        diagnostics[domain] = scores

        buckets: dict[str, list[str]] = defaultdict(list)
        for doc in domain_docs:
            prefix = _safe_prefix(doc.segments, depth)
            buckets[prefix].append(doc.id)

        for prefix, doc_ids in buckets.items():
            group_id = f"{domain}|d{depth}|{prefix}"
            groups[group_id] = UrlGroup(
                id=group_id,
                domain=domain,
                depth=depth,
                prefix=prefix,
                doc_ids=doc_ids,
            )

    return groups, domain_depths, diagnostics


def _fetch_docs(db, sample_size: int, preview_chars: int) -> list[DocRecord]:
    preview_chars = max(1, preview_chars)
    stmt = (
        select(
            KnowledgeBase.id,
            KnowledgeBase.url,
            func.coalesce(KnowledgeBase.title, ""),
            func.left(func.coalesce(KnowledgeBase.content, ""), preview_chars),
        )
        .where(KnowledgeBase.url.is_not(None))
        .order_by(KnowledgeBase.id)
    )
    if sample_size > 0:
        stmt = stmt.limit(sample_size)

    rows = list(db.execute(stmt).all())
    docs: list[DocRecord] = []
    for row in rows:
        domain, segments = _parse_url(row[1] or "")
        docs.append(
            DocRecord(
                id=str(row[0]),
                url=row[1] or "",
                title=_normalize_space(row[2] or ""),
                preview=_normalize_space(row[3] or ""),
                domain=domain,
                segments=segments,
            )
        )
    return docs


def _fetch_embeddings(db, *, doc_ids: list[str], model_id: int, batch_size: int = 2000) -> dict[str, np.ndarray]:
    if not doc_ids:
        return {}

    sql = text(
        """
        SELECT kb_id::text AS kb_id, embedding::text AS embedding_text
        FROM knowledge_base_embeddings
        WHERE model_id = :model_id AND kb_id IN :kb_ids
        """
    ).bindparams(bindparam("kb_ids", expanding=True))

    out: dict[str, np.ndarray] = {}
    for i in range(0, len(doc_ids), batch_size):
        chunk = doc_ids[i : i + batch_size]
        rows = list(db.execute(sql, {"model_id": model_id, "kb_ids": chunk}).all())
        for kb_id, embedding_text in rows:
            out[kb_id] = _vector_from_text(embedding_text)
    return out


def _sample_docs(doc_ids: list[str], docs_by_id: dict[str, DocRecord], n: int, rng: random.Random) -> list[DocRecord]:
    if not doc_ids:
        return []
    sample_n = min(n, len(doc_ids))
    chosen = rng.sample(doc_ids, sample_n) if len(doc_ids) > sample_n else list(doc_ids)
    return [docs_by_id[doc_id] for doc_id in chosen if doc_id in docs_by_id]


def _split_group_one_level(
    group: UrlGroup,
    *,
    docs_by_id: dict[str, DocRecord],
    max_url_depth: int,
    min_child_docs: int,
) -> list[UrlGroup]:
    next_depth = group.depth + 1
    if next_depth > max_url_depth:
        return []

    buckets: dict[str, list[str]] = defaultdict(list)
    for doc_id in group.doc_ids:
        doc = docs_by_id.get(doc_id)
        if doc is None:
            continue
        prefix = _safe_prefix(doc.segments, next_depth)
        buckets[prefix].append(doc_id)

    if len(buckets) <= 1:
        return []

    children: list[UrlGroup] = []
    small_ids: list[str] = []
    for prefix, child_ids in buckets.items():
        if len(child_ids) < min_child_docs:
            small_ids.extend(child_ids)
            continue
        child_id = f"{group.domain}|d{next_depth}|{prefix}"
        children.append(
            UrlGroup(
                id=child_id,
                domain=group.domain,
                depth=next_depth,
                prefix=prefix,
                doc_ids=child_ids,
            )
        )

    if small_ids:
        other_prefix = f"{group.prefix}/__other"
        children.append(
            UrlGroup(
                id=f"{group.domain}|d{next_depth}|{other_prefix}",
                domain=group.domain,
                depth=next_depth,
                prefix=other_prefix,
                doc_ids=small_ids,
            )
        )

    covered = sum(len(c.doc_ids) for c in children)
    if len(children) <= 1:
        return []
    if covered < len(group.doc_ids):
        # Split is too weak; avoid spending extra LLM calls.
        return []
    return sorted(children, key=lambda g: len(g.doc_ids), reverse=True)


def _call_llm(llm: LLMService, prompt: str) -> str:
    raw = "".join(llm.generate(prompt)).strip()
    if raw.startswith("[Error:"):
        raise RuntimeError(raw)
    return raw


def _ask_group_consistency(
    llm: LLMService,
    *,
    group_id: str,
    sampled_docs: list[DocRecord],
    fallback_label: str,
) -> tuple[bool, str, str]:
    docs_text = []
    for i, doc in enumerate(sampled_docs, start=1):
        docs_text.append(
            f"{i}. Title: {doc.title or '[no title]'}\n"
            f"   Content (first 300 chars): {doc.preview or '[no content]'}"
        )
    docs_blob = "\n\n".join(docs_text)

    prompt = (
        "You are a strict taxonomy validator.\n"
        "Task: decide if the following documents belong to ONE category.\n"
        "Rules:\n"
        "- Return YES only if at least 4/5 docs clearly match one category.\n"
        "- If mixed, broad, or uncertain, return NO.\n"
        "- Category label must be concrete, 2-4 words, no placeholders.\n"
        '- Forbidden labels: "2-4 words", "3 words", "category", "misc", "general", "other".\n\n'
        f"URL Group: {group_id}\n\n"
        "Documents:\n"
        f"{docs_blob}\n\n"
        "Return ONLY valid JSON in one exact form:\n"
        '{"decision":"YES","category":"Library Resources"}\n'
        '{"decision":"NO","category":null}'
    )

    raw = _call_llm(llm, prompt)
    parsed = _extract_json_obj(raw)

    if parsed is not None:
        decision = str(parsed.get("decision", "")).strip().upper()
        category = str(parsed.get("category", "") or "").strip()
        if decision == "YES":
            normalized = _normalize_category_name(category, fallback=fallback_label)
            if _is_placeholder_label(normalized):
                normalized = _normalize_category_name("", fallback=fallback_label)
            return True, normalized, raw
        if decision == "NO":
            return False, "", raw

    upper = raw.upper()
    if re.search(r"\bNO\b", upper):
        return False, "", raw
    if re.search(r"\bYES\b", upper):
        fallback = _normalize_category_name("", fallback=fallback_label)
        return True, fallback, raw

    # Conservative fallback: NO (forces phase 3)
    return False, "", raw


def _ask_subcluster_label(
    llm: LLMService,
    *,
    group_id: str,
    subcluster_id: int,
    sampled_docs: list[DocRecord],
    fallback_label: str,
) -> tuple[str, str]:
    docs_text = []
    for i, doc in enumerate(sampled_docs, start=1):
        docs_text.append(
            f"{i}. Title: {doc.title or '[no title]'}\n"
            f"   Content (first 300 chars): {doc.preview or '[no content]'}"
        )
    docs_blob = "\n\n".join(docs_text)

    prompt = (
        "You are assigning one concrete category label to a semantic cluster.\n"
        "Rules:\n"
        "- Label must be 2-4 words.\n"
        "- No placeholders or generic labels.\n"
        '- Forbidden labels: "2-4 words", "3 words", "category", "misc", "general", "other".\n\n'
        f"URL Group: {group_id}\n"
        f"Sub-cluster: {subcluster_id}\n\n"
        "Documents:\n"
        f"{docs_blob}\n\n"
        'Return ONLY valid JSON: {"category":"Concrete Category"}'
    )

    raw = _call_llm(llm, prompt)
    parsed = _extract_json_obj(raw)
    if parsed is not None:
        category = str(parsed.get("category", "") or "").strip()
        normalized = _normalize_category_name(category, fallback=fallback_label)
        if _is_placeholder_label(normalized):
            return _normalize_category_name("", fallback=fallback_label), raw
        return normalized, raw
    return _normalize_category_name("", fallback=fallback_label), raw


def _subcluster_doc_ids(
    *,
    doc_ids: list[str],
    embeddings: dict[str, np.ndarray],
    k: int,
    seed: int,
) -> tuple[dict[int, list[str]], list[str]]:
    with_emb = [doc_id for doc_id in doc_ids if doc_id in embeddings]
    missing = [doc_id for doc_id in doc_ids if doc_id not in embeddings]

    if not with_emb:
        return {}, missing

    if len(with_emb) == 1:
        return {1: with_emb}, missing

    k_eff = min(max(1, k), len(with_emb))
    if k_eff == 1:
        return {1: with_emb}, missing

    x = np.vstack([embeddings[doc_id] for doc_id in with_emb]).astype(np.float32)
    model = MiniBatchKMeans(
        n_clusters=k_eff,
        random_state=seed,
        batch_size=min(2048, max(256, len(with_emb))),
        n_init="auto",
        max_iter=300,
        reassignment_ratio=0.01,
    )
    labels = model.fit_predict(x) + 1

    out: dict[int, list[str]] = defaultdict(list)
    for doc_id, label in zip(with_emb, labels, strict=True):
        out[int(label)].append(doc_id)
    return dict(out), missing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="URL-first + LLM + embedding subcluster categorization")
    parser.add_argument("--model-id", type=int, default=6, help="Embedding model_id in knowledge_base_embeddings")
    parser.add_argument("--sample-size", type=int, default=0, help="0 means all rows")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--preview-chars", type=int, default=300)
    parser.add_argument("--llm-sample-docs", type=int, default=5)
    parser.add_argument("--subcluster-k", type=int, default=8)

    parser.add_argument("--max-url-depth", type=int, default=5)
    parser.add_argument("--min-group-size", type=int, default=50)
    parser.add_argument("--max-group-size", type=int, default=5000)
    parser.set_defaults(url_refine_on_no=True)
    parser.add_argument(
        "--url-refine-on-no",
        dest="url_refine_on_no",
        action="store_true",
        help="If a URL group is rejected, split one level deeper and re-validate before embeddings.",
    )
    parser.add_argument(
        "--no-url-refine-on-no",
        dest="url_refine_on_no",
        action="store_false",
        help="Disable URL refinement on rejected groups.",
    )
    parser.add_argument(
        "--url-refine-min-docs",
        type=int,
        default=120,
        help="Minimum group size to allow URL refinement on NO.",
    )
    parser.add_argument(
        "--url-refine-min-child-docs",
        type=int,
        default=20,
        help="Minimum docs per child group during URL refinement split.",
    )

    parser.add_argument(
        "--phase2-max-groups",
        type=int,
        default=0,
        help="For testing: limit number of URL groups validated in phase 2 (0 means all).",
    )
    parser.add_argument(
        "--use-ollama",
        action="store_true",
        help="Use local Ollama via OpenAI-compatible endpoint through existing LLMService.",
    )
    parser.add_argument(
        "--ollama-model",
        type=str,
        default="dolphin-llama3:8b",
        help="Ollama model name (recommended for this job: dolphin-llama3:8b).",
    )
    parser.add_argument(
        "--ollama-base-url",
        type=str,
        default="http://localhost:11434/v1",
        help="Ollama OpenAI-compatible base URL.",
    )

    parser.add_argument("--run-name", type=str, default="url_categorize")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.model_id <= 0:
        raise ValueError("--model-id must be > 0")
    if args.sample_size < 0:
        raise ValueError("--sample-size must be >= 0")
    if args.preview_chars <= 0:
        raise ValueError("--preview-chars must be > 0")
    if args.llm_sample_docs <= 0:
        raise ValueError("--llm-sample-docs must be > 0")
    if args.subcluster_k <= 0:
        raise ValueError("--subcluster-k must be > 0")
    if args.max_url_depth <= 0:
        raise ValueError("--max-url-depth must be > 0")
    if args.min_group_size <= 0:
        raise ValueError("--min-group-size must be > 0")
    if args.max_group_size <= 0:
        raise ValueError("--max-group-size must be > 0")
    if args.max_group_size < args.min_group_size:
        raise ValueError("--max-group-size must be >= --min-group-size")
    if args.url_refine_min_docs <= 0:
        raise ValueError("--url-refine-min-docs must be > 0")
    if args.url_refine_min_child_docs <= 0:
        raise ValueError("--url-refine-min-child-docs must be > 0")
    if args.phase2_max_groups < 0:
        raise ValueError("--phase2-max-groups must be >= 0")

    t0 = time.perf_counter()
    rng = random.Random(args.seed)

    db = SessionLocal()
    try:
        print("[url-categorize] fetching documents...")
        docs = _fetch_docs(db, sample_size=args.sample_size, preview_chars=args.preview_chars)
        if not docs:
            raise RuntimeError("No documents found in knowledge_base.")
        print(f"[url-categorize] docs fetched: {len(docs)}")

        docs_by_id = {d.id: d for d in docs}

        # Phase 1
        print("[url-categorize] phase 1: URL grouping...")
        groups, domain_depths, domain_diagnostics = _build_url_groups(
            docs,
            min_group_size=args.min_group_size,
            max_group_size=args.max_group_size,
            max_url_depth=args.max_url_depth,
        )
        print(f"[url-categorize] url groups: {len(groups)}")

        if args.use_ollama:
            _patch_openai_compat_for_httpx_028()
            os.environ["LLM_PROVIDER"] = "openai"
            os.environ["OPENAI_MODEL"] = args.ollama_model
            os.environ["OPENAI_BASE_URL"] = args.ollama_base_url
            # Ollama's OpenAI-compatible endpoint accepts any non-empty API key.
            os.environ.setdefault("OPENAI_API_KEY", "ollama")
            print(
                f"[url-categorize] ollama enabled model={args.ollama_model} "
                f"base_url={args.ollama_base_url}"
            )

        llm = LLMService()
        print(f"[url-categorize] llm provider={llm.provider} model={llm.model_name}")

        # Phase 2
        print("[url-categorize] phase 2: LLM validation per URL group...")
        ordered_groups = sorted(groups.values(), key=lambda g: len(g.doc_ids), reverse=True)
        if args.phase2_max_groups > 0:
            active_groups = ordered_groups[: args.phase2_max_groups]
            skipped_groups = ordered_groups[args.phase2_max_groups :]
        else:
            active_groups = ordered_groups
            skipped_groups = []

        assignments: dict[str, dict[str, Any]] = {}
        rejected_groups: list[UrlGroup] = []
        accepted_group_count = 0
        rejected_group_count = 0
        refined_group_count = 0
        phase2_calls = 0
        phase2_decisions: list[dict[str, Any]] = []

        pending_groups = list(active_groups)
        while pending_groups:
            group = pending_groups.pop(0)
            phase2_calls += 1
            sample_docs = _sample_docs(group.doc_ids, docs_by_id, args.llm_sample_docs, rng)
            fallback = _humanize_prefix(group.prefix, fallback=group.domain)
            same_category, category_name, raw = _ask_group_consistency(
                llm,
                group_id=group.id,
                sampled_docs=sample_docs,
                fallback_label=fallback,
            )
            decision = "NO"
            refinement_children: list[UrlGroup] = []
            if same_category:
                decision = "YES"
                if _needs_label_repair(category_name):
                    repaired_label, repair_raw = _ask_subcluster_label(
                        llm,
                        group_id=group.id,
                        subcluster_id=0,
                        sampled_docs=sample_docs,
                        fallback_label=fallback,
                    )
                    if not _needs_label_repair(repaired_label):
                        category_name = repaired_label
                    raw = f"{raw}\n\n[repair]\n{repair_raw}"
                accepted_group_count += 1
                for doc_id in group.doc_ids:
                    assignments[doc_id] = {
                        "category": category_name,
                        "source": "url_accepted",
                        "url_group": group.id,
                    }
            else:
                if args.url_refine_on_no and len(group.doc_ids) >= args.url_refine_min_docs:
                    refinement_children = _split_group_one_level(
                        group,
                        docs_by_id=docs_by_id,
                        max_url_depth=args.max_url_depth,
                        min_child_docs=args.url_refine_min_child_docs,
                    )

                if refinement_children:
                    decision = "REFINE"
                    refined_group_count += 1
                    pending_groups = refinement_children + pending_groups
                else:
                    rejected_group_count += 1
                    rejected_groups.append(group)

            phase2_decisions.append(
                {
                    "group_id": group.id,
                    "docs": len(group.doc_ids),
                    "decision": decision,
                    "depth": group.depth,
                    "category": category_name if same_category else None,
                    "refined_children": [child.id for child in refinement_children],
                    "raw": raw,
                }
            )

            if phase2_calls % 25 == 0 or not pending_groups:
                print(
                    f"[url-categorize] phase2 calls={phase2_calls} pending={len(pending_groups)} "
                    f"accepted={accepted_group_count} refined={refined_group_count} "
                    f"rejected={rejected_group_count}"
                )

        if skipped_groups:
            print(f"[url-categorize] skipped groups (phase2_max_groups): {len(skipped_groups)}")
            rejected_groups.extend(skipped_groups)

        # Phase 3
        print("[url-categorize] phase 3: embedding sub-clustering for rejected groups...")
        rejected_doc_ids = [doc_id for group in rejected_groups for doc_id in group.doc_ids]
        embedding_map = _fetch_embeddings(db, doc_ids=rejected_doc_ids, model_id=args.model_id)
        print(
            f"[url-categorize] rejected docs={len(rejected_doc_ids)} embeddings_found={len(embedding_map)}"
        )

        subcluster_count_total = 0
        missing_embedding_docs = 0
        phase3_labels: list[dict[str, Any]] = []

        for i, group in enumerate(rejected_groups, start=1):
            clusters, missing_docs = _subcluster_doc_ids(
                doc_ids=group.doc_ids,
                embeddings=embedding_map,
                k=args.subcluster_k,
                seed=args.seed,
            )

            for cluster_id, cluster_doc_ids in sorted(clusters.items(), key=lambda x: x[0]):
                sample_docs = _sample_docs(cluster_doc_ids, docs_by_id, args.llm_sample_docs, rng)
                fallback = _humanize_prefix(
                    group.prefix,
                    fallback=f"{group.domain} cluster {cluster_id}",
                )
                label, raw = _ask_subcluster_label(
                    llm,
                    group_id=group.id,
                    subcluster_id=cluster_id,
                    sampled_docs=sample_docs,
                    fallback_label=fallback,
                )
                subcluster_count_total += 1
                phase3_labels.append(
                    {
                        "group_id": group.id,
                        "subcluster_id": cluster_id,
                        "docs": len(cluster_doc_ids),
                        "category": label,
                        "raw": raw,
                    }
                )
                for doc_id in cluster_doc_ids:
                    assignments[doc_id] = {
                        "category": label,
                        "source": "subclustered",
                        "url_group": group.id,
                    }

            if missing_docs:
                missing_embedding_docs += len(missing_docs)
                sample_docs = _sample_docs(missing_docs, docs_by_id, args.llm_sample_docs, rng)
                fallback = _humanize_prefix(group.prefix, fallback=f"{group.domain} missing")
                label, raw = _ask_subcluster_label(
                    llm,
                    group_id=group.id,
                    subcluster_id=-1,
                    sampled_docs=sample_docs,
                    fallback_label=fallback,
                )
                subcluster_count_total += 1
                phase3_labels.append(
                    {
                        "group_id": group.id,
                        "subcluster_id": -1,
                        "docs": len(missing_docs),
                        "category": label,
                        "raw": raw,
                        "note": "missing_embedding",
                    }
                )
                for doc_id in missing_docs:
                    assignments[doc_id] = {
                        "category": label,
                        "source": "subclustered",
                        "url_group": group.id,
                    }

            if i % 25 == 0 or i == len(rejected_groups):
                print(
                    f"[url-categorize] phase3 progress {i}/{len(rejected_groups)} "
                    f"subclusters={subcluster_count_total}"
                )

        # Safety: assign any still-unassigned docs.
        if len(assignments) < len(docs):
            unassigned = [d.id for d in docs if d.id not in assignments]
            print(f"[url-categorize] warning: assigning fallback for unassigned docs={len(unassigned)}")
            for doc_id in unassigned:
                assignments[doc_id] = {
                    "category": "Fallback Category",
                    "source": "subclustered",
                    "url_group": "fallback",
                }

        # Stats
        stats_per_category: dict[str, dict[str, Any]] = {}
        source_counts = Counter(v["source"] for v in assignments.values())

        for meta in assignments.values():
            cat = meta["category"]
            src = meta["source"]
            if cat not in stats_per_category:
                stats_per_category[cat] = {
                    "count": 0,
                    "source_counts": {"url_accepted": 0, "subclustered": 0},
                }
            stats_per_category[cat]["count"] += 1
            stats_per_category[cat]["source_counts"][src] += 1

        category_counts_sorted = sorted(
            (
                {
                    "category": category,
                    "count": info["count"],
                    "source_counts": info["source_counts"],
                }
                for category, info in stats_per_category.items()
            ),
            key=lambda x: x["count"],
            reverse=True,
        )

        output = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "config": {
                "model_id": args.model_id,
                "sample_size": args.sample_size,
                "seed": args.seed,
                "preview_chars": args.preview_chars,
                "llm_sample_docs": args.llm_sample_docs,
                "subcluster_k": args.subcluster_k,
                "max_url_depth": args.max_url_depth,
                "min_group_size": args.min_group_size,
                "max_group_size": args.max_group_size,
                "url_refine_on_no": args.url_refine_on_no,
                "url_refine_min_docs": args.url_refine_min_docs,
                "url_refine_min_child_docs": args.url_refine_min_child_docs,
                "phase2_max_groups": args.phase2_max_groups,
                "use_ollama": args.use_ollama,
                "ollama_model": args.ollama_model if args.use_ollama else None,
                "ollama_base_url": args.ollama_base_url if args.use_ollama else None,
                "llm_provider": llm.provider,
                "llm_model": llm.model_name,
            },
            "phase1": {
                "total_docs": len(docs),
                "domain_count": len(domain_depths),
                "url_group_count": len(groups),
                "domain_depths": domain_depths,
                "domain_depth_diagnostics": domain_diagnostics,
            },
            "phase2": {
                "accepted_groups": accepted_group_count,
                "rejected_groups": rejected_group_count + len(skipped_groups),
                "refined_groups": refined_group_count,
                "llm_calls": phase2_calls,
                "skipped_groups": len(skipped_groups),
                "decisions": phase2_decisions,
            },
            "phase3": {
                "processed_rejected_groups": len(rejected_groups),
                "subcluster_count": subcluster_count_total,
                "missing_embedding_docs": missing_embedding_docs,
                "labels": phase3_labels,
            },
            "doc_categories": assignments,
            "stats": {
                "total_docs": len(docs),
                "assigned_docs": len(assignments),
                "source_counts": dict(source_counts),
                "category_count": len(stats_per_category),
                "stats_per_category": category_counts_sorted,
            },
            "total_seconds": round(time.perf_counter() - t0, 3),
        }

        args.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = args.output_dir / f"{args.run_name}_{stamp}.json"
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"[url-categorize] output: {output_path}")
        print(f"[url-categorize] done in {output['total_seconds']}s")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
