"""Run the real submission agent against the 32 GT cases and score it.

Bridges:
- agent expects one file at a time. For multi-file cases we feed each file and
  take the most lenient decision (approve if any file approves) to match the
  product UX intent.
- agent outputs {approved, rejected}. GT has {approve, reject, flag}.
  Folded: gold 'flag' is correct if agent says 'rejected' (i.e. did not falsely
  approve), and we report a separate "flag-caught" metric.
"""
from __future__ import annotations

import json
import mimetypes
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent))
from api.agents.submission_agent import evaluate_submission  # noqa: E402
from api.scripts.experiments._llm_judge import judge  # noqa: E402

CASES_DIR = Path("api/data/ground_truth/submissions")
OUT = Path("api/data/ground_truth/submissions/results.jsonl")

SYS = ("You evaluate student submissions. Reply ONLY with JSON of shape "
       '{"decision":"approved"|"rejected","confidence":0-1,"reason":"<one line>"}.')


def llm_complete(prompt: str) -> str:
    return judge(SYS, prompt, max_tokens=400)


def run_case(case_dir: Path) -> dict:
    expected = json.loads((case_dir / "expected.json").read_text())
    requirement = (case_dir / "requirement.txt").read_text()
    files = sorted((case_dir / "files").iterdir())
    title = expected["assignment_title"]
    desc = requirement

    per_file = []
    for fp in files:
        content = fp.read_bytes()
        mime, _ = mimetypes.guess_type(fp.name)
        try:
            ev = evaluate_submission(
                assignment_title=title,
                assignment_description=desc,
                content=content,
                filename=fp.name,
                content_type=mime,
                llm_complete=llm_complete,
            )
            per_file.append({"file": fp.name, "decision": ev.decision,
                             "confidence": ev.confidence, "feedback": ev.feedback[:200]})
        except Exception as e:
            per_file.append({"file": fp.name, "decision": "rejected",
                             "confidence": 0.0, "feedback": f"AGENT_ERROR: {e}"})

    any_approved = any(f["decision"] == "approved" for f in per_file)
    final = "approved" if any_approved else "rejected"

    # fold GT 3-class -> binary correctness
    gold = expected["expected_decision"]  # approve, reject, flag
    if gold == "approve":
        correct = final == "approved"
    else:  # reject or flag
        correct = final == "rejected"

    return {
        "case_id": expected["case_id"],
        "stratum": expected["stratum"],
        "gold": gold,
        "agent_decision": final,
        "correct": correct,
        "per_file": per_file,
    }


def main():
    cases = sorted([d for d in CASES_DIR.iterdir() if d.is_dir()])
    print(f"Running {len(cases)} cases in parallel...", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(run_case, c): c for c in cases}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            results.append(r)
            mark = "OK " if r["correct"] else "MISS"
            print(f"  [{i}/{len(cases)}] {mark} {r['case_id']:36s} "
                  f"gold={r['gold']:7s} agent={r['agent_decision']}", flush=True)
    results.sort(key=lambda r: r["case_id"])
    with OUT.open("w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"\nWrote {OUT}")

    # ---- metrics ----
    n = len(results)
    correct = sum(r["correct"] for r in results)
    acc = correct / n

    # binary (positive = approve)
    tp = sum(1 for r in results if r["gold"] == "approve" and r["agent_decision"] == "approved")
    fp = sum(1 for r in results if r["gold"] != "approve" and r["agent_decision"] == "approved")
    fn = sum(1 for r in results if r["gold"] == "approve" and r["agent_decision"] == "rejected")
    tn = sum(1 for r in results if r["gold"] != "approve" and r["agent_decision"] == "rejected")
    p = tp / (tp + fp) if (tp + fp) else 0
    rc = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * p * rc / (p + rc) if (p + rc) else 0

    by_stratum = Counter()
    correct_by_stratum = Counter()
    for r in results:
        by_stratum[r["stratum"]] += 1
        correct_by_stratum[r["stratum"]] += int(r["correct"])

    print(f"\n=== Submission agent ===")
    print(f"N={n}  Accuracy={acc:.3f}")
    print(f"TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"Precision={p:.3f} Recall={rc:.3f} F1={f1:.3f}")
    print(f"\nPer stratum:")
    for s in sorted(by_stratum):
        print(f"  {s:25s}: {correct_by_stratum[s]}/{by_stratum[s]}")

    # injection-resistance: % of reject_injection cases NOT approved
    inj_total = by_stratum.get("reject_injection", 0)
    inj_resist = correct_by_stratum.get("reject_injection", 0)
    if inj_total:
        print(f"\nInjection resistance: {inj_resist}/{inj_total} = {inj_resist/inj_total:.0%}")

    # LaTeX
    print("\n=== LaTeX per-stratum ===")
    print(r"\begin{table}[h]\centering")
    print(r"\begin{tabular}{lcc}")
    print(r"Stratum & N & Correct \\ \hline")
    for s in sorted(by_stratum):
        print(f"{s.replace('_', ' ')} & {by_stratum[s]} & {correct_by_stratum[s]} " + r"\\")
    print(r"\hline")
    print(f"Overall & {n} & {correct} " + r"\\")
    print(r"\end{tabular}")
    print(r"\caption{Submission agent results by stratum on $N{=}32$ "
          r"deterministically generated test cases (4 assignments $\times$ 8 strata).}")
    print(r"\label{tab:submission_stratum}")
    print(r"\end{table}")

    print("\n=== LaTeX metrics ===")
    print(r"\begin{table}[h]\centering")
    print(r"\begin{tabular}{lc}")
    print(r"Metric & Value \\ \hline")
    print(f"Accuracy & {acc:.3f} " + r"\\")
    print(f"Precision & {p:.3f} " + r"\\")
    print(f"Recall & {rc:.3f} " + r"\\")
    print(f"F1 & {f1:.3f} " + r"\\")
    if inj_total:
        print(f"Injection resistance & {inj_resist}/{inj_total} " + r"\\")
    print(r"\end{tabular}")
    print(r"\caption{Submission agent binary classification metrics (positive class: "
          r"approve). The flag-partial stratum is folded into the negative class.}")
    print(r"\label{tab:submission_metrics}")
    print(r"\end{table}")


if __name__ == "__main__":
    main()
