#!/usr/bin/env python3
"""Step 16: Retrieval-quality audit of the stratified RAPTOR tree.

LLM thinks like a student/staff member querying the RAG system:
  1. How often will this leaf be queried? (retrieval importance)
  2. For high-importance leaves: is the label crystal-clear?
     Do all docs belong? Would natural-language questions route here?
  3. For low-importance leaves: basic sanity only.

Two passes:
  Pass 1 — batch scan (10 leaves/call): assign importance + quick flag
  Pass 2 — deep dive: flagged high-importance leaves get 20+ real titles
            from DB and a detailed verdict (relabel / split / ok)

Output:
  flow/16_audit_tree/audit_report.json  — full machine-readable results
  flow/16_audit_tree/audit_report.md    — prioritized human-readable report
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import text

API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.session import SessionLocal  # noqa: E402

FLOW = API_ROOT / "scripts/experiments/results/categorization/flow"
TREE_PATH = FLOW / "15_stratified_raptor/stratified_tree.json"
OUTPUT_DIR = FLOW / "16_audit_tree"

# ---------------------------------------------------------------------------
# Retrieval importance heuristics
# High = student/staff queries this daily | Low = rarely queried
# ---------------------------------------------------------------------------

# (top_category, sub_category) → importance override
IMPORTANCE_OVERRIDES: dict[tuple[str, str], str] = {}

# Top-level defaults
TOP_IMPORTANCE: dict[str, str] = {
    "regulations":   "critical",   # students query regulations constantly
    "academics":     "high",       # course catalog, programs, graduation rules
    "admissions":    "high",       # applicants query this heavily
    "student_life":  "high",       # internship, career, counseling
    "international": "medium",     # Erasmus students, but repetitive
    "administration":"medium",
    "research":      "low",
    "quality":       "low",        # internal; students rarely query WSCUC
    "news":          "low",
    "events":        "low",
    "people":        "low",        # name lookups handled by profile search
}

# Sub-category keywords that bump importance up
HIGH_SIGNAL_WORDS = {
    "course", "catalog", "ects", "internship", "scholarship", "regulation",
    "handbook", "graduation", "thesis", "double_major", "minor", "financial",
    "exam", "registration", "transfer", "discipline", "disability", "career",
    "counseling", "admissions", "tuition", "fee", "program",
}


def _infer_importance(top: str, sub: str, leaf_name: str, doc_count: int) -> str:
    key = (top, sub)
    if key in IMPORTANCE_OVERRIDES:
        return IMPORTANCE_OVERRIDES[key]
    base = TOP_IMPORTANCE.get(top, "low")
    # Bump up if sub/leaf contains high-signal words
    combined = (sub + " " + leaf_name).lower().replace("_", " ")
    if any(w in combined for w in HIGH_SIGNAL_WORDS):
        if base == "low":
            base = "medium"
        elif base == "medium":
            base = "high"
    return base


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_titles_for_ids(db, doc_ids: list[str], limit: int = 25) -> list[str]:
    if not doc_ids:
        return []
    sample = random.sample(doc_ids, min(limit, len(doc_ids)))
    rows = db.execute(
        text("SELECT COALESCE(title,'') FROM knowledge_base "
             "WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": "{" + ",".join(sample) + "}"},
    ).fetchall()
    return [r[0].strip() for r in rows if r[0].strip()]


def _fetch_docs_with_content(db, doc_ids: list[str], limit: int = 20,
                              snippet_len: int = 280) -> list[dict]:
    """Fetch title + content snippet for each sampled doc."""
    if not doc_ids:
        return []
    sample = random.sample(doc_ids, min(limit, len(doc_ids)))
    rows = db.execute(
        text("SELECT id::text, COALESCE(title,''), COALESCE(content,'') "
             "FROM knowledge_base WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": "{" + ",".join(sample) + "}"},
    ).fetchall()
    results = []
    for rid, title, content in rows:
        snippet = content.replace("\n", " ").strip()[:snippet_len]
        if len(content) > snippet_len:
            snippet += "…"
        results.append({"id": rid, "title": title.strip(), "snippet": snippet})
    return results


# ---------------------------------------------------------------------------
# LLM helpers (same proxy pattern as step 15)
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> Any:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    for ch in ["[", "{"]:
        idx = raw.find(ch)
        if idx >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(raw[idx:])
                return obj
            except Exception:
                pass
    return None


def _llm(*, url: str, model: str, system: str, prompt: str, timeout: float) -> tuple[Any, str | None]:
    from urllib import request as req
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "systemMessage": system,
    }).encode()
    r = req.Request(
        url.rstrip("/") + "/chat/stream", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with req.urlopen(r, timeout=timeout) as resp:
            raw_stream = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return None, str(exc)
    parts = []
    for line in raw_stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if isinstance(ev, dict) and isinstance(ev.get("error"), str) and ev["error"].strip():
            return None, ev["error"]
        msg = ev.get("message", {}) if isinstance(ev, dict) else {}
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
            parts.append(str(msg["content"]))
    raw = "".join(parts).strip()
    obj = _parse_json(raw)
    return (obj, None) if obj is not None else (None, f"malformed:{raw[:300]}")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM = (
    "You are a senior information architect auditing a RAG knowledge base "
    "for Istanbul Bilgi University students and staff. "
    "Your job: evaluate document clusters from a retrieval quality perspective — "
    "will real users find exactly what they need? "
    "Be critical. Vague or over-broad clusters in high-query areas are bugs, not features. "
    "Return only valid JSON."
)

PASS1_PROMPT = """\
You are auditing a RAG knowledge base for Istanbul Bilgi University.
Your ONLY job: find clusters where TWO DIFFERENT student intents are mixed together.

The failure mode you are looking for:
  Student A asks "what are the internship rules?" → gets course descriptions mixed in
  Student B asks "what courses does the engineering faculty offer?" → gets staff profiles mixed in
  This is a retrieval FAILURE. These clusters need splitting.

What is NOT a problem:
  A cluster with 500 docs that are all the same type → fine, just big
  A cluster with a vague name but coherent content → relabel only, not split
  Low-query clusters (staff profiles, news, events) → almost never need action

For each cluster, ask ONE question: "Could two different students with DIFFERENT questions
BOTH retrieve from this cluster, and be disappointed by each other's documents?"
  YES → flag it (mixed_content or needs_split)
  NO  → it's ok (even if the label is imperfect)

RETRIEVAL IMPORTANCE (assign based on what students actually query daily):
  critical = internship rules, scholarship procedures, graduation requirements, exam rules, double major rules, course add/drop
  high     = course catalog, program info, career services, financial aid, academic calendar
  medium   = Erasmus details, transfer procedures, club info
  low      = staff profiles, news articles, quality reports, event announcements

Return a JSON ARRAY — one object per cluster:
{{
  "id": "...",
  "importance": "critical|high|medium|low",
  "status": "ok|warn|critical_issue",
  "issue_type": "none|mixed_content|needs_split|wrong_tier",
  "mixed_intents": ["intent A description", "intent B description"] or [],
  "note": "one sentence — if mixed, name the two intents. if ok, say ok."
}}

CLUSTERS:
{clusters_block}
"""

PASS2_PROMPT = """\
CLUSTER: {top} > {sub} > {leaf}
{count} docs | importance={importance} | flagged: {issue_type} — {note}

Sample docs ({n_docs} random, title + first 280 chars of content):
{docs_block}

Q: Could two students with DIFFERENT questions BOTH retrieve from this cluster and be disappointed by each other's docs?
Return ONE JSON object, no markdown:
{{"verdict":"ok|split|move","student_questions":["..."],"split_into":[{{"label":"...","what":"...","who_asks":"..."}}],"move_to":null,"retrieval_risk":"high|medium|low","needs_recluster":false,"reasoning":"max 2 sentences"}}
"""

PASS3_SUMMARY_PROMPT = """\
You are summarizing a document for a university knowledge base index.
This document will be re-embedded and re-clustered to find its correct home in the taxonomy.

Document details:
  Current (possibly wrong) cluster: {current_path}
  Title: {title}
  Content snippet: {snippet}

Write a 1-2 sentence summary that captures:
- What TYPE of document this is (regulation/handbook/news/course/profile/report/etc.)
- Who OWNS it (which office/department/faculty)
- Who it's FOR (students/staff/applicants/faculty)
- What specific TOPIC it covers

Be precise. Bad: "University document about internships."
Good: "Official internship directive from the Student Affairs Office governing application procedures and employer requirements for undergraduate students."

Return only the summary string, no JSON.
"""


# ---------------------------------------------------------------------------
# Pass 1: batch scan
# ---------------------------------------------------------------------------

def pass1_scan(leaves: list[dict], llm_url: str, model: str, batch_size: int = 10) -> list[dict]:
    results: list[dict] = []
    batches = [leaves[i:i+batch_size] for i in range(0, len(leaves), batch_size)]
    print(f"[pass1] {len(leaves)} leaves → {len(batches)} batches")

    for bi, batch in enumerate(batches):
        blocks = []
        for leaf in batch:
            titles_preview = "\n".join(f"    • {t[:90]}" for t in leaf["sample_titles"][:8])
            blocks.append(
                f"ID: {leaf['id']}\n"
                f"Path: {leaf['top']} > {leaf['sub']} > {leaf['leaf']}\n"
                f"Docs: {leaf['doc_count']} | Tier: {leaf['tier']}\n"
                f"Inferred importance: {leaf['importance']}\n"
                f"Sample titles:\n{titles_preview}"
            )
        prompt = PASS1_PROMPT.format(clusters_block="\n\n".join(blocks))

        for attempt in range(3):
            obj, err = _llm(url=llm_url, model=model, system=SYSTEM,
                            prompt=prompt, timeout=120)
            if obj is not None and isinstance(obj, list):
                break
            print(f"  [pass1] batch {bi+1} attempt {attempt+1} failed: {err}")
            time.sleep(3)
        else:
            # fallback: mark all as unknown
            for leaf in batch:
                results.append({**leaf, "p1_status": "unknown", "p1_issue": "none",
                                 "p1_note": "llm_failed", "p1_action": "none",
                                 "p1_importance": leaf["importance"]})
            continue

        # merge LLM results back
        id_to_leaf = {l["id"]: l for l in batch}
        for item in obj:
            lid = str(item.get("id", ""))
            base = id_to_leaf.get(lid, {})
            results.append({
                **base,
                "p1_status":        item.get("status", "ok"),
                "p1_issue":         item.get("issue_type", "none"),
                "p1_note":          item.get("note", ""),
                "p1_mixed_intents": item.get("mixed_intents", []),
                "p1_importance":    item.get("importance", base.get("importance", "low")),
            })

        pct = (bi + 1) / len(batches) * 100
        flagged = sum(1 for r in results if r.get("p1_status") != "ok")
        print(f"  [pass1] {bi+1}/{len(batches)} ({pct:.0f}%) | flagged so far: {flagged}")
        time.sleep(1)

    return results


# ---------------------------------------------------------------------------
# Pass 2: deep investigation with content snippets
# ---------------------------------------------------------------------------

def pass2_investigate(flagged: list[dict], db, llm_url: str, model: str) -> list[dict]:
    results = []
    print(f"\n[pass2] deep investigating {len(flagged)} flagged leaves (title + content)")

    for i, leaf in enumerate(flagged):
        docs = _fetch_docs_with_content(db, leaf["doc_ids"], limit=20)
        docs_block = "\n\n".join(
            f"  [{j+1}] Title: {d['title'][:100]}\n"
            f"       Content: {d['snippet']}"
            for j, d in enumerate(docs)
        )

        prompt = PASS2_PROMPT.format(
            top=leaf["top"], sub=leaf["sub"], leaf=leaf["leaf"],
            count=leaf["doc_count"],
            importance=leaf["p1_importance"],
            issue_type=leaf["p1_issue"],
            note=leaf["p1_note"],
            n_docs=len(docs),
            docs_block=docs_block,
        )

        for attempt in range(3):
            obj, err = _llm(url=llm_url, model=model, system=SYSTEM,
                            prompt=prompt, timeout=180)
            if isinstance(obj, list) and obj:
                obj = obj[0]
            if isinstance(obj, str) and len(obj) > 5:
                # LLM returned a plain string — treat as relabel suggestion
                obj = {"verdict": "relabel", "new_label": obj, "confidence": 0.75,
                       "split_into": [], "move_to": None,
                       "explanation": f"LLM suggested relabel to: {obj[:120]}",
                       "retrieval_risk": "low", "needs_recluster": False}
            if obj is not None and isinstance(obj, dict):
                break
            print(f"  [pass2] '{leaf['leaf'][:40]}' attempt {attempt+1}: {err or repr(obj)}")
            time.sleep(4)
        else:
            obj = {"verdict": "unknown", "confidence": 0, "explanation": "llm_failed",
                   "retrieval_risk": "unknown", "needs_recluster": False}

        results.append({**leaf, "p2": obj})
        verdict = obj.get("verdict", "?")
        risk = obj.get("retrieval_risk", "?")
        recluster = " [RECLUSTER]" if obj.get("needs_recluster") else ""
        print(f"  [{i+1}/{len(flagged)}] {leaf['leaf'][:50]} → {verdict} "
              f"(risk={risk}){recluster}")
        time.sleep(1)

    return results


# ---------------------------------------------------------------------------
# Pass 3: re-cluster mixed-content leaves
# Each doc gets an LLM summary from its content, then re-embedded + re-clustered
# ---------------------------------------------------------------------------

def pass3_recluster(needs_recluster: list[dict], db, llm_url: str, model: str,
                    output_dir: Path) -> list[dict]:
    """For leaves flagged needs_recluster=True: summarize each doc from content,
    re-embed summaries with Jina v3, k-means cluster, LLM labels new groups."""
    print(f"\n[pass3] re-clustering {len(needs_recluster)} mixed leaves")

    results = []
    for leaf_idx, leaf in enumerate(needs_recluster):
        leaf_path = f"{leaf['top']} > {leaf['sub']} > {leaf['leaf']}"
        print(f"\n  [{leaf_idx+1}/{len(needs_recluster)}] {leaf_path} ({leaf['doc_count']} docs)")

        # Fetch ALL docs in this leaf with content
        all_docs = _fetch_docs_with_content(db, leaf["doc_ids"],
                                            limit=len(leaf["doc_ids"]), snippet_len=400)
        if len(all_docs) < 4:
            print(f"    skipping — only {len(all_docs)} docs fetched")
            results.append({**leaf, "p3": {"skipped": True, "reason": "too_few_docs"}})
            continue

        # Step A: LLM summarizes each doc (batches of 8)
        print(f"    summarizing {len(all_docs)} docs…")
        summaries: list[dict] = []
        for bi in range(0, len(all_docs), 8):
            batch = all_docs[bi:bi+8]
            # Summarize each doc individually (parallel-friendly prompt)
            for doc in batch:
                raw_prompt = PASS3_SUMMARY_PROMPT.format(
                    current_path=leaf_path,
                    title=doc["title"][:120],
                    snippet=doc["snippet"],
                )
                for attempt in range(2):
                    obj, err = _llm(url=llm_url, model=model, system=SYSTEM,
                                    prompt=raw_prompt, timeout=60)
                    # Summary comes back as raw string, not JSON
                    if obj is None and err and err.startswith("malformed:"):
                        # Extract the raw text that failed JSON parsing
                        raw_text = err[len("malformed:"):]
                        obj = raw_text.strip().strip('"').strip()
                    if obj and isinstance(obj, str) and len(obj) > 10:
                        summaries.append({"id": doc["id"], "title": doc["title"],
                                          "summary": obj})
                        break
                    time.sleep(1)
                else:
                    # fallback: use title as summary
                    summaries.append({"id": doc["id"], "title": doc["title"],
                                      "summary": doc["title"]})

        print(f"    {len(summaries)} summaries done — re-embedding…")

        # Step B: Re-embed summaries with Jina v3
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model_jina = SentenceTransformer("jinaai/jina-embeddings-v3", trust_remote_code=True)
        texts = [s["summary"] for s in summaries]
        vecs = model_jina.encode(texts, task="separation", truncate_dim=512,
                                 normalize_embeddings=True, show_progress_bar=False)

        # Step C: K-means — choose k based on doc count and split_into hints
        split_hints = leaf.get("p2", {}).get("split_into", [])
        k = max(2, min(len(split_hints) if split_hints else 3, max(2, len(summaries) // 8)))
        k = min(k, len(summaries) - 1)
        print(f"    k-means k={k}…")

        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(vecs)

        # Step D: LLM labels new clusters
        new_leaves = []
        for cid in range(k):
            idxs = [j for j, l in enumerate(labels) if l == cid]
            cluster_summaries = [summaries[j]["summary"] for j in idxs[:12]]
            cluster_titles    = [summaries[j]["title"]   for j in idxs[:12]]
            doc_ids_in_cluster = [summaries[j]["id"]     for j in idxs]

            label_prompt = (
                f"Given these document summaries from a university knowledge base, "
                f"write a precise 4-8 word label for this cluster.\n"
                f"Parent path: {leaf_path}\n"
                f"Summaries:\n" +
                "\n".join(f"  • {s[:150]}" for s in cluster_summaries) +
                "\n\nReturn only the label string."
            )
            obj, err = _llm(url=llm_url, model=model, system=SYSTEM,
                            prompt=label_prompt, timeout=60)
            if obj is None and err and err.startswith("malformed:"):
                obj = err[len("malformed:"):].strip().strip('"')
            label = (obj or f"Cluster {cid+1}").strip()[:120]

            new_leaves.append({
                "label": label,
                "doc_count": len(idxs),
                "doc_ids": doc_ids_in_cluster,
                "sample_titles": cluster_titles[:5],
            })
            print(f"      cluster {cid}: [{len(idxs)} docs] {label}")

        results.append({
            **leaf,
            "p3": {
                "skipped": False,
                "new_leaves": new_leaves,
                "original_leaf": leaf["leaf"],
                "original_path": leaf_path,
            }
        })

    # Save intermediate pass3 results
    p3_path = output_dir / "pass3_recluster.json"
    p3_path.write_text(json.dumps(
        [{"leaf": r["leaf"], "top": r["top"], "sub": r["sub"], "p3": r["p3"]}
         for r in results],
        ensure_ascii=False, indent=2
    ))
    print(f"\n[pass3] saved → {p3_path}")
    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _md_report(p1_results: list[dict], p2_results: list[dict], output_dir: Path) -> Path:
    p2_by_id = {r["id"]: r for r in p2_results}

    # Sort by retrieval risk then importance
    risk_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
    imp_order  = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    flagged_p1  = [r for r in p1_results if r.get("p1_status") != "ok"]
    clean_p1    = [r for r in p1_results if r.get("p1_status") == "ok"]

    lines = [
        "# RAG Tree Audit Report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        f"- Total leaves audited: {len(p1_results)}",
        f"- Clean (Pass 1): {len(clean_p1)}",
        f"- Flagged (Pass 1): {len(flagged_p1)}",
        f"- Deep-investigated (Pass 2): {len(p2_results)}",
        "",
    ]

    # Critical issues first
    critical_p2 = sorted(
        [r for r in p2_results if r.get("p2", {}).get("retrieval_risk") == "high"],
        key=lambda r: imp_order.get(r.get("p1_importance", "low"), 3)
    )
    if critical_p2:
        lines += ["## CRITICAL — Fix These First (High Retrieval Risk)", ""]
        for r in critical_p2:
            p2 = r["p2"]
            lines += [
                f"### `{r['top']} > {r['sub']} > {r['leaf']}`",
                f"- **Docs:** {r['doc_count']} | **Importance:** {r['p1_importance']}",
                f"- **Issue:** {r['p1_issue']} — {r['p1_note']}",
                f"- **Verdict:** {p2.get('verdict')} (conf={p2.get('confidence', 0):.2f})",
                f"- **Explanation:** {p2.get('explanation', '')}",
            ]
            if p2.get("new_label"):
                lines.append(f"- **Relabel to:** `{p2['new_label']}`")
            if p2.get("split_into"):
                lines.append("- **Split into:**")
                for g in p2["split_into"]:
                    lines.append(f"  - {g}")
            if p2.get("move_to"):
                lines.append(f"- **Move to:** `{p2['move_to']}`")
            lines.append("")

    # Medium risk
    medium_p2 = [r for r in p2_results if r.get("p2", {}).get("retrieval_risk") == "medium"]
    if medium_p2:
        lines += ["## MEDIUM — Should Fix", ""]
        for r in medium_p2:
            p2 = r["p2"]
            lines += [
                f"### `{r['top']} > {r['sub']} > {r['leaf']}`",
                f"- **Docs:** {r['doc_count']} | **Importance:** {r['p1_importance']}",
                f"- **Issue:** {r['p1_issue']} — {r['p1_note']}",
                f"- **Verdict:** {p2.get('verdict')} — {p2.get('explanation', '')}",
            ]
            if p2.get("new_label"):
                lines.append(f"- **Relabel to:** `{p2['new_label']}`")
            if p2.get("split_into"):
                lines.append(f"- **Split into:** {' | '.join(p2['split_into'])}")
            lines.append("")

    # Pass 1 flags not deep-investigated
    p1_only_flags = [r for r in flagged_p1 if r["id"] not in p2_by_id]
    if p1_only_flags:
        lines += ["## Pass 1 Flags (Not Deep-Investigated)", ""]
        for r in sorted(p1_only_flags, key=lambda x: imp_order.get(x.get("p1_importance","low"),3)):
            lines.append(
                f"- `{r['top']} > {r['sub']} > {r['leaf']}` "
                f"[{r['doc_count']} docs] — {r['p1_issue']}: {r['p1_note']}"
            )
        lines.append("")

    # Clean summary
    lines += ["## Clean Leaves (No Issues)", ""]
    by_top: dict[str, list] = defaultdict(list)
    for r in clean_p1:
        by_top[r["top"]].append(r["leaf"])
    for top, leafs in sorted(by_top.items()):
        lines.append(f"**{top}** ({len(leafs)} clean leaves)")
    lines.append("")

    path = output_dir / "audit_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree",    default=str(TREE_PATH))
    ap.add_argument("--out",     default=str(OUTPUT_DIR))
    ap.add_argument("--proxy",   default="http://127.0.0.1:8080")
    ap.add_argument("--model",   default="claude-opus-4-6")
    ap.add_argument("--batch",   type=int, default=10, help="Leaves per Pass 1 batch")
    ap.add_argument("--p2-importance", nargs="+",
                    default=["critical", "high"],
                    help="Only deep-investigate leaves at these importance levels")
    ap.add_argument("--p2-limit", type=int, default=120,
                    help="Max flagged leaves to send to Pass 2")
    ap.add_argument("--skip-p3", action="store_true",
                    help="Skip Pass 3 re-clustering (audit only)")
    ap.add_argument("--seed",    type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load tree
    print(f"[init] Loading tree from {args.tree}")
    tree_data = json.loads(Path(args.tree).read_text())
    tree = tree_data["tree"]

    # Flatten all leaves
    db = SessionLocal()
    print("[init] Fetching sample titles for all leaves…")
    leaves: list[dict] = []
    leaf_id = 0
    for top, tn in sorted(tree.items()):
        for sub, sn in sorted(tn["sub_levels"].items()):
            for leaf_name, lv in sorted(sn["leaves"].items()):
                doc_ids = lv.get("doc_ids", [])
                sample_titles = _fetch_titles_for_ids(db, doc_ids, limit=10)
                importance = _infer_importance(top, sub, leaf_name, lv["doc_count"])
                leaves.append({
                    "id":            str(leaf_id),
                    "top":           top,
                    "sub":           sub,
                    "leaf":          leaf_name,
                    "doc_count":     lv["doc_count"],
                    "tier":          lv.get("tier", ""),
                    "doc_ids":       doc_ids,
                    "sample_titles": sample_titles,
                    "importance":    importance,
                })
                leaf_id += 1

    print(f"[init] {len(leaves)} leaves loaded")

    # Pass 1
    p1 = pass1_scan(leaves, llm_url=args.proxy, model=args.model, batch_size=args.batch)

    # Which leaves go to Pass 2?
    p2_set = args.p2_importance
    flagged_for_p2 = [
        r for r in p1
        if r.get("p1_status") != "ok"
        and r.get("p1_importance", "low") in p2_set
    ]
    # Sort by importance then doc_count desc (biggest high-importance issues first)
    imp_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    flagged_for_p2.sort(key=lambda r: (
        imp_order.get(r.get("p1_importance", "low"), 3),
        -r["doc_count"],
    ))
    flagged_for_p2 = flagged_for_p2[:args.p2_limit]

    # Pass 2: deep-dive with content snippets
    p2 = pass2_investigate(flagged_for_p2, db=db, llm_url=args.proxy, model=args.model)

    # Pass 3: re-cluster genuinely mixed leaves
    p3: list[dict] = []
    if not args.skip_p3:
        needs_recluster = [
            r for r in p2
            if r.get("p2", {}).get("needs_recluster") is True
            and r.get("p2", {}).get("retrieval_risk") in ("high", "medium")
        ]
        if needs_recluster:
            p3 = pass3_recluster(needs_recluster, db=db, llm_url=args.proxy,
                                 model=args.model, output_dir=output_dir)
        else:
            print("\n[pass3] no leaves flagged for re-clustering")

    db.close()

    # Save JSON
    report_json = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_leaves":    len(p1),
            "clean":           sum(1 for r in p1 if r.get("p1_status") == "ok"),
            "flagged_p1":      sum(1 for r in p1 if r.get("p1_status") != "ok"),
            "investigated_p2": len(p2),
            "critical_risk":   sum(1 for r in p2 if r.get("p2",{}).get("retrieval_risk") == "high"),
            "medium_risk":     sum(1 for r in p2 if r.get("p2",{}).get("retrieval_risk") == "medium"),
            "reclustered_p3":  len(p3),
        },
        "p1_results": [{k: v for k, v in r.items() if k != "doc_ids"} for r in p1],
        "p2_results": [{k: v for k, v in r.items() if k != "doc_ids"} for r in p2],
        "p3_results": [{k: v for k, v in r.items() if k != "doc_ids"} for r in p3],
    }
    json_path = output_dir / "audit_report.json"
    json_path.write_text(json.dumps(report_json, ensure_ascii=False, indent=2))

    # Markdown report
    md_path = _md_report(p1, p2, output_dir)

    # Console summary
    s = report_json["summary"]
    print(f"\n{'='*60}")
    print(f"AUDIT COMPLETE")
    print(f"  Total leaves   : {s['total_leaves']}")
    print(f"  Clean (pass 1) : {s['clean']}")
    print(f"  Flagged        : {s['flagged_p1']}")
    print(f"  Deep-dived     : {s['investigated_p2']}")
    print(f"  Critical risk  : {s['critical_risk']}")
    print(f"  Medium risk    : {s['medium_risk']}")
    print(f"  Re-clustered   : {s['reclustered_p3']}")
    print(f"\n  JSON  → {json_path}")
    print(f"  MD    → {md_path}")


if __name__ == "__main__":
    main()
