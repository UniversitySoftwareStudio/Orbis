#!/usr/bin/env python3
"""Step 14: Merge RAPTOR tree + targeted regulation subtree into final golden tree.

- Take RAPTOR tree (all docs, high confidence)
- Replace regulations node with step-12 precision regulation subtree
- Output the final merged tree
"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone

API_ROOT = Path(__file__).resolve().parents[3]
FLOW = API_ROOT / "scripts/experiments/results/categorization/flow"

raptor    = json.load(open(FLOW / "13_raptor_taxonomy/raptor_tree.json"))
reg_tree  = json.load(open(FLOW / "12_cluster_regulations/tree_with_regulations.json"))

tree = raptor["tree"]

# Replace regulations node with step-12's precision subtree
tree["regulations"] = reg_tree["tree"]["regulations"]

# Stats
n_top  = len(tree)
n_sub  = sum(len(tn["sub_levels"]) for tn in tree.values())
n_leaf = sum(len(sn["leaves"]) for tn in tree.values() for sn in tn["sub_levels"].values())
total_docs = sum(tn["doc_count"] for tn in tree.values())

out = {
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "method": "raptor_v1 + targeted_regulations_v2",
    "summary": {"top": n_top, "sub": n_sub, "leaves": n_leaf, "total_docs": total_docs},
    "tree": tree,
}

out_dir = FLOW / "14_final_tree"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "final_tree.json"
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

# Quick summary
lines = [f"# Final Merged Taxonomy", "",
         f"- {n_top} top categories, {n_sub} sub-categories, {n_leaf} leaves",
         f"- {total_docs:,} total docs", ""]
for top, tn in sorted(tree.items()):
    lines.append(f"## {top} ({tn['doc_count']:,} docs, {len(tn['sub_levels'])} subs)")
for sub, sn in tn.get("sub_levels",{}).items():
    lines.append(f"  - {sub}: {sn['doc_count']:,} docs, {len(sn['leaves'])} leaves")
lines.append("")

md_path = out_dir / "final_tree.md"
md_path.write_text("\n".join(lines))
print(f"top={n_top}  sub={n_sub}  leaves={n_leaf}  docs={total_docs:,}")
print(f"→ {out_path}")
