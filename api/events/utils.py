from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip())


def canonicalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")
    return f"{host}{path}"


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_source_key(url: str, content_hash: str) -> str:
    return hash_text(f"{canonicalize_url(url)}:{content_hash}")


def make_event_fingerprint(obligation_text: str, target_role: str) -> str:
    normalized = normalize_text(obligation_text).lower()
    role = (target_role or "").strip().lower()
    return hash_text(f"{normalized}|{role}")
