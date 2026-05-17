"""Score the event extraction pipeline against silver GT.

Reads candidates_gt.jsonl, emits a confusion matrix and P/R/F1.
Also emits a LaTeX-ready table to stdout.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

GT = Path("api/data/ground_truth/events/candidates_gt.jsonl")


def load():
    with GT.open() as f:
        return [json.loads(l) for l in f]


def main():
    rows = load()
    n = len(rows)
    gold = Counter(r["gold_label"] for r in rows)
    sysd = Counter(r["system_decision"] for r in rows)
    joint = Counter((r["system_decision"], r["gold_label"]) for r in rows)
    parse_err = sum(1 for r in rows if r.get("parse_error"))

    # binary: positive class = true_obligation, predicted positive = ACCEPT_PENDING
    tp = joint[("ACCEPT_PENDING", "true_obligation")]
    fp = joint[("ACCEPT_PENDING", "non_obligation")] + joint[("ACCEPT_PENDING", "ambiguous")]
    fn = joint[("REJECT_QUALITY", "true_obligation")]
    tn = joint[("REJECT_QUALITY", "non_obligation")] + joint[("REJECT_QUALITY", "ambiguous")]
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    accuracy = (tp + tn) / n

    print(f"N={n}  parse_errors={parse_err}")
    print(f"Gold dist:   {dict(gold)}")
    print(f"System dist: {dict(sysd)}")
    print()
    print("Confusion (rows=system, cols=gold):")
    cats = ["true_obligation", "non_obligation", "ambiguous"]
    print(f"{'':>20} | " + " | ".join(f"{c:>16}" for c in cats))
    for s in ["ACCEPT_PENDING", "REJECT_QUALITY"]:
        cells = [str(joint[(s, c)]) for c in cats]
        print(f"{s:>20} | " + " | ".join(f"{x:>16}" for x in cells))
    print()
    print(f"Binary (positive=true_obligation, predicted=ACCEPT):")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Accuracy = {accuracy:.3f}")
    print(f"  Precision= {precision:.3f}")
    print(f"  Recall   = {recall:.3f}")
    print(f"  F1       = {f1:.3f}")

    print("\n=== LaTeX confusion matrix ===")
    print(r"\begin{table}[h]\centering")
    print(r"\begin{tabular}{l|ccc}")
    print(r"System decision $\backslash$ Gold & True obligation & Non-obligation & Ambiguous \\ \hline")
    for s, sl in [("ACCEPT_PENDING", "Accept"), ("REJECT_QUALITY", "Reject")]:
        print(f"{sl} & " + " & ".join(str(joint[(s, c)]) for c in cats) + r" \\")
    print(r"\end{tabular}")
    print(r"\caption{Confusion matrix of the event extraction pipeline against silver "
          r"ground truth ($N{=}323$ candidates, judge: \texttt{gemini-2.5-flash-lite}).}")
    print(r"\label{tab:event_confusion}")
    print(r"\end{table}")

    print("\n=== LaTeX metrics ===")
    print(r"\begin{table}[h]\centering")
    print(r"\begin{tabular}{lc}")
    print(r"Metric & Value \\ \hline")
    print(f"Accuracy & {accuracy:.3f} " + r"\\")
    print(f"Precision & {precision:.3f} " + r"\\")
    print(f"Recall & {recall:.3f} " + r"\\")
    print(f"F1 & {f1:.3f} " + r"\\")
    print(r"\end{tabular}")
    print(r"\caption{Binary classification metrics for the event extraction pipeline. "
          r"Positive class: true obligation accepted by the system.}")
    print(r"\label{tab:event_metrics}")
    print(r"\end{table}")


if __name__ == "__main__":
    main()
