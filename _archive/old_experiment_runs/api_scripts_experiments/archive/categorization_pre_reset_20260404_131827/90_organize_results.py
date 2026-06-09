#!/usr/bin/env python3
"""
Organize latest categorization artifacts into a clean, stage-ordered run folder.

Why:
- Keep one obvious flow per run.
- Avoid dumping many timestamped files at the same level.
- Make status readable directly from file names and directory layout.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


API_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = API_ROOT / "scripts" / "experiments" / "results" / "categorization"
DEFAULT_RUNS_DIR = DEFAULT_RESULTS_DIR / "runs"
DEFAULT_LATEST_LINK = DEFAULT_RESULTS_DIR / "latest_clean_run"
DEFAULT_ARCHIVE_ROOT = DEFAULT_RESULTS_DIR / "archive"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _latest_match(
    results_dir: Path,
    pattern: str,
    *,
    predicate: Callable[[Path], bool] | None = None,
) -> Path | None:
    candidates = sorted(results_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if predicate is not None:
        candidates = [p for p in candidates if predicate(p)]
    return candidates[0] if candidates else None


def _sanitize_name(text: str) -> str:
    out = []
    for ch in (text or "").strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("-")
    collapsed = "".join(out)
    while "--" in collapsed:
        collapsed = collapsed.replace("--", "-")
    return collapsed.strip("-_") or "x"


def _metrics_url_umbrella(payload: dict[str, Any]) -> tuple[list[str], str]:
    summary = payload.get("summary", {}) or {}
    dyn = (payload.get("depth_results", {}) or {}).get("dynamic", {}) or {}
    docs = _as_int(summary.get("total_docs"))
    clusters = _as_int(dyn.get("parent_cluster_count"))
    return [f"docs-{docs}", f"clusters-{clusters}"], f"docs={docs}, clusters={clusters}"


def _metrics_depth_diversity(payload: dict[str, Any]) -> tuple[list[str], str]:
    summary = payload.get("summary", {}) or {}
    parent = _as_int(summary.get("url_only_parent"))
    categorize = _as_int(summary.get("url_only_categorize"))
    needs = _as_int(summary.get("needs_algorithm"))
    return (
        [f"parent-{parent}", f"categorize-{categorize}", f"needs-{needs}"],
        f"url_only_parent={parent}, url_only_categorize={categorize}, needs_algorithm={needs}",
    )


def _metrics_shortlist(payload: dict[str, Any]) -> tuple[list[str], str]:
    summary = payload.get("summary", {}) or {}
    candidates = _as_int(summary.get("candidate_groups"))
    top_n = _as_int(summary.get("top_n"))
    return [f"candidates-{candidates}", f"top-{top_n}"], f"candidate_groups={candidates}, top_n={top_n}"


def _metrics_ai_input(payload: dict[str, Any]) -> tuple[list[str], str]:
    summary = payload.get("summary", {}) or {}
    categories = _as_int(summary.get("categories_for_ai_count"))
    excluded = (summary.get("excluded_by_decision", {}) or {})
    needs = _as_int(excluded.get("needs_algorithm"))
    return [f"categories-{categories}", f"excluded-needs-{needs}"], f"categories_for_ai={categories}, excluded_needs={needs}"


def _metrics_ai_taxonomy(payload: dict[str, Any]) -> tuple[list[str], str]:
    summary = payload.get("summary", {}) or {}
    mapped = _as_int(summary.get("mapped_count"))
    unresolved = _as_int(summary.get("unresolved_count"))
    source = str(summary.get("llm_provider", "unknown"))
    return [f"mapped-{mapped}", f"unresolved-{unresolved}", f"provider-{_sanitize_name(source)}"], (
        f"mapped={mapped}, unresolved={unresolved}, provider={source}"
    )


def _metrics_tree(payload: dict[str, Any]) -> tuple[list[str], str]:
    summary = payload.get("summary", {}) or {}
    top = _as_int(summary.get("top_level_count"))
    mapped = _as_int(summary.get("mapped_category_count"))
    unresolved = _as_int(summary.get("unresolved_count"))
    return [f"top-{top}", f"mapped-{mapped}", f"unresolved-{unresolved}"], (
        f"top_levels={top}, mapped_categories={mapped}, unresolved={unresolved}"
    )


def _metrics_merge(payload: dict[str, Any]) -> tuple[list[str], str]:
    summary = payload.get("summary", {}) or {}
    mapped_sub = _as_int(summary.get("mapped_algorithm_subcluster_count"))
    unresolved_sub = _as_int(summary.get("unresolved_algorithm_subcluster_count"))
    merged_docs = _as_int(summary.get("merged_tree_doc_count"))
    return [f"mapped-sub-{mapped_sub}", f"unresolved-sub-{unresolved_sub}", f"docs-{merged_docs}"], (
        f"mapped_subclusters={mapped_sub}, unresolved_subclusters={unresolved_sub}, merged_docs={merged_docs}"
    )


@dataclass(frozen=True)
class StageSpec:
    order: int
    key: str
    pattern: str
    required: bool
    metric_fn: Callable[[dict[str, Any]], tuple[list[str], str]]
    predicate: Callable[[Path], bool] | None = None


STAGES: list[StageSpec] = [
    StageSpec(1, "url_umbrella", "pass1_url_umbrella_*.json", True, _metrics_url_umbrella),
    StageSpec(2, "depth_diversity", "pass1_url_depth_diversity_*.json", True, _metrics_depth_diversity),
    StageSpec(3, "shortlist", "pass1_url_shortlist_*.json", True, _metrics_shortlist),
    StageSpec(4, "ai_input", "pass1_ai_taxonomy_input_*.json", True, _metrics_ai_input),
    StageSpec(
        5,
        "ai_taxonomy",
        "pass1_ai_taxonomy_*.json",
        True,
        _metrics_ai_taxonomy,
        predicate=lambda p: "_input_" not in p.name,
    ),
    StageSpec(6, "taxonomy_tree", "pass1_taxonomy_tree_directional_*.json", True, _metrics_tree),
    StageSpec(7, "algorithm_merge", "pass2_algorithm_merge_*.json", False, _metrics_merge),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a clean, numbered output run from latest categorization files.")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--run-name", type=str, default="clean_run")
    parser.add_argument("--allow-missing-required", action="store_true")
    parser.add_argument("--update-latest-link", action="store_true")
    parser.add_argument("--latest-link-path", type=Path, default=DEFAULT_LATEST_LINK)
    parser.add_argument(
        "--archive-source-files",
        action="store_true",
        help="After copying stage files into clean run folder, move matched source files into archive/",
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=DEFAULT_ARCHIVE_ROOT,
        help="Archive root used when --archive-source-files is enabled.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.results_dir.exists():
        raise FileNotFoundError(f"Results dir not found: {args.results_dir}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_name = _sanitize_name(args.run_name)
    run_dir = args.runs_dir / f"{stamp}_{run_name}"
    run_dir.mkdir(parents=True, exist_ok=False)

    stage_lines: list[str] = []
    stage_lines.append("# Clean Categorization Run")
    stage_lines.append("")
    stage_lines.append(f"- created_at_utc: `{datetime.now(timezone.utc).isoformat()}`")
    stage_lines.append(f"- source_results_dir: `{args.results_dir}`")
    stage_lines.append(f"- run_dir: `{run_dir}`")
    stage_lines.append("")
    stage_lines.append("## Stage Files")
    stage_lines.append("")
    stage_lines.append("| Stage | Status | File | Notes |")
    stage_lines.append("|---|---|---|---|")

    missing_required: list[str] = []
    copied_count = 0
    copied_sources: list[Path] = []

    for spec in STAGES:
        src = _latest_match(args.results_dir, spec.pattern, predicate=spec.predicate)
        if src is None:
            status = "missing_required" if spec.required else "missing_optional"
            stage_lines.append(f"| {spec.order:02d}_{spec.key} | {status} | - | no file matched `{spec.pattern}` |")
            if spec.required:
                missing_required.append(spec.key)
            continue

        payload = json.loads(src.read_text(encoding="utf-8"))
        metrics, notes = spec.metric_fn(payload)
        metric_suffix = "__".join(_sanitize_name(m) for m in metrics if _sanitize_name(m))
        target_name = f"{spec.order:02d}_{spec.key}"
        if metric_suffix:
            target_name += f"__{metric_suffix}"
        target_path = run_dir / f"{target_name}.json"
        shutil.copy2(src, target_path)
        copied_count += 1
        copied_sources.append(src)

        stage_lines.append(
            f"| {spec.order:02d}_{spec.key} | ok | `{target_path.name}` | {notes} |"
        )

    if missing_required and not args.allow_missing_required:
        stage_lines.append("")
        stage_lines.append("## Status")
        stage_lines.append("")
        stage_lines.append(
            f"- FAILED: missing required stages `{', '.join(missing_required)}`. "
            "Re-run with `--allow-missing-required` to keep partial layout."
        )
        (run_dir / "FLOW.md").write_text("\n".join(stage_lines) + "\n", encoding="utf-8")
        raise RuntimeError(f"Missing required stages: {', '.join(missing_required)}")

    stage_lines.append("")
    stage_lines.append("## Status")
    stage_lines.append("")
    stage_lines.append(f"- copied_stage_files: `{copied_count}`")
    if missing_required:
        stage_lines.append(f"- warning: missing required stages but allowed: `{', '.join(missing_required)}`")
    else:
        stage_lines.append("- required_stages: `complete`")

    flow_path = run_dir / "FLOW.md"
    flow_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")

    if args.archive_source_files and copied_sources:
        archive_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_dir = args.archive_root / f"{archive_stamp}_organize_sources"
        archive_dir.mkdir(parents=True, exist_ok=True)
        moved = 0
        for src in copied_sources:
            if not src.exists():
                continue
            # Only move flat files from results root; do not move anything under runs/archive.
            if src.parent.resolve() != args.results_dir.resolve():
                continue
            target = archive_dir / src.name
            if target.exists():
                target = archive_dir / f"{src.stem}__dup{src.suffix}"
            shutil.move(str(src), str(target))
            moved += 1
        note = archive_dir / "ARCHIVE_NOTE.md"
        note.write_text(
            "\n".join(
                [
                    "# Organizer Source Archive",
                    "",
                    f"- created_at_utc: `{datetime.now(timezone.utc).isoformat()}`",
                    f"- source_results_dir: `{args.results_dir}`",
                    f"- moved_files: `{moved}`",
                    "- reason: keep results root clean after promoting clean run folder",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(f"[clean-run] archived_sources: {moved} -> {archive_dir}")

    if args.update_latest_link:
        latest_link = args.latest_link_path
        if latest_link.exists():
            if latest_link.is_symlink():
                latest_link.unlink()
            else:
                print(f"[clean-run] latest link target exists and is not a symlink, skipped: {latest_link}")
                print(f"[clean-run] run_dir: {run_dir}")
                print(f"[clean-run] flow: {flow_path}")
                return 0
        latest_link.parent.mkdir(parents=True, exist_ok=True)
        latest_link.symlink_to(run_dir, target_is_directory=True)
        print(f"[clean-run] latest_link: {latest_link} -> {run_dir}")

    print(f"[clean-run] run_dir: {run_dir}")
    print(f"[clean-run] flow: {flow_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
