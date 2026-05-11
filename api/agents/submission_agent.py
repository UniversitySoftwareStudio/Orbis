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
}
DOCUMENT_EXTENSIONS = {".pdf", ".docx"}
ARCHIVE_EXTENSIONS = {".zip"}
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS | ARCHIVE_EXTENSIONS

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
    config = config or SubmissionAgentConfig()
    file_report, extracted_text = _inspect_and_extract(
        content=content,
        filename=filename,
        content_type=content_type,
        config=config,
    )
    if file_report["blocking_errors"]:
        return _reject(
            "REJECTED: The file could not be evaluated: "
            + "; ".join(file_report["blocking_errors"]),
            confidence=1.0,
            report={
                "agent": "submission_agent",
                "version": 1,
                "assignment": _assignment_profile(assignment_title, assignment_description),
                "file": file_report,
                "line_review": None,
                "llm": None,
            },
        )

    line_review = _review_lines(
        extracted_text,
        assignment_title=assignment_title,
        assignment_description=assignment_description or "",
    )
    prompt = _build_prompt(
        assignment_title=assignment_title,
        assignment_description=assignment_description or "",
        file_report=file_report,
        line_review=line_review,
        extracted_text=extracted_text,
        config=config,
    )
    raw_response = ""
    llm_error = None
    try:
        if llm_complete is None:
            from llm.service import get_llm_service

            raw_response = get_llm_service().complete(prompt)
        else:
            raw_response = llm_complete(prompt)
    except Exception as exc:  # pragma: no cover - exercised through integration config
        llm_error = str(exc)

    parsed = _parse_llm_response(raw_response) if raw_response else None
    if parsed is None:
        parsed = _fallback_decision(
            line_review,
            llm_error=llm_error,
        )

    decision = _normalize_decision(parsed.get("decision"))
    confidence = _normalize_confidence(parsed.get("confidence"))
    reason = str(parsed.get("reason") or "").strip()
    feedback = f"{decision.upper()}: {reason or _default_reason(decision)}"

    report = {
        "agent": "submission_agent",
        "version": 1,
        "assignment": _assignment_profile(assignment_title, assignment_description),
        "file": file_report,
        "line_review": line_review,
        "llm": {
            "parsed": parsed,
            "raw_response": raw_response[:4000] if raw_response else None,
            "error": llm_error,
        },
    }
    return SubmissionEvaluation(
        decision=decision,
        feedback=feedback,
        confidence=confidence,
        report=report,
    )


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
            if ext not in TEXT_EXTENSIONS:
                entry["reason"] = "skipped non-text file"
                report["entries"].append(entry)
                continue
            if info.file_size > config.max_single_zip_member_bytes:
                entry["reason"] = "skipped large text file"
                report["entries"].append(entry)
                continue
            if total_text_bytes + info.file_size > config.max_zip_text_bytes:
                entry["reason"] = "skipped because archive text limit was reached"
                report["entries"].append(entry)
                continue

            with archive.open(info) as fh:
                member_text = _decode_text(fh.read())
            if _looks_binary_text(member_text):
                entry["reason"] = "skipped binary-looking text"
                report["entries"].append(entry)
                continue
            total_text_bytes += info.file_size
            entry["read"] = True
            report["entries"].append(entry)
            text_parts.append(f"\n--- FILE: {path} ---\n{member_text}")

    if not text_parts:
        report["warnings"].append("archive did not contain readable supported text files")
    return "\n".join(text_parts), report


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


def _build_prompt(
    *,
    assignment_title: str,
    assignment_description: str,
    file_report: dict[str, Any],
    line_review: dict[str, Any],
    extracted_text: str,
    config: SubmissionAgentConfig,
) -> str:
    clipped_text = extracted_text[: config.max_llm_chars]
    return f"""You are a university assignment submission evaluation agent.

Your job:
1. Understand the assignment requirement from the title and description.
2. Inspect the submitted document evidence.
3. Decide whether the document is genuinely relevant to the assignment.

Approve only when the submission appears to be a real attempt for this assignment.
Reject when it is unrelated, empty, placeholder-only, unreadable, or clearly for another task.
Do not grade quality. Do not reject merely because it may be incomplete unless it is too thin to be a real submission.
Return concise reasoning summaries, not hidden chain-of-thought.

Assignment title:
{assignment_title}

Assignment description:
{assignment_description or "No description provided."}

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
