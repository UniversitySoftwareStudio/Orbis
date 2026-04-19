#!/usr/bin/env python3
"""Step 05: AI iterative tree refinement.

Algorithm:
  1) Load taxonomy_result.json from step 04.
  2) Build a compact tree representation for the AI prompt.
  3) AI proposes structural operations: merge, rename, move.
  4) Apply operations programmatically.
  5) Repeat for --max-iterations.
  6) Export refined tree.

Outputs:
  - refined_tree_result.json  — full payload with per-iteration ops log + final tree
  - refined_tree.json         — final tree only
  - refactor_log.md           — human-readable iteration log
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
except Exception:
    pass

API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))

DEFAULT_TREE_JSON = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "04_build_taxonomy_tree"
    / "taxonomy_result.json"
)
DEFAULT_OUTPUT_DIR = (
    API_ROOT
    / "scripts"
    / "experiments"
    / "results"
    / "categorization"
    / "flow"
    / "05_refactor_tree"
)

SYSTEM_MESSAGE = (
    "You are a university website taxonomy architect. "
    "You review taxonomy trees and propose precise structural improvements. "
    "Always output strict JSON."
)


# ---------------------------------------------------------------------------
# Text utilities
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


def _title(text: str) -> str:
    pieces = [p for p in re.split(r"[^a-zA-Z0-9]+", (text or "").strip()) if p]
    return " ".join(w.capitalize() for w in pieces) if pieces else "General"


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
# LLM callers  (same pattern as other scripts)
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
# Tree utilities
# ---------------------------------------------------------------------------

def _tree_stats(tree: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return (n_top, n_sub, n_leaves, n_docs)."""
    n_top = len(tree)
    n_sub = sum(len(tn["sub_levels"]) for tn in tree.values())
    n_leaves = sum(
        len(sn["leaves"])
        for tn in tree.values()
        for sn in tn["sub_levels"].values()
    )
    n_docs = sum(int(tn.get("doc_count", 0)) for tn in tree.values())
    return n_top, n_sub, n_leaves, n_docs


def _build_compact_tree_text(tree: dict[str, Any]) -> str:
    """Build compact textual representation for the AI prompt."""
    n_top, n_sub, n_leaves, n_docs = _tree_stats(tree)
    lines: list[str] = [
        f"Current taxonomy tree ({n_top} top-levels, {n_leaves} leaves, {n_docs:,} docs):",
        "",
    ]
    for top_name in sorted(tree.keys()):
        top_node = tree[top_name]
        top_docs = int(top_node.get("doc_count", 0))
        top_n_leaves = sum(len(sn["leaves"]) for sn in top_node["sub_levels"].values())
        lines.append(f"{top_name} ({top_docs:,} docs, {top_n_leaves} leaves):")
        for sub_name in sorted(top_node["sub_levels"].keys()):
            sub_node = top_node["sub_levels"][sub_name]
            for leaf_label, leaf in sorted(sub_node["leaves"].items(),
                                           key=lambda x: -x[1].get("doc_count", 0)):
                leaf_docs = int(leaf.get("doc_count", 0))
                lines.append(f"  {sub_name} / {leaf_label}: {leaf_docs:,} docs")
        lines.append("")
    return "\n".join(lines)


def _build_refactor_prompt(tree: dict[str, Any], iteration: int) -> str:
    compact = _build_compact_tree_text(tree)
    return (
        f"{compact}\n"
        f"Iteration {iteration}. Task: Identify the top problems and propose fix operations.\n\n"
        "Focus on:\n"
        "1. Leaves with generic/bad labels (rename) — e.g. 'General Resources', 'Other', 'Misc', 'Content'\n"
        "2. Leaves that clearly overlap in topic (merge) — same concept in different sub-categories\n"
        "3. Leaves in the wrong top-category (move) — clear misclassification\n\n"
        "Operation schemas:\n"
        '  merge:  {"op": "merge", "from_leaf": "top/sub/label", "into_leaf": "top/sub/label", "reason": "..."}\n'
        '  rename: {"op": "rename", "leaf": "top/sub/label", "new_label": "...", "reason": "..."}\n'
        '  move:   {"op": "move", "leaf": "top/sub/label", "new_top": "...", "new_sub": "...", "reason": "..."}\n\n'
        "Rules:\n"
        "- leaf paths use format 'top_category/sub_category/Leaf Label' (exactly as shown above)\n"
        "- Propose at most 15 operations per iteration\n"
        "- Only propose operations you are confident about (high signal)\n"
        "- If the tree looks good, set done=true and return empty operations\n"
        "- Keep all top-category names within the existing set or standard university categories\n\n"
        'Return JSON: {"operations": [...], "quality_assessment": "...", "done": true/false}'
    )


# ---------------------------------------------------------------------------
# Operation application
# ---------------------------------------------------------------------------

def _find_leaf(tree: dict[str, Any], path: str) -> tuple[str, str, str] | None:
    """Parse 'top/sub/Leaf Label' and verify existence. Returns (top, sub, label) or None."""
    parts = path.split("/", 2)
    if len(parts) != 3:
        return None
    top, sub, label = parts[0].strip(), parts[1].strip(), parts[2].strip()
    top_node = tree.get(top)
    if top_node is None:
        return None
    sub_node = top_node.get("sub_levels", {}).get(sub)
    if sub_node is None:
        return None
    if label not in sub_node.get("leaves", {}):
        return None
    return top, sub, label


def _apply_merge(tree: dict[str, Any], op: dict[str, Any]) -> tuple[bool, str]:
    """Merge from_leaf into into_leaf (add doc_count, group_ids, etc.)."""
    from_path = str(op.get("from_leaf", ""))
    into_path = str(op.get("into_leaf", ""))
    from_loc = _find_leaf(tree, from_path)
    into_loc = _find_leaf(tree, into_path)
    if from_loc is None:
        return False, f"from_leaf not found: {from_path}"
    if into_loc is None:
        return False, f"into_leaf not found: {into_path}"
    if from_loc == into_loc:
        return False, "from and into are the same leaf"

    f_top, f_sub, f_label = from_loc
    i_top, i_sub, i_label = into_loc

    from_leaf = tree[f_top]["sub_levels"][f_sub]["leaves"][f_label]
    into_leaf = tree[i_top]["sub_levels"][i_sub]["leaves"][i_label]

    # Merge data into into_leaf
    into_leaf["doc_count"] = int(into_leaf.get("doc_count", 0)) + int(from_leaf.get("doc_count", 0))
    into_leaf["group_count"] = int(into_leaf.get("group_count", 0)) + int(from_leaf.get("group_count", 0))
    into_leaf["group_ids"] = list(into_leaf.get("group_ids", [])) + list(from_leaf.get("group_ids", []))
    existing_parents = into_leaf.get("representative_parents", [])
    for p in from_leaf.get("representative_parents", []):
        if p and p not in existing_parents:
            existing_parents.append(p)
    into_leaf["representative_parents"] = existing_parents[:6]
    existing_urls = into_leaf.get("sample_urls", [])
    for u in from_leaf.get("sample_urls", []):
        if u and u not in existing_urls:
            existing_urls.append(u)
    into_leaf["sample_urls"] = existing_urls[:6]
    srcs = set(into_leaf.get("sources", [])) | set(from_leaf.get("sources", []))
    into_leaf["sources"] = sorted(srcs)

    # Remove from_leaf
    del tree[f_top]["sub_levels"][f_sub]["leaves"][f_label]
    # Update sub-level doc_count
    tree[f_top]["sub_levels"][f_sub]["doc_count"] = max(
        0, int(tree[f_top]["sub_levels"][f_sub].get("doc_count", 0)) - int(from_leaf.get("doc_count", 0))
    )
    tree[f_top]["sub_levels"][f_sub]["group_count"] = max(
        0, int(tree[f_top]["sub_levels"][f_sub].get("group_count", 0)) - int(from_leaf.get("group_count", 0))
    )
    # Remove empty sub-level
    if not tree[f_top]["sub_levels"][f_sub]["leaves"]:
        del tree[f_top]["sub_levels"][f_sub]
    # Update top doc_count
    tree[f_top]["doc_count"] = max(
        0, int(tree[f_top].get("doc_count", 0)) - int(from_leaf.get("doc_count", 0))
    )
    tree[f_top]["group_count"] = max(
        0, int(tree[f_top].get("group_count", 0)) - int(from_leaf.get("group_count", 0))
    )

    return True, f"merged '{from_path}' into '{into_path}'"


def _apply_rename(tree: dict[str, Any], op: dict[str, Any]) -> tuple[bool, str]:
    """Rename a leaf's label."""
    leaf_path = str(op.get("leaf", ""))
    new_label = str(op.get("new_label", "")).strip()
    loc = _find_leaf(tree, leaf_path)
    if loc is None:
        return False, f"leaf not found: {leaf_path}"
    if not new_label:
        return False, "new_label is empty"

    top, sub, old_label = loc
    if new_label == old_label:
        return False, "new_label is same as current label"

    leaf_data = tree[top]["sub_levels"][sub]["leaves"].pop(old_label)
    leaf_data["taxonomy_url"] = f"/taxonomy/{_url_slug(top)}/{_url_slug(sub)}/{_url_slug(new_label)}"
    tree[top]["sub_levels"][sub]["leaves"][new_label] = leaf_data

    return True, f"renamed '{leaf_path}' → '{new_label}'"


def _apply_move(tree: dict[str, Any], op: dict[str, Any]) -> tuple[bool, str]:
    """Move a leaf to a different top/sub location."""
    leaf_path = str(op.get("leaf", ""))
    new_top = str(op.get("new_top", "")).strip()
    new_sub = str(op.get("new_sub", "")).strip()
    loc = _find_leaf(tree, leaf_path)
    if loc is None:
        return False, f"leaf not found: {leaf_path}"
    if not new_top or not new_sub:
        return False, "new_top or new_sub is empty"

    old_top, old_sub, label = loc

    if new_top == old_top and new_sub == old_sub:
        return False, "destination is same as source"

    leaf_data = tree[old_top]["sub_levels"][old_sub]["leaves"].pop(label)
    leaf_data["taxonomy_url"] = f"/taxonomy/{_url_slug(new_top)}/{_url_slug(new_sub)}/{_url_slug(label)}"

    # Update old sub/top counts
    old_sub_doc = int(leaf_data.get("doc_count", 0))
    old_sub_grp = int(leaf_data.get("group_count", 0))
    tree[old_top]["sub_levels"][old_sub]["doc_count"] = max(
        0, int(tree[old_top]["sub_levels"][old_sub].get("doc_count", 0)) - old_sub_doc
    )
    tree[old_top]["sub_levels"][old_sub]["group_count"] = max(
        0, int(tree[old_top]["sub_levels"][old_sub].get("group_count", 0)) - old_sub_grp
    )
    tree[old_top]["doc_count"] = max(0, int(tree[old_top].get("doc_count", 0)) - old_sub_doc)
    tree[old_top]["group_count"] = max(0, int(tree[old_top].get("group_count", 0)) - old_sub_grp)

    # Remove empty sub-level
    if not tree[old_top]["sub_levels"][old_sub]["leaves"]:
        del tree[old_top]["sub_levels"][old_sub]

    # Add to new location
    if new_top not in tree:
        tree[new_top] = {"doc_count": 0, "group_count": 0, "sub_levels": {}}
    tree[new_top]["doc_count"] = int(tree[new_top].get("doc_count", 0)) + old_sub_doc
    tree[new_top]["group_count"] = int(tree[new_top].get("group_count", 0)) + old_sub_grp

    if new_sub not in tree[new_top]["sub_levels"]:
        tree[new_top]["sub_levels"][new_sub] = {"doc_count": 0, "group_count": 0, "leaves": {}}
    tree[new_top]["sub_levels"][new_sub]["doc_count"] = (
        int(tree[new_top]["sub_levels"][new_sub].get("doc_count", 0)) + old_sub_doc
    )
    tree[new_top]["sub_levels"][new_sub]["group_count"] = (
        int(tree[new_top]["sub_levels"][new_sub].get("group_count", 0)) + old_sub_grp
    )
    tree[new_top]["sub_levels"][new_sub]["leaves"][label] = leaf_data

    return True, f"moved '{leaf_path}' → '{new_top}/{new_sub}/{label}'"


def _recompute_counts(tree: dict[str, Any]) -> None:
    """Recompute all sub-level and top-level doc/group counts from leaves (source of truth)."""
    for top_node in tree.values():
        top_docs = 0
        top_grps = 0
        for sub_node in top_node.get("sub_levels", {}).values():
            sub_docs = sum(int(lf.get("doc_count", 0)) for lf in sub_node.get("leaves", {}).values())
            sub_grps = sum(int(lf.get("group_count", 0)) for lf in sub_node.get("leaves", {}).values())
            sub_node["doc_count"] = sub_docs
            sub_node["group_count"] = sub_grps
            top_docs += sub_docs
            top_grps += sub_grps
        top_node["doc_count"] = top_docs
        top_node["group_count"] = top_grps


def _apply_operations(
    tree: dict[str, Any], operations: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply operations to a copy of the tree. Returns (new_tree, ops_log)."""
    new_tree = copy.deepcopy(tree)
    ops_log: list[dict[str, Any]] = []

    for op in operations:
        op_type = str(op.get("op", "")).strip().lower()
        reason = str(op.get("reason", ""))

        if op_type == "merge":
            ok, msg = _apply_merge(new_tree, op)
        elif op_type == "rename":
            ok, msg = _apply_rename(new_tree, op)
        elif op_type == "move":
            ok, msg = _apply_move(new_tree, op)
        else:
            ok, msg = False, f"unknown op: {op_type}"

        ops_log.append({
            "op": op_type,
            "details": op,
            "applied": ok,
            "message": msg,
            "reason": reason,
        })
        status = "OK" if ok else "SKIP"
        print(f"  [{status}] {op_type}: {msg}")

    _recompute_counts(new_tree)
    return new_tree, ops_log


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step 05: AI iterative tree refinement.")
    parser.add_argument("--tree-json", type=Path, default=DEFAULT_TREE_JSON,
                        help="taxonomy_result.json from step 04")
    parser.add_argument("--max-iterations", type=int, default=2)
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

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    if not args.tree_json.exists():
        raise FileNotFoundError(f"tree-json not found: {args.tree_json}")
    if args.max_iterations < 1:
        raise ValueError("--max-iterations must be >= 1")

    print(f"[05] loading tree: {args.tree_json}")
    src = json.loads(args.tree_json.read_text(encoding="utf-8"))
    current_tree: dict[str, Any] = copy.deepcopy(src.get("tree", {}))
    source_summary = src.get("summary", {})

    if not current_tree:
        raise RuntimeError("No 'tree' key found in input JSON.")

    n_top, n_sub, n_leaves, n_docs = _tree_stats(current_tree)
    print(f"[05] initial tree: {n_top} top | {n_sub} sub | {n_leaves} leaves | {n_docs:,} docs")

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
    print(f"[05] LLM provider={args.llm_provider}")

    # ------------------------------------------------------------------
    # Iterative refinement
    # ------------------------------------------------------------------
    iterations_log: list[dict[str, Any]] = []
    ai_calls = 0
    ai_errors = 0

    for iteration in range(1, args.max_iterations + 1):
        print(f"\n[05] === Iteration {iteration}/{args.max_iterations} ===")

        n_top_i, n_sub_i, n_leaves_i, n_docs_i = _tree_stats(current_tree)
        print(f"[05] tree state: {n_top_i} top | {n_sub_i} sub | {n_leaves_i} leaves | {n_docs_i:,} docs")

        if args.llm_provider == "off":
            print("[05] LLM provider=off, skipping AI pass.")
            iterations_log.append({
                "iteration": iteration,
                "tree_before_stats": {"top": n_top_i, "sub": n_sub_i, "leaves": n_leaves_i, "docs": n_docs_i},
                "tree_after_stats": {"top": n_top_i, "sub": n_sub_i, "leaves": n_leaves_i, "docs": n_docs_i},
                "operations_proposed": [],
                "operations_log": [],
                "quality_assessment": "LLM disabled.",
                "ai_done": True,
                "ai_error": None,
            })
            break

        prompt = _build_refactor_prompt(current_tree, iteration)
        ai_calls += 1
        obj, raw_response, err = _call_llm(prompt=prompt, **llm_config)

        if err:
            ai_errors += 1
            print(f"[05] AI error: {err}")
            iterations_log.append({
                "iteration": iteration,
                "tree_before_stats": {"top": n_top_i, "sub": n_sub_i, "leaves": n_leaves_i, "docs": n_docs_i},
                "tree_after_stats": {"top": n_top_i, "sub": n_sub_i, "leaves": n_leaves_i, "docs": n_docs_i},
                "operations_proposed": [],
                "operations_log": [],
                "quality_assessment": f"AI error: {err}",
                "ai_done": False,
                "ai_error": err,
            })
            continue

        operations = obj.get("operations", [])
        quality_assessment = str(obj.get("quality_assessment", ""))
        ai_done = bool(obj.get("done", False))

        print(f"[05] AI proposed {len(operations)} operations. done={ai_done}")
        print(f"[05] quality_assessment: {quality_assessment[:200]}")

        if not operations:
            iterations_log.append({
                "iteration": iteration,
                "tree_before_stats": {"top": n_top_i, "sub": n_sub_i, "leaves": n_leaves_i, "docs": n_docs_i},
                "tree_after_stats": {"top": n_top_i, "sub": n_sub_i, "leaves": n_leaves_i, "docs": n_docs_i},
                "operations_proposed": [],
                "operations_log": [],
                "quality_assessment": quality_assessment,
                "ai_done": ai_done,
                "ai_error": None,
            })
            if ai_done:
                print("[05] AI reports tree is satisfactory. Stopping early.")
                break
            continue

        new_tree, ops_log = _apply_operations(current_tree, operations)

        n_top_a, n_sub_a, n_leaves_a, n_docs_a = _tree_stats(new_tree)
        applied = sum(1 for o in ops_log if o["applied"])
        skipped = sum(1 for o in ops_log if not o["applied"])
        print(
            f"[05] applied={applied} skipped={skipped} | "
            f"leaves: {n_leaves_i} → {n_leaves_a}"
        )

        iterations_log.append({
            "iteration": iteration,
            "tree_before_stats": {"top": n_top_i, "sub": n_sub_i, "leaves": n_leaves_i, "docs": n_docs_i},
            "tree_after_stats": {"top": n_top_a, "sub": n_sub_a, "leaves": n_leaves_a, "docs": n_docs_a},
            "operations_proposed": operations,
            "operations_log": ops_log,
            "quality_assessment": quality_assessment,
            "ai_done": ai_done,
            "ai_error": None,
        })

        current_tree = new_tree

        if ai_done:
            print("[05] AI reports tree is satisfactory. Stopping early.")
            break

    # ------------------------------------------------------------------
    # Final stats
    # ------------------------------------------------------------------
    n_top_f, n_sub_f, n_leaves_f, n_docs_f = _tree_stats(current_tree)
    print(f"\n[05] Final tree: {n_top_f} top | {n_sub_f} sub | {n_leaves_f} leaves | {n_docs_f:,} docs")

    # ------------------------------------------------------------------
    # Build output payloads
    # ------------------------------------------------------------------
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_tree_json": str(args.tree_json),
        "llm_provider": args.llm_provider,
        "llm_model": (
            openai_model if args.llm_provider == "openai"
            else args.outlier_model if args.llm_provider == "outlier"
            else args.ollama_model
        ),
        "max_iterations": args.max_iterations,
        "iterations_run": len(iterations_log),
        "ai_calls": ai_calls,
        "ai_errors": ai_errors,
        "source_tree_summary": source_summary,
        "initial_tree_stats": {"top": n_top, "sub": n_sub, "leaves": n_leaves, "docs": n_docs},
        "final_tree_stats": {"top": n_top_f, "sub": n_sub_f, "leaves": n_leaves_f, "docs": n_docs_f},
    }

    refined_result = {
        "summary": summary,
        "iterations": iterations_log,
        "final_tree": current_tree,
    }

    refined_tree_only = {
        "summary": summary,
        "tree": current_tree,
    }

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "refined_tree_result.json"
    tree_path = args.output_dir / "refined_tree.json"
    log_path = args.output_dir / "refactor_log.md"

    result_path.write_text(json.dumps(refined_result, ensure_ascii=False, indent=2), encoding="utf-8")
    tree_path.write_text(json.dumps(refined_tree_only, ensure_ascii=False, indent=2), encoding="utf-8")

    # Human-readable log
    log_lines: list[str] = ["# Step 05 — Taxonomy Refactor Log", ""]
    log_lines += ["## Summary", ""]
    log_lines += [f"- input: `{args.tree_json}`"]
    log_lines += [f"- LLM provider: `{summary['llm_provider']}` / model: `{summary['llm_model']}`"]
    log_lines += [f"- iterations run: `{summary['iterations_run']}`"]
    log_lines += [f"- ai_calls: `{summary['ai_calls']}` errors: `{summary['ai_errors']}`"]
    log_lines += [
        f"- initial tree: `{n_top}` top / `{n_sub}` sub / `{n_leaves}` leaves / `{n_docs:,}` docs"
    ]
    log_lines += [
        f"- final tree:   `{n_top_f}` top / `{n_sub_f}` sub / `{n_leaves_f}` leaves / `{n_docs_f:,}` docs"
    ]
    log_lines += [""]

    for entry in iterations_log:
        it = entry["iteration"]
        log_lines += [f"## Iteration {it}", ""]
        before = entry["tree_before_stats"]
        after = entry["tree_after_stats"]
        log_lines += [
            f"- before: `{before['top']}` top / `{before['sub']}` sub / `{before['leaves']}` leaves"
        ]
        log_lines += [
            f"- after:  `{after['top']}` top / `{after['sub']}` sub / `{after['leaves']}` leaves"
        ]
        log_lines += [f"- quality_assessment: {entry.get('quality_assessment', '')[:300]}"]
        if entry.get("ai_error"):
            log_lines += [f"- **AI error**: `{entry['ai_error']}`"]
        if entry.get("ai_done"):
            log_lines += ["- AI reports: **done** (tree satisfactory)"]
        log_lines += [""]

        ops_log = entry.get("operations_log", [])
        if ops_log:
            log_lines += ["### Operations", ""]
            log_lines += ["| # | Op | Applied | Message | Reason |"]
            log_lines += ["|---:|---|---:|---|---|"]
            for i, o in enumerate(ops_log, start=1):
                applied_str = "yes" if o["applied"] else "no"
                msg = str(o.get("message", "")).replace("|", "\\|")[:80]
                reason = str(o.get("reason", "")).replace("|", "\\|")[:60]
                log_lines += [f"| {i} | `{o['op']}` | {applied_str} | {msg} | {reason} |"]
            log_lines += [""]
        else:
            log_lines += ["*(no operations)*", ""]

    log_lines += ["## Final Tree", ""]
    log_lines += ["| Top | Sub | Leaf | Docs |"]
    log_lines += ["|---|---|---|---:|"]
    for top_name in sorted(current_tree.keys()):
        top_node = current_tree[top_name]
        for sub_name in sorted(top_node.get("sub_levels", {}).keys()):
            sub_node = top_node["sub_levels"][sub_name]
            for leaf_label, leaf in sorted(sub_node.get("leaves", {}).items(),
                                           key=lambda x: -x[1].get("doc_count", 0)):
                lbl = leaf_label.replace("|", "\\|")
                log_lines += [f"| `{top_name}` | `{sub_name}` | {lbl} | {leaf.get('doc_count', 0):,} |"]
    log_lines += [""]

    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    print(f"[05] refined_tree_result: {result_path}")
    print(f"[05] refined_tree:        {tree_path}")
    print(f"[05] refactor_log:        {log_path}")
    print(
        f"[05] DONE — leaves: {n_leaves} → {n_leaves_f} | "
        f"ai_calls={ai_calls} errors={ai_errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
