import os
import json
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from database import models

_TEST_STARTED_AT: datetime | None = None
_TEST_CASE_REPORTS: dict[str, dict[str, object]] = {}


def _test_db_url() -> str:
    return (
        os.getenv("TEST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "postgresql://postgres:postgres@localhost:55432/postgres"
    )


engine = create_engine(_test_db_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def prepare_schema() -> Generator[None, None, None]:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    models.Base.metadata.create_all(bind=engine)
    yield
    models.Base.metadata.drop_all(bind=engine)


def _truncate_all_tables(db: Session) -> None:
    table_names = [table.name for table in models.Base.metadata.sorted_tables]
    if not table_names:
        return
    quoted = ", ".join(f'"{name}"' for name in table_names)
    db.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    db.commit()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        _truncate_all_tables(db)
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def strict_session(db_session: Session) -> Generator[Session, None, None]:
    yield db_session


def _report_dir() -> Path:
    root = Path(__file__).resolve().parent
    target = os.getenv("TEST_REPORT_DIR", str(root / "reports"))
    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)
    return out


def pytest_configure(config: pytest.Config) -> None:
    global _TEST_STARTED_AT, _TEST_CASE_REPORTS
    _TEST_STARTED_AT = datetime.now(timezone.utc)
    _TEST_CASE_REPORTS = {}


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    case = _TEST_CASE_REPORTS.setdefault(
        report.nodeid,
        {
            "nodeid": report.nodeid,
            "outcome": "passed",
            "duration_seconds": 0.0,
            "phases": {},
            "error": None,
        },
    )
    case["duration_seconds"] += report.duration
    case["phases"][report.when] = {
        "outcome": report.outcome,
        "duration_seconds": report.duration,
    }
    if report.outcome == "failed":
        case["outcome"] = "failed"
        case["error"] = getattr(report, "longreprtext", str(report.longrepr))
    elif report.outcome == "skipped" and case["outcome"] != "failed":
        case["outcome"] = "skipped"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    started_at = _TEST_STARTED_AT or datetime.now(timezone.utc)
    finished_at = datetime.now(timezone.utc)
    cases = list(_TEST_CASE_REPORTS.values())

    counts = {
        "total": len(cases),
        "passed": sum(1 for c in cases if c["outcome"] == "passed"),
        "failed": sum(1 for c in cases if c["outcome"] == "failed"),
        "skipped": sum(1 for c in cases if c["outcome"] == "skipped"),
    }
    status = "passed" if counts["failed"] == 0 and exitstatus == 0 else "failed"
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")

    payload = {
        "run_id": run_id,
        "status": status,
        "exit_status": exitstatus,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "database_url": _test_db_url(),
        "counts": counts,
        "cases": sorted(cases, key=lambda c: c["nodeid"]),
    }

    out_dir = _report_dir()
    json_path = out_dir / f"pytest-report-{run_id}.json"
    latest_json_path = out_dir / "pytest-report-latest.json"
    md_path = out_dir / f"pytest-report-{run_id}.md"
    latest_md_path = out_dir / "pytest-report-latest.md"

    artifacts = [
        {"name": "json", "path": str(json_path), "type": "report/json"},
        {"name": "json_latest", "path": str(latest_json_path), "type": "report/json"},
        {"name": "markdown", "path": str(md_path), "type": "report/markdown"},
        {"name": "markdown_latest", "path": str(latest_md_path), "type": "report/markdown"},
    ]
    payload["artifacts"] = artifacts

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    failed_cases = [c for c in payload["cases"] if c["outcome"] == "failed"]
    lines = [
        "# Pytest Report",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Status: `{payload['status']}`",
        f"- Started (UTC): `{payload['started_at_utc']}`",
        f"- Finished (UTC): `{payload['finished_at_utc']}`",
        f"- Duration (s): `{payload['duration_seconds']:.3f}`",
        f"- Total: `{counts['total']}` | Passed: `{counts['passed']}` | Failed: `{counts['failed']}` | Skipped: `{counts['skipped']}`",
        "",
        "## Artifacts",
        "",
    ]
    for artifact in payload["artifacts"]:
        lines.append(f"- `{artifact['name']}`: `{artifact['path']}` ({artifact['type']})")
    lines.append("")

    if failed_cases:
        lines.append("## Failures")
        lines.append("")
        for case in failed_cases:
            lines.append(f"### `{case['nodeid']}`")
            lines.append("")
            lines.append("```text")
            lines.append((case["error"] or "").strip())
            lines.append("```")
            lines.append("")
    else:
        lines.append("## Failures")
        lines.append("")
        lines.append("None")
        lines.append("")

    md_text = "\n".join(lines)
    md_path.write_text(md_text, encoding="utf-8")
    latest_md_path.write_text(md_text, encoding="utf-8")
