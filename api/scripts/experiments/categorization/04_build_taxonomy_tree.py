#!/usr/bin/env python3
"""Step 04: build unified taxonomy tree from URL-known groups + embedding-discovered clusters.

This is a revamp of the old 03_refactor_taxonomy_tree.py.

Pipeline:
  A) Load known groups from step 02 + discovered clusters from step 03.
  B) Bilingual deduplication on URL-known groups (same as old step 03).
  C) Upload reclassification for URL-known groups.
  D) AI taxonomy pass on URL-known groups (same prompts as old step 03).
  E) Separate AI taxonomy pass on discovered clusters (new prompt).
  F) Compose final_rows with source="url_known" or "discovered".
  G) Build taxonomy tree (reused from old step 03).
  H) Write taxonomy_result.json.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
except Exception:
    pass

API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))


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
DEFAULT_DISCOVERY_JSON = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "03_discover_categories"
    / "discovery_result.json"
)
DEFAULT_OUTPUT_DIR = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "04_build_taxonomy_tree"
)

# ---------------------------------------------------------------------------
# Closed-set vocabulary — same 12 as old step 03
# ---------------------------------------------------------------------------
ALLOWED_TOP_CATEGORIES: list[str] = [
    "academics",
    "admissions",
    "administration",
    "events",
    "international",
    "library",
    "news",
    "people",
    "quality",
    "regulations",
    "research",
    "student_life",
]

GENERIC_TOKENS: set[str] = {
    "upload", "uploads", "media", "file", "files", "asset", "assets",
    "page", "pages", "misc", "other", "unknown", "content", "folder",
    "folders", "category", "categories", "general", "information",
    "detail", "details", "default", "index", "home",
}

LOCALE_TOKENS: set[str] = {"tr", "en", "turkish", "english"}
NOISE_TOKENS: set[str] = {"www", "tr", "en", "ve", "the", "and", "ek", "ic", "n"}

SYSTEM_MESSAGE = (
    "You are a university website taxonomy expert. "
    "You classify URL clusters from a university website into a structured 3-level taxonomy. "
    "Always output strict JSON. Never include explanations outside the JSON."
)


# ---------------------------------------------------------------------------
# Text utilities  (identical to old step 03)
# ---------------------------------------------------------------------------

def _ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", (text or "")).encode("ascii", "ignore").decode("ascii")


def _slug(text: str) -> str:
    base = _ascii_fold(text).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", base)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "general"


def _url_slug(text: str) -> str:
    base = _ascii_fold(text).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", base)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "general"


def _normalize_id(text: str) -> str:
    s = _slug(text)
    s = re.sub(r"_(tr|en|turkish|english)$", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "general"


def _title(text: str) -> str:
    pieces = [p for p in re.split(r"[^a-zA-Z0-9]+", (text or "").strip()) if p]
    return " ".join(w.capitalize() for w in pieces) if pieces else "General"


def _is_dynamic_token(tok: str) -> bool:
    s = tok.strip().lower()
    if not s:
        return False
    if s.isdigit():
        return True
    if re.fullmatch(r"\d{4}([-_]\d{1,2}){1,2}", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8,}", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{13,}", s):
        return True
    digits = sum(c.isdigit() for c in s)
    return len(s) >= 5 and digits / len(s) >= 0.60


def _is_semantic_token(tok: str) -> bool:
    s = tok.strip().lower()
    if not s or len(s) <= 1:
        return False
    if s in NOISE_TOKENS:
        return False
    if _is_dynamic_token(s):
        return False
    return bool(re.search(r"[a-z]", s))


def _parse_parent_key(parent_key: str) -> tuple[str, list[str]]:
    raw = (parent_key or "").strip()
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    p = urlparse(raw)
    host = (p.netloc or "unknown").lower().strip() or "unknown"
    segs = [s.lower() for s in (p.path or "").split("/") if s]
    return host, segs


def _semantic_tokens_from_parent(parent_key: str) -> list[str]:
    _host, segs = _parse_parent_key(parent_key)
    out: list[str] = []
    seen: set[str] = set()
    for seg in segs:
        for tok in re.split(r"[-_]+", seg):
            t = tok.strip().lower()
            if not _is_semantic_token(t):
                continue
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
    return out


def _is_bad_label(label: str) -> bool:
    text = (label or "").strip().lower()
    if not text:
        return True
    if _is_dynamic_token(text):
        return True
    words = [w for w in re.split(r"[^a-z0-9]+", text) if w]
    if not words:
        return True
    if all(w in GENERIC_TOKENS for w in words):
        return True
    return False


def _sanitize_label(label: str, fallback: str) -> str:
    cleaned = re.sub(r"\s+", " ", (label or "").strip())
    if _is_bad_label(cleaned):
        cleaned = fallback
    cleaned = re.sub(r"\s+(En|Tr|Turkish|English)\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    if not cleaned or _is_bad_label(cleaned):
        return fallback or "General Resources"
    return _title(cleaned)[:90]


def _sanitize_identifier(text: str) -> str:
    s = _normalize_id(text)
    if not s or s in GENERIC_TOKENS:
        return "general"
    return s


def _category_url(top: str, sub: str, label: str) -> str:
    return f"/taxonomy/{_url_slug(top)}/{_url_slug(sub)}/{_url_slug(label)}"


def _extract_json_obj(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    start = text.find("{")
    if start >= 0:
        dec = json.JSONDecoder()
        try:
            obj, _ = dec.raw_decode(text[start:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# LLM callers  (identical to old step 03)
# ---------------------------------------------------------------------------

def _call_ollama(*, url: str, model: str, timeout: float, prompt: str) -> tuple[dict[str, Any], str, str | None]:
    endpoint = url.rstrip("/") + "/api/generate"
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json",
                       "options": {"temperature": 0}}).encode()
    req = urlrequest.Request(endpoint, data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            parsed = json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        return {}, "", f"ollama_error:{exc}"
    raw = str(parsed.get("response", "")).strip()
    obj = _extract_json_obj(raw)
    return (obj, raw, None) if obj else ({}, raw, "malformed_model_output")


def _call_openai(
    *, api_key: str, model: str, timeout: float, prompt: str, system_message: str
) -> tuple[dict[str, Any], str, str | None]:
    endpoint = "https://api.openai.com/v1/chat/completions"
    messages = []
    if system_message.strip():
        messages.append({"role": "system", "content": system_message.strip()})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            parsed = json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        return {}, "", f"openai_error:{exc}"
    choices = parsed.get("choices", [])
    if not choices:
        return {}, "", "openai_no_choices"
    raw = str(choices[0].get("message", {}).get("content", "")).strip()
    obj = _extract_json_obj(raw)
    return (obj, raw, None) if obj else ({}, raw, "malformed_model_output")


def _call_outlier(*, url: str, model: str, timeout: float, prompt: str,
                  system_message: str) -> tuple[dict[str, Any], str, str | None]:
    endpoint = url.rstrip("/") + "/chat/stream"
    payload: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if system_message.strip():
        payload["systemMessage"] = system_message.strip()
    body = json.dumps(payload).encode()
    req = urlrequest.Request(endpoint, data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            raw_stream = r.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return {}, "", f"outlier_error:{exc}"
    parts: list[str] = []
    for line in raw_stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if isinstance(event, dict) and isinstance(event.get("error"), str) and event["error"].strip():
            return {}, raw_stream[:500], f"outlier_stream_error:{event['error'].strip()}"
        msg = event.get("message", {}) if isinstance(event, dict) else {}
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            c = str(msg.get("content", ""))
            if c:
                parts.append(c)
    raw = "".join(parts).strip()
    obj = _extract_json_obj(raw)
    return (obj, raw, None) if obj else ({}, raw, "malformed_model_output")


def _call_llm(*, provider: str, ollama_url: str, ollama_model: str, outlier_url: str,
              outlier_model: str, openai_api_key: str, openai_model: str,
              system_message: str, timeout: float,
              prompt: str) -> tuple[dict[str, Any], str, str | None]:
    if provider == "outlier":
        return _call_outlier(url=outlier_url, model=outlier_model, timeout=timeout,
                             prompt=prompt, system_message=system_message)
    if provider == "openai":
        return _call_openai(api_key=openai_api_key, model=openai_model, timeout=timeout,
                            prompt=prompt, system_message=system_message)
    return _call_ollama(url=ollama_url, model=ollama_model, timeout=timeout, prompt=prompt)


# ---------------------------------------------------------------------------
# Stage A: Bilingual deduplication  (identical to old step 03)
# ---------------------------------------------------------------------------

def _locale_stripped_key(parent_key: str) -> str:
    host, segs = _parse_parent_key(parent_key)
    filtered = [s for s in segs if s not in {"tr", "en"}]
    normalised = [_ascii_fold(s) for s in filtered]
    return host + "/" + "/".join(normalised)


def _deduplicate_bilingual(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fingerprint_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for g in groups:
        fp = _locale_stripped_key(str(g.get("parent_key", "")))
        fingerprint_map[fp].append(g)

    merged: list[dict[str, Any]] = []
    for fp, twins in fingerprint_map.items():
        if len(twins) == 1:
            merged.append({**twins[0], "bilingual_twin": False, "twin_group_ids": []})
            continue
        twins_sorted = sorted(twins, key=lambda g: -int(g.get("doc_count", 0)))
        canonical = twins_sorted[0]
        twin_ids = [int(t.get("group_id", 0)) for t in twins_sorted[1:]]
        extra_samples: list[str] = []
        for t in twins_sorted[1:]:
            extra_samples.extend(t.get("sample_urls", []))
        merged_samples = list(dict.fromkeys(canonical.get("sample_urls", []) + extra_samples))[:5]
        total_docs = sum(int(t.get("doc_count", 0)) for t in twins_sorted)
        merged.append({
            **canonical,
            "doc_count": total_docs,
            "sample_urls": merged_samples,
            "bilingual_twin": True,
            "twin_group_ids": twin_ids,
            "twin_parent_keys": [str(t.get("parent_key", "")) for t in twins_sorted[1:]],
        })

    merged.sort(key=lambda g: (-int(g.get("doc_count", 0)), int(g.get("group_id", 0))))
    return merged


# ---------------------------------------------------------------------------
# Stage B: Upload cluster reclassification  (identical to old step 03)
# ---------------------------------------------------------------------------

def _is_upload_group(group: dict[str, Any]) -> bool:
    pk = str(group.get("parent_key", "")).lower()
    _, segs = _parse_parent_key(pk)
    return "upload" in segs or (bool(segs) and segs[0] == "upload")


def _upload_semantic_tokens(parent_key: str) -> list[str]:
    _host, segs = _parse_parent_key(parent_key)
    slug_segs = [s for s in segs if s != "upload"]
    tokens: list[str] = []
    seen: set[str] = set()
    for seg in slug_segs:
        for tok in re.split(r"[-_]+", seg):
            t = tok.strip().lower()
            if not _is_semantic_token(t) or t in seen:
                continue
            seen.add(t)
            tokens.append(t)
    return tokens


def _build_upload_prompt(batch: list[dict[str, Any]], vocab: list[str]) -> str:
    items = [
        {
            "group_id": int(g["group_id"]),
            "upload_slug": str(g.get("parent_key", "")).split("/upload/")[-1].strip("/"),
            "slug_tokens": g.get("_upload_tokens", [])[:8],
            "doc_count": int(g.get("doc_count", 0)),
        }
        for g in batch
    ]
    return (
        "You classify university /upload/ document slugs into a content taxonomy.\n"
        "Each item is from a university website's document upload area — the slug tells you WHAT the document is about.\n\n"
        f"Allowed top_category values — pick the single best fit (MUST use exact snake_case name):\n{json.dumps(vocab)}\n\n"
        "Rules:\n"
        "1) Classify by CONTENT, not by file location. /uploads/ is just a delivery mechanism.\n"
        "2) top_category: pick the best match to what the DOCUMENT IS ABOUT.\n"
        "3) sub_category: snake_case English, specific (e.g. 'research_reports', 'student_handbooks', 'mobility_programs').\n"
        "4) category_label: short, clear English title (max 60 chars). Must describe the document TOPIC, not its location.\n"
        "5) FORBIDDEN labels — never use any of these: 'Document Uploads', 'Uploads', 'Media Files', 'Files', "
        "'Documents', 'General', 'Other', 'Misc', 'Content', 'Assets', 'Upload', 'Uploaded Documents'. "
        "These are delivery containers, NOT content categories.\n"
        "6) Examples of GOOD labels: 'Erasmus Mobility Guides', 'Institutional Quality Reports', 'Research Project Publications', "
        "'Student Academic Regulations', 'Faculty Brochures', 'Conference Proceedings'.\n"
        "7) Return one entry per group_id. Return ONLY strict JSON.\n\n"
        f"Input:\n{json.dumps(items, ensure_ascii=False)}\n\n"
        '{"mappings":[{"group_id":1,"top_category":"...","sub_category":"...","category_label":"..."}]}'
    )


# ---------------------------------------------------------------------------
# Stage D: Main URL-known taxonomy prompt  (identical to old step 03)
# ---------------------------------------------------------------------------

def _build_taxonomy_prompt(batch: list[dict[str, Any]], vocab: list[str]) -> str:
    items = [
        {
            "group_id": int(g["group_id"]),
            "parent_key": str(g.get("parent_key", ""))[:120],
            "doc_count": int(g.get("doc_count", 0)),
            "semantic_tokens": g.get("semantic_tokens", [])[:8],
            "sample_urls": [u[:120] for u in g.get("sample_urls", [])[:2]],
            "top_tail_patterns": [
                [str(p[0])[:80], int(p[1])]
                for p in (g.get("top_tail_patterns") or [])[:3]
                if isinstance(p, list) and len(p) >= 2
            ],
        }
        for g in batch
    ]
    return (
        "You are classifying URL clusters from Istanbul Bilgi University's website into a content taxonomy.\n\n"
        f"You MUST pick top_category from this exact list (snake_case):\n{json.dumps(vocab)}\n\n"
        "Rules:\n"
        "1) top_category: pick the single best match from the allowed list above.\n"
        "2) sub_category: invent a specific snake_case English identifier (e.g. 'faculty_of_engineering', 'graduate_programs', 'exchange_programs', 'institutional_reports').\n"
        "3) category_label: a short, clear English title for this group (e.g. 'Faculty of Engineering and Natural Sciences', 'Erasmus Exchange Programs'). Max 60 chars.\n"
        "4) Do NOT include locale suffixes (_tr/_en, Turkish, English) in labels.\n"
        "5) FORBIDDEN words in category_label — never use any of these: "
        "'uploads', 'upload', 'media', 'files', 'file', 'document', 'documents', 'page', 'pages', "
        "'content', 'misc', 'other', 'unknown', 'general', 'assets', 'services'. "
        "Every label must describe WHAT THE CONTENT IS, not where it lives.\n"
        "6) Return exactly one mapping per group_id. Return ONLY strict JSON.\n\n"
        f"Input groups:\n{json.dumps(items, ensure_ascii=False)}\n\n"
        '{"mappings":[{"group_id":1,"top_category":"academics","sub_category":"faculty_of_engineering","category_label":"Faculty of Engineering and Natural Sciences","confidence":0.95}]}'
    )


def _build_retry_prompt(batch: list[dict[str, Any]], vocab: list[str],
                        bad_labels_seen: list[str]) -> str:
    items = [
        {
            "group_id": int(g["group_id"]),
            "parent_key": str(g.get("parent_key", ""))[:120],
            "doc_count": int(g.get("doc_count", 0)),
            "semantic_tokens": g.get("semantic_tokens", [])[:10],
            "sample_urls": [u[:120] for u in g.get("sample_urls", [])[:3]],
            "previous_label": str(g.get("_ai_label_attempt", "")) or "(none)",
            "previous_sub": str(g.get("_ai_sub_attempt", "")) or "(none)",
        }
        for g in batch
    ]
    bad_ex = json.dumps(bad_labels_seen[:15])
    return (
        "RETRY pass for taxonomy classification. The previous attempt had issues.\n\n"
        f"Allowed top_category values: {json.dumps(vocab)}\n\n"
        f"Examples of BAD labels to avoid: {bad_ex}\n\n"
        "Requirements:\n"
        "1) Be SPECIFIC. Use the actual name of the faculty/department/program from the URL tokens.\n"
        "2) Do NOT repeat locale suffixes or path tokens verbatim as labels.\n"
        "3) If you see 'iletisim' in tokens → 'Faculty of Communication'. 'hukuk' → 'Faculty of Law'. etc.\n"
        "4) sub_category must be different for each distinct faculty/program/topic.\n"
        "5) Return ONLY strict JSON.\n\n"
        f"Groups to re-classify:\n{json.dumps(items, ensure_ascii=False)}\n\n"
        '{"mappings":[{"group_id":1,"top_category":"...","sub_category":"...","category_label":"...","confidence":0.9}]}'
    )


# ---------------------------------------------------------------------------
# Stage E: New AI prompt for discovered clusters
# ---------------------------------------------------------------------------

def _build_discovery_prompt(batch: list[dict[str, Any]], vocab: list[str]) -> str:
    """Build prompt for embedding-discovered clusters (no parent_key, use label_tokens instead)."""
    items = [
        {
            "cluster_id": str(g.get("cluster_id", "")),
            "doc_count": int(g.get("doc_count", 0)),
            "label_tokens": g.get("label_tokens", [])[:6],
            "representative_titles": [t[:100] for t in g.get("representative_titles", [])[:3]],
            "language_dist": g.get("language_dist", {}),
            "top_url_segments": g.get("top_url_segments", [])[:3],
        }
        for g in batch
    ]
    return (
        "You are classifying semantically-discovered document clusters from Istanbul Bilgi University "
        "into a content taxonomy.\n"
        "These clusters were discovered by embedding similarity — you have NO URL path for them, "
        "only content signals: TF-IDF label tokens, representative document titles, and top URL path segments.\n\n"
        f"You MUST pick top_category from this exact list (snake_case):\n{json.dumps(vocab)}\n\n"
        "Rules:\n"
        "1) top_category: pick the single best match from the allowed list.\n"
        "2) sub_category: invent a specific snake_case English identifier that describes what this cluster IS ABOUT "
        "(e.g. 'erasmus_mobility', 'faculty_brochures', 'graduate_regulations', 'research_publications').\n"
        "3) category_label: a short, clear English title (max 60 chars) describing the cluster content.\n"
        "4) Use label_tokens and representative_titles as your primary signals for classification.\n"
        "5) FORBIDDEN words in category_label: 'cluster', 'group', 'misc', 'other', 'unknown', "
        "'general', 'files', 'uploads', 'documents', 'content', 'general resources'.\n"
        "6) Return exactly one mapping per cluster_id. Return ONLY strict JSON.\n\n"
        f"Input clusters:\n{json.dumps(items, ensure_ascii=False)}\n\n"
        '{"mappings":[{"cluster_id":"disc_12","top_category":"international","sub_category":"erasmus_mobility","category_label":"Erasmus Exchange Programs","confidence":0.88}]}'
    )


# ---------------------------------------------------------------------------
# Quality scoring  (identical to old step 03)
# ---------------------------------------------------------------------------

def _quality_score(label: str, ai_fraction: float, group_count: int, max_leaf: int) -> float:
    words = [w for w in re.split(r"[^a-z0-9]+", label.lower()) if w]
    generic_ratio = sum(1 for w in words if w in GENERIC_TOKENS) / max(1, len(words))
    locale_ratio = sum(1 for w in words if w in LOCALE_TOKENS) / max(1, len(words))
    specificity = max(0.0, 1.0 - generic_ratio - locale_ratio)
    coverage = ai_fraction
    if group_count == 0:
        size_health = 0.0
    elif group_count <= max_leaf:
        size_health = min(1.0, group_count / 3)
    else:
        size_health = max(0.0, 1.0 - (group_count - max_leaf) / max(1, max_leaf))
    return round(0.45 * specificity + 0.35 * coverage + 0.20 * size_health, 3)


# ---------------------------------------------------------------------------
# Stage G: Tree builder  (identical to old step 03)
# ---------------------------------------------------------------------------

def _build_tree(final_rows: list[dict[str, Any]], max_leaf_clusters: int) -> dict[str, Any]:
    leaf_map: dict[tuple[str, str, str], dict[str, Any]] = {}

    for r in final_rows:
        top = str(r["top_category"])
        sub = str(r["sub_category"])
        label = str(r["category_label"])
        key = (top, sub, label)
        if key not in leaf_map:
            leaf_map[key] = {
                "doc_count": 0,
                "group_count": 0,
                "group_ids": [],
                "representative_parents": [],
                "sample_urls": [],
                "mapping_sources": [],
                "sources": [],
                "quality_score": 0.0,
            }
        node = leaf_map[key]
        node["doc_count"] += int(r.get("doc_count", 0))
        node["group_count"] += 1
        node["group_ids"].append(r.get("group_id") or r.get("cluster_id"))
        for u in r.get("sample_urls", [])[:2]:
            if u and u not in node["sample_urls"]:
                node["sample_urls"].append(u)
        pk = str(r.get("parent_key", ""))
        if pk and pk not in node["representative_parents"]:
            node["representative_parents"].append(pk)
        node["mapping_sources"].append(str(r.get("mapping_source", "fallback")))
        node["sources"].append(str(r.get("source", "url_known")))

    expanded_rows: list[tuple[str, str, str, dict[str, Any]]] = []
    for (top, sub, label), node in leaf_map.items():
        if node["group_count"] > max_leaf_clusters:
            sub_buckets: dict[str, dict[str, Any]] = {}
            for r in final_rows:
                if (str(r["top_category"]), str(r["sub_category"]), str(r["category_label"])) != (top, sub, label):
                    continue
                split_key = str(r.get("sub_split_key", label))
                if split_key not in sub_buckets:
                    sub_buckets[split_key] = {
                        "doc_count": 0, "group_count": 0, "group_ids": [],
                        "representative_parents": [], "sample_urls": [],
                        "mapping_sources": [], "sources": [],
                    }
                bn = sub_buckets[split_key]
                bn["doc_count"] += int(r.get("doc_count", 0))
                bn["group_count"] += 1
                bn["group_ids"].append(r.get("group_id") or r.get("cluster_id"))
                for u in r.get("sample_urls", [])[:2]:
                    if u and u not in bn["sample_urls"]:
                        bn["sample_urls"].append(u)
                pk = str(r.get("parent_key", ""))
                if pk and pk not in bn["representative_parents"]:
                    bn["representative_parents"].append(pk)
                bn["mapping_sources"].append(str(r.get("mapping_source", "fallback")))
                bn["sources"].append(str(r.get("source", "url_known")))
            for split_label, bn in sub_buckets.items():
                expanded_rows.append((top, sub, split_label, bn))
        else:
            expanded_rows.append((top, sub, label, node))

    tree: dict[str, Any] = {}
    for top, sub, label, node in expanded_rows:
        top_node = tree.setdefault(top, {"doc_count": 0, "group_count": 0, "sub_levels": {}})
        top_node["doc_count"] += node["doc_count"]
        top_node["group_count"] += node["group_count"]

        sub_node = top_node["sub_levels"].setdefault(sub, {"doc_count": 0, "group_count": 0, "leaves": {}})
        sub_node["doc_count"] += node["doc_count"]
        sub_node["group_count"] += node["group_count"]

        leaf_url = _category_url(top, sub, label)
        ai_frac = node["mapping_sources"].count("ai") / max(1, len(node["mapping_sources"]))
        quality = _quality_score(label=label, ai_fraction=ai_frac,
                                 group_count=node["group_count"], max_leaf=max_leaf_clusters)
        sub_node["leaves"][label] = {
            "doc_count": node["doc_count"],
            "group_count": node["group_count"],
            "group_ids": node["group_ids"],
            "representative_parents": node["representative_parents"][:4],
            "sample_urls": node["sample_urls"][:4],
            "taxonomy_url": leaf_url,
            "quality_score": round(quality, 3),
            "sources": list(set(node["sources"])),
        }

    return tree


# ---------------------------------------------------------------------------
# Heuristic fallback  (identical to old step 03)
# ---------------------------------------------------------------------------

_KEYWORD_MAP: list[tuple[list[str], str, str]] = [
    (["ects", "course", "katalog", "catalog", "ders"], "academics", "course_catalog"),
    (["kadro", "staff", "faculty", "akademik-kadro", "academic-staff"], "people", "academic_staff"),
    (["haber", "news", "duyuru", "announcement", "haberler"], "news", "university_news"),
    (["etkinlik", "event", "etkinlikler", "konferans", "sempozyum", "seminar"], "events", "university_events"),
    (["lisansustu", "graduate", "postgraduate", "yukseklisans", "doktora", "phd"], "academics", "graduate_programs"),
    (["lisans", "undergraduate", "onlisans", "associate"], "academics", "undergraduate_programs"),
    (["international", "uluslararasi", "erasmus", "exchange", "bilateral", "mobility"], "international", "international_programs"),
    (["faculty", "fakulte", "school", "okul", "enstitu", "institute"], "academics", "academic_units"),
    (["student", "ogrenci", "ogrenci-isleri", "student-affairs"], "student_life", "student_affairs"),
    (["library", "kutuphane", "kutuphanesi"], "library", "library_resources"),
    (["about", "hakkinda", "university", "universite", "tarihce", "history"], "administration", "about_the_university"),
    (["governance", "rektorluk", "rectorate", "yonetim"], "administration", "institutional_governance"),
    (["yonetmelik", "regulation", "kural", "mevzuat", "policy"], "regulations", "policies_and_regulations"),
    (["arastirma", "research", "arge"], "research", "research_overview"),
    (["kalite", "quality", "akreditasyon", "accreditation"], "quality", "quality_assurance"),
    (["burs", "scholarship", "yardim", "financial-aid"], "admissions", "scholarships"),
]


def _heuristic_classify(parent_key: str, tokens: list[str]) -> tuple[str, str, str]:
    pk_lower = parent_key.lower()
    tok_set = set(tokens)
    for keywords, top, sub in _KEYWORD_MAP:
        for kw in keywords:
            if kw in pk_lower or kw in tok_set:
                label_tokens = [t for t in tokens if _is_semantic_token(t) and t not in NOISE_TOKENS][:3]
                label = _title(" ".join(label_tokens)) if label_tokens else _title(sub.replace("_", " "))
                return top, sub, label
    label_tokens = [t for t in tokens if _is_semantic_token(t)][:3]
    label = _title(" ".join(label_tokens)) if label_tokens else "General Resources"
    return "administration", "general_resources", label


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step 04: build unified taxonomy tree from known + discovered groups.")
    parser.add_argument("--classify-json", type=Path, default=DEFAULT_CLASSIFY_JSON)
    parser.add_argument("--discovery-json", type=Path, default=DEFAULT_DISCOVERY_JSON)
    parser.add_argument("--include-discovery-level", type=str, default="mid",
                        choices=["coarse", "mid", "fine"],
                        help="Which cluster level from step 03 to use (default: mid)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    # LLM
    parser.add_argument("--llm-provider", choices=["off", "outlier", "ollama", "openai"], default="openai")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default="qwen2.5:14b")
    parser.add_argument("--outlier-url", default="http://127.0.0.1:8080")
    parser.add_argument("--outlier-model", default="claude-opus-4-6")
    parser.add_argument("--outlier-system-message", default="")
    parser.add_argument("--openai-api-key", default="")
    parser.add_argument("--openai-model", default="gpt-4o-mini")
    parser.add_argument("--llm-timeout", type=float, default=120.0)

    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-leaf-clusters", type=int, default=8)

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    if not args.classify_json.exists():
        raise FileNotFoundError(f"classify-json not found: {args.classify_json}")
    if not args.discovery_json.exists():
        raise FileNotFoundError(f"discovery-json not found: {args.discovery_json}")

    print(f"[04] loading classify: {args.classify_json}")
    classify_src = json.loads(args.classify_json.read_text(encoding="utf-8"))
    all_groups: list[dict[str, Any]] = list(classify_src.get("groups", []))
    known_groups = [g for g in all_groups if str(g.get("decision", "")) == "known"]
    print(f"[04] total groups={len(all_groups)} known={len(known_groups)}")

    print(f"[04] loading discovery: {args.discovery_json}")
    disc_src = json.loads(args.discovery_json.read_text(encoding="utf-8"))
    all_disc_clusters: list[dict[str, Any]] = [
        c for c in disc_src.get("clusters", [])
        if str(c.get("level", "")) == args.include_discovery_level
    ]
    print(f"[04] discovery clusters at level '{args.include_discovery_level}': {len(all_disc_clusters)}")

    # ------------------------------------------------------------------
    # Stage A: Bilingual dedup on URL-known groups
    # ------------------------------------------------------------------
    print("[04·A] bilingual deduplication on known groups...")
    deduped = _deduplicate_bilingual(known_groups)
    bilingual_twins = sum(1 for g in deduped if g.get("bilingual_twin"))
    print(f"[04·A] groups after dedup={len(deduped)} twins_merged={bilingual_twins}")

    # ------------------------------------------------------------------
    # Stage B: Classify upload groups
    # ------------------------------------------------------------------
    upload_groups = [g for g in deduped if _is_upload_group(g)]
    non_upload_groups = [g for g in deduped if not _is_upload_group(g)]
    print(f"[04·B] upload={len(upload_groups)} non_upload={len(non_upload_groups)}")

    for g in upload_groups:
        g["_upload_tokens"] = _upload_semantic_tokens(str(g.get("parent_key", "")))
        g.setdefault("semantic_tokens", g["_upload_tokens"])

    for g in non_upload_groups:
        if not g.get("semantic_tokens"):
            g["semantic_tokens"] = _semantic_tokens_from_parent(str(g.get("parent_key", "")))

    # ------------------------------------------------------------------
    # Assign discovery cluster IDs for use as group_id
    # ------------------------------------------------------------------
    for i, c in enumerate(all_disc_clusters):
        c.setdefault("_disc_idx", i)
        # Use a synthetic group_id that won't collide with URL-group IDs
        c["_disc_group_id"] = f"disc_{c.get('cluster_id', i)}"

    # ------------------------------------------------------------------
    # LLM setup
    # ------------------------------------------------------------------
    openai_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
    openai_model = args.openai_model or os.environ.get("OPENAI_SMALL_MODEL", "gpt-4o-mini")
    if args.llm_provider == "openai" and not openai_key:
        raise ValueError("--openai-api-key required for openai provider (or set OPENAI_API_KEY)")

    llm_config: dict[str, Any] = {
        "provider": args.llm_provider,
        "ollama_url": args.ollama_url,
        "ollama_model": args.ollama_model,
        "outlier_url": args.outlier_url,
        "outlier_model": args.outlier_model,
        "openai_api_key": openai_key,
        "openai_model": openai_model,
        "system_message": args.outlier_system_message or SYSTEM_MESSAGE,
        "timeout": args.llm_timeout,
    }
    print(f"[04] LLM provider={args.llm_provider}")

    ai_calls = 0
    ai_errors = 0
    ai_retries = 0
    ai_retry_errors = 0

    def call_llm(prompt: str) -> tuple[dict[str, Any], str, str | None]:
        nonlocal ai_calls, ai_errors
        ai_calls += 1
        result = _call_llm(prompt=prompt, **llm_config)
        if result[2]:
            ai_errors += 1
        return result

    # ------------------------------------------------------------------
    # Stage D upload: AI for upload groups
    # ------------------------------------------------------------------
    if upload_groups and args.llm_provider != "off":
        print(f"[04·D-upload] classifying {len(upload_groups)} upload groups...")
        for i in range(0, len(upload_groups), args.batch_size):
            batch = upload_groups[i : i + args.batch_size]
            prompt = _build_upload_prompt(batch, ALLOWED_TOP_CATEGORIES)
            obj, _raw, err = call_llm(prompt)
            if not err:
                mappings = obj.get("mappings", obj.get("items", []))
                if isinstance(mappings, list):
                    by_id = {int(g.get("group_id", 0)): g for g in batch}
                    for item in mappings:
                        if not isinstance(item, dict):
                            continue
                        gid = int(item.get("group_id", 0) or 0)
                        g = by_id.get(gid)
                        if g is None:
                            continue
                        raw_top = str(item.get("top_category", "")).strip().lower()
                        top = raw_top if raw_top in ALLOWED_TOP_CATEGORIES else ALLOWED_TOP_CATEGORIES[0]
                        g["_ai_top"] = top
                        g["_ai_sub"] = _sanitize_identifier(str(item.get("sub_category", "")))
                        g["_ai_label"] = _sanitize_label(
                            str(item.get("category_label", "")),
                            _title(" ".join(g.get("semantic_tokens", ["General"])[:3]))
                        )
                        g["_ai_confidence"] = float(item.get("confidence", 0.8))
            print(f"  upload batch {i // args.batch_size + 1} done")

    # ------------------------------------------------------------------
    # Stage D main: AI for non-upload URL-known groups
    # ------------------------------------------------------------------
    if non_upload_groups and args.llm_provider != "off":
        print(f"[04·D-main] classifying {len(non_upload_groups)} non-upload groups...")
        for i in range(0, len(non_upload_groups), args.batch_size):
            batch = non_upload_groups[i : i + args.batch_size]
            prompt = _build_taxonomy_prompt(batch, ALLOWED_TOP_CATEGORIES)
            obj, _raw, err = call_llm(prompt)
            if not err:
                mappings = obj.get("mappings", obj.get("items", obj.get("results", [])))
                if isinstance(mappings, list):
                    by_id = {int(g.get("group_id", 0)): g for g in batch}
                    for item in mappings:
                        if not isinstance(item, dict):
                            continue
                        gid = int(item.get("group_id", 0) or 0)
                        g = by_id.get(gid)
                        if g is None:
                            continue
                        raw_top = str(item.get("top_category", "")).strip().lower()
                        top = raw_top if raw_top in ALLOWED_TOP_CATEGORIES else ALLOWED_TOP_CATEGORIES[0]
                        g["_ai_top"] = top
                        g["_ai_sub"] = _sanitize_identifier(str(item.get("sub_category", "")))
                        g["_ai_label"] = _sanitize_label(
                            str(item.get("category_label", "")),
                            _title(" ".join(g.get("semantic_tokens", ["General"])[:3]))
                        )
                        g["_ai_confidence"] = float(item.get("confidence", 0.8))
            print(f"  main batch {i // args.batch_size + 1}/{math.ceil(len(non_upload_groups) / args.batch_size)} done")

    # QA retry for URL-known groups
    needs_retry = [g for g in deduped if not g.get("_ai_label") or _is_bad_label(g.get("_ai_label", ""))]
    if needs_retry and args.llm_provider != "off":
        bad_labels_seen = [g.get("_ai_label", "") for g in needs_retry if g.get("_ai_label")]
        print(f"[04·D-retry] retry for {len(needs_retry)} low-quality groups...")
        for i in range(0, len(needs_retry), args.batch_size):
            batch = needs_retry[i : i + args.batch_size]
            prompt = _build_retry_prompt(batch, ALLOWED_TOP_CATEGORIES, bad_labels_seen)
            ai_retries += 1
            obj, _raw, err = call_llm(prompt)
            if err:
                ai_retry_errors += 1
                continue
            mappings = obj.get("mappings", obj.get("items", obj.get("results", [])))
            if not isinstance(mappings, list):
                ai_retry_errors += 1
                continue
            by_id = {int(g.get("group_id", 0)): g for g in batch}
            for item in mappings:
                if not isinstance(item, dict):
                    continue
                gid = int(item.get("group_id", 0) or 0)
                g = by_id.get(gid)
                if g is None:
                    continue
                raw_top = str(item.get("top_category", "")).strip().lower()
                top = raw_top if raw_top in ALLOWED_TOP_CATEGORIES else ALLOWED_TOP_CATEGORIES[0]
                g["_ai_top"] = top
                g["_ai_sub"] = _sanitize_identifier(str(item.get("sub_category", "")))
                g["_ai_label"] = _sanitize_label(
                    str(item.get("category_label", "")),
                    _title(" ".join(g.get("semantic_tokens", ["General"])[:3]))
                )
                g["_ai_confidence"] = float(item.get("confidence", 0.8))

    # ------------------------------------------------------------------
    # Stage E: AI for discovered clusters
    # ------------------------------------------------------------------
    if all_disc_clusters and args.llm_provider != "off":
        print(f"[04·E] classifying {len(all_disc_clusters)} discovered clusters...")
        for i in range(0, len(all_disc_clusters), args.batch_size):
            batch = all_disc_clusters[i : i + args.batch_size]
            prompt = _build_discovery_prompt(batch, ALLOWED_TOP_CATEGORIES)
            obj, _raw, err = call_llm(prompt)
            if not err:
                mappings = obj.get("mappings", obj.get("items", []))
                if isinstance(mappings, list):
                    by_disc_id: dict[str, dict[str, Any]] = {
                        str(c.get("_disc_group_id", "")): c for c in batch
                    }
                    # also index by cluster_id string for robustness
                    by_cluster_id: dict[str, dict[str, Any]] = {
                        str(c.get("cluster_id", "")): c for c in batch
                    }
                    for item in mappings:
                        if not isinstance(item, dict):
                            continue
                        cid = str(item.get("cluster_id", ""))
                        c = by_disc_id.get(cid) or by_cluster_id.get(cid.replace("disc_", ""))
                        if c is None:
                            # try numeric match
                            for key in by_cluster_id:
                                if cid.endswith(key) or key.endswith(cid):
                                    c = by_cluster_id[key]
                                    break
                        if c is None:
                            continue
                        raw_top = str(item.get("top_category", "")).strip().lower()
                        top = raw_top if raw_top in ALLOWED_TOP_CATEGORIES else ALLOWED_TOP_CATEGORIES[0]
                        c["_ai_top"] = top
                        c["_ai_sub"] = _sanitize_identifier(str(item.get("sub_category", "")))
                        c["_ai_label"] = _sanitize_label(
                            str(item.get("category_label", "")),
                            _title(" ".join(c.get("label_tokens", ["General"])[:3]))
                        )
                        c["_ai_confidence"] = float(item.get("confidence", 0.8))
            print(f"  discovery batch {i // args.batch_size + 1} done")

    # ------------------------------------------------------------------
    # Compose final_rows for URL-known groups
    # ------------------------------------------------------------------
    final_rows: list[dict[str, Any]] = []

    for g in deduped:
        ai_top = g.get("_ai_top", "")
        ai_sub = g.get("_ai_sub", "")
        ai_label = g.get("_ai_label", "")
        if ai_top and ai_sub and ai_label and not _is_bad_label(ai_label):
            top, sub, label = ai_top, ai_sub, ai_label
            mapping_source = "ai"
        else:
            tokens = g.get("semantic_tokens", []) or _semantic_tokens_from_parent(str(g.get("parent_key", "")))
            top, sub, label = _heuristic_classify(str(g.get("parent_key", "")), tokens)
            mapping_source = "heuristic"

        final_rows.append({
            "group_id": int(g.get("group_id", 0)),
            "cluster_id": None,
            "parent_key": str(g.get("parent_key", "")),
            "doc_count": int(g.get("doc_count", 0)),
            "bilingual_twin": bool(g.get("bilingual_twin", False)),
            "twin_group_ids": g.get("twin_group_ids", []),
            "top_category": top,
            "sub_category": sub,
            "category_label": label,
            "mapping_source": mapping_source,
            "ai_confidence": float(g.get("_ai_confidence", 0.0)),
            "sample_urls": g.get("sample_urls", []),
            "semantic_tokens": g.get("semantic_tokens", []),
            "sub_split_key": label,
            "source": "url_known",
        })

    # Compose final_rows for discovered clusters
    disc_final: list[dict[str, Any]] = []
    for c in all_disc_clusters:
        ai_top = c.get("_ai_top", "")
        ai_sub = c.get("_ai_sub", "")
        ai_label = c.get("_ai_label", "")
        if ai_top and ai_sub and ai_label and not _is_bad_label(ai_label):
            top, sub, label = ai_top, ai_sub, ai_label
            mapping_source = "ai"
        else:
            label_tokens = c.get("label_tokens", [])
            fallback_label = _title(" ".join(label_tokens[:3])) if label_tokens else "General Resources"
            top, sub, label = "administration", "general_resources", fallback_label
            mapping_source = "heuristic"

        disc_final.append({
            "group_id": None,
            "cluster_id": str(c.get("_disc_group_id", f"disc_{c.get('cluster_id', '')}")),
            "parent_key": "",
            "doc_count": int(c.get("doc_count", 0)),
            "bilingual_twin": False,
            "twin_group_ids": [],
            "top_category": top,
            "sub_category": sub,
            "category_label": label,
            "mapping_source": mapping_source,
            "ai_confidence": float(c.get("_ai_confidence", 0.0)),
            "sample_urls": [],
            "label_tokens": c.get("label_tokens", []),
            "representative_titles": c.get("representative_titles", []),
            "top_url_segments": c.get("top_url_segments", []),
            "language_dist": c.get("language_dist", {}),
            "source_group_ids": c.get("source_group_ids", []),
            "sub_split_key": label,
            "source": "discovered",
        })

    all_final_rows = final_rows + disc_final
    all_final_rows.sort(key=lambda r: -int(r.get("doc_count", 0)))

    ai_mapped = sum(1 for r in all_final_rows if r["mapping_source"].startswith("ai"))
    heuristic_mapped = sum(1 for r in all_final_rows if r["mapping_source"] == "heuristic")
    url_known_count = sum(1 for r in all_final_rows if r["source"] == "url_known")
    discovered_count = sum(1 for r in all_final_rows if r["source"] == "discovered")
    print(
        f"[04] final_rows={len(all_final_rows)} "
        f"url_known={url_known_count} discovered={discovered_count} "
        f"ai={ai_mapped} heuristic={heuristic_mapped}"
    )

    # ------------------------------------------------------------------
    # Stage G: Build tree
    # ------------------------------------------------------------------
    print("[04·G] building taxonomy tree...")
    tree = _build_tree(all_final_rows, max_leaf_clusters=args.max_leaf_clusters)

    top_count = len(tree)
    total_subs = sum(len(tn["sub_levels"]) for tn in tree.values())
    total_leaves = sum(
        len(sn["leaves"])
        for tn in tree.values()
        for sn in tn["sub_levels"].values()
    )
    print(f"[04·G] tree: {top_count} top | {total_subs} sub | {total_leaves} leaves")

    all_quality_scores = [
        leaf["quality_score"]
        for tn in tree.values()
        for sn in tn["sub_levels"].values()
        for leaf in sn["leaves"].values()
    ]
    avg_quality = round(sum(all_quality_scores) / max(1, len(all_quality_scores)), 3)
    high_quality_leaves = sum(1 for q in all_quality_scores if q >= 0.70)
    low_quality_leaves = sum(1 for q in all_quality_scores if q < 0.40)

    # ------------------------------------------------------------------
    # Summary + output
    # ------------------------------------------------------------------
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classify_json": str(args.classify_json),
        "discovery_json": str(args.discovery_json),
        "include_discovery_level": args.include_discovery_level,
        "input": {
            "total_classify_groups": len(all_groups),
            "known_groups": len(known_groups),
            "discovery_clusters": len(all_disc_clusters),
        },
        "deduplication": {
            "groups_after_dedup": len(deduped),
            "bilingual_twins_merged": bilingual_twins,
            "upload_groups": len(upload_groups),
            "non_upload_groups": len(non_upload_groups),
        },
        "ai": {
            "provider": args.llm_provider,
            "model": (
                openai_model if args.llm_provider == "openai"
                else args.outlier_model if args.llm_provider == "outlier"
                else args.ollama_model
            ),
            "total_calls": ai_calls,
            "errors": ai_errors,
            "retry_calls": ai_retries,
            "retry_errors": ai_retry_errors,
        },
        "mapping": {
            "total_final": len(all_final_rows),
            "url_known": url_known_count,
            "discovered": discovered_count,
            "ai_mapped": ai_mapped,
            "heuristic_mapped": heuristic_mapped,
        },
        "tree": {
            "top_levels": top_count,
            "sub_levels": total_subs,
            "leaves": total_leaves,
        },
        "quality": {
            "avg_quality_score": avg_quality,
            "high_quality_leaves": high_quality_leaves,
            "low_quality_leaves": low_quality_leaves,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    full_payload = {
        "summary": summary,
        "tree": tree,
        "final_rows": all_final_rows,
    }
    result_path = args.output_dir / "taxonomy_result.json"
    tree_path = args.output_dir / "taxonomy_tree_clean.json"
    quick_md_path = args.output_dir / "taxonomy_quick.md"

    result_path.write_text(json.dumps(full_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tree_path.write_text(json.dumps({"summary": summary, "tree": tree}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = ["# Step 04 — Unified Taxonomy Tree", ""]
    lines += ["## Summary", ""]
    lines += [f"- known groups in: `{summary['input']['known_groups']}`"]
    lines += [f"- discovery clusters in (level={args.include_discovery_level}): `{summary['input']['discovery_clusters']}`"]
    lines += [f"- bilingual twins merged: `{summary['deduplication']['bilingual_twins_merged']}`"]
    lines += [f"- AI provider: `{summary['ai']['provider']}` / model: `{summary['ai']['model']}`"]
    lines += [f"- AI calls: `{summary['ai']['total_calls']}` errors: `{summary['ai']['errors']}`"]
    lines += [f"- final rows: `{summary['mapping']['total_final']}` (url_known: `{url_known_count}` | discovered: `{discovered_count}`)"]
    lines += [f"- ai_mapped: `{ai_mapped}` heuristic_mapped: `{heuristic_mapped}`"]
    lines += [f"- tree: `{top_count}` top / `{total_subs}` sub / `{total_leaves}` leaves"]
    lines += [f"- avg quality: `{avg_quality}` high: `{high_quality_leaves}` low: `{low_quality_leaves}`"]
    lines += [""]

    lines += ["## Taxonomy Tree", ""]
    for top_name in sorted(tree.keys()):
        top_node = tree[top_name]
        lines += [f"### `{top_name}` — {top_node['doc_count']:,} docs", ""]
        for sub_name in sorted(top_node["sub_levels"].keys()):
            sub_node = top_node["sub_levels"][sub_name]
            lines += [f"#### {sub_name}"]
            lines += ["| Leaf | Docs | Groups | Quality | Sources |"]
            lines += ["|---|---:|---:|---:|---|"]
            for leaf_label, leaf in sorted(sub_node["leaves"].items(), key=lambda x: -x[1]["doc_count"]):
                lbl = leaf_label.replace("|", "\\|")
                srcs = ", ".join(sorted(set(leaf.get("sources", []))))
                lines += [f"| {lbl} | {leaf['doc_count']:,} | {leaf['group_count']} | `{leaf['quality_score']}` | {srcs} |"]
            lines += [""]

    quick_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[04] result_json:   {result_path}")
    print(f"[04] tree_clean:    {tree_path}")
    print(f"[04] quick_md:      {quick_md_path}")
    print(
        f"[04] DONE — top:{top_count} sub:{total_subs} leaves:{total_leaves} "
        f"avg_quality:{avg_quality} ai_calls:{ai_calls}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
