#!/usr/bin/env python3
"""
Context-aware AI taxonomy refinement for URL-resolved groups.

Input:
- JSON from `04_build_ai_input.py` (pass-1, URL-resolved groups only)

Output:
- JSON with AI taxonomy labels per category, plus validation metadata.

Safety rules:
- Preserve source structure (cluster_id + representative_parent are fixed).
- Ground decisions in provided evidence only.
- Fall back to `unresolved` when evidence is weak or model output is invalid.
- Require explicit count confirmation before a full run.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.parse import urlparse


API_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"

ALLOWED_TOP_LEVELS = [
    "academics",
    "administration",
    "admissions",
    "announcements",
    "events",
    "people",
    "programs",
    "research",
    "regulations_policies",
    "services",
    "student_life",
    "media_library",
    "international",
    "unknown",
]

ALLOWED_DOC_TYPES = [
    "policy",
    "regulation",
    "announcement",
    "event",
    "profile",
    "course",
    "program",
    "unit_page",
    "form",
    "media",
    "other",
    "unknown",
]

ALLOWED_REGULATORY_RELEVANCE = ["high", "medium", "low", "unknown"]

PLACEHOLDER_LABELS = {
    "",
    "category",
    "general",
    "misc",
    "other",
    "unknown",
    "n/a",
    "na",
    "unresolved",
}

KEYWORDS_BY_TOP_LEVEL: dict[str, set[str]] = {
    "people": {"staff", "kadro", "personel", "instructor", "lecturer", "professor"},
    "announcements": {
        "haber",
        "haberler",
        "news",
        "duyuru",
        "duyurular",
        "announcement",
        "announcements",
    },
    "events": {"etkinlik", "etkinlikler", "event", "events", "calendar"},
    "programs": {
        "program",
        "programs",
        "lisans",
        "lisansustu",
        "undergraduate",
        "graduate",
        "masters",
        "phd",
        "certificate",
    },
    "academics": {
        "akademik",
        "academic",
        "course",
        "courses",
        "ders",
        "department",
        "bolum",
        "faculty",
        "ogretim",
        "elemani",
        "uzem",
    },
    "admissions": {"admission", "admissions", "apply", "application", "basvuru", "kabul"},
    "regulations_policies": {
        "policy",
        "policies",
        "regulation",
        "regulations",
        "directive",
        "procedure",
        "procedures",
        "mevzuat",
        "yonetmelik",
        "kural",
        "rule",
        "ihale",
        "ihaleler",
        "tender",
        "procurement",
    },
    "services": {
        "service",
        "services",
        "hizmet",
        "library",
        "kutuphane",
        "support",
        "units-and-services",
        "birimler",
        "talent",
        "internship",
        "staj",
        "yetenek",
        "gelisim",
        "ofisi",
        "office",
        "career",
    },
    "international": {
        "international",
        "international-office",
        "uluslararasi",
        "uluslararasi-ofis",
        "global",
        "erasmus",
        "exchange",
        "degisim",
    },
    "media_library": {"media", "gallery", "video", "podcast", "press", "upload"},
    "research": {"research", "arastirma", "lab", "laboratory", "publication"},
    "student_life": {
        "student",
        "students",
        "ogrenci",
        "mezun",
        "alumni",
        "mentorluk",
        "mentorship",
        "kulup",
        "kulupleri",
        "club",
        "campus",
        "life-at-bilgi",
        "yasam",
    },
    "administration": {
        "admin",
        "administration",
        "yonetim",
        "governance",
        "hakkinda",
        "about",
        "quality",
        "kalite",
        "processes",
        "surecler",
        "rektorluk",
        "rectorate",
        "university-governance",
        "university",
        "universite",
        "institutional-principles",
        "ik",
        "human",
        "resources",
        "calisan",
        "employee",
    },
}

KEYWORDS_BY_DOC_TYPE: dict[str, set[str]] = {
    "profile": {"staff", "kadro", "personel", "profile", "faculty"},
    "announcement": {"haber", "haberler", "news", "duyuru", "duyurular", "announcement"},
    "event": {"etkinlik", "etkinlikler", "event", "events", "calendar"},
    "course": {"course", "ders"},
    "program": {"program", "lisans", "lisansustu", "undergraduate", "graduate", "masters", "phd"},
    "policy": {"policy", "policies", "procedure", "procedures", "directive"},
    "regulation": {"regulation", "regulations", "mevzuat", "yonetmelik", "rule", "kural", "ihale"},
    "form": {"form", "forms", "pdf"},
    "media": {"media", "gallery", "video", "podcast", "press"},
}


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _extract_json_obj(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
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


def _is_dynamic_segment(seg: str) -> bool:
    s = (seg or "").strip().lower()
    if not s:
        return True
    if re.fullmatch(r"\d+", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8,}", s):
        return True
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{13,}", s):
        return True
    if re.fullmatch(r"\d{4}[-_/]?\d{1,2}[-_/]?\d{1,2}", s):
        return True
    if len(s) >= 5:
        digits = sum(ch.isdigit() for ch in s)
        if (digits / len(s)) >= 0.60:
            return True
    return False


def _is_semantic_segment(seg: str) -> bool:
    s = (seg or "").strip().lower()
    if not s:
        return False
    if len(s) <= 1:
        return False
    if s in {"tr", "en", "www"}:
        return False
    if _is_dynamic_segment(s):
        return False
    if not re.search(r"[a-z]", s):
        return False
    return True


def _expand_semantic_tokens(seg: str) -> list[str]:
    base = (seg or "").strip().lower()
    if not _is_semantic_segment(base):
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        t = token.strip().lower()
        if not t or t in seen:
            return
        seen.add(t)
        out.append(t)

    add(base)
    for part in re.split(r"[-_/]+", base):
        t = part.strip().lower()
        if len(t) <= 1:
            continue
        if _is_dynamic_segment(t):
            continue
        if not re.search(r"[a-z]", t):
            continue
        add(t)
    return out


def _split_url_segments(raw: str) -> tuple[str, list[str]]:
    text = (raw or "").strip()
    if not text:
        return "unknown", []
    if "://" not in text:
        # representative_parent can be host/path without scheme
        tokens = [t for t in text.strip("/").split("/") if t]
        if not tokens:
            return "unknown", []
        host = tokens[0].lower()
        segments = tokens[1:]
        return host, segments
    parsed = urlparse(text)
    host = (parsed.netloc or "").lower() or "unknown"
    segments = [s for s in (parsed.path or "").split("/") if s]
    return host, segments


def _semantic_terms_from_url(raw: str) -> list[str]:
    _host, segs = _split_url_segments(raw)
    out: list[str] = []
    for seg in segs:
        out.extend(_expand_semantic_tokens(seg))
    return out


def _coerce_float(v: Any, default: float = 0.0) -> float:
    try:
        out = float(v)
        if out != out:  # NaN
            return default
        return out
    except Exception:
        return default


def _build_global_context(categories: list[dict[str, Any]]) -> tuple[Counter[str], dict[str, Counter[str]], Counter[str]]:
    global_terms: Counter[str] = Counter()
    host_terms: dict[str, Counter[str]] = defaultdict(Counter)
    host_counts: Counter[str] = Counter()

    for c in categories:
        hint = c.get("path_hint", {}) or {}
        host = str(hint.get("host", "unknown")).lower() or "unknown"
        host_counts[host] += 1

        for seg in hint.get("segments", []) or []:
            token = str(seg).strip().lower()
            if _is_semantic_segment(token):
                global_terms[token] += 1
                host_terms[host][token] += 1

        for sample_url in c.get("sample_urls", []) or []:
            for token in _semantic_terms_from_url(str(sample_url)):
                global_terms[token] += 1
                host_terms[host][token] += 1

    return global_terms, host_terms, host_counts


def _collect_category_tokens(category: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    parent = str(category.get("representative_parent", ""))
    _host, parent_segs = _split_url_segments(parent)
    for seg in parent_segs:
        for token in _expand_semantic_tokens(seg):
            out.add(token)

    hint = category.get("path_hint", {}) or {}
    for seg in hint.get("segments", []) or []:
        for token in _expand_semantic_tokens(str(seg)):
            out.add(token)
    return out


def _infer_top_level_candidates(tokens: set[str]) -> list[str]:
    candidates: set[str] = set()
    for top_level, words in KEYWORDS_BY_TOP_LEVEL.items():
        if tokens & words:
            candidates.add(top_level)
    if not candidates:
        return ["unknown"]
    candidates.add("unknown")
    return sorted(candidates)


def _infer_doc_type_candidates(tokens: set[str]) -> list[str]:
    candidates: set[str] = set()
    for doc_type, words in KEYWORDS_BY_DOC_TYPE.items():
        if tokens & words:
            candidates.add(doc_type)
    if not candidates:
        return ["unknown", "unit_page", "other"]
    candidates.update({"unknown", "other"})
    return sorted(candidates)


def _heuristic_fallback(tokens: set[str]) -> dict[str, Any] | None:
    def pick(choices: set[str]) -> list[str]:
        return sorted(list(tokens & choices))

    reg_terms = pick(KEYWORDS_BY_TOP_LEVEL["regulations_policies"])
    if reg_terms:
        is_reg = any(t in {"regulation", "regulations", "mevzuat", "yonetmelik", "rule", "kural"} for t in reg_terms)
        doc_type = "regulation" if is_reg else "policy"
        return {
            "status": "mapped",
            "top_level": "regulations_policies",
            "sub_level": "regulatory_documents",
            "canonical_label": "Regulations and Policies",
            "document_type": doc_type,
            "regulatory_relevance": "high",
            "confidence": 0.72,
            "evidence_terms": reg_terms[:3],
            "reason": "Rule fallback from regulatory URL tokens.",
        }

    ppl_terms = pick(KEYWORDS_BY_TOP_LEVEL["people"])
    if ppl_terms:
        return {
            "status": "mapped",
            "top_level": "people",
            "sub_level": "academic_staff",
            "canonical_label": "Academic Staff Profiles",
            "document_type": "profile",
            "regulatory_relevance": "low",
            "confidence": 0.7,
            "evidence_terms": ppl_terms[:3],
            "reason": "Rule fallback from staff/profile URL tokens.",
        }

    intl_anchor_terms = {
        "international-office",
        "uluslararasi-ofis",
        "international-admissions",
        "erasmus",
        "exchange",
        "degisim",
    }
    service_anchor_terms = {
        "talent",
        "internship",
        "staj",
        "yetenek",
        "career",
        "units-and-services",
        "birimler",
    }
    admin_anchor_terms = {
        "quality",
        "kalite",
        "rektorluk",
        "rectorate",
        "university-governance",
        "hakkinda",
        "ik",
        "calisan",
    }
    announce_anchor_terms = {"haber", "haberler", "news", "duyuru", "duyurular", "announcement", "announcements"}
    event_anchor_terms = {"etkinlik", "etkinlikler", "event", "events", "calendar"}

    intl_anchor = sorted(list(tokens & intl_anchor_terms))
    if intl_anchor:
        return {
            "status": "mapped",
            "top_level": "international",
            "sub_level": "international_programs",
            "canonical_label": "International Office and Programs",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.7,
            "evidence_terms": intl_anchor[:3],
            "reason": "Rule fallback from international anchor tokens.",
        }

    service_anchor = sorted(list(tokens & service_anchor_terms))
    if service_anchor:
        return {
            "status": "mapped",
            "top_level": "services",
            "sub_level": "campus_services",
            "canonical_label": "Campus Services",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.67,
            "evidence_terms": service_anchor[:3],
            "reason": "Rule fallback from services anchor tokens.",
        }

    admin_anchor = sorted(list(tokens & admin_anchor_terms))
    if admin_anchor:
        return {
            "status": "mapped",
            "top_level": "administration",
            "sub_level": "institutional_governance",
            "canonical_label": "Institutional Governance Pages",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.68,
            "evidence_terms": admin_anchor[:3],
            "reason": "Rule fallback from administration anchor tokens.",
        }

    ann_anchor = sorted(list(tokens & announce_anchor_terms))
    if ann_anchor:
        return {
            "status": "mapped",
            "top_level": "announcements",
            "sub_level": "news_announcements",
            "canonical_label": "University Announcements",
            "document_type": "announcement",
            "regulatory_relevance": "medium",
            "confidence": 0.68,
            "evidence_terms": ann_anchor[:3],
            "reason": "Rule fallback from announcement/news anchor tokens.",
        }

    evt_anchor = sorted(list(tokens & event_anchor_terms))
    if evt_anchor:
        return {
            "status": "mapped",
            "top_level": "events",
            "sub_level": "events_calendar",
            "canonical_label": "University Events",
            "document_type": "event",
            "regulatory_relevance": "low",
            "confidence": 0.68,
            "evidence_terms": evt_anchor[:3],
            "reason": "Rule fallback from event anchor tokens.",
        }

    intl_terms = pick(KEYWORDS_BY_TOP_LEVEL["international"])
    if intl_terms:
        return {
            "status": "mapped",
            "top_level": "international",
            "sub_level": "international_programs",
            "canonical_label": "International Office and Programs",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.68,
            "evidence_terms": intl_terms[:3],
            "reason": "Rule fallback from international URL tokens.",
        }

    adm_terms = pick(KEYWORDS_BY_TOP_LEVEL["admissions"])
    if adm_terms:
        return {
            "status": "mapped",
            "top_level": "admissions",
            "sub_level": "admissions_information",
            "canonical_label": "Admissions Information",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.67,
            "evidence_terms": adm_terms[:3],
            "reason": "Rule fallback from admissions URL tokens.",
        }

    service_terms = pick(KEYWORDS_BY_TOP_LEVEL["services"])
    if service_terms:
        return {
            "status": "mapped",
            "top_level": "services",
            "sub_level": "campus_services",
            "canonical_label": "Campus Services",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.65,
            "evidence_terms": service_terms[:3],
            "reason": "Rule fallback from services URL tokens.",
        }

    life_terms = pick(KEYWORDS_BY_TOP_LEVEL["student_life"])
    if life_terms:
        return {
            "status": "mapped",
            "top_level": "student_life",
            "sub_level": "student_resources",
            "canonical_label": "Student Life and Resources",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.65,
            "evidence_terms": life_terms[:3],
            "reason": "Rule fallback from student-life URL tokens.",
        }

    admin_terms = pick(KEYWORDS_BY_TOP_LEVEL["administration"])
    if admin_terms:
        return {
            "status": "mapped",
            "top_level": "administration",
            "sub_level": "institutional_governance",
            "canonical_label": "Institutional Governance Pages",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.66,
            "evidence_terms": admin_terms[:3],
            "reason": "Rule fallback from university-administration URL tokens.",
        }

    research_terms = pick(KEYWORDS_BY_TOP_LEVEL["research"])
    if research_terms:
        return {
            "status": "mapped",
            "top_level": "research",
            "sub_level": "research_units",
            "canonical_label": "Research Pages",
            "document_type": "unit_page",
            "regulatory_relevance": "medium",
            "confidence": 0.64,
            "evidence_terms": research_terms[:3],
            "reason": "Rule fallback from research URL tokens.",
        }

    prog_terms = pick(KEYWORDS_BY_TOP_LEVEL["programs"])
    if prog_terms:
        return {
            "status": "mapped",
            "top_level": "programs",
            "sub_level": "degree_programs",
            "canonical_label": "Program Information",
            "document_type": "program",
            "regulatory_relevance": "medium",
            "confidence": 0.66,
            "evidence_terms": prog_terms[:3],
            "reason": "Rule fallback from program-level URL tokens.",
        }

    acad_terms = pick(KEYWORDS_BY_TOP_LEVEL["academics"])
    if acad_terms:
        doc_type = "course" if any(t in {"course", "ders"} for t in acad_terms) else "unit_page"
        label = "Course Catalog Pages" if doc_type == "course" else "Academic Unit Pages"
        return {
            "status": "mapped",
            "top_level": "academics",
            "sub_level": "academic_information",
            "canonical_label": label,
            "document_type": doc_type,
            "regulatory_relevance": "medium",
            "confidence": 0.64,
            "evidence_terms": acad_terms[:3],
            "reason": "Rule fallback from academic URL tokens.",
        }

    ann_terms = pick(KEYWORDS_BY_TOP_LEVEL["announcements"])
    if ann_terms:
        return {
            "status": "mapped",
            "top_level": "announcements",
            "sub_level": "news_announcements",
            "canonical_label": "University Announcements",
            "document_type": "announcement",
            "regulatory_relevance": "medium",
            "confidence": 0.68,
            "evidence_terms": ann_terms[:3],
            "reason": "Rule fallback from announcement/news URL tokens.",
        }

    evt_terms = pick(KEYWORDS_BY_TOP_LEVEL["events"])
    if evt_terms:
        return {
            "status": "mapped",
            "top_level": "events",
            "sub_level": "events_calendar",
            "canonical_label": "University Events",
            "document_type": "event",
            "regulatory_relevance": "low",
            "confidence": 0.68,
            "evidence_terms": evt_terms[:3],
            "reason": "Rule fallback from event URL tokens.",
        }

    media_terms = pick(KEYWORDS_BY_TOP_LEVEL["media_library"])
    if media_terms:
        return {
            "status": "mapped",
            "top_level": "media_library",
            "sub_level": "uploaded_documents",
            "canonical_label": "Uploaded Documents",
            "document_type": "media",
            "regulatory_relevance": "medium",
            "confidence": 0.63,
            "evidence_terms": media_terms[:3],
            "reason": "Rule fallback from upload/media URL tokens.",
        }

    return None


def _build_prompt(
    *,
    category: dict[str, Any],
    host_terms: list[str],
    global_terms: list[str],
    top_level_candidates: list[str],
    doc_type_candidates: list[str],
    min_evidence_terms: int,
) -> str:
    category_json = json.dumps(category, ensure_ascii=False, indent=2)
    return (
        "You are an assistant for a university-source taxonomy pipeline.\n"
        "Goal: refine taxonomy labels for already grouped URL branches.\n"
        "Important project context:\n"
        "- These groups are produced by deterministic URL algorithms.\n"
        "- This pass is ONLY for url_only_parent + url_only_categorize groups.\n"
        "- needs_algorithm groups are intentionally excluded for now.\n"
        "- Structure must be preserved: no breaking changes to source groups.\n"
        "- We will later attach algorithm clusters under this taxonomy.\n"
        "\n"
        "Hard constraints:\n"
        "1) Never invent categories from random URL fragments.\n"
        "2) Use only the evidence provided in the JSON input.\n"
        "2.1) evidence_terms must come from representative_parent/path_hint/sample_urls.\n"
        "2.2) Do not use host/global context terms as evidence_terms.\n"
        "3) If evidence is weak/ambiguous, return unresolved.\n"
        "4) Keep output strict JSON only (no markdown, no prose).\n"
        "5) evidence_terms must copy exact tokens from provided evidence.\n"
        "\n"
        f"Allowed top_level values: {json.dumps(ALLOWED_TOP_LEVELS)}\n"
        f"Allowed document_type values: {json.dumps(ALLOWED_DOC_TYPES)}\n"
        f"Allowed regulatory_relevance values: {json.dumps(ALLOWED_REGULATORY_RELEVANCE)}\n"
        f"Candidate top_level values for THIS category: {json.dumps(top_level_candidates, ensure_ascii=False)}\n"
        f"Candidate document_type values for THIS category: {json.dumps(doc_type_candidates, ensure_ascii=False)}\n"
        f"Minimum evidence terms required for mapped status: {min_evidence_terms}\n"
        "\n"
        "Host context (top semantic terms):\n"
        f"{json.dumps(host_terms, ensure_ascii=False)}\n"
        "\n"
        "Global context (frequent semantic terms across all categories):\n"
        f"{json.dumps(global_terms, ensure_ascii=False)}\n"
        "\n"
        "Category input:\n"
        f"{category_json}\n"
        "\n"
        "Return JSON only with these keys:\n"
        '- "status"\n'
        '- "top_level"\n'
        '- "sub_level"\n'
        '- "canonical_label"\n'
        '- "document_type"\n'
        '- "regulatory_relevance"\n'
        '- "confidence"\n'
        '- "evidence_terms"\n'
        '- "reason"\n'
        "\n"
        "Important: do NOT output placeholder strings such as "
        '"mapped|unresolved", "one_of_allowed_top_levels", or "term1".\n'
        "\n"
        "Valid mapped example:\n"
        '{"status":"mapped","top_level":"people","sub_level":"academic_staff","canonical_label":"Academic Staff Profiles","document_type":"profile","regulatory_relevance":"low","confidence":0.91,"evidence_terms":["akademik","kadro"],"reason":"Paths and samples consistently point to staff profile pages."}\n'
        "\n"
        "Valid unresolved example:\n"
        '{"status":"unresolved","top_level":"unknown","sub_level":"unknown","canonical_label":"UNRESOLVED","document_type":"unknown","regulatory_relevance":"unknown","confidence":0.18,"evidence_terms":[],"reason":"Evidence is too weak or mixed for safe mapping."}'
    )


def _call_ollama(
    *,
    ollama_url: str,
    ollama_model: str,
    timeout_seconds: float,
    prompt: str,
) -> tuple[dict[str, Any], str, str | None]:
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
        return {}, "", f"ollama_error:{exc}"
    raw = str(parsed.get("response", "")).strip()
    obj = _extract_json_obj(raw)
    if not obj:
        return {}, raw, "malformed_model_output"
    return obj, raw, None


def _call_outlier(
    *,
    outlier_url: str,
    model: str,
    timeout_seconds: float,
    prompt: str,
    system_message: str = "",
) -> tuple[dict[str, Any], str, str | None]:
    endpoint = outlier_url.rstrip("/") + "/chat/stream"
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

    assistant_chunks: list[str] = []
    for line in raw_stream.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            event = json.loads(text)
        except Exception:
            continue
        if isinstance(event, dict) and isinstance(event.get("error"), str) and event["error"].strip():
            return {}, raw_stream[:600], f"outlier_stream_error:{event['error'].strip()}"
        msg = event.get("message", {}) if isinstance(event, dict) else {}
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            chunk = str(msg.get("content", "")).strip()
            if chunk:
                assistant_chunks.append(chunk)

    raw = "".join(assistant_chunks).strip()
    obj = _extract_json_obj(raw)
    if not obj:
        return {}, raw, "malformed_model_output"
    return obj, raw, None


def _call_llm(
    *,
    provider: str,
    ollama_url: str,
    outlier_url: str,
    model: str,
    timeout_seconds: float,
    prompt: str,
    outlier_system_message: str,
) -> tuple[dict[str, Any], str, str | None]:
    if provider == "outlier":
        return _call_outlier(
            outlier_url=outlier_url,
            model=model,
            timeout_seconds=timeout_seconds,
            prompt=prompt,
            system_message=outlier_system_message,
        )
    return _call_ollama(
        ollama_url=ollama_url,
        ollama_model=model,
        timeout_seconds=timeout_seconds,
        prompt=prompt,
    )


def _normalize_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


def _normalize_evidence_terms(raw_terms: Any) -> list[str]:
    if not isinstance(raw_terms, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_terms:
        term = _normalize_text(item).lower()
        if not term:
            continue
        if term in seen:
            continue
        seen.add(term)
        out.append(term)
    return out


def _validate_ai_output(
    *,
    ai_obj: dict[str, Any],
    evidence_text: str,
    top_level_candidates: list[str],
    doc_type_candidates: list[str],
    min_evidence_terms: int,
) -> tuple[dict[str, Any], bool, list[str]]:
    issues: list[str] = []
    status = str(ai_obj.get("status", "unresolved")).strip().lower()
    if status not in {"mapped", "unresolved"}:
        issues.append("invalid_status")
        status = "unresolved"

    top_level = str(ai_obj.get("top_level", "unknown")).strip().lower()
    if top_level not in ALLOWED_TOP_LEVELS:
        issues.append("invalid_top_level")
        top_level = "unknown"

    sub_level = _normalize_text(ai_obj.get("sub_level", "unknown"))
    if not sub_level:
        sub_level = "unknown"

    canonical_label = _normalize_text(ai_obj.get("canonical_label", "UNRESOLVED"))
    if canonical_label.lower() in PLACEHOLDER_LABELS:
        issues.append("placeholder_canonical_label")
        canonical_label = "UNRESOLVED"

    document_type = str(ai_obj.get("document_type", "unknown")).strip().lower()
    if document_type not in ALLOWED_DOC_TYPES:
        issues.append("invalid_document_type")
        document_type = "unknown"

    regulatory_relevance = str(ai_obj.get("regulatory_relevance", "unknown")).strip().lower()
    if regulatory_relevance not in ALLOWED_REGULATORY_RELEVANCE:
        issues.append("invalid_regulatory_relevance")
        regulatory_relevance = "unknown"

    confidence = _coerce_float(ai_obj.get("confidence", 0.0), default=0.0)
    confidence = max(0.0, min(1.0, confidence))

    reason = _normalize_text(ai_obj.get("reason", ""))
    evidence_terms = _normalize_evidence_terms(ai_obj.get("evidence_terms", []))

    evidence_lc = evidence_text.lower()
    grounded_terms = [term for term in evidence_terms if term in evidence_lc]
    if status == "mapped":
        if top_level == "unknown":
            issues.append("mapped_with_unknown_top_level")
        if top_level_candidates and top_level not in set(top_level_candidates):
            issues.append("mapped_top_level_outside_candidates")
        if canonical_label == "UNRESOLVED":
            issues.append("mapped_with_unresolved_label")
        if doc_type_candidates and document_type not in set(doc_type_candidates):
            issues.append("mapped_doc_type_outside_candidates")
        if len(grounded_terms) < min_evidence_terms:
            issues.append("insufficient_grounded_evidence_terms")

    accepted = len(issues) == 0
    if issues and status == "mapped":
        status = "unresolved"
        top_level = "unknown"
        sub_level = "unknown"
        canonical_label = "UNRESOLVED"
        if document_type not in {"unknown", "other"}:
            document_type = "unknown"
        if regulatory_relevance != "unknown":
            regulatory_relevance = "unknown"
        confidence = min(confidence, 0.35)
        accepted = False

    if issues and status == "unresolved":
        accepted = False

    normalized = {
        "status": status,
        "top_level": top_level,
        "sub_level": sub_level,
        "canonical_label": canonical_label,
        "document_type": document_type,
        "regulatory_relevance": regulatory_relevance,
        "confidence": round(confidence, 4),
        "evidence_terms": grounded_terms,
        "reason": reason,
    }
    return normalized, accepted, issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run context-aware taxonomy pass on prepared AI input.")
    parser.add_argument("--llm-provider", type=str, choices=["outlier", "ollama"], default="outlier")
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434")
    parser.add_argument("--outlier-url", type=str, default="http://127.0.0.1:8080")
    parser.add_argument("--outlier-system-message", type=str, default="")
    parser.add_argument("--ollama-model", type=str, default="qwen:4b")
    parser.add_argument("--ollama-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--max-categories", type=int, default=0, help="0 means process all selected rows.")
    parser.add_argument("--start-index", type=int, default=0, help="0-based offset in categories_for_ai.")
    parser.add_argument("--min-evidence-terms", type=int, default=1)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument(
        "--ai-on-rule-matches",
        action="store_true",
        help="Also call AI even when deterministic rule mapping exists (default: skip AI for rule-matched categories).",
    )
    parser.add_argument("--dry-run-count", action="store_true")
    parser.add_argument(
        "--confirm-count",
        type=int,
        default=None,
        help="Safety gate: required for full run when max-categories=0. Must equal selected count.",
    )
    parser.add_argument("--run-name", type=str, default="ai_taxonomy_ollama_pass1")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_json.exists():
        raise FileNotFoundError(f"Input JSON not found: {args.input_json}")
    if args.ollama_timeout_seconds <= 0:
        raise ValueError("--ollama-timeout-seconds must be > 0")
    if args.start_index < 0:
        raise ValueError("--start-index must be >= 0")
    if args.max_categories < 0:
        raise ValueError("--max-categories must be >= 0")
    if args.min_evidence_terms < 0:
        raise ValueError("--min-evidence-terms must be >= 0")
    if args.max_retries < 0:
        raise ValueError("--max-retries must be >= 0")

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    summary = payload.get("summary", {}) or {}
    all_categories = list(payload.get("categories_for_ai", []) or [])
    total_count = len(all_categories)
    total_docs = sum(int(c.get("doc_count", 0)) for c in all_categories)

    if args.start_index >= total_count:
        raise ValueError(
            f"--start-index ({args.start_index}) is out of range for {total_count} categories."
        )

    selected = all_categories[args.start_index :]
    if args.max_categories > 0:
        selected = selected[: args.max_categories]
    selected_count = len(selected)
    selected_docs = sum(int(c.get("doc_count", 0)) for c in selected)

    print(f"[ai-taxonomy] input={args.input_json}")
    print(f"[ai-taxonomy] total_categories={total_count} total_docs={total_docs}")
    print(
        f"[ai-taxonomy] selected_count={selected_count} selected_docs={selected_docs} "
        f"(start_index={args.start_index}, max_categories={args.max_categories})"
    )

    global_terms_counter, host_terms_map, host_counts = _build_global_context(all_categories)
    top_hosts = host_counts.most_common(10)
    print(f"[ai-taxonomy] top_hosts={top_hosts}")

    if args.dry_run_count:
        print("[ai-taxonomy] dry run only; no Ollama calls were made.")
        return 0

    full_run = args.max_categories == 0 and args.start_index == 0 and selected_count == total_count
    if full_run and args.confirm_count is None:
        print(
            "[ai-taxonomy] refusing full run without --confirm-count. "
            f"Use --confirm-count {selected_count} after reviewing the count gate."
        )
        return 2
    if args.confirm_count is not None and args.confirm_count != selected_count:
        print(
            f"[ai-taxonomy] --confirm-count mismatch: expected {selected_count}, got {args.confirm_count}"
        )
        return 2

    selected_model = args.ollama_model.strip() or "qwen:4b"
    if args.llm_provider == "outlier" and selected_model == "qwen:4b":
        selected_model = "claude-opus-4-6"

    print(
        f"[ai-taxonomy] llm_provider={args.llm_provider} model={selected_model} "
        f"ollama_url={args.ollama_url} outlier_url={args.outlier_url}"
    )

    global_terms = [term for term, _count in global_terms_counter.most_common(30)]
    results: list[dict[str, Any]] = []
    llm_errors = 0
    unresolved = 0
    mapped = 0
    validation_failures = 0
    ai_mapped = 0
    rule_mapped = 0

    for idx, category in enumerate(selected, start=1):
        cluster_id = int(category.get("cluster_id", 0))
        hint = category.get("path_hint", {}) or {}
        host = str(hint.get("host", "unknown")).lower() or "unknown"
        category_tokens = _collect_category_tokens(category)
        rule_guess = _heuristic_fallback(category_tokens)
        top_level_candidates = _infer_top_level_candidates(category_tokens)
        doc_type_candidates = _infer_doc_type_candidates(category_tokens)
        host_terms = [term for term, _count in host_terms_map.get(host, Counter()).most_common(20)]
        evidence_blob = json.dumps(
            {
                "representative_parent": category.get("representative_parent"),
                "path_hint": category.get("path_hint"),
                "sample_urls": category.get("sample_urls"),
            },
            ensure_ascii=False,
        )
        prompt = _build_prompt(
            category=category,
            host_terms=host_terms,
            global_terms=global_terms,
            top_level_candidates=top_level_candidates,
            doc_type_candidates=doc_type_candidates,
            min_evidence_terms=args.min_evidence_terms,
        )

        ai_obj: dict[str, Any] = {}
        raw_response = ""
        call_error: str | None = None
        mapping_source = "ai"
        normalized = {
            "status": "unresolved",
            "top_level": "unknown",
            "sub_level": "unknown",
            "canonical_label": "UNRESOLVED",
            "document_type": "unknown",
            "regulatory_relevance": "unknown",
            "confidence": 0.0,
            "evidence_terms": [],
            "reason": "not_processed",
        }
        accepted = False
        issues: list[str] = []
        if rule_guess and not args.ai_on_rule_matches:
            normalized = rule_guess
            accepted = True
            issues = []
            mapping_source = "rule"
        else:
            retry_prompt = prompt
            attempts = max(1, args.max_retries + 1)
            for _attempt in range(attempts):
                ai_obj, raw_response, call_error = _call_llm(
                    provider=args.llm_provider,
                    ollama_url=args.ollama_url,
                    outlier_url=args.outlier_url,
                    model=selected_model,
                    timeout_seconds=args.ollama_timeout_seconds,
                    prompt=retry_prompt,
                    outlier_system_message=args.outlier_system_message,
                )
                if call_error:
                    issues = ["llm_call_failed"]
                    continue

                normalized, accepted, issues = _validate_ai_output(
                    ai_obj=ai_obj,
                    evidence_text=evidence_blob,
                    top_level_candidates=top_level_candidates,
                    doc_type_candidates=doc_type_candidates,
                    min_evidence_terms=args.min_evidence_terms,
                )
                if accepted:
                    break
                retry_prompt = (
                    prompt
                    + "\n\nYour previous output was invalid for this strict parser. "
                    + "Fix it and return only concrete JSON values using allowed enums. "
                    + f"Invalid reasons: {json.dumps(issues)}"
                )

            if call_error:
                llm_errors += 1
                normalized = {
                    "status": "unresolved",
                    "top_level": "unknown",
                    "sub_level": "unknown",
                    "canonical_label": "UNRESOLVED",
                    "document_type": "unknown",
                    "regulatory_relevance": "unknown",
                    "confidence": 0.0,
                    "evidence_terms": [],
                    "reason": call_error,
                }
                accepted = False
                issues = ["llm_call_failed"]

            if (not accepted or normalized["status"] == "unresolved") and rule_guess:
                normalized = rule_guess
                accepted = True
                issues = [*issues, "fallback_rule_applied"]
                mapping_source = "ai_then_rule"

        if normalized["status"] == "mapped":
            mapped += 1
            if mapping_source == "ai":
                ai_mapped += 1
            else:
                rule_mapped += 1
        else:
            unresolved += 1
        if not accepted:
            validation_failures += 1

        result_row = {
            "cluster_id": cluster_id,
            "decision": category.get("decision"),
            "doc_count": category.get("doc_count"),
            "representative_parent": category.get("representative_parent"),
            "path_hint": category.get("path_hint"),
            "sample_urls": category.get("sample_urls"),
            "candidate_top_levels": top_level_candidates,
            "candidate_document_types": doc_type_candidates,
            "ai_taxonomy": normalized,
            "validation": {
                "accepted": accepted,
                "mapping_source": mapping_source,
                "issues": issues,
                "raw_response_excerpt": raw_response[:400],
            },
        }
        results.append(result_row)
        print(
            f"[ai-taxonomy] {idx}/{selected_count} "
            f"cluster={cluster_id} status={normalized['status']} top={normalized['top_level']} source={mapping_source}"
        )

    out_summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_input_json": str(args.input_json),
        "source_input_summary": summary,
        "llm_provider": args.llm_provider,
        "ollama_url": args.ollama_url,
        "outlier_url": args.outlier_url,
        "model": selected_model,
        "selected_count": selected_count,
        "selected_docs": selected_docs,
        "start_index": args.start_index,
        "max_categories": args.max_categories,
        "confirm_count": args.confirm_count,
        "mapped_count": mapped,
        "ai_mapped_count": ai_mapped,
        "rule_mapped_count": rule_mapped,
        "unresolved_count": unresolved,
        "validation_failures": validation_failures,
        "llm_errors": llm_errors,
        "top_hosts": top_hosts,
    }

    out_payload = {
        "summary": out_summary,
        "results": results,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_json = args.output_dir / f"{args.run_name}_{stamp}.json"
    out_json.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ai-taxonomy] output: {out_json}")
    print(
        f"[ai-taxonomy] mapped={mapped} unresolved={unresolved} "
        f"validation_failures={validation_failures} llm_errors={llm_errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
