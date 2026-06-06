#!/usr/bin/env python3
"""
Clean stage entrypoint for the categorization pipeline.

Use this instead of memorizing many script names.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Stage:
    id: str
    name: str
    script: str
    description: str


STAGES: list[Stage] = [
    Stage("01", "url-groups", "01_build_url_groups.py", "Build URL groups"),
    Stage("02", "classify-groups", "02_classify_url_groups.py", "Classify URL groups"),
    Stage("03", "shortlist", "03_build_shortlist.py", "Build candidate shortlist view"),
    Stage("04", "ai-input", "04_build_ai_input.py", "Build AI input"),
    Stage("05", "ai-mapping", "05_run_ai_mapping.py", "Run AI mapping"),
    Stage("06", "tree", "06_build_tree.py", "Build taxonomy tree"),
    Stage("07", "merge", "07_merge_algorithm_groups.py", "Merge algorithm groups"),
    Stage("08", "visuals", "08_build_visuals.py", "Build visuals"),
    Stage("90", "organize", "90_organize_results.py", "Organize results"),
]


def _stage_index() -> dict[str, Stage]:
    out: dict[str, Stage] = {}
    for s in STAGES:
        out[s.id] = s
        out[s.name] = s
    return out


def _print_stage_list() -> None:
    print("Clean flow stages:")
    for s in STAGES:
        print(f"- {s.id}  {s.name:<10}  {s.script:<34}  {s.description}")
    print("")
    print("Example:")
    print("  python3 -u api/scripts/experiments/categorization/00_run_flow.py 01 -- --sample-size 0 --dynamic-depth")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single clean entrypoint for categorization flow stages.")
    parser.add_argument(
        "stage",
        type=str,
        help="Stage id/name (01, url-groups, 02, classify-groups, ..., 90, organize) or 'list'.",
    )
    parser.add_argument(
        "stage_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass through to the underlying stage script. Use `--` before stage args.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stage_key = args.stage.strip().lower()
    if stage_key in {"list", "ls"}:
        _print_stage_list()
        return 0

    index = _stage_index()
    stage = index.get(stage_key)
    if stage is None:
        _print_stage_list()
        raise ValueError(f"Unknown stage: {args.stage}")

    script_path = ROOT / stage.script
    if not script_path.exists():
        raise FileNotFoundError(f"Stage script not found: {script_path}")

    passthrough = list(args.stage_args)
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    cmd = [sys.executable, "-u", str(script_path), *passthrough]
    print(f"[flow] stage={stage.id}:{stage.name} script={script_path.name}")
    if passthrough:
        print(f"[flow] args={' '.join(passthrough)}")
    else:
        print("[flow] args=<none>")
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
