#!/usr/bin/env python3
"""Step 13: RAPTOR-Lite Taxonomy — recursive clustering with LLM-summary re-embedding.

RAPTOR forces semantic coherence at every node:
  Level 0 (leaves): cluster all docs by raw embedding → LLM names each cluster from titles
  Level 1 (mid):    embed LLM names → re-cluster → LLM names each group
  Level 2 (top):    embed mid names → re-cluster → top-level categories

No doc content sent to LLM — only titles (cheap).
The summaries are re-embedded so higher-level clusters group by actual semantic meaning,
not noisy raw embedding proximity.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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
DEFAULT_OUTPUT_DIR = FLOW / "13_raptor_taxonomy"

# ---------------------------------------------------------------------------
# Embedding helper — local Jina v3 via SentenceTransformer
# ---------------------------------------------------------------------------

_embedder_cache: dict = {}

def _load_jina_embedder(model_name: str = "jinaai/jina-embeddings-v3") -> Any:
    if model_name in _embedder_cache:
        return _embedder_cache[model_name]
    import shutil
    from sentence_transformers import SentenceTransformer
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=model_name)
        dep_snapshot = Path(snapshot_download(repo_id="jinaai/xlm-roberta-flash-implementation"))
        module_root = (Path.home() / ".cache" / "huggingface" / "modules"
                       / "transformers_modules" / "jinaai" / "xlm-roberta-flash-implementation")
        module_root.mkdir(parents=True, exist_ok=True)
        commit_dirs = [p for p in module_root.iterdir()
                       if p.is_dir() and p.name != "__pycache__"]
        if not commit_dirs:
            commit_dir = module_root / dep_snapshot.name
            commit_dir.mkdir(parents=True, exist_ok=True)
            commit_dirs = [commit_dir]
        for src in dep_snapshot.glob("*.py"):
            for cd in commit_dirs:
                dst = cd / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
            for cd in commit_dirs:
                init = cd / "__init__.py"
                if not init.exists():
                    init.write_text("", encoding="utf-8")
    except Exception as exc:
        print(f"[jina] prewarm warning: {exc}")
    model = SentenceTransformer(model_name, trust_remote_code=True)
    _embedder_cache[model_name] = model
    return model


def _embed_texts(texts: list[str], model_name: str = "jinaai/jina-embeddings-v3",
                 task: str = "clustering", truncate_dim: int = 512,
                 batch_size: int = 32) -> np.ndarray:
    """Embed texts with Jina v3 using the specified task. Returns L2-normalized float32."""
    model = _load_jina_embedder(model_name)
    all_vecs: list[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        vecs = model.encode(
            batch,
            task=task,
            truncate_dim=truncate_dim,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        all_vecs.append(vecs)
    return np.vstack(all_vecs).astype(np.float32)


# ---------------------------------------------------------------------------
# LLM helper (outlier proxy)
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> Any:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    for ch_open, ch_close in [("[", "]"), ("{", "}")]:
        idx = raw.find(ch_open)
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
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "systemMessage": system,
    }).encode()
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
    return (obj, None) if obj is not None else (None, f"malformed: {raw[:300]}")


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def _kmeans(X: np.ndarray, k: int) -> np.ndarray:
    km = MiniBatchKMeans(n_clusters=k, random_state=42, batch_size=1024,
                         n_init=5, max_iter=300)
    return km.fit_predict(X)


def _tfidf_terms(titles: list[str], n: int = 6) -> list[str]:
    if not titles:
        return []
    try:
        vec = TfidfVectorizer(max_features=200, ngram_range=(1, 2), min_df=1).fit(titles)
        scores = vec.transform(titles).sum(axis=0).A1
        top = sorted(zip(vec.get_feature_names_out(), scores), key=lambda x: -x[1])[:n]
        return [t for t, _ in top]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

SYSTEM_LABEL = (
    "You are a university knowledge taxonomy expert. "
    "Label document clusters concisely. Return only valid JSON."
)

TOP_CATEGORIES = [
    "academics", "admissions", "administration", "events",
    "international", "library", "news", "people",
    "quality", "regulations", "research", "student_life",
]


def _leaf_label_prompt(clusters: list[dict]) -> str:
    """Ask LLM to label leaf clusters. Input: titles only."""
    blocks = []
    for c in clusters:
        titles_str = "\n".join(f"    - {t[:90]}" for t in c["titles"][:35])
        blocks.append(
            f'Cluster {c["id"]} ({c["n"]} docs, terms: {", ".join(c["terms"])}):\n{titles_str}'
        )
    return (
        "Label each document cluster for a Turkish university RAG system.\n\n"
        + "\n\n".join(blocks)
        + f'\n\nTop-level categories: {", ".join(TOP_CATEGORIES)}\n\n'
        "For each cluster provide:\n"
        "  - top_category: one of the top-level categories above\n"
        "  - sub_category: snake_case 2-4 word descriptor\n"
        "  - leaf_label: human-readable 3-6 word label (Title Case)\n"
        "  - summary: one sentence describing what these documents are about\n"
        "  - confidence: 0.0-1.0\n\n"
        "Return JSON array: "
        '[{"cluster_id":0,"top_category":"regulations","sub_category":"academic_regulations",'
        '"leaf_label":"Undergraduate Academic Regulations","summary":"...","confidence":0.95},...]'
    )


def _mid_label_prompt(groups: list[dict]) -> str:
    """Label mid-level groups from leaf summaries."""
    blocks = []
    for g in groups:
        summaries_str = "\n".join(
            f"    - [{leaf['top_category']}/{leaf['sub_category']}] {leaf['summary']}"
            for leaf in g["leaves"]
        )
        blocks.append(f'Group {g["id"]} ({g["n_leaves"]} leaves, {g["n_docs"]} docs):\n{summaries_str}')
    return (
        "Group these leaf-level taxonomy clusters into broader mid-level categories.\n\n"
        + "\n\n".join(blocks)
        + f'\n\nTop-level categories: {", ".join(TOP_CATEGORIES)}\n\n'
        "For each group provide:\n"
        "  - group_id, top_category, sub_category (snake_case), label (Title Case), summary (1 sentence)\n\n"
        "Return JSON array."
    )


# ---------------------------------------------------------------------------
# DB fetch
# ---------------------------------------------------------------------------

JINA_MODEL_ID = 6  # id=6 is active jinaai/jina-embeddings-v3 in embedding_models table


def _fetch_all_docs(chunk_size: int = 5000) -> tuple[list[str], list[str], list[str], np.ndarray]:
    """Fetch all KB docs with Jina v3 embeddings (knowledge_base_embeddings, model_id=6)."""
    db = SessionLocal()
    try:
        count = db.execute(text(
            "SELECT COUNT(*) FROM knowledge_base_embeddings WHERE model_id = :mid"
        ), {"mid": JINA_MODEL_ID}).scalar()
        print(f"[13] total docs with Jina v3 embeddings: {count:,}")

        ids, titles, urls, embs = [], [], [], []
        offset = 0
        while offset < count:
            rows = db.execute(text("""
                SELECT kbe.kb_id::text,
                       COALESCE(kb.title,'') AS title,
                       COALESCE(kb.url,'')   AS url,
                       kbe.embedding
                FROM knowledge_base_embeddings kbe
                JOIN knowledge_base kb ON kb.id = kbe.kb_id
                WHERE kbe.model_id = :mid
                ORDER BY kbe.kb_id
                LIMIT :lim OFFSET :off
            """), {"mid": JINA_MODEL_ID, "lim": chunk_size, "off": offset}).all()
            if not rows:
                break
            for r in rows:
                ids.append(r[0])
                titles.append(r[1])
                urls.append(r[2])
                e = r[3]
                embs.append(json.loads(e) if isinstance(e, str) else list(e))
            offset += len(rows)
            print(f"  fetched {offset:,}/{count:,}...", end="\r")

        print()
        X = np.array(embs, dtype=np.float32)
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return ids, titles, urls, X / norms
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main RAPTOR pipeline
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir",    type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--outlier-url",   type=str, default="http://127.0.0.1:8080")
    p.add_argument("--outlier-model", type=str, default="claude-opus-4-6")
    p.add_argument("--llm-timeout",   type=float, default=120.0)
    p.add_argument("--leaf-k",        type=int, default=0,
                   help="Leaf cluster count (0=auto: n/400)")
    p.add_argument("--mid-k",         type=int, default=0,
                   help="Mid cluster count (0=auto: leaf_k/5)")
    p.add_argument("--llm-batch",     type=int, default=12,
                   help="Clusters per LLM call at leaf level")
    args = p.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------
    # LEVEL 0: Fetch all docs and cluster raw embeddings
    # ---------------------------------------------------------------
    print("\n[13] === LEVEL 0: raw embedding clustering ===")
    ids, titles, urls, X = _fetch_all_docs()
    n = len(ids)

    leaf_k = args.leaf_k or max(30, min(200, round(n / 400)))
    print(f"[13] leaf clusters k={leaf_k} for {n:,} docs")

    leaf_labels = _kmeans(X, leaf_k)
    print(f"[13] clustering done")

    # Group docs by cluster
    leaf_clusters: dict[int, dict] = {}
    for idx, cid in enumerate(leaf_labels):
        cid = int(cid)
        lc = leaf_clusters.setdefault(cid, {"ids": [], "titles": [], "urls": []})
        lc["ids"].append(ids[idx])
        lc["titles"].append(titles[idx])
        lc["urls"].append(urls[idx])

    sorted_leaves = sorted(leaf_clusters.items(), key=lambda x: -len(x[1]["ids"]))
    leaf_infos = [
        {
            "id": seq,
            "orig_cid": orig,
            "n": len(d["ids"]),
            "titles": d["titles"],
            "urls": d["urls"],
            "doc_ids": d["ids"],
            "terms": _tfidf_terms(d["titles"]),
        }
        for seq, (orig, d) in enumerate(sorted_leaves)
    ]
    print(f"[13] leaf cluster sizes: min={min(c['n'] for c in leaf_infos)} "
          f"max={max(c['n'] for c in leaf_infos)} avg={n // leaf_k}")

    # ---------------------------------------------------------------
    # LEVEL 0 → LLM label leaves (titles only, batched)
    # ---------------------------------------------------------------
    print(f"\n[13] === LLM labeling {leaf_k} leaf clusters (titles only) ===")
    batches = [leaf_infos[i: i + args.llm_batch]
               for i in range(0, len(leaf_infos), args.llm_batch)]
    print(f"[13] {len(batches)} LLM batches of ~{args.llm_batch} clusters each")

    leaf_label_map: dict[int, dict] = {}
    for b_idx, batch in enumerate(batches):
        prompt = _leaf_label_prompt(batch)
        result, err = _call_outlier(
            url=args.outlier_url, model=args.outlier_model,
            system=SYSTEM_LABEL, prompt=prompt, timeout=args.llm_timeout,
        )
        if err or not isinstance(result, list):
            print(f"  batch {b_idx+1}/{len(batches)} ERROR: {err}")
            # assign fallback
            for c in batch:
                leaf_label_map[c["id"]] = {
                    "top_category": "unknown",
                    "sub_category": f"cluster_{c['id']}",
                    "leaf_label": f"Cluster {c['id']}",
                    "summary": " ".join(c["terms"][:5]),
                    "confidence": 0.0,
                }
            continue
        for item in result:
            cid = int(item.get("cluster_id", -1))
            leaf_label_map[cid] = item
        print(f"  batch {b_idx+1}/{len(batches)} ✓  ({len(result)} labels)")
        time.sleep(0.5)  # brief pause between batches

    # Attach labels to leaf_infos and build leaf summary texts for re-embedding
    leaf_summaries: list[str] = []
    for c in leaf_infos:
        lbl = leaf_label_map.get(c["id"], {})
        c["top_category"] = lbl.get("top_category", "unknown")
        c["sub_category"] = lbl.get("sub_category", f"cluster_{c['id']}")
        c["leaf_label"]   = lbl.get("leaf_label", f"Cluster {c['id']}")
        c["summary"]      = lbl.get("summary", " ".join(c["terms"][:5]))
        c["confidence"]   = float(lbl.get("confidence", 0.0))
        # Summary text used for re-embedding: label + summary
        leaf_summaries.append(f"{c['top_category']} {c['sub_category']}: {c['summary']}")

    # ---------------------------------------------------------------
    # LEVEL 1: Re-embed summaries → cluster → LLM label mid-level
    # ---------------------------------------------------------------
    print(f"\n[13] === LEVEL 1: re-embedding {leaf_k} leaf summaries with Jina v3 task=clustering ===")
    X_sum = _embed_texts(leaf_summaries, task="separation", truncate_dim=512)
    print(f"[13] summary embeddings: {X_sum.shape}")

    mid_k = args.mid_k or max(8, min(30, round(leaf_k / 5)))
    print(f"[13] mid clusters k={mid_k}")
    mid_labels = _kmeans(X_sum, mid_k)

    # Group leaves by mid cluster
    mid_clusters: dict[int, list[dict]] = {}
    for seq, cid in enumerate(mid_labels):
        mid_clusters.setdefault(int(cid), []).append(leaf_infos[seq])

    mid_infos = [
        {
            "id": seq,
            "orig_cid": orig,
            "n_leaves": len(leaves),
            "n_docs": sum(lf["n"] for lf in leaves),
            "leaves": leaves,
        }
        for seq, (orig, leaves) in enumerate(
            sorted(mid_clusters.items(), key=lambda x: -sum(lf["n"] for lf in x[1]))
        )
    ]

    print(f"\n[13] === LLM labeling {mid_k} mid-level groups ===")
    mid_prompt = _mid_label_prompt(mid_infos)
    mid_result, mid_err = _call_outlier(
        url=args.outlier_url, model=args.outlier_model,
        system=SYSTEM_LABEL, prompt=mid_prompt, timeout=args.llm_timeout,
    )
    if mid_err or not isinstance(mid_result, list):
        print(f"[13] mid-level LLM error: {mid_err} — using top_category from leaves")
        mid_result = []

    mid_label_map: dict[int, dict] = {int(r.get("group_id", -1)): r for r in (mid_result or [])}
    for mg in mid_infos:
        ml = mid_label_map.get(mg["id"], {})
        mg["top_category"] = ml.get("top_category", "unknown")
        mg["sub_category"] = ml.get("sub_category", f"mid_{mg['id']}")
        mg["label"]        = ml.get("label", f"Group {mg['id']}")
        mg["summary"]      = ml.get("summary", "")

    # ---------------------------------------------------------------
    # Build tree bottom-up
    # ---------------------------------------------------------------
    print("\n[13] === building taxonomy tree ===")
    tree: dict[str, Any] = {}

    for mg in mid_infos:
        top_cat = mg["top_category"]
        if top_cat not in tree:
            tree[top_cat] = {"doc_count": 0, "sub_levels": {}}

        for leaf in mg["leaves"]:
            sub = leaf["sub_category"]
            if sub not in tree[top_cat]["sub_levels"]:
                tree[top_cat]["sub_levels"][sub] = {"doc_count": 0, "leaves": {}}

            tree[top_cat]["sub_levels"][sub]["leaves"][leaf["leaf_label"]] = {
                "doc_count":            leaf["n"],
                "doc_ids":              leaf["doc_ids"],
                "sample_urls":          leaf["urls"][:5],
                "group_ids":            [leaf["orig_cid"]],
                "sources":              "raptor_level0",
                "quality_score":        leaf["confidence"],
                "representative_titles": leaf["titles"][:5],
                "summary":              leaf["summary"],
            }
            tree[top_cat]["sub_levels"][sub]["doc_count"] += leaf["n"]
            tree[top_cat]["doc_count"] += leaf["n"]

    # ---------------------------------------------------------------
    # Stats
    # ---------------------------------------------------------------
    n_top  = len(tree)
    n_sub  = sum(len(tn["sub_levels"]) for tn in tree.values())
    n_leaf = sum(len(sn["leaves"]) for tn in tree.values() for sn in tn["sub_levels"].values())
    total_classified = sum(tn["doc_count"] for tn in tree.values())
    avg_conf = np.mean([
        leaf["quality_score"]
        for tn in tree.values()
        for sn in tn["sub_levels"].values()
        for leaf in sn["leaves"].values()
    ])

    print(f"[13] tree: {n_top} top / {n_sub} sub / {n_leaf} leaves")
    print(f"[13] docs classified: {total_classified:,} / {n:,}")
    print(f"[13] avg confidence: {avg_conf:.3f}")

    # ---------------------------------------------------------------
    # Write outputs
    # ---------------------------------------------------------------
    out = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "raptor_lite_v1",
        "leaf_k": leaf_k, "mid_k": mid_k,
        "n_docs": n,
        "summary": {"top": n_top, "sub": n_sub, "leaves": n_leaf,
                    "avg_confidence": round(float(avg_conf), 4)},
        "tree": tree,
    }

    tree_path = args.output_dir / "raptor_tree.json"
    tree_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # Quick markdown summary
    lines = [
        "# RAPTOR Taxonomy Tree", "",
        f"- method: raptor_lite (titles only, no doc content)",
        f"- leaf_k={leaf_k}  mid_k={mid_k}",
        f"- docs: {total_classified:,}/{n:,}  avg_conf={avg_conf:.3f}",
        "",
    ]
    for top, tn in sorted(tree.items()):
        lines.append(f"## {top} ({tn['doc_count']:,} docs)")
        for sub, sn in sorted(tn["sub_levels"].items()):
            lines.append(f"  ### {sub} ({sn['doc_count']:,} docs)")
            for lbl, lv in sorted(sn["leaves"].items()):
                lines.append(f"    - {lbl}: {lv['doc_count']:,} docs  conf={lv['quality_score']:.2f}")
        lines.append("")

    md_path = args.output_dir / "raptor_tree.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[13] tree → {tree_path}")
    print(f"[13] md   → {md_path}")
    print("[13] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
