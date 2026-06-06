from __future__ import annotations

import io
import json
import mimetypes
import re
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


Decision = str


@dataclass(frozen=True)
class SubmissionAgentConfig:
    max_file_size: int = 10 * 1024 * 1024
    max_llm_chars: int = 18000
    max_zip_members: int = 80
    max_zip_text_bytes: int = 2 * 1024 * 1024
    max_single_zip_member_bytes: int = 512 * 1024


@dataclass(frozen=True)
class SubmissionEvaluation:
    decision: Decision
    feedback: str
    confidence: float
    report: dict[str, Any]


@dataclass(frozen=True)
class AgentEvent:
    """A progress event emitted while the agent reasons, for live streaming."""

    type: str
    data: dict[str, Any]


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".cs",
    ".go",
    ".rb",
    ".rs",
    ".php",
    ".html",
    ".css",
    ".json",
    ".csv",
    ".xml",
    ".yaml",
    ".yml",
    ".sql",
    ".sh",
    # LaTeX / academic typesetting
    ".tex",
    ".bib",
    ".sty",
    ".cls",
    ".bbl",
    # more source languages
    ".kt",
    ".kts",
    ".swift",
    ".scala",
    ".m",
    ".mm",
    ".r",
    ".jl",
    ".lua",
    ".pl",
    ".pm",
    ".dart",
    ".vue",
    ".svelte",
    ".scss",
    ".sass",
    ".less",
    ".hs",
    ".clj",
    ".ex",
    ".exs",
    ".erl",
    ".groovy",
    ".gradle",
    ".bat",
    ".ps1",
    ".asm",
    ".s",
    ".h",
    ".hpp",
    # config / data / notebooks / docs
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".properties",
    ".tsv",
    ".ipynb",
    ".org",
    ".tex",
    ".adoc",
    ".markdown",
    ".text",
    ".log",
    ".gitignore",
    ".dockerfile",
    ".makefile",
}
DOCUMENT_EXTENSIONS = {".pdf", ".docx"}
ARCHIVE_EXTENSIONS = {".zip"}
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS | ARCHIVE_EXTENSIONS

# Extensions we know are binary; inside a zip these are skipped without trying to
# decode them. Everything NOT in this set is attempted and gated on content.
BINARY_EXTENSIONS = {
    # images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".ico", ".webp",
    ".svg", ".heic", ".psd", ".ai", ".eps",
    # audio / video
    ".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a",
    ".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".flv",
    # archives / compressed
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    # compiled / binary objects
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".obj", ".class",
    ".pyc", ".pyo", ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
    # office binaries handled elsewhere or not extractable here
    ".pdf", ".doc", ".ppt", ".pptx", ".xls", ".xlsx",
    # fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # misc binary
    ".pdf", ".pkl", ".npy", ".npz", ".parquet", ".lockb",
}

ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/zip",
    "application/x-zip-compressed",
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/x-python",
    "text/x-python-script",
    "text/javascript",
    "application/javascript",
    "application/json",
    "application/xml",
    "application/x-python-code",
    "application/octet-stream",
}

STOPWORDS = {
    "about",
    "after",
    "also",
    "analysis",
    "answer",
    "assignment",
    "before",
    "case",
    "course",
    "data",
    "describe",
    "document",
    "each",
    "essay",
    "final",
    "from",
    "homework",
    "include",
    "into",
    "must",
    "paper",
    "part",
    "project",
    "provide",
    "report",
    "should",
    "student",
    "submission",
    "submit",
    "task",
    "that",
    "their",
    "this",
    "using",
    "what",
    "when",
    "where",
    "with",
    "work",
    "write",
    "your",
}


def evaluate_submission(
    *,
    assignment_title: str,
    assignment_description: str | None,
    content: bytes,
    filename: str | None,
    content_type: str | None,
    llm_complete: Callable[[str], str] | None = None,
    config: SubmissionAgentConfig | None = None,
) -> SubmissionEvaluation:
    """Run the agent end-to-end and return the final evaluation.

    This is a thin wrapper that drains :func:`stream_submission_evaluation`,
    so non-streaming callers (and tests) keep the original blocking contract.
    """
    result: SubmissionEvaluation | None = None
    for event in stream_submission_evaluation(
        assignment_title=assignment_title,
        assignment_description=assignment_description,
        content=content,
        filename=filename,
        content_type=content_type,
        llm_complete=llm_complete,
        config=config,
    ):
        if event.type == "complete":
            result = event.data["evaluation"]
    assert result is not None  # the generator always ends with a complete event
    return result


def stream_submission_evaluation(
    *,
    assignment_title: str,
    assignment_description: str | None,
    content: bytes,
    filename: str | None,
    content_type: str | None,
    llm_complete: Callable[[str], str] | None = None,
    llm_stream: Callable[[str], Any] | None = None,
    config: SubmissionAgentConfig | None = None,
):
    """Evaluate a submission while yielding :class:`AgentEvent` progress events.

    The agent reasons in causal steps and emits an event after each one so the
    caller (e.g. an SSE endpoint) can show the work as it happens:
      1. ``inspecting`` / ``inspected`` — open and extract text from the file.
      2. ``understanding`` / ``requirements`` — decompose the assignment into a
         checklist of atomic, checkable requirements.
      3. ``judging`` / ``token`` / ``finding`` — walk the document
         requirement-by-requirement, streaming the raw reasoning tokens as they
         arrive, then judge each with cited evidence and causal reasoning.
      4. ``complete`` — the final :class:`SubmissionEvaluation`.

    If ``llm_stream`` is provided it is used for the verdict step and each token
    chunk is surfaced as a ``token`` event; otherwise ``llm_complete`` is used
    for a single blocking call.
    """
    config = config or SubmissionAgentConfig()

    yield AgentEvent("inspecting", {"message": "Opening and reading the document"})
    file_report, extracted_text = _inspect_and_extract(
        content=content,
        filename=filename,
        content_type=content_type,
        config=config,
    )
    yield AgentEvent(
        "inspected",
        {
            "message": "Document read",
            "filename": file_report["filename"],
            "extension": file_report["extension"],
            "content_type": file_report["content_type"],
            "size_kb": file_report["size_kb"],
            "extraction_method": file_report["extraction_method"],
            "extracted_chars": file_report["extracted_chars"],
            "line_count": file_report["line_count"],
            "archive_entries": file_report["archive_entries"],
            "warnings": file_report["warnings"],
            # Full extracted text (capped) so the UI can show the source document
            # and highlight exactly where each finding's evidence came from.
            "extracted_text": extracted_text[: config.max_llm_chars],
            "extracted_truncated": len(extracted_text) > config.max_llm_chars,
        },
    )

    if file_report["blocking_errors"]:
        evaluation = _reject(
            "REJECTED: We couldn't read your file, so it wasn't evaluated "
            f"(not a judgement of your work). {_friendly_block_reason(file_report)} "
            "Please re-upload as a PDF, DOCX, plain text, source code, or a ZIP "
            "containing those, then flag this if you think it's a mistake.",
            confidence=1.0,
            report={
                "agent": "submission_agent",
                "version": 2,
                "assignment": _assignment_profile(assignment_title, assignment_description),
                "file": file_report,
                "line_review": None,
                "requirements": [],
                "requirement_findings": None,
                "llm": None,
            },
        )
        yield AgentEvent(
            "blocked",
            {
                "message": "We couldn't read this file, so it wasn't evaluated",
                "detail": _friendly_block_reason(file_report),
                "errors": file_report["blocking_errors"],
            },
        )
        yield AgentEvent("complete", {"evaluation": evaluation})
        return

    line_review = _review_lines(
        extracted_text,
        assignment_title=assignment_title,
        assignment_description=assignment_description or "",
    )

    if llm_complete is None:
        from llm.service import get_llm_service

        llm_complete = get_llm_service().complete

    steps: list[dict[str, Any]] = []
    first_error: str | None = None

    # --- Step 1: decompose the assignment into atomic requirements --------------
    yield AgentEvent("understanding", {"message": "Understanding what the assignment asks for"})
    requirements: list[str] = []
    req_prompt = _build_requirement_prompt(
        assignment_title=assignment_title,
        assignment_description=assignment_description or "",
    )
    req_raw = ""
    try:
        req_raw = llm_complete(req_prompt)
    except Exception as exc:  # pragma: no cover - exercised through integration config
        first_error = str(exc)
    req_parsed = _parse_llm_response(req_raw) if req_raw else None
    if isinstance(req_parsed, dict):
        requirements = _normalize_requirements(req_parsed.get("requirements"))
    steps.append(
        {
            "step": "decompose_requirements",
            "raw_response": req_raw[:2000] if req_raw else None,
            "requirements": requirements,
        }
    )
    # Keyword terms are a safety net so step 2 still has structure to anchor on
    # even when the decomposition call returns nothing usable.
    requirements_from_keywords = False
    if not requirements:
        requirements_from_keywords = True
        requirements = [
            f"Submission must address: {term}"
            for term in (line_review.get("assignment_terms") or [])[:8]
        ]
    yield AgentEvent(
        "requirements",
        {
            "message": "Broke the assignment into checkable requirements",
            "requirements": requirements,
            "derived_from": "keywords" if requirements_from_keywords else "assignment",
        },
    )

    # --- Step 2: judge the document against the requirements, then decide -------
    yield AgentEvent(
        "judging",
        {"message": "Checking the document against each requirement", "requirement_count": len(requirements)},
    )
    verdict_prompt = _build_verdict_prompt(
        assignment_title=assignment_title,
        assignment_description=assignment_description or "",
        requirements=requirements,
        file_report=file_report,
        line_review=line_review,
        extracted_text=extracted_text,
        config=config,
    )
    verdict_raw = ""
    try:
        if llm_stream is not None:
            for chunk in llm_stream(verdict_prompt):
                if not chunk:
                    continue
                verdict_raw += chunk
                yield AgentEvent("token", {"text": chunk})
        else:
            verdict_raw = llm_complete(verdict_prompt)
    except Exception as exc:  # pragma: no cover - exercised through integration config
        if first_error is None:
            first_error = str(exc)
    parsed = _parse_llm_response(verdict_raw) if verdict_raw else None
    steps.append(
        {
            "step": "judge_and_decide",
            "raw_response": verdict_raw[:4000] if verdict_raw else None,
            "decided": parsed is not None,
        }
    )

    # Stream each requirement finding so the student sees the causal reasoning land.
    findings = parsed.get("requirement_findings") if isinstance(parsed, dict) else None
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict):
                yield AgentEvent("finding", {"finding": finding})

    if parsed is None:
        parsed = _fallback_decision(line_review, llm_error=first_error)

    decision = _normalize_decision(parsed.get("decision"))
    confidence = _normalize_confidence(parsed.get("confidence"))
    reason = str(parsed.get("reason") or "").strip()
    feedback = f"{decision.upper()}: {reason or _default_reason(decision)}"

    report = {
        "agent": "submission_agent",
        "version": 2,
        "assignment": _assignment_profile(assignment_title, assignment_description),
        "file": file_report,
        "line_review": line_review,
        "requirements": requirements,
        "requirement_findings": parsed.get("requirement_findings"),
        "llm": {
            "parsed": parsed,
            "steps": steps,
            "error": first_error,
        },
    }
    evaluation = SubmissionEvaluation(
        decision=decision,
        feedback=feedback,
        confidence=confidence,
        report=report,
    )
    yield AgentEvent(
        "verdict",
        {"decision": decision, "confidence": confidence, "feedback": feedback},
    )
    yield AgentEvent("complete", {"evaluation": evaluation})


def _assignment_profile(title: str, description: str | None) -> dict[str, Any]:
    requirement_text = "\n".join(part for part in [title, description or ""] if part).strip()
    return {
        "title": title,
        "description": description,
        "keywords": _keywords(requirement_text),
    }


def _inspect_and_extract(
    *,
    content: bytes,
    filename: str | None,
    content_type: str | None,
    config: SubmissionAgentConfig,
) -> tuple[dict[str, Any], str]:
    safe_name = Path(filename or "submission").name
    extension = Path(safe_name).suffix.lower()
    mime = (content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream").lower()
    report: dict[str, Any] = {
        "filename": safe_name,
        "extension": extension,
        "content_type": mime,
        "size_bytes": len(content),
        "size_kb": round(len(content) / 1024, 2),
        "extraction_method": None,
        "extracted_chars": 0,
        "line_count": 0,
        "warnings": [],
        "blocking_errors": [],
        "archive_entries": [],
    }

    if not content:
        report["blocking_errors"].append("file is empty")
        return report, ""
    if len(content) > config.max_file_size:
        report["blocking_errors"].append(
            f"file is too large ({report['size_kb']} KB, max {round(config.max_file_size / 1024, 2)} KB)"
        )
        return report, ""

    if extension not in ALLOWED_EXTENSIONS and not (mime.startswith("text/") or mime in ALLOWED_MIME):
        report["blocking_errors"].append(f"unsupported file type: {extension or mime}")
        return report, ""

    try:
        if extension == ".pdf" or mime == "application/pdf":
            text = _extract_pdf(content)
            report["extraction_method"] = "pdf_text"
        elif extension == ".docx" or "wordprocessingml" in mime:
            text = _extract_docx(content)
            report["extraction_method"] = "docx_paragraphs"
        elif extension == ".zip" or mime in {"application/zip", "application/x-zip-compressed"}:
            text, archive_report = _extract_zip_text(content, config)
            report["archive_entries"] = archive_report["entries"]
            report["warnings"].extend(archive_report["warnings"])
            report["extraction_method"] = "zip_text_members"
        else:
            text = _decode_text(content)
            report["extraction_method"] = "plain_text"
    except Exception as exc:
        report["blocking_errors"].append(f"text extraction failed: {exc}")
        return report, ""

    text = _clean_text(text)
    report["extracted_chars"] = len(text)
    report["line_count"] = len(text.splitlines())
    if not text.strip():
        report["blocking_errors"].append("no readable text could be extracted")
    return report, text


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF extraction dependency pypdf is not installed") from exc

    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("DOCX extraction dependency python-docx is not installed") from exc

    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_zip_text(content: bytes, config: SubmissionAgentConfig) -> tuple[str, dict[str, Any]]:
    report: dict[str, Any] = {"entries": [], "warnings": []}
    text_parts: list[str] = []
    total_text_bytes = 0
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        if len(members) > config.max_zip_members:
            raise RuntimeError(f"archive has too many files ({len(members)}, max {config.max_zip_members})")

        for info in members:
            path = info.filename
            name = Path(path).name
            ext = Path(name).suffix.lower()
            entry = {
                "path": path,
                "size_bytes": info.file_size,
                "read": False,
                "reason": None,
            }
            if path.startswith("__MACOSX/") or name == ".DS_Store" or name.startswith("._"):
                entry["reason"] = "skipped archive metadata"
                report["entries"].append(entry)
                continue
            # Only skip outright on extensions we KNOW are binary. For anything
            # else (including unknown extensions and extensionless files) we try
            # to decode it and let the binary-content check below be the judge —
            # so a .tex, a Makefile, a README without extension, etc. still read.
            if ext in BINARY_EXTENSIONS:
                entry["reason"] = "skipped non-text file"
                report["entries"].append(entry)
                continue
            if info.file_size > config.max_single_zip_member_bytes:
                entry["reason"] = "skipped large file"
                report["entries"].append(entry)
                continue
            if total_text_bytes + info.file_size > config.max_zip_text_bytes:
                entry["reason"] = "skipped because archive text limit was reached"
                report["entries"].append(entry)
                continue

            with archive.open(info) as fh:
                member_text = _decode_text(fh.read())
            if _looks_binary_text(member_text):
                entry["reason"] = "skipped binary file"
                report["entries"].append(entry)
                continue
            if not member_text.strip():
                entry["reason"] = "skipped empty file"
                report["entries"].append(entry)
                continue
            total_text_bytes += info.file_size
            entry["read"] = True
            report["entries"].append(entry)
            text_parts.append(f"\n--- FILE: {path} ---\n{member_text}")

    if not text_parts:
        report["warnings"].append("archive did not contain any readable text files")
    return "\n".join(text_parts), report


def _friendly_block_reason(file_report: dict[str, Any]) -> str:
    """Translate raw blocking errors into a clear, human explanation."""
    errors = file_report.get("blocking_errors") or []
    joined = "; ".join(errors)
    if any("no readable text" in e for e in errors):
        entries = file_report.get("archive_entries") or []
        if entries:
            skipped = [e["path"] for e in entries if not e.get("read")]
            if skipped:
                preview = ", ".join(skipped[:5])
                return (
                    "The archive only contained files we couldn't read as text "
                    f"(e.g. {preview}). If your work is in images or another binary "
                    "format, export it to text or PDF first."
                )
        return "No readable text could be extracted from the file."
    if any("empty" in e for e in errors):
        return "The file appears to be empty."
    if any("too large" in e for e in errors):
        return joined.capitalize() + "."
    if any("unsupported file type" in e for e in errors):
        return joined.capitalize() + "."
    return joined.capitalize() + "." if joined else "The file could not be read."


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\r\n?", "\n", text)
    return text.strip()


def _looks_binary_text(text: str) -> bool:
    sample = text[:2000]
    if not sample:
        return False
    control_chars = sum(
        1 for char in sample
        if ord(char) < 32 and char not in "\n\r\t"
    )
    return control_chars / max(1, len(sample)) > 0.08


def _review_lines(
    text: str,
    *,
    assignment_title: str,
    assignment_description: str,
) -> dict[str, Any]:
    lines = text.splitlines()
    non_empty = [(idx + 1, line.strip()) for idx, line in enumerate(lines) if line.strip()]
    terms = _keywords(f"{assignment_title}\n{assignment_description}")
    term_hits: dict[str, list[int]] = {term: [] for term in terms}
    scored: list[tuple[int, int, str, list[str]]] = []

    for line_no, line in non_empty:
        lower = line.lower()
        matched = [term for term in terms if term in lower]
        for term in matched:
            if len(term_hits[term]) < 12:
                term_hits[term].append(line_no)
        if matched:
            scored.append((len(matched), line_no, line[:400], matched))

    scored.sort(key=lambda item: (-item[0], item[1]))
    evidence = [
        {
            "line": line_no,
            "text": line,
            "matched_terms": matched[:8],
        }
        for _, line_no, line, matched in scored[:30]
    ]

    headings = [
        {"line": line_no, "text": line[:180]}
        for line_no, line in non_empty
        if _looks_like_heading(line)
    ][:30]
    first_lines = [{"line": line_no, "text": line[:240]} for line_no, line in non_empty[:20]]
    last_lines = [{"line": line_no, "text": line[:240]} for line_no, line in non_empty[-10:]]

    return {
        "total_lines": len(lines),
        "non_empty_lines": len(non_empty),
        "assignment_terms": terms,
        "term_hit_counts": {term: len(hits) for term, hits in term_hits.items()},
        "term_hit_lines": {term: hits for term, hits in term_hits.items() if hits},
        "heading_candidates": headings,
        "first_lines": first_lines,
        "last_lines": last_lines,
        "evidence_lines": evidence,
    }


def _build_requirement_prompt(
    *,
    assignment_title: str,
    assignment_description: str,
) -> str:
    return f"""You are the planning step of a university assignment evaluation agent.

Read the assignment and break it into a checklist of discrete, atomic requirements
a real submission would have to satisfy. Capture both the topic ("what it must be
about") and any concrete deliverables ("what artifacts/sections it must contain").
Keep each requirement short and independently checkable. Do not invent requirements
that the assignment does not state or clearly imply.

Assignment title:
{assignment_title}

Assignment description:
{assignment_description or "No description provided."}

Respond with only valid JSON in this exact shape:
{{
  "requirements": [
    "first atomic requirement",
    "second atomic requirement"
  ]
}}
"""


def _build_verdict_prompt(
    *,
    assignment_title: str,
    assignment_description: str,
    requirements: list[str],
    file_report: dict[str, Any],
    line_review: dict[str, Any],
    extracted_text: str,
    config: SubmissionAgentConfig,
) -> str:
    clipped_text = extracted_text[: config.max_llm_chars]
    return f"""You are a university assignment submission evaluation agent.

You are given a checklist of requirements that was already derived from the
assignment. Reason causally and requirement-by-requirement:
1. For EACH requirement, search the submitted document for concrete evidence
   that it is or is not satisfied. Quote or cite the line that supports your call.
2. Explain WHY that evidence does or does not satisfy the requirement (the causal
   link between what the assignment asks and what the document actually contains).
3. Only after walking every requirement, synthesize one overall decision.

Approve when the document is a genuine attempt that addresses the core requirements.
Reject when it is unrelated, empty, placeholder-only, unreadable, or for another task.
Do not grade quality, and do not reject solely for being incomplete unless it is too
thin to be a real submission. Return concise reasoning summaries, not hidden
chain-of-thought.

Assignment title:
{assignment_title}

Assignment description:
{assignment_description or "No description provided."}

Requirement checklist JSON:
{json.dumps(requirements, ensure_ascii=False)}

File profile JSON:
{json.dumps(file_report, ensure_ascii=False)}

Line-by-line review JSON:
{json.dumps(line_review, ensure_ascii=False)}

Extracted submission text, clipped if long:
{clipped_text}

Respond with only valid JSON in this exact shape:
{{
  "decision": "approved",
  "confidence": 0.0,
  "reason": "one or two sentence reason for the student",
  "assignment_understanding": "short summary of what the assignment asks for",
  "submission_summary": "short summary of what the student submitted",
  "requirement_findings": [
    {{
      "requirement": "the requirement being checked",
      "satisfied": true,
      "evidence_line": 1,
      "evidence": "short quote or paraphrase from the document",
      "reasoning": "why this evidence does or does not satisfy the requirement"
    }}
  ],
  "evidence": [
    {{"line": 1, "quote": "short quote or paraphrase", "why_it_matters": "short explanation"}}
  ],
  "missing_requirements": ["important missing or mismatched requirement, if any"],
  "flags": ["notable file/content issues, if any"]
}}
"""


def _parse_llm_response(raw_response: str) -> dict[str, Any] | None:
    text = raw_response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            text = match.group(0)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _fallback_decision(line_review: dict[str, Any], *, llm_error: str | None) -> dict[str, Any]:
    hit_counts = line_review.get("term_hit_counts") or {}
    total_hits = sum(int(v) for v in hit_counts.values())
    matched_terms = sum(1 for v in hit_counts.values() if int(v) > 0)
    terms = len(line_review.get("assignment_terms") or [])
    if total_hits >= 4 and matched_terms >= max(1, min(3, terms // 3)):
        return {
            "decision": "approved",
            "confidence": 0.55,
            "reason": "The submission contains repeated evidence matching the assignment topic, but the AI evaluator response could not be parsed.",
            "flags": ["fallback_keyword_review", llm_error] if llm_error else ["fallback_keyword_review"],
        }
    return {
        "decision": "rejected",
        "confidence": 0.65,
        "reason": "The submission could not be confidently matched to the assignment requirements.",
        "flags": ["fallback_keyword_review", llm_error] if llm_error else ["fallback_keyword_review"],
    }


def _reject(feedback: str, *, confidence: float, report: dict[str, Any]) -> SubmissionEvaluation:
    return SubmissionEvaluation(
        decision="rejected",
        feedback=feedback,
        confidence=confidence,
        report=report,
    )


def _normalize_requirements(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    requirements: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("requirement") or item.get("text") or "").strip()
        else:
            text = str(item).strip()
        if text and text not in requirements:
            requirements.append(text)
        if len(requirements) >= 20:
            break
    return requirements


def _normalize_decision(value: Any) -> Decision:
    decision = str(value or "").strip().lower()
    return "approved" if decision == "approved" else "rejected"


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    if confidence > 1:
        confidence = confidence / 100
    return max(0.0, min(1.0, confidence))


def _default_reason(decision: Decision) -> str:
    if decision == "approved":
        return "The submission appears relevant to the assignment."
    return "The submission does not appear relevant enough to the assignment."


def _keywords(text: str, limit: int = 24) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{3,}", text.lower())
    counts = Counter(token for token in tokens if token not in STOPWORDS)
    return [token for token, _ in counts.most_common(limit)]


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 140:
        return False
    if stripped.startswith(("#", "##")):
        return True
    if stripped.endswith(":"):
        return True
    alpha = [char for char in stripped if char.isalpha()]
    if alpha and sum(1 for char in alpha if char.isupper()) / len(alpha) > 0.75:
        return True
    return False
