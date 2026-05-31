"""Build ground truth for the event extraction pipeline.

Outputs:
- api/data/ground_truth/events/candidates_gt.jsonl
- api/data/ground_truth/events/assignment_matching_gt.jsonl
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent))
from api.scripts.experiments._llm_judge import judge_json  # noqa: E402

OUT_DIR = Path("api/data/ground_truth/events")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CAND_PATH = OUT_DIR / "candidates_gt.jsonl"
MATCH_PATH = OUT_DIR / "assignment_matching_gt.jsonl"

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:supersecret@172.17.0.1:5432/orbisdb")
engine = create_engine(DB_URL)

WORKERS = int(os.getenv("GT_WORKERS", "12"))

CAND_SYSTEM = (
    "You evaluate university regulation extractions. A 'strict assignable obligation' "
    "is a concrete duty a specific role (student/staff/faculty) MUST perform, with a "
    "clear action verb, deadline or condition, and an identifiable target. "
    "Reject vague policy statements, definitions, governance descriptions, or rights. "
    "Reply ONLY with JSON: "
    '{"label": "true_obligation" | "non_obligation" | "ambiguous", "reason": "<one line>"}'
)

MATCH_SYSTEM = (
    "You decide whether a university obligation applies to a specific student profile. "
    "Apply common-sense academic rules. If the obligation targets a specific situation "
    "(e.g. graduation project, exchange, probation) the profile must match it. "
    "Reply ONLY with JSON: "
    '{"applies": "yes" | "no" | "maybe", "reason": "<one line>"}'
)


def fetch_candidates():
    with engine.connect() as c:
        return c.execute(
            text(
                "select id, candidate_text, target_role, decision, reason_code, source_url "
                "from event_candidate_logs order by created_at"
            )
        ).mappings().all()


def fetch_profiles():
    with engine.connect() as c:
        return c.execute(
            text(
                "select id, department, faculty, program_level, academic_year, "
                "semester_number, total_credits_completed, is_on_probation, "
                "is_exchange_student, is_double_major, is_minor, has_advisor_hold, "
                "has_financial_hold, extra_context "
                "from user_profiles order by id"
            )
        ).mappings().all()


def profile_summary(p) -> str:
    flags = []
    for k in ("is_on_probation", "is_exchange_student", "is_double_major", "is_minor",
              "has_advisor_hold", "has_financial_hold"):
        if p[k]:
            flags.append(k)
    extra = p["extra_context"] or {}
    return (
        f"Department: {p['department']}; Faculty: {p['faculty']}; "
        f"Level: {p['program_level']}; Year {p['academic_year']} Semester {p['semester_number']}; "
        f"Credits done: {p['total_credits_completed']}; "
        f"Flags: {', '.join(flags) or 'none'}; Extra: {extra}"
    )


def label_candidate(row) -> dict:
    user = (
        f"Candidate text:\n{row['candidate_text']}\n\n"
        f"Target role: {row['target_role']}\nSource: {row['source_url']}"
    )
    res = judge_json(CAND_SYSTEM, user)
    return {
        "candidate_id": str(row["id"]),
        "candidate_text": row["candidate_text"],
        "target_role": row["target_role"],
        "system_decision": row["decision"],
        "system_reason": row["reason_code"],
        "gold_label": res.get("label", "ambiguous"),
        "gold_reason": res.get("reason", ""),
        "parse_error": res.get("_parse_error", False),
    }


def label_pair(profile, candidate) -> dict:
    user = (
        f"Student profile:\n{profile_summary(profile)}\n\n"
        f"Obligation:\n{candidate['candidate_text']}\n"
        f"(target role: {candidate['target_role']})"
    )
    res = judge_json(MATCH_SYSTEM, user)
    return {
        "profile_id": str(profile["id"]),
        "candidate_id": str(candidate["id"]),
        "gold_applies": res.get("applies", "maybe"),
        "gold_reason": res.get("reason", ""),
        "parse_error": res.get("_parse_error", False),
    }


def run_pool(items, fn, label):
    out = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fn, x): i for i, x in enumerate(items)}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                out.append(f.result())
            except Exception as e:
                out.append({"error": str(e), "index": futs[f]})
            if i % 25 == 0 or i == len(items):
                print(f"  [{label}] {i}/{len(items)}", flush=True)
    return out


def main():
    print("== Event candidate GT ==")
    candidates = fetch_candidates()
    print(f"Loaded {len(candidates)} candidates")
    labeled = run_pool(candidates, label_candidate, "cand")
    with CAND_PATH.open("w") as f:
        for r in labeled:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {CAND_PATH} ({len(labeled)} rows)")

    print("\n== Assignment matching GT ==")
    profiles = fetch_profiles()
    accepted = [c for c in candidates if c["decision"] == "ACCEPT_PENDING"]
    print(f"Profiles: {len(profiles)}, accepted candidates: {len(accepted)}, "
          f"pairs: {len(profiles)*len(accepted)}")
    pairs = [(p, c) for p in profiles for c in accepted]
    labeled_pairs = run_pool(pairs, lambda pc: label_pair(*pc), "pair")
    with MATCH_PATH.open("w") as f:
        for r in labeled_pairs:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {MATCH_PATH} ({len(labeled_pairs)} rows)")


if __name__ == "__main__":
    main()
