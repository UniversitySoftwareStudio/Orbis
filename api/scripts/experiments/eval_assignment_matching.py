"""Score assignment matching: silver GT (profile x candidate) vs system's
actual `user_rule_assignments` (user_id x rule_id).

Bridge: regulation_rules.rule_text == event_candidate_logs.candidate_text.
       user_profiles.user_id == user_rule_assignments.user_id.

For each (profile, accepted_candidate) pair we have:
  - gold_applies in {yes, no, maybe}
  - system_assigned in {True, False}  (was the user actually matched to that rule?)

Report per-profile + overall precision/recall/F1 treating gold=yes as positive
and 'maybe' as ambiguous (counted both ways for sensitivity).
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import create_engine, text

GT = Path("api/data/ground_truth/events/assignment_matching_gt.jsonl")
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:supersecret@172.17.0.1:5432/orbisdb")
engine = create_engine(DB_URL)


def load_gt():
    with GT.open() as f:
        return [json.loads(l) for l in f]


def fetch_system_pairs():
    """Return set of (profile_id, candidate_id) the system actually assigned."""
    with engine.connect() as c:
        rows = c.execute(text("""
            select up.id::text as profile_id, ec.id::text as candidate_id
            from user_rule_assignments ura
            join regulation_rules r on r.id = ura.rule_id
            join event_candidate_logs ec on ec.candidate_text = r.rule_text
            join user_profiles up on up.user_id = ura.user_id
        """)).all()
    return {(p, c) for p, c in rows}


def score(gold_labels, system_pairs):
    """gold_labels: list of dicts with profile_id, candidate_id, gold_applies."""
    per_profile = defaultdict(lambda: Counter())
    overall = Counter()
    for r in gold_labels:
        key = (r["profile_id"], r["candidate_id"])
        sys_pos = key in system_pairs
        gold = r["gold_applies"]
        # strict: positive iff gold=='yes'
        gold_pos = (gold == "yes")
        bucket = ("TP" if sys_pos and gold_pos else
                  "FP" if sys_pos and not gold_pos else
                  "FN" if not sys_pos and gold_pos else "TN")
        per_profile[r["profile_id"]][bucket] += 1
        per_profile[r["profile_id"]][f"gold_{gold}"] += 1
        overall[bucket] += 1
        overall[f"gold_{gold}"] += 1
    return per_profile, overall


def prf(c):
    tp, fp, fn = c["TP"], c["FP"], c["FN"]
    p = tp / (tp + fp) if (tp + fp) else 0
    r = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * p * r / (p + r) if (p + r) else 0
    return p, r, f1


def main():
    gt = load_gt()
    pairs = fetch_system_pairs()
    print(f"GT pairs: {len(gt)}; system positive pairs: {len(pairs)}")

    per, overall = score(gt, pairs)

    print("\n=== Overall ===")
    print(f"TP={overall['TP']}  FP={overall['FP']}  FN={overall['FN']}  TN={overall['TN']}")
    print(f"Gold dist: yes={overall['gold_yes']} no={overall['gold_no']} maybe={overall['gold_maybe']}")
    p, r, f1 = prf(overall)
    print(f"Precision={p:.3f}  Recall={r:.3f}  F1={f1:.3f}")

    print("\n=== Per profile ===")
    rows = []
    for pid in sorted(per, key=int):
        c = per[pid]
        pp, pr, pf1 = prf(c)
        print(f"profile {pid}: TP={c['TP']} FP={c['FP']} FN={c['FN']} TN={c['TN']} "
              f"P={pp:.3f} R={pr:.3f} F1={pf1:.3f} "
              f"(gold yes={c['gold_yes']} no={c['gold_no']} maybe={c['gold_maybe']})")
        rows.append((pid, c, pp, pr, pf1))

    print("\n=== LaTeX per-profile table ===")
    print(r"\begin{table}[h]\centering")
    print(r"\begin{tabular}{l|cccc|ccc}")
    print(r"Profile & TP & FP & FN & TN & Precision & Recall & F1 \\ \hline")
    for pid, c, pp, pr, pf1 in rows:
        print(f"P{pid} & {c['TP']} & {c['FP']} & {c['FN']} & {c['TN']} & "
              f"{pp:.3f} & {pr:.3f} & {pf1:.3f} " + r"\\")
    op, orr, of1 = prf(overall)
    print(r"\hline")
    print(f"Overall & {overall['TP']} & {overall['FP']} & {overall['FN']} & {overall['TN']} & "
          f"{op:.3f} & {orr:.3f} & {of1:.3f} " + r"\\")
    print(r"\end{tabular}")
    print(r"\caption{Per-profile assignment matching scores against silver ground truth "
          r"($N{=}712$ pairs: 4 student profiles $\times$ 178 accepted obligations).}")
    print(r"\label{tab:matching_perprofile}")
    print(r"\end{table}")


if __name__ == "__main__":
    main()
