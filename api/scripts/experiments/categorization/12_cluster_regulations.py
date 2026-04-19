#!/usr/bin/env python3
"""Step 12: Targeted regulation clustering — extract, cluster, label, merge.

Strategy (cheap & precise):
  1. Extract ~1500 regulation-signal docs from DB (URL + title patterns)
  2. Cluster by embedding (MiniBatchKMeans, k=auto)
  3. LLM sees TITLES ONLY per cluster (never doc content) → names the category
  4. Replace tree["regulations"] with the new high-quality subtree

Cost: ~N_clusters × 40 titles × ~8 tokens each = tiny.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest

import numpy as np
from dotenv import load_dotenv
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import text

API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.append(str(API_ROOT))
load_dotenv(API_ROOT / ".env")

from database.session import SessionLocal  # noqa: E402

FLOW = API_ROOT / "scripts/experiments/results/categorization/flow"
DEFAULT_TREE_JSON = FLOW / "05_refactor_tree/refined_tree.json"
DEFAULT_OUTPUT_DIR = FLOW / "12_cluster_regulations"

# ---------------------------------------------------------------------------
# SQL — regulation signal extraction
# ---------------------------------------------------------------------------

REGULATION_SQL = text("""
SELECT
    id::text          AS kb_id,
    COALESCE(title,'') AS title,
    COALESCE(url,'')   AS url,
    embedding
FROM knowledge_base
WHERE (
    -- URL-pattern match: strict regulation paths
    url ~* '/(mevzuat|yonetmelik|yonerge|talimat|genelge|sozlesme|sözleşme|statute|bylaw|regulation|handbook)([/?#]|$)'
    OR (
        -- Title-keyword match
        title ILIKE ANY(ARRAY[
            '%yönetmelik%','%yönerge%','%mevzuat%','%talimat%',
            '%genelge%','%sözleşme%','%protokol%',
            '%regulation%','%handbook%','%statute%','%bylaw%','%directive%',
            '%usul ve esaslar%','%çalışma usul%','%disiplin%',
            '%etik kurul%','%etik ilke%','%akademik etik%'
        ])
        -- Exclude noise: news pages, course catalog, event pages, staff listings
        AND url NOT LIKE '%/haber/%'
        AND url NOT LIKE '%/haberler%'
        AND url NOT LIKE '%ects.bilgi.edu.tr%'
        AND url NOT LIKE '%/etkinlik%'
        AND url NOT LIKE '%/kadro/%'
        AND url NOT LIKE '%/duyuru/%'
    )
    -- Internship guides (missed by directive-only signal)
    OR url LIKE '%internship-guide%'
    OR url LIKE '%staj-kilavuzu%'
    OR url LIKE '%staj_kilavuzu%'
    -- Scholarship regulations
    OR url LIKE '%bursvedestep%'
    OR url LIKE '%ihtiyac-bu%'
    OR url LIKE '%scholarship-application%'
    OR (title ILIKE '%burs%' AND url LIKE '%/media/%'
        AND url NOT LIKE '%/haber/%')
    -- Credit transfer forms
    OR url LIKE '%kredi-transfer%'
    OR url LIKE '%kredi_transfer%'
    -- Doctoral thesis procedures
    OR url LIKE '%doktora-tez%'
    OR url LIKE '%doktora_tez%'
    OR (title ILIKE '%doktora%tez%' AND url LIKE '%/media/%')
    -- Thesis submission rules (YÖK)
    OR url LIKE '%lisansustu-tez%'
    OR url LIKE '%yuksekogretim%tez%'
    -- Graduation project directives (not just any mezuniyet page)
    OR (url LIKE '%mezuniyet%' AND url LIKE '%yonerge%')
    OR (title ILIKE '%mezuniyet%yönerge%')
    -- Academic calendar (official PDFs only)
    OR (title ILIKE '%akademik takvim%' AND url LIKE '%/media/%')
    OR (title ILIKE '%academic calendar%' AND url LIKE '%/media/%')
)
AND embedding IS NOT NULL
ORDER BY id
""")

# ---------------------------------------------------------------------------
# LLM caller (outlier proxy, titles only — no doc content)
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> Any:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    # find first [ or {
    for start_ch, end_ch in [("[", "]"), ("{", "}")]:
        idx = raw.find(start_ch)
        if idx >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(raw[idx:])
                return obj
            except Exception:
                pass
    return None


def _call_outlier(*, url: str, model: str, system: str,
                  prompt: str, timeout: float) -> tuple[Any, str | None]:
    endpoint = url.rstrip("/") + "/chat/stream"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "systemMessage": system,
    }
    body = json.dumps(payload).encode()
    req = urlrequest.Request(endpoint, data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            raw_stream = r.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return None, f"connection_error: {exc}"

    parts: list[str] = []
    for line in raw_stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if isinstance(ev, dict) and isinstance(ev.get("error"), str) and ev["error"].strip():
            return None, f"stream_error: {ev['error']}"
        msg = ev.get("message", {}) if isinstance(ev, dict) else {}
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            c = str(msg.get("content", ""))
            if c:
                parts.append(c)

    raw = "".join(parts).strip()
    obj = _extract_json(raw)
    if obj is None:
        return None, f"malformed: {raw[:200]}"
    return obj, None

# ---------------------------------------------------------------------------
# Clustering helpers
# ---------------------------------------------------------------------------

def _auto_k(n: int) -> int:
    """~1 cluster per 50 regulation docs, capped 15–35."""
    k = max(15, min(35, round(n / 50)))
    return k


def _tfidf_top_terms(titles: list[str], n: int = 8) -> list[str]:
    if not titles:
        return []
    try:
        vec = TfidfVectorizer(max_features=200, ngram_range=(1, 2),
                               min_df=1, analyzer="word").fit([" ".join(titles)])
        scores = vec.transform(titles).sum(axis=0).A1
        top = sorted(zip(vec.get_feature_names_out(), scores),
                     key=lambda x: -x[1])[:n]
        return [t for t, _ in top]
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Labelling prompt  (titles only — cheap)
# ---------------------------------------------------------------------------

SYSTEM = (
    "You are a university regulation taxonomy expert for a Turkish private university "
    "(Istanbul Bilgi University). Your job is to assign each document cluster to the "
    "correct regulation category. Return only valid JSON."
)

KNOWN_REGULATION_CATEGORIES = [
    "academic_regulations",          # credit system, grading, attendance rules
    "student_handbooks",             # undergraduate / graduate student handbooks
    "double_major_minor_regulations",
    "financial_regulations",         # tuition, scholarships, financial procedures
    "disciplinary_regulations",      # student/staff discipline
    "research_regulations",          # research fund rules, ethics, grant procedures
    "international_program_regulations",  # erasmus, exchange, bilateral agreements
    "personnel_hr_regulations",      # staff hiring, academic titles, HR procedures
    "senate_board_regulations",      # senate, board of trustees, advisory councils
    "quality_assurance_procedures",  # accreditation, internal quality rules
    "disability_accessibility_policy",
    "data_privacy_ethics_policy",
    "admission_regulations",         # entrance exam rules, transfer rules
    "graduate_program_regulations",  # masters, PhD-specific rules
    "vocational_school_regulations", # associate degree program rules
    "scholarship_financial_aid_regulations",  # burs, need-based aid, scholarship directives
    "graduate_thesis_procedures",    # doctoral/master thesis committee, submission, YÖK rules
    "credit_transfer_lateral_entry", # yatay geçiş, credit transfer forms
    "academic_calendar",             # official academic year calendars
]


def _label_prompt(clusters: list[dict]) -> str:
    blocks = []
    for c in clusters:
        titles_str = "\n".join(f"    - {t[:100]}" for t in c["titles"][:40])
        blocks.append(
            f'Cluster {c["id"]} ({c["n"]} docs, top terms: {", ".join(c["terms"])}):\n{titles_str}'
        )
    body = "\n\n".join(blocks)

    known = "\n".join(f"  - {cat}" for cat in KNOWN_REGULATION_CATEGORIES)

    return (
        "Below are document clusters from a university's regulation corpus.\n"
        "Each entry shows cluster ID, doc count, TF-IDF terms, and up to 40 document titles.\n\n"
        f"{body}\n\n"
        "Known regulation categories (use these when they fit):\n"
        f"{known}\n\n"
        "Task: For each cluster assign:\n"
        "  - sub_category: snake_case identifier (use a known category above, or create a new one)\n"
        "  - leaf_label: short human-readable label (3-6 words, Title Case)\n"
        "  - confidence: 0.0–1.0\n\n"
        "Return a JSON array — one object per cluster, in cluster ID order:\n"
        '[{"cluster_id": 0, "sub_category": "academic_regulations", '
        '"leaf_label": "Undergraduate Academic Regulations", "confidence": 0.95}, ...]'
    )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Step 12: targeted regulation clustering")
    p.add_argument("--tree-json",    type=Path, default=DEFAULT_TREE_JSON)
    p.add_argument("--output-dir",   type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--outlier-url",  type=str, default="http://127.0.0.1:8080")
    p.add_argument("--outlier-model",type=str, default="claude-opus-4-6")
    p.add_argument("--llm-timeout",  type=float, default=120.0)
    p.add_argument("--k",            type=int, default=0,
                   help="Override number of clusters (0 = auto)")
    args = p.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Extract regulation docs
    # ------------------------------------------------------------------
    print("[12] extracting regulation-signal docs from DB...")
    db = SessionLocal()
    try:
        rows = list(db.execute(REGULATION_SQL).all())
    finally:
        db.close()

    print(f"[12] found {len(rows)} docs with regulation signals")
    if len(rows) < 10:
        print("[12] too few docs — check DB connection or widen signals")
        return 1

    # Build arrays
    kb_ids   = [r[0] for r in rows]
    titles   = [r[1] for r in rows]
    urls     = [r[2] for r in rows]
    # embeddings stored as pgvector — comes back as list or str
    raw_embs = [r[3] for r in rows]

    embs_list: list[list[float]] = []
    for e in raw_embs:
        if isinstance(e, str):
            # pgvector string format: "[0.1,0.2,...]"
            embs_list.append(json.loads(e))
        else:
            embs_list.append(list(e))

    X = np.array(embs_list, dtype=np.float32)
    # L2 normalize for cosine similarity
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = X / norms
    print(f"[12] embedding matrix: {X.shape}")

    # ------------------------------------------------------------------
    # 2. Cluster
    # ------------------------------------------------------------------
    k = args.k if args.k > 0 else _auto_k(len(rows))
    print(f"[12] clustering into k={k} clusters...")
    km = MiniBatchKMeans(n_clusters=k, random_state=42, batch_size=1024,
                         n_init=5, max_iter=300)
    labels = km.fit_predict(X)
    print(f"[12] clustering done — {k} clusters")

    # Group by cluster
    cluster_data: dict[int, dict] = {}
    for idx, cid in enumerate(labels):
        cid = int(cid)
        if cid not in cluster_data:
            cluster_data[cid] = {"ids": [], "titles": [], "urls": []}
        cluster_data[cid]["ids"].append(kb_ids[idx])
        cluster_data[cid]["titles"].append(titles[idx])
        cluster_data[cid]["urls"].append(urls[idx])

    # Sort clusters by size desc, assign sequential IDs
    sorted_clusters = sorted(cluster_data.items(), key=lambda x: -len(x[1]["ids"]))
    cluster_infos = []
    for seq_id, (orig_cid, data) in enumerate(sorted_clusters):
        terms = _tfidf_top_terms(data["titles"])
        cluster_infos.append({
            "id": seq_id,
            "orig_cid": orig_cid,
            "n": len(data["ids"]),
            "titles": data["titles"],
            "urls": data["urls"],
            "doc_ids": data["ids"],
            "terms": terms,
        })

    print(f"[12] cluster sizes: min={min(c['n'] for c in cluster_infos)} "
          f"max={max(c['n'] for c in cluster_infos)} "
          f"avg={sum(c['n'] for c in cluster_infos)/len(cluster_infos):.0f}")

    # ------------------------------------------------------------------
    # 3. LLM label — titles only, all clusters in one call
    # ------------------------------------------------------------------
    print(f"[12] calling LLM to label {len(cluster_infos)} clusters (titles only)...")
    prompt = _label_prompt(cluster_infos)
    print(f"[12] prompt size: {len(prompt)} chars / ~{len(prompt)//4} tokens")

    result, err = _call_outlier(
        url=args.outlier_url, model=args.outlier_model,
        system=SYSTEM, prompt=prompt, timeout=args.llm_timeout,
    )

    if err or result is None:
        print(f"[12] LLM error: {err}")
        return 1

    labels_list: list[dict] = result if isinstance(result, list) else []
    print(f"[12] LLM returned {len(labels_list)} labels")

    # Map cluster seq_id → label
    label_map: dict[int, dict] = {int(l["cluster_id"]): l for l in labels_list}

    # ------------------------------------------------------------------
    # 4. Build regulation subtree
    # ------------------------------------------------------------------
    reg_sub: dict[str, Any] = {}  # sub_category → {leaves}

    for c in cluster_infos:
        lbl = label_map.get(c["id"], {})
        sub_cat = str(lbl.get("sub_category", f"regulation_group_{c['id']}")).strip()
        leaf_label = str(lbl.get("leaf_label", f"Regulation Group {c['id']}")).strip()
        conf = float(lbl.get("confidence", 0.5))

        if sub_cat not in reg_sub:
            reg_sub[sub_cat] = {"doc_count": 0, "leaves": {}}

        # Sample URLs (up to 5)
        sample_urls = list({u.split("/")[-2] if "/" in u else u
                            for u in c["urls"] if u})[:5]

        reg_sub[sub_cat]["leaves"][leaf_label] = {
            "doc_count": c["n"],
            "doc_ids": c["doc_ids"],
            "sample_urls": c["urls"][:5],
            "group_ids": [c["orig_cid"]],
            "sources": "regulation_targeted",
            "quality_score": conf,
            "representative_titles": c["titles"][:5],
        }
        reg_sub[sub_cat]["doc_count"] += c["n"]

    total_reg_docs = sum(v["doc_count"] for v in reg_sub.values())
    print(f"[12] regulation subtree: {len(reg_sub)} sub_categories, "
          f"{sum(len(v['leaves']) for v in reg_sub.values())} leaves, "
          f"{total_reg_docs} docs total")

    # ------------------------------------------------------------------
    # 5. Merge into existing tree
    # ------------------------------------------------------------------
    print(f"[12] loading existing tree from {args.tree_json} ...")
    tree_src = json.loads(args.tree_json.read_text(encoding="utf-8"))
    tree = tree_src.get("tree", tree_src)

    # Replace regulations top-node
    tree["regulations"] = {
        "doc_count": total_reg_docs,
        "sub_levels": reg_sub,
    }

    # ------------------------------------------------------------------
    # 6. Write outputs
    # ------------------------------------------------------------------
    out_tree = {"tree": tree, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": "12_cluster_regulations merged into 05_refactor_tree"}

    tree_path = args.output_dir / "tree_with_regulations.json"
    tree_path.write_text(json.dumps(out_tree, ensure_ascii=False, indent=2), encoding="utf-8")

    # Quick markdown summary
    lines = ["# Regulation Subtree", "",
             f"- docs extracted: {len(rows)}",
             f"- clusters: {k}",
             f"- sub_categories: {len(reg_sub)}",
             f"- leaves: {sum(len(v['leaves']) for v in reg_sub.values())}",
             ""]
    for sub, sv in sorted(reg_sub.items()):
        lines.append(f"## {sub} ({sv['doc_count']} docs)")
        for leaf, lv in sorted(sv["leaves"].items()):
            lines.append(f"  - {leaf}: {lv['doc_count']} docs  (conf={lv['quality_score']:.2f})")
        lines.append("")

    md_path = args.output_dir / "regulation_tree.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[12] tree    → {tree_path}")
    print(f"[12] summary → {md_path}")
    print("[12] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
