"""Tiny OpenRouter client for ground-truth labeling."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

PROVIDERS_PATH = Path.home() / ".config" / "agent" / "providers.json"
MODEL = os.getenv("JUDGE_MODEL", "google/gemini-2.5-flash-lite")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def _load_key() -> str:
    data = json.loads(PROVIDERS_PATH.read_text())
    for p in data["providers"]:
        if p["name"] == "openrouter":
            return p["api_key"]
    raise RuntimeError("openrouter key not found")


_API_KEY = _load_key()


def judge(system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 200, retries: int = 3) -> str:
    payload = {
        "model": MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=60.0) as c:
                r = c.post(BASE_URL, json=payload, headers=headers)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"judge failed after {retries}: {last_err}")


def judge_json(system: str, user: str, **kw) -> dict:
    """Parse JSON out of judge response, tolerating prose wrappers."""
    raw = judge(system, user, **kw)
    s = raw
    if "```" in s:
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1:
        return {"_raw": raw, "_parse_error": True}
    try:
        return json.loads(s[start : end + 1])
    except Exception:
        return {"_raw": raw, "_parse_error": True}
