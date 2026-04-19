#!/usr/bin/env python3
"""Step 15: Stratified RAPTOR — tier-aware clustering with parent-context summarization.

Core insight:
  Cluster within tiers (regulations, news, academic, people, quality) so same-topic
  docs from different tiers never compete in the same cluster.
  LLM writes summaries that capture WHERE in the university hierarchy a chunk lives —
  not just what it's about, but who owns it, who reads it, what its role is.
  Those summaries are re-embedded with Jina v3 (task=separation) and re-clustered.

Tiers (URL/title signals, no LLM):
  T1 regulations   — official PDFs, directives, handbooks, yönetmelik
  T2 quality       — evaluation reports, accreditation, self-study
  T3 academic      — courses, programs, faculty, ECTS catalog
  T4 people        — staff profiles, academic CV pages
  T5 international — erasmus, exchange, mobility
  T6 news_events   — /haber/, /etkinlik/, announcements
  T7 other         — everything else
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
DEFAULT_OUTPUT_DIR = FLOW / "15_stratified_raptor"

JINA_MODEL_ID = 6

# ---------------------------------------------------------------------------
# Tier definitions — ordered, first match wins
# ---------------------------------------------------------------------------

TIERS: list[tuple[str, str, str, int]] = [
    # (name, description, url_regex_hint, target_k_per_500_docs)
    # k_per_500: how many clusters per 500 docs (higher = finer granularity)
    ("regulations",  "Official regulations, directives, handbooks, yönetmelik, policy PDFs",   "regulations",  8),
    ("quality",      "Quality assurance reports, accreditation, self-evaluation, WSCUC",        "quality",      5),
    ("international","Erasmus, exchange, mobility, international student programs",             "international",5),
    ("academic",     "Courses, programs, departments, faculty pages, ECTS catalog, curriculum", "academic",     4),
    ("people",       "Academic staff profiles, CV pages, personal pages",                       "people",       4),
    ("news_events",  "News articles, announcements, events, haber, etkinlik",                   "news_events",  2),
    ("other",        "Everything else that doesn't fit a specific tier",                        "other",        2),
]

TIER_URL_PATTERNS: dict[str, list[str]] = {
    "regulations": [
        "/mevzuat/", "/yonetmelik/", "/yonerge/", "/statute/", "/bylaw/", "/regulation/",
        "/handbook/", "internship_directive", "internship-guide", "staj-kilavuzu",
        "bursvedestep", "scholarship-application",
    ],
    "quality": [
        "/kalite/", "/quality/", "/akreditasyon/", "/accreditation/",
        "/ozerlendirme/", "/idr/", "/wscuc",
    ],
    "international": [
        "/erasmus/", "/exchange/", "/international/", "/mobility/",
        "/hareketlilik/", "/uluslararasi/",
    ],
    "academic": [
        "ects.bilgi.edu.tr", "/akademik/", "/academic/", "/faculty-of-", "/fakulte/",
        "/program/", "/ders/", "/course/", "/bolum/", "/department/",
    ],
    "people": [
        "/kadro/", "/staff/", "/akademik-kadro/", "/academic-staff/", "/ogretim-uyesi/",
    ],
    "news_events": [
        "/haber/", "/news/", "/etkinlik/", "/event/", "/duyuru/", "/announcement/",
        "/medya/", "/basin/",
    ],
}

TIER_TITLE_PATTERNS: dict[str, list[str]] = {
    "regulations": [
        "yönetmelik", "yönerge", "esaslar", "talimat", "genelge", "mevzuat",
        "regulation", "directive", "handbook", "statute", "bylaw", "policy",
        "usul ve", "çalışma ilke", "disiplin", "etik kurul", "sözleşme",
    ],
    "quality": [
        "değerlendirme raporu", "iç değerlendirme", "evaluation report",
        "self-study", "accreditation", "wscuc", "müfredat", "program çıktı",
    ],
    "people": [
        "cv", "özgeçmiş", "academic profile", "profil",
    ],
}


def _assign_tier(url: str, title: str) -> str:
    url_l   = url.lower()
    title_l = title.lower()

    for tier, patterns in TIER_URL_PATTERNS.items():
        if any(p in url_l for p in patterns):
            return tier

    for tier, patterns in TIER_TITLE_PATTERNS.items():
        if any(p in title_l for p in patterns):
            return tier

    return "other"


# ---------------------------------------------------------------------------
# Jina v3 embedding (local SentenceTransformer)
# ---------------------------------------------------------------------------

_embedder_cache: dict = {}


def _load_jina(model_name: str = "jinaai/jina-embeddings-v3") -> Any:
    if model_name in _embedder_cache:
        return _embedder_cache[model_name]
    from sentence_transformers import SentenceTransformer
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=model_name)
        dep = Path(snapshot_download(repo_id="jinaai/xlm-roberta-flash-implementation"))
        mod_root = (Path.home() / ".cache/huggingface/modules/transformers_modules"
                    / "jinaai/xlm-roberta-flash-implementation")
        mod_root.mkdir(parents=True, exist_ok=True)
        commit_dirs = [p for p in mod_root.iterdir() if p.is_dir() and p.name != "__pycache__"]
        if not commit_dirs:
            cd = mod_root / dep.name; cd.mkdir(parents=True, exist_ok=True); commit_dirs = [cd]
        for src in dep.glob("*.py"):
            for cd in commit_dirs:
                dst = cd / src.name
                if not dst.exists(): shutil.copy2(src, dst)
            for cd in commit_dirs:
                init = cd / "__init__.py"
                if not init.exists(): init.write_text("")
    except Exception as e:
        print(f"[jina] prewarm: {e}")
    model = SentenceTransformer(model_name, trust_remote_code=True)
    _embedder_cache[model_name] = model
    return model


def _embed(texts: list[str], task: str = "separation",
           dim: int = 512, batch: int = 32) -> np.ndarray:
    model = _load_jina()
    vecs = []
    for i in range(0, len(texts), batch):
        v = model.encode(texts[i:i+batch], task=task, truncate_dim=dim,
                         normalize_embeddings=True, show_progress_bar=False)
        vecs.append(v)
    return np.vstack(vecs).astype(np.float32)


# ---------------------------------------------------------------------------
# LLM (outlier proxy)
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> Any:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    for open_ch in ["[", "{"]:
        idx = raw.find(open_ch)
        if idx >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(raw[idx:])
                return obj
            except Exception:
                pass
    return None


def _llm(*, url: str, model: str, system: str, prompt: str, timeout: float) -> tuple[Any, str | None]:
    from urllib import request as req
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "systemMessage": system}).encode()
    r = req.Request(url.rstrip("/") + "/chat/stream", data=body,
                    headers={"Content-Type": "application/json"}, method="POST")
    try:
        with req.urlopen(r, timeout=timeout) as resp:
            raw_stream = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return None, str(exc)
    parts = []
    for line in raw_stream.splitlines():
        line = line.strip()
        if not line: continue
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
    return (obj, None) if obj is not None else (None, f"malformed:{raw[:200]}")


# ---------------------------------------------------------------------------
# The prompt that makes LLM feel the parent relationship
# ---------------------------------------------------------------------------

SYSTEM = (
    "You are the chief librarian and information architect for Istanbul Bilgi University. "
    "You deeply understand how a modern university organizes its knowledge: "
    "official regulations, course catalogs, faculty research, student services, "
    "quality reports, news, events, and more. "
    "Your job is to place each document cluster precisely in the institutional hierarchy. "
    "Return only valid JSON."
)

UNIVERSITY_STRUCTURE = """
Istanbul Bilgi University information hierarchy:
  regulations/        → official rules binding on students or staff (yönetmelik, yönerge, handbook, directive, esaslar)
  academics/          → courses, programs, departments, curriculum, faculty research
  admissions/         → entrance exams, application procedures, YKS, transfer
  administration/     → institutional governance, policies, HR, campus operations
  international/      → Erasmus, exchange programs, international students
  quality/            → accreditation reports, self-evaluation, WSCUC, program assessment
  research/           → funded projects, publications, research centers
  student_life/       → counseling, clubs, health, sports, career services
  people/             → academic staff profiles, bios, CVs
  events/             → conferences, exhibitions, film festivals, seminars
  news/               → announcements, press releases, institutional news
  library/            → library resources, databases, borrowing rules
"""


def _label_prompt(clusters: list[dict], tier_name: str, tier_desc: str) -> str:
    blocks = []
    for c in clusters:
        titles = "\n".join(f"    • {t[:100]}" for t in c["titles"][:30])
        blocks.append(
            f"Cluster {c['id']} | tier={tier_name} | {c['n']} docs | "
            f"top terms: {', '.join(c['terms'])}\n{titles}"
        )

    return f"""You are classifying document clusters from {tier_name.upper()} tier of the university.
Tier context: {tier_desc}

{UNIVERSITY_STRUCTURE}

For each cluster below, determine exactly where it belongs in the institutional hierarchy.
Think: What TYPE of document is this? Who OWNS it (which office/department)? Who READS it (students/staff/faculty/public)? What is its PARENT node in the university tree?

Then write a summary sentence in this format:
"These are [document type] from [owning office/department] about [specific topic], intended for [audience]."

This summary will be machine-embedded — make it semantically precise and specific.
BAD: "University documents about internships."
GOOD: "These are official PDF regulation directives from the Student Affairs Office about internship application procedures and workplace requirements, intended for undergraduate students seeking internship approval."

--- CLUSTERS ---

{'='*60 + chr(10) + (chr(10)*2).join(blocks)}

Return a JSON array, one object per cluster in order:
[{{
  "cluster_id": 0,
  "top_category": "regulations",
  "sub_category": "internship_student_work_regulations",
  "leaf_label": "Internship Directive and Procedures",
  "summary": "These are official regulation PDFs from Student Affairs about internship application and workplace requirements for undergraduate students.",
  "confidence": 0.95
}}, ...]"""


# ---------------------------------------------------------------------------
# Clustering helpers
# ---------------------------------------------------------------------------

def _kmeans(X: np.ndarray, k: int) -> np.ndarray:
    k = max(1, min(k, len(X)))
    return MiniBatchKMeans(n_clusters=k, random_state=42, batch_size=1024,
                           n_init=5, max_iter=300).fit_predict(X)


def _tfidf(titles: list[str], n: int = 6) -> list[str]:
    if not titles: return []
    try:
        vec = TfidfVectorizer(max_features=200, ngram_range=(1, 2), min_df=1).fit(titles)
        scores = vec.transform(titles).sum(axis=0).A1
        return [t for t, _ in sorted(zip(vec.get_feature_names_out(), scores),
                                      key=lambda x: -x[1])[:n]]
    except Exception:
        return []


def _tier_k(n: int, k_per_500: int) -> int:
    return max(2, min(80, round(n / 500 * k_per_500 * 10)))


# ---------------------------------------------------------------------------
# DB fetch
# ---------------------------------------------------------------------------

def _fetch_docs() -> tuple[list[str], list[str], list[str], np.ndarray]:
    db = SessionLocal()
    try:
        count = db.execute(text(
            "SELECT COUNT(*) FROM knowledge_base_embeddings WHERE model_id=:m"
        ), {"m": JINA_MODEL_ID}).scalar()
        print(f"[15] total Jina v3 docs: {count:,}")
        ids, titles, urls, embs = [], [], [], []
        offset = 0
        while offset < count:
            rows = db.execute(text("""
                SELECT kbe.kb_id::text, COALESCE(kb.title,''), COALESCE(kb.url,''), kbe.embedding
                FROM knowledge_base_embeddings kbe
                JOIN knowledge_base kb ON kb.id = kbe.kb_id
                WHERE kbe.model_id = :m
                ORDER BY kbe.kb_id LIMIT :lim OFFSET :off
            """), {"m": JINA_MODEL_ID, "lim": 5000, "off": offset}).all()
            if not rows: break
            for r in rows:
                ids.append(r[0]); titles.append(r[1]); urls.append(r[2])
                e = r[3]
                embs.append(json.loads(e) if isinstance(e, str) else list(e))
            offset += len(rows)
            print(f"  {offset:,}/{count:,}...", end="\r")
        print()
        X = np.array(embs, dtype=np.float32)
        n = np.linalg.norm(X, axis=1, keepdims=True); n[n == 0] = 1
        return ids, titles, urls, X / n
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir",    type=Path,  default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--outlier-url",   type=str,   default="http://127.0.0.1:8080")
    p.add_argument("--outlier-model", type=str,   default="claude-opus-4-6")
    p.add_argument("--llm-timeout",   type=float, default=120.0)
    p.add_argument("--llm-batch",     type=int,   default=8)
    p.add_argument("--mid-k",         type=int,   default=20)
    args = p.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Fetch all docs
    # ------------------------------------------------------------------
    ids, titles, urls, X = _fetch_docs()
    n_total = len(ids)

    # ------------------------------------------------------------------
    # 2. Assign tiers
    # ------------------------------------------------------------------
    print("[15] assigning tiers...")
    tier_indices: dict[str, list[int]] = defaultdict(list)
    for idx in range(n_total):
        tier = _assign_tier(urls[idx], titles[idx])
        tier_indices[tier].append(idx)

    for tier_name, _, _, _ in TIERS:
        cnt = len(tier_indices.get(tier_name, []))
        print(f"  {tier_name:20s}: {cnt:,} docs")

    # ------------------------------------------------------------------
    # 3. Cluster each tier separately
    # ------------------------------------------------------------------
    print("\n[15] clustering each tier...")
    all_clusters: list[dict] = []
    global_seq = 0

    for tier_name, tier_desc, _, k_per_500 in TIERS:
        idxs = tier_indices.get(tier_name, [])
        if not idxs:
            continue
        Xt = X[idxs]
        k  = _tier_k(len(idxs), k_per_500)
        print(f"  {tier_name}: {len(idxs):,} docs → k={k}")
        labels = _kmeans(Xt, k)

        # group by cluster
        cl: dict[int, dict] = {}
        for seq_in_tier, orig_idx in enumerate(idxs):
            cid = int(labels[seq_in_tier])
            if cid not in cl:
                cl[cid] = {"ids": [], "titles": [], "urls": []}
            cl[cid]["ids"].append(ids[orig_idx])
            cl[cid]["titles"].append(titles[orig_idx])
            cl[cid]["urls"].append(urls[orig_idx])

        for cid, data in sorted(cl.items(), key=lambda x: -len(x[1]["ids"])):
            all_clusters.append({
                "id":       global_seq,
                "tier":     tier_name,
                "tier_desc": tier_desc,
                "n":        len(data["ids"]),
                "doc_ids":  data["ids"],
                "titles":   data["titles"],
                "urls":     data["urls"],
                "terms":    _tfidf(data["titles"]),
            })
            global_seq += 1

    print(f"\n[15] total leaf clusters: {len(all_clusters)}")

    # ------------------------------------------------------------------
    # 4. LLM label all clusters — tier-grouped batches
    # ------------------------------------------------------------------
    print(f"\n[15] LLM labeling with parent-context prompt...")
    label_map: dict[int, dict] = {}

    # batch by tier so prompt context is homogeneous
    tier_batches: dict[str, list[list[dict]]] = defaultdict(list)
    for tier_name, _, _, _ in TIERS:
        tier_cl = [c for c in all_clusters if c["tier"] == tier_name]
        for i in range(0, len(tier_cl), args.llm_batch):
            tier_batches[tier_name].append(tier_cl[i: i + args.llm_batch])

    total_batches = sum(len(v) for v in tier_batches.values())
    done = 0

    for tier_name, tier_desc, _, _ in TIERS:
        for batch in tier_batches.get(tier_name, []):
            prompt  = _label_prompt(batch, tier_name, tier_desc)
            result, err = _llm(url=args.outlier_url, model=args.outlier_model,
                               system=SYSTEM, prompt=prompt, timeout=args.llm_timeout)
            done += 1
            if err or not isinstance(result, list):
                print(f"  [{done}/{total_batches}] {tier_name} ERROR: {err}")
                for c in batch:
                    label_map[c["id"]] = {
                        "top_category": tier_name, "sub_category": f"tier_{tier_name}_{c['id']}",
                        "leaf_label": f"{tier_name.title()} Group {c['id']}",
                        "summary": " ".join(c["terms"][:5]), "confidence": 0.0,
                    }
                continue
            for item in result:
                cid = int(item.get("cluster_id", -1))
                label_map[cid] = item
            print(f"  [{done}/{total_batches}] {tier_name} ✓ ({len(result)} labels)")
            time.sleep(0.3)

    # attach labels
    leaf_summaries: list[str] = []
    for c in all_clusters:
        lbl = label_map.get(c["id"], {})
        c["top_category"] = lbl.get("top_category", c["tier"])
        c["sub_category"] = lbl.get("sub_category",  f"cluster_{c['id']}")
        c["leaf_label"]   = lbl.get("leaf_label",    f"Cluster {c['id']}")
        c["summary"]      = lbl.get("summary",       " ".join(c["terms"][:5]))
        c["confidence"]   = float(lbl.get("confidence", 0.0))
        # Dense summary for re-embedding — type + owner + topic + audience
        leaf_summaries.append(
            f"{c['top_category']} {c['sub_category']}: {c['summary']}"
        )

    # ------------------------------------------------------------------
    # 5. Re-embed summaries → mid-level clustering (RAPTOR level 1)
    # ------------------------------------------------------------------
    print(f"\n[15] re-embedding {len(all_clusters)} summaries with Jina v3 task=separation...")
    X_sum = _embed(leaf_summaries, task="separation", dim=512)
    print(f"[15] summary embeddings: {X_sum.shape}")

    mid_k = args.mid_k
    print(f"[15] mid-level clustering k={mid_k}...")
    mid_labels = _kmeans(X_sum, mid_k)

    mid_groups: dict[int, list[dict]] = defaultdict(list)
    for seq, cid in enumerate(mid_labels):
        mid_groups[int(cid)].append(all_clusters[seq])

    # ------------------------------------------------------------------
    # 6. Build tree bottom-up
    # ------------------------------------------------------------------
    print("[15] building tree...")
    tree: dict[str, Any] = {}

    for mg_leaves in mid_groups.values():
        for leaf in mg_leaves:
            top = leaf["top_category"]
            sub = leaf["sub_category"]
            if top not in tree:
                tree[top] = {"doc_count": 0, "sub_levels": {}}
            if sub not in tree[top]["sub_levels"]:
                tree[top]["sub_levels"][sub] = {"doc_count": 0, "leaves": {}}

            tree[top]["sub_levels"][sub]["leaves"][leaf["leaf_label"]] = {
                "doc_count":             leaf["n"],
                "doc_ids":               leaf["doc_ids"],
                "sample_urls":           leaf["urls"][:5],
                "tier":                  leaf["tier"],
                "sources":               f"stratified_{leaf['tier']}",
                "quality_score":         leaf["confidence"],
                "representative_titles": leaf["titles"][:5],
                "summary":               leaf["summary"],
            }
            tree[top]["sub_levels"][sub]["doc_count"] += leaf["n"]
            tree[top]["doc_count"] += leaf["n"]

    # stats
    n_top  = len(tree)
    n_sub  = sum(len(tn["sub_levels"]) for tn in tree.values())
    n_leaf = sum(len(sn["leaves"]) for tn in tree.values()
                 for sn in tn["sub_levels"].values())
    classified = sum(tn["doc_count"] for tn in tree.values())
    avg_conf = float(np.mean([
        lv["quality_score"]
        for tn in tree.values()
        for sn in tn["sub_levels"].values()
        for lv in sn["leaves"].values()
    ]))

    print(f"\n[15] tree: {n_top} top / {n_sub} sub / {n_leaf} leaves")
    print(f"[15] docs: {classified:,}/{n_total:,}  avg_conf={avg_conf:.3f}")

    # ------------------------------------------------------------------
    # 7. Write outputs
    # ------------------------------------------------------------------
    out = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "stratified_raptor_v1",
        "summary": {"top": n_top, "sub": n_sub, "leaves": n_leaf,
                    "avg_confidence": round(avg_conf, 4), "total_docs": classified},
        "tree": tree,
    }
    (args.output_dir / "stratified_tree.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2))

    lines = ["# Stratified RAPTOR Tree", "",
             f"- {n_top} top / {n_sub} sub / {n_leaf} leaves",
             f"- {classified:,} docs  avg_conf={avg_conf:.3f}", ""]
    for top, tn in sorted(tree.items()):
        lines.append(f"## {top} ({tn['doc_count']:,} docs)")
        for sub, sn in sorted(tn["sub_levels"].items()):
            lines.append(f"  ### {sub} ({sn['doc_count']:,})")
            for lbl, lv in sorted(sn["leaves"].items()):
                lines.append(f"    - {lbl}: {lv['doc_count']} docs  conf={lv['quality_score']:.2f}  [{lv['tier']}]")
        lines.append("")
    (args.output_dir / "stratified_tree.md").write_text("\n".join(lines))

    print(f"[15] → {args.output_dir}/stratified_tree.json")
    print("[15] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
