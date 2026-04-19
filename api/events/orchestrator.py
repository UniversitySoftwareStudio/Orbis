"""Regulation rule extraction pipeline.

Flow per document:
  1. Load chunks from KB by doc_ids (from step 12 regulation tree)
  2. Pass 1 — LLM extracts structured rules from the full document text
  3. Pass 2 — LLM reviews the extracted rules against the original text (adversarial)
  4. Persist accepted rules to regulation_rules with full traceability
  5. Log every step to event_agent_logs for auditability

Each pipeline run is recorded in event_runs.
Every document processed is logged in event_source_logs.
Every rule candidate (accepted or rejected) is logged in event_candidate_logs.
"""
from __future__ import annotations

import difflib
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as date_cls, datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import (
    EventAgent,
    EventAgentLog,
    EventCandidateDecision,
    EventCandidateLog,
    EventRun,
    EventRunStatus,
    EventSourceLog,
    EventSourceStatus,
    RegulationRule,
    RuleMatchType,
    RuleStatus,
    EventTargetRole,
)
from embedding.service import get_embedding_service
from events.utils import hash_text, normalize_text

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# LLM caller — same Outlier proxy pattern used across all experiment scripts
# ---------------------------------------------------------------------------

def _call_llm(
    *,
    url: str,
    model: str,
    system: str,
    prompt: str,
    timeout: float,
) -> tuple[Any, str | None]:
    endpoint = url.rstrip("/") + "/chat/stream"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "systemMessage": system,
    }
    body = json.dumps(payload).encode()
    req = urlrequest.Request(
        endpoint, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            raw_stream = r.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return None, f"connection_error: {exc}"

    parts: list[str] = []
    for line in raw_stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if isinstance(ev, dict) and isinstance(ev.get("error"), str) and ev["error"].strip():
            return None, f"stream_error: {ev['error']}"
        msg = ev.get("message", {}) if isinstance(ev, dict) else {}
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            c = str(msg.get("content", ""))
            if c:
                parts.append(c)

    raw = "".join(parts).strip()
    # try to parse JSON
    try:
        obj = json.loads(raw)
        return obj, None
    except Exception:
        pass
    # find first [ or {
    for ch in ("[", "{"):
        idx = raw.find(ch)
        if idx >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(raw[idx:])
                return obj, None
            except Exception:
                pass
    return None, f"malformed_json: {raw[:300]}"


def _is_retryable_llm_error(err: str | None) -> bool:
    if not err:
        return False
    lowered = err.lower()
    return any(token in lowered for token in (
        "connection_error",
        "stream_error",
        "status code 500",
        "status code 502",
        "status code 503",
        "status code 504",
        "timed out",
        "timeout",
        "malformed_json:",
    ))


def _call_llm_with_retry(
    *,
    url: str,
    model: str,
    system: str,
    prompt: str,
    timeout: float,
    attempts: int = 4,
    initial_sleep_s: float = 2.0,
) -> tuple[Any, str | None]:
    last_obj: Any = None
    last_err: str | None = None
    sleep_s = initial_sleep_s

    for attempt in range(1, attempts + 1):
        obj, err = _call_llm(
            url=url,
            model=model,
            system=system,
            prompt=prompt,
            timeout=timeout,
        )
        last_obj, last_err = obj, err
        if not err:
            return obj, None
        if attempt >= attempts or not _is_retryable_llm_error(err):
            break
        wait_s = sleep_s
        lowered = err.lower()
        if "429" in lowered or "too many requests" in lowered:
            wait_s = max(wait_s, 8.0)
        time.sleep(wait_s)
        sleep_s = max(sleep_s * 2, wait_s)

    return last_obj, last_err


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM = (
    "You are an extraction engine for Istanbul Bilgi University. "
    "You do NOT output legal clauses or policy summaries. "
    "You output notification-ready actionable suggestions that the university can proactively show to a student, staff member, or admin. "
    "Every item must tell a real person what to do, avoid, prepare, verify, or expect. "
    "You must judge whether each item is still relevant as of the provided current date. "
    "Do not output stale one-time announcements or expired application windows unless the document clearly states an ongoing recurring obligation that still applies. "
    "ALL output fields except evidence_quote MUST be in English, even if the source document is Turkish. "
    "evidence_quote is the ONLY field that may stay in the original document language. "
    "Never invent facts, deadlines, offices, consequences, channels, exam names, document names, equivalent-score options, or tactical advice. Everything must be traceable to the document. "
    "Do not add motivational or optimization language. Rewrite only what the document actually supports. "
    "Return only valid JSON. No markdown. No explanation."
)

PASS1_PROMPT = """ACTIONABLE SUGGESTION EXTRACTION TASK — Istanbul Bilgi University

CURRENT DATE: {current_date}
DOCUMENT TITLE: {title}
DOCUMENT TYPE: {document_type}
DOCUMENT URL: {url}
DOCUMENT TEXT:
{text}

===========================
CORE MISSION
You are not extracting "rules" in the legal sense.
You are converting regulation text into high-signal actionable suggestions that could be shown directly to a person as a proactive alert or reminder.

Think of the final product as something like:
  - "Apply now ..."
  - "Submit ..."
  - "Do not assume ..."
  - "Check your GPA before registration ..."
  - "Prepare ..."

If an item would sound weak, abstract, or overly legal as a notification, do not output it.
If, after reading the item, the recipient would still ask "Does this really apply to me?", "When exactly do I need to act?", or "What exactly should I do now?", do not output it.
===========================

===========================
TEMPORAL VALIDITY
Judge every item against CURRENT DATE: {current_date}

Keep an item ONLY if it is still useful and actionable as of the current date.

DROP items that are clearly historical or expired, such as:
  - past application windows
  - past deadlines
  - one-off announcements for a past academic year
  - reminders tied to an already-finished event

KEEP items that are evergreen or still active, such as:
  - standing eligibility thresholds
  - ongoing prohibitions or restrictions
  - continuing obligations under a regulation
  - recurring duties that are not limited to a past one-time window

If a document is old but the rule is structurally ongoing, keep it.
If a document is old and the action window has clearly passed, drop it.
Never treat an expired deadline as currently actionable.
If the document is a dated news post, announcement, campaign page, or academic-year notice, assume its instructions are scoped to that notice unless the text clearly states a continuing standing policy.
Do NOT promote generic instructions from an expired announcement into an evergreen rule unless the document explicitly supports that interpretation.
===========================

===========================
DOCUMENT TYPE HANDLING
You are given DOCUMENT TYPE explicitly.

If DOCUMENT TYPE is "announcement":
  - treat the page as cycle-scoped by default
  - assume it is about a specific academic year / application cycle / one-time notice unless the text clearly says otherwise
  - if the cycle has expired before CURRENT DATE, default to returning []

If DOCUMENT TYPE is "form_template":
  - default to returning []
  - do NOT extract from blank fields, labels, headers, signature areas, notes, or explanatory footnotes attached to the form
  - only extract if the document contains a clearly separate, standing policy instruction that would still matter even outside the act of filling out this form
  - most form_template documents should produce no output

If DOCUMENT TYPE is "regulation":
  - apply the normal extraction rules below
===========================

===========================
OUTPUT LANGUAGE: ENGLISH ONLY
All fields you write — rule_text, applies_to, trigger, deadline, valid_from, valid_until, consequence, authority, exceptions — MUST be in English.
This is mandatory even if the document is entirely Turkish.
Only evidence_quote may remain in the original document language.
===========================

PHASE 1 — UNDERSTAND THE DOCUMENT BEFORE WRITING
Identify all of the following silently:
1. What exact regulation, directive, policy, form, or announcement is this?
2. Who is affected?
3. What real-world action or restriction matters to that person?
4. What event or trigger makes that action relevant?
5. What office, faculty, or authority is responsible?
6. What happens if the person ignores it, misses it, or fails the requirement?

You must carry this context into the output. The final item must make sense to a person with zero prior knowledge.

===========================

FAITHFULNESS OVERRIDES STYLE
Sharper wording is good only when it stays faithful.
If the document states only an eligibility requirement, permission, or consequence, your rewrite must stay inside that boundary.

WRONG:
  "Pass the English language proficiency requirement and contact your faculty to arrange the assessment promptly."
BETTER:
  "Meet the English language proficiency requirement before starting the Undergraduate Preparation Program."

WRONG:
  "Your GPA at Istanbul Bilgi University is calculated only from Bilgi courses. Every course grade you earn from the first semester counts toward your cumulative GPA."
BETTER:
  "Plan your GPA expectations around Bilgi coursework only; prior associate-degree grades do not carry over."

WRONG:
  "Add upper-semester courses during registration to accelerate your progress."
BETTER:
  "Add eligible upper-semester courses during registration if the credit-load rules allow it."

If a stronger rewrite would require adding an exam, office, workflow step, submission channel, benefit, or strategy that is not explicitly supported by the document, do not add it.
===========================

PHASE 2 — EXTRACTION GATE
Extract an item ONLY if ALL of these are true:
1. A specific person can act on it, prepare for it, avoid a mistake because of it, or verify eligibility because of it.
2. The content matters enough that the university could reasonably notify someone about it.
3. The content is traceable to an exact sentence or sentences in the document.
4. The content is still relevant as of CURRENT DATE, or is an evergreen rule with continuing force.

If any of these are false, do not extract it.

HIGH-VALUE ITEMS THAT SHOULD USUALLY BE EXTRACTED IF PRESENT:
  - course registration or advisor approval steps
  - transfer, exemption, adaptation, or recognition procedures that require student action
  - accommodation or support requests with a concrete submission step
  - document / form / petition submissions required as part of a real student workflow
  - eligibility checks that materially change what the student can do next
  - appeal, objection, make-up, additional exam, or continuation rights with a concrete trigger
  - recurring semester-based obligations inside a program, even if they are not tied to a one-off calendar date

These are NOT "generic awareness" items if they tell a clearly scoped student what they need to do in a specific university process.

STRICTLY FORBIDDEN OUTPUT:
  - Definitions
  - Purpose statements
  - Historical background
  - Organizational descriptions
  - What a committee, board, jury, or office does internally
  - Staff confidentiality/process obligations that are not a real alert-worthy action for the target person
  - Blank forms, headings, signatures, or template structure
  - Generic awareness items with no clear action, restriction, eligibility implication, or consequence
  - Generic conduct warnings that apply to everyone all the time with no concrete trigger, decision point, deadline, or situational relevance
  - Campus-wide "do not do bad thing X" reminders that are always true and are not tied to a specific student state, workflow, submission, eligibility check, deadline, or process stage

===========================

PHASE 3 — CONSOLIDATE HARD
One output item must represent ONE notification-worthy action or eligibility checkpoint.

If several requirements belong to the same action, merge them into one item.

WRONG:
  - "Poster must be A3."
  - "Poster must be in English."
  - "Poster must include the project title."

CORRECT:
  - "Prepare one final A3 poster in English and include the project title, Istanbul Bilgi University logos, the department name, and the company name if applicable before the jury presentation."

Merge items whenever they share the same target person, trigger, deadline, and real-world action.
Split items only when they have genuinely different triggers, deadlines, or actions.

===========================

PHASE 4 — WRITE NOTIFICATION-READY OUTPUT
For each extracted item, fill these fields:

rule_text (ENGLISH, required):
  This is the user-facing actionable suggestion.
  Write it as a direct recommendation or instruction, not as legal prose.
  Start with a strong verb whenever possible: Apply, Submit, Upload, Prepare, Check, Meet, Do not, Complete, Contact, Register, Renew.
  The best outputs read like an immediate next step the recipient can take now.
  Keep it concise and strong. Usually 1 sentence, optionally 2 if a consequence is essential.
  Do NOT start with "As a student..." or "Students must..." unless there is no better wording.
  Do NOT start with weak openers like "Be aware", "Know that", "Expect", "Remember", or "Note that".
  Do NOT start with weak advisory phrasing like "Consider...", "Take advantage of...", or "You should be aware...".
  Do NOT sound like a regulation clause.

  WRONG:
    "As an associate degree or undergraduate student at Istanbul Bilgi University applying for a need-based scholarship, you must submit your application online through the official university system within the announced application period and upload the required supporting documents."

  BETTER:
    "Apply for need-based scholarship support through the official Istanbul Bilgi University online system during the announced application window and upload all required supporting documents."

  WRONG:
    "Students with a GPA below 2.00 cannot take the graduation project course."

  BETTER:
    "Check your cumulative GPA before registration; you can take the Graduation Design Project course only if your GPA meets the required threshold."

  WRONG:
    "Pass the English language proficiency requirement and contact the relevant office to take the assessment."

  BETTER:
    "Meet the English language proficiency requirement before starting the Undergraduate Preparation Program."

  WRONG:
    "When registering for courses, you may also select upper-semester courses."

  BETTER:
    "Add eligible upper-semester courses during registration if the credit-load rules allow it."

  WRONG:
    "Your GPA will be calculated only from Bilgi courses."

  BETTER:
    "Plan your GPA expectations around Bilgi coursework only; prior associate-degree grades do not carry over."

  WRONG:
    "Need-based scholarships do not cover summer school."

  BETTER:
    "Do not rely on your need-based scholarship to cover summer school; plan summer funding separately."

  VERY IMPORTANT:
  If the source text states a condition or consequence instead of a direct command, rewrite it into the clearest faithful action-oriented guidance for the affected person.
  You may convert:
    - eligibility statements -> "Check / make sure / you can only ..."
    - prohibitions -> "Do not ..."
    - consequence statements -> "Do not assume ... / make sure ..."
  But you must NOT invent new steps, offices, or deadlines.
  You must NOT add tactical advice, motivational framing, optimization language, or concrete methods that the document does not explicitly state.
  Bad additions include things like:
    - naming an exam or submission method that is not in the quote
    - saying "promptly", "proactively", "to accelerate your progress", or "perform well from your first courses"
    - turning a permission into coaching language like "take advantage of your right"
    - adding "contact the relevant office", "submit an equivalent score", or similar operational details unless explicitly stated
  If the document only says a person "may" do something, keep it ONLY if it changes a real student decision. Rewrite it as a concrete decision-point instruction using only document-supported content.
  If the only possible output would still feel generic after rewriting, drop it instead.

applies_to (ENGLISH, required):
  Precisely define the audience.
  Include program level, faculty/department if stated, and student/staff type if relevant.
  This field carries the scope and institutional context that rule_text does not need to repeat.

  WRONG: "students"
  WRONG: "undergraduate students"
  CORRECT: "undergraduate students at Istanbul Bilgi University applying for need-based scholarship support"
  CORRECT: "undergraduate students in the Faculty of Engineering at Istanbul Bilgi University preparing for the Graduation Design Project jury"

evidence_quote (original document language, required):
  Copy the exact supporting sentence or sentences from the document. Do not translate. Do not paraphrase.

trigger (ENGLISH, required):
  This is the trigger for relevance.
  Write when or why this suggestion matters right now.
  Phrase it as a concrete trigger, not as a vague summary.
  A semester stage, process stage, or administrative workflow moment is acceptable if it clearly tells the recipient when the item matters.

  WRONG: "if GPA < 2.00"
  BETTER: "when the student attempts to register for the Graduation Design Project course and eligibility depends on cumulative GPA"
  BETTER: "when the annual need-based scholarship application window is open"
  BETTER: "when the student is preparing a vertical transfer application"
  BETTER: "when the student enters the course registration period and advisor approval is required"
  BAD: "when on campus"
  BAD: "when participating in any activity"
  BAD: "when sitting any examination"
  GOOD: "when the student is about to sit a make-up exam after receiving additional exam rights"
  GOOD: "when the student reaches Week 13 of the Graduation Design Project semester"

deadline (ENGLISH, or null):
  The exact time window, submission deadline, semester moment, or process stage when the action must be completed.

valid_from (ENGLISH date in YYYY-MM-DD, or null):
  Fill this only when the document gives a specific calendar date after which this action becomes active.
  If the action is evergreen or the date is not explicit, use null.

valid_until (ENGLISH date in YYYY-MM-DD, or null):
  Fill this only when the document gives a specific calendar date after which this action stops being valid.
  If the action is evergreen or the end date is not explicit, use null.

blocking (required boolean):
  Write true when ignoring or failing this action blocks the person's next academic or administrative step.
  Write false otherwise.

consequence (ENGLISH, or null):
  State the direct consequence if the person ignores the action, misses the deadline, or fails the requirement.
  Do not invent consequences.

authority (ENGLISH, or null):
  The office, faculty, board, coordinator, or unit responsible for this requirement.

exceptions (ENGLISH, or null):
  Any stated exception, exemption, or carve-out from the document.

target_role:
  Must be exactly one of: "student" | "staff" | "admin" | "all"

match_type:
  Write "sql" ONLY when the suggestion can be triggered entirely and directly from one or more of these database fields:
    - gpa
    - enrolled_credits
    - is_active
  Otherwise write "contextual".

sql_condition:
  Fill this ONLY when match_type is "sql".
  It must be a valid Python boolean expression using ONLY:
    gpa, enrolled_credits, is_active

  Valid examples:
    "gpa >= 2.00"
    "gpa < 1.80"
    "enrolled_credits < 12"
    "is_active == False"

  If any other field would be needed, use "contextual" and set sql_condition to null.

confidence:
  Must be one of exactly: "explicit" | "inferred" | "ambiguous"

===========================

PHASE 5 — FINAL SELF-CHECK
Drop the item if ANY of these are true:
  - It is not strong enough to send as a university notification
  - It does not tell the person what to do, avoid, check, prepare, or expect
  - It is mainly awareness-only instead of a concrete next step
  - It is just a legal clause rewritten in English
  - It is only institutional workflow with no meaningful action for the recipient
  - It is tied to a past one-time date, deadline, or application window that has already expired before CURRENT DATE
  - It is a past academic-year announcement with no evidence that it still applies
  - It comes from an expired announcement or news page and the supposed continuing rule is only an inference, not clearly stated
  - It is too generic about the audience
  - It is a generic always-on warning for everyone with no concrete trigger or decision point
  - The trigger is too broad to be useful, such as "when on campus", "when participating in activities", or other always-on situations
  - The item does not fully answer: who exactly, what exact action, and when exactly it matters
  - It comes from a form_template and is really just form guidance, labels, or attached notes
  - It is a micro-rule that should have been merged into a bigger action
  - It is duplicated elsewhere in your own output
  - It is not fully supported by evidence_quote
  - Any output field other than evidence_quote is in Turkish
  - trigger is missing
  - blocking is missing
  - the item has an obvious consequence in the document but consequence is omitted
  - valid_from or valid_until is not in YYYY-MM-DD format

===========================

Return a JSON array. No markdown. No explanation.
[
  {{
    "rule_text": "...",
    "evidence_quote": "...",
    "applies_to": "...",
    "trigger": "...",
    "deadline": "..." or null,
    "valid_from": null,
    "valid_until": null,
    "blocking": false,
    "consequence": null,
    "authority": "..." or null,
    "exceptions": "..." or null,
    "target_role": "student",
    "match_type": "contextual",
    "sql_condition": null,
    "confidence": "explicit"
  }}
]"""


PASS2_PROMPT = """ACTIONABLE SUGGESTION REVIEW TASK — Istanbul Bilgi University

CURRENT DATE: {current_date}
DOCUMENT TITLE: {title}
DOCUMENT TYPE: {document_type}
DOCUMENT URL: {url}
DOCUMENT TEXT:
{text}

EXTRACTED ITEMS:
{rules}

===========================
OUTPUT LANGUAGE: ENGLISH ONLY
All fields except evidence_quote must be in English.
evidence_quote is the only field that may remain in the original document language.
===========================

YOUR JOB
Review every extracted item and decide: keep, fix, or remove.
Then find any important actionable suggestions that were missed.

The standard is NOT "is this a valid clause?"
The standard is:
  "Could Istanbul Bilgi University proactively show this item to the right person as a useful action reminder, warning, eligibility check, or preparation tip?"
If the recipient would still need follow-up questions to understand whether it applies, when it matters, or what to do, it is not good enough.
Recurring procedural student tasks are valid if they clearly specify the workflow moment and next step.

The item must also be temporally valid as of CURRENT DATE: {current_date}.
Remove or fix any item that is stale, historical-only, or tied to an already-expired one-time window.
If the source is a dated announcement or news page, treat its instructions as cycle-scoped by default unless the document clearly states a continuing standing policy.
If DOCUMENT TYPE is "form_template", heavily prefer removal; most forms should produce no actionable suggestions.

FAITHFULNESS OVERRIDES STYLE
When you fix wording, you are allowed to sharpen the action but not to add new operational details.
If the document states only an eligibility requirement, permission, or consequence, keep your rewrite inside that boundary.

WRONG FIX:
  "Pass the English language proficiency requirement and contact your faculty to arrange the assessment promptly."
BETTER FIX:
  "Meet the English language proficiency requirement before starting the Undergraduate Preparation Program."

WRONG FIX:
  "Your GPA at Istanbul Bilgi University is calculated only from Bilgi courses. Every course grade you earn from the first semester counts toward your cumulative GPA."
BETTER FIX:
  "Plan your GPA expectations around Bilgi coursework only; prior associate-degree grades do not carry over."

WRONG FIX:
  "Add upper-semester courses during registration to accelerate your progress."
BETTER FIX:
  "Add eligible upper-semester courses during registration if the credit-load rules allow it."

If a fix would require adding an exam, office, assessment step, submission channel, benefit, or strategy that is not explicitly supported by the document, do not add it.

DECISION RULES

"keep" only if ALL are true:
  - rule_text is strong, concise, and notification-ready
  - rule_text tells the person what to do, avoid, check, prepare, or expect
  - rule_text reads like a concrete next step, not just awareness
  - rule_text is English and does not read like raw legal prose
  - applies_to is specific and properly scoped
  - trigger is concrete enough that the recipient can tell when this matters
  - blocking is present and defensible from the document
  - valid_from / valid_until are null or valid YYYY-MM-DD dates
  - evidence_quote is traceable to the document
  - the item is not a duplicate
  - the item is not only internal administrative workflow
  - the item is still relevant as of CURRENT DATE or is an evergreen ongoing rule
  - the item is not just generic conduct advice for everyone with no concrete trigger
  - if DOCUMENT TYPE is "form_template", the item is truly a standing policy rather than form guidance
  - recurring process obligations are allowed when they clearly specify the student workflow stage and required action

"fix" if the underlying item is valid but the presentation is weak or incomplete. Fix it in fixed_rule.
Use "fix" for cases like:
  - rule_text is too soft, passive, or regulation-like -> rewrite as a direct actionable suggestion
  - rule_text starts with "Be aware", "Know that", "Expect", or similar weak wording -> rewrite as a concrete next step
  - rule_text starts with "Consider", "Take advantage of", or another advisory/rights-marketing phrase -> rewrite as a direct decision-point instruction or remove it
  - rule_text starts with "As a student..." and can be made sharper
  - rule_text is in Turkish -> translate to English
  - applies_to is too broad -> narrow it
  - trigger is vague -> rewrite it as a clear trigger
  - blocking is missing or wrong -> fix it
  - consequence is recoverable from the document -> add it
  - valid_from or valid_until is explicitly stated in the document -> add it in YYYY-MM-DD format
  - deadline or authority is recoverable from the document
  - two or more items are micro-rules for the same action -> merge them into one fixed_rule
  - the source gives only a restriction/eligibility/consequence and the wording should be converted into direct guidance
  - the core rule is evergreen but the wording incorrectly focuses on an expired historical date -> rewrite it as the continuing obligation only if the document supports that
  - the underlying item is a valid recurring administrative or academic workflow step, but its trigger or next step is not stated concretely enough
  - BUT you must not add exam names, equivalent-score options, filing channels, motivational advice, strategic tips, or benefits unless the document explicitly states them

"remove" if ANY are true:
  - no solid evidence_quote exists
  - it is only a definition, purpose statement, or document structure
  - it is only internal process by a committee, board, jury, or office
  - it is too weak to be worth notifying someone about
  - it has no meaningful action, restriction, eligibility implication, or consequence for the target person
  - it is mostly awareness or explanation with no concrete next step
  - it duplicates a better item
  - it is a one-time announcement or deadline that is already expired before CURRENT DATE
  - it is clearly tied to a past academic year or finished event and is no longer actionable now
  - it was lifted from an expired announcement or news page without clear evidence that it remains standing policy
  - it is generic conduct advice with no concrete trigger, decision point, process stage, or timing
  - the trigger is too broad or always-on, such as "when on campus", "when participating in any activity", or similar
  - the recipient would still need obvious follow-up questions after reading it
  - it comes from a form_template and is really just part of the form or explanatory notes around the form
  - fixing it would require adding details that are not explicitly supported by the evidence quote or surrounding document text

AFTER reviewing the extracted items:
Scan the document for important missed actionable suggestions and add them to missed_rules using the same schema.

Return this exact JSON structure. No markdown. No explanation.
{{
  "reviewed": [
    {{
      "index": 0,
      "action": "keep",
      "reason": "Notification-ready, traceable, specific, and actionable.",
      "fixed_rule": null
    }},
    {{
      "index": 1,
      "action": "fix",
      "reason": "Valid source content but wording is weak and should be rewritten as a direct action reminder.",
      "fixed_rule": {{
        "rule_text": "...",
        "evidence_quote": "...",
        "applies_to": "...",
        "trigger": "...",
        "deadline": null,
        "valid_from": null,
        "valid_until": null,
        "blocking": false,
        "consequence": null,
        "authority": null,
        "exceptions": null,
        "target_role": "student",
        "match_type": "contextual",
        "sql_condition": null,
        "confidence": "explicit"
      }}
    }}
  ],
  "missed_rules": []
}}"""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_doc_chunks(db: Session, doc_ids: list[str]) -> list[dict]:
    """Fetch KB chunks by UUID list, return list of {id, url, title, content}."""
    if not doc_ids:
        return []
    rows = db.execute(text("""
        SELECT id::text, COALESCE(url,'') AS url,
               COALESCE(title,'') AS title,
               COALESCE(content,'') AS content
        FROM knowledge_base
        WHERE id::text = ANY(:ids)
        ORDER BY url, id
    """), {"ids": doc_ids}).all()
    return [{"id": r[0], "url": r[1], "title": r[2], "content": r[3]} for r in rows]


def _group_by_url(chunks: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for c in chunks:
        groups.setdefault(c["url"], []).append(c)
    return groups


def _document_title(chunks: list[dict]) -> str:
    for c in chunks:
        title = normalize_text(c.get("title", ""))
        if title:
            return title
    return ""


def _infer_document_type(url: str, title: str) -> str:
    text_blob = f"{url} {title}".lower()

    form_tokens = (
        "formu",
        "form ",
        " form",
        "tutanak",
        "onay-formu",
        "bildirim-formu",
        "raporu",
        "rapor ",
        "basvuru-formu",
        "degerlendirme-formu",
    )
    if any(token in text_blob for token in form_tokens):
        return "form_template"

    announcement_tokens = (
        "/news/",
        "/duyuru/",
        "announcement",
        "applications",
        "application window",
        "academic year",
    )
    if any(token in text_blob for token in announcement_tokens):
        return "announcement"

    return "regulation"


def _specificity_issue(rule: dict) -> str | None:
    rule_text = normalize_text(rule.get("rule_text", ""))
    applies_to = normalize_text(rule.get("applies_to", ""))
    trigger = normalize_text(rule.get("trigger", "") or "")
    deadline = normalize_text(rule.get("deadline", "") or "")
    consequence = normalize_text(rule.get("consequence", "") or "")
    valid_from = normalize_text(rule.get("valid_from", "") or "")
    valid_until = normalize_text(rule.get("valid_until", "") or "")

    if not rule_text or not applies_to or not trigger:
        return "missing_specificity_fields"

    if "blocking" not in rule:
        return "missing_blocking"

    applies_lower = applies_to.lower()
    rule_lower = rule_text.lower()
    trigger_lower = trigger.lower()

    if applies_lower in {
        "students",
        "all students",
        "all students at istanbul bilgi university",
    }:
        return "audience_too_broad"

    if trigger_lower in {
        "when on campus",
        "when participating in any activity",
        "when participating in activities",
        "when sitting any examination",
    }:
        return "trigger_too_broad"

    if any(marker in trigger_lower for marker in (
        "when on campus",
        "when participating in any activity",
        "when participating in university activities",
        "when encountering official university notices",
        "when using university premises",
    )):
        return "trigger_too_broad"

    if valid_from and _normalized_date(valid_from) is None:
        return "invalid_valid_from"

    if valid_until and _normalized_date(valid_until) is None:
        return "invalid_valid_until"

    if applies_lower.startswith("all students at istanbul bilgi university") and rule_lower.startswith("do not ") and not deadline:
        return "generic_all_students_warning"

    generic_broad_starts = (
        "do not engage in actions that",
        "do not obstruct or interfere",
        "do not remove, tear, alter",
        "do not distribute leaflets",
        "do not attempt to cheat in any exam",
    )
    if applies_lower.startswith("all students at istanbul bilgi university") and rule_lower.startswith(generic_broad_starts):
        return "generic_disciplinary_warning"

    weak_openers = (
        "be aware",
        "consider ",
        "expect ",
        "know that",
        "remember ",
        "note that",
        "take advantage of",
    )
    if rule_lower.startswith(weak_openers):
        return "awareness_only_wording"

    action_text = rule_lower
    for lead in ("when ", "during ", "after ", "before ", "if "):
        if action_text.startswith(lead) and ", " in action_text:
            action_text = action_text.split(", ", 1)[1].strip()
            break

    action_prefixes = (
        "add",
        "apply",
        "base",
        "begin",
        "print",
        "scan",
        "start",
        "submit",
        "upload",
        "pass",
        "prepare",
        "check",
        "ensure",
        "meet",
        "do not",
        "complete",
        "contact",
        "register",
        "renew",
        "track",
        "verify",
        "plan",
        "reduce",
        "find",
        "attend",
        "deliver",
        "reapply",
        "make sure",
        "keep",
        "bring",
        "request",
        "use",
        "demonstrate",
    )
    if not action_text.startswith(action_prefixes):
        return "not_imperative_enough"

    if _normalized_bool(rule.get("blocking")) and not consequence:
        return "missing_blocking_consequence"

    return None


def _normalize_review_result(review: Any) -> dict[str, list[dict]] | None:
    if isinstance(review, list):
        return {"reviewed": [item for item in review if isinstance(item, dict)], "missed_rules": []}

    if not isinstance(review, dict):
        return None

    reviewed = review.get("reviewed")
    if not isinstance(reviewed, list):
        for key in ("review", "reviews", "items"):
            candidate = review.get(key)
            if isinstance(candidate, list):
                reviewed = candidate
                break
    if not isinstance(reviewed, list):
        return None

    missed = review.get("missed_rules", [])
    if not isinstance(missed, list):
        missed = []

    return {
        "reviewed": [item for item in reviewed if isinstance(item, dict)],
        "missed_rules": [item for item in missed if isinstance(item, dict)],
    }


def _rule_dedup_text(rule_text: str, applies_to: str) -> str:
    return normalize_text(f"{rule_text}\nAudience: {applies_to}")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalized_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = normalize_text(str(value))
    return cleaned or None


def _normalized_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    lowered = normalize_text(str(value)).lower()
    return lowered in {"true", "1", "yes", "y"}


def _normalized_date(value: Any) -> date_cls | None:
    if value is None:
        return None
    cleaned = normalize_text(str(value))
    if not cleaned:
        return None
    try:
        return date_cls.fromisoformat(cleaned)
    except ValueError:
        return None


def _normalize_action_rule(rule: dict) -> dict:
    normalized = dict(rule)
    normalized["trigger"] = normalize_text(
        normalized.get("trigger") or normalized.get("condition") or ""
    )
    normalized["blocking"] = _normalized_bool(normalized.get("blocking"))

    consequence = _normalized_optional(normalized.get("consequence"))
    normalized["consequence"] = consequence
    if normalized["blocking"] and not consequence:
        normalized["blocking"] = False

    valid_from = _normalized_optional(normalized.get("valid_from"))
    valid_until = _normalized_optional(normalized.get("valid_until"))
    normalized["valid_from"] = valid_from if _normalized_date(valid_from) is not None else None
    normalized["valid_until"] = valid_until if _normalized_date(valid_until) is not None else None
    return normalized


def _emit_agent_log(
    db: Session,
    run_id: Any,
    source_url: str | None,
    agent: EventAgent,
    state: str,
    decision: str,
    reason: str,
    payload: dict,
) -> None:
    db.add(EventAgentLog(
        run_id=run_id,
        source_key=hash_text(source_url or "")[:64] if source_url else None,
        agent=agent,
        state=state,
        decision=decision,
        reason=reason,
        payload=payload,
    ))


def _map_role(role: str) -> EventTargetRole:
    return {
        "student": EventTargetRole.STUDENT,
        "staff": EventTargetRole.STAFF,
        "admin": EventTargetRole.ADMIN,
    }.get((role or "").lower(), EventTargetRole.ALL)


def _map_match_type(mt: str) -> RuleMatchType:
    return RuleMatchType.SQL if (mt or "").lower() == "sql" else RuleMatchType.CONTEXTUAL


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class RuleExtractionOrchestrator:

    def __init__(
        self,
        outlier_url: str = "http://127.0.0.1:8080",
        outlier_model: str = "claude-opus-4-6",
        llm_timeout: float = 180.0,
        current_date: str | None = None,
        regulation_tree_path: str | None = None,
    ) -> None:
        self.outlier_url = outlier_url
        self.outlier_model = outlier_model
        self.llm_timeout = llm_timeout
        self.current_date = current_date or datetime.now(timezone.utc).date().isoformat()
        self.semantic_duplicate_cosine_threshold = 0.97
        self.semantic_duplicate_lexical_threshold = 0.82
        self.lexical_duplicate_threshold = 0.93
        self._semantic_lock = threading.Lock()
        self._semantic_cache_loaded = False
        self._semantic_embeddings_enabled = True
        self._semantic_warning_emitted = False
        self._semantic_texts: list[str] = []
        self._semantic_vectors: list[list[float]] = []
        self._embedding_service = None
        self.regulation_tree_path = regulation_tree_path or str(
            Path(__file__).resolve().parents[1]
            / "scripts/experiments/results/categorization/flow/12_cluster_regulations/tree_with_regulations.json"
        )

    def _get_embedding_service(self):
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    def _ensure_semantic_cache(self, db: Session) -> None:
        if self._semantic_cache_loaded:
            return

        with self._semantic_lock:
            if self._semantic_cache_loaded:
                return

            rows = (
                db.query(RegulationRule.rule_text, RegulationRule.applies_to)
                .filter(RegulationRule.status == RuleStatus.ACTIVE)
                .all()
            )
            texts = [
                _rule_dedup_text(rule_text or "", applies_to or "")
                for rule_text, applies_to in rows
                if (rule_text or "").strip() and (applies_to or "").strip()
            ]
            vectors: list[list[float]] = []
            self._semantic_embeddings_enabled = True
            if texts:
                try:
                    vectors = self._get_embedding_service().embed_batch(texts)
                except Exception as exc:
                    self._semantic_embeddings_enabled = False
                    if not self._semantic_warning_emitted:
                        logger.warning("Semantic dedup embeddings unavailable, falling back to lexical-only duplicate checks: %s", exc)
                        self._semantic_warning_emitted = True
                    vectors = []

            self._semantic_texts = texts
            self._semantic_vectors = vectors
            self._semantic_cache_loaded = True

    def _semantic_duplicate_info(self, candidate_text: str) -> dict | None:
        candidate_vector: list[float] | None = None
        if self._semantic_embeddings_enabled:
            try:
                candidate_vector = self._get_embedding_service().embed_text(candidate_text)
            except Exception as exc:
                self._semantic_embeddings_enabled = False
                if not self._semantic_warning_emitted:
                    logger.warning("Semantic dedup embeddings unavailable, falling back to lexical-only duplicate checks: %s", exc)
                    self._semantic_warning_emitted = True

        with self._semantic_lock:
            best_cosine = 0.0
            best_lexical = 0.0
            best_idx = -1

            for idx, known_text in enumerate(self._semantic_texts):
                lexical = difflib.SequenceMatcher(None, candidate_text, known_text).ratio()
                cosine = 0.0
                if (
                    candidate_vector is not None and
                    self._semantic_embeddings_enabled and
                    idx < len(self._semantic_vectors)
                ):
                    cosine = _cosine_similarity(candidate_vector, self._semantic_vectors[idx])
                if cosine > best_cosine or (cosine == best_cosine and lexical > best_lexical):
                    best_cosine = cosine
                    best_lexical = lexical
                    best_idx = idx

            is_duplicate = (
                best_idx >= 0 and (
                    best_lexical >= self.lexical_duplicate_threshold or
                    (best_cosine >= self.semantic_duplicate_cosine_threshold and best_lexical >= self.semantic_duplicate_lexical_threshold)
                )
            )

            if not is_duplicate:
                self._semantic_texts.append(candidate_text)
                if candidate_vector is not None and self._semantic_embeddings_enabled:
                    self._semantic_vectors.append(candidate_vector)
                return None

            return {
                "cosine": round(best_cosine, 6),
                "lexical": round(best_lexical, 6),
            }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, db: Session) -> dict:
        run = EventRun(status=EventRunStatus.RUNNING)
        db.add(run)
        db.commit()
        db.refresh(run)

        _emit_agent_log(db, run.id, None, EventAgent.ORCHESTRATOR,
                        "START", "run_started", "extraction_pipeline",
                        {"model": self.outlier_model, "run_id": str(run.id)})
        db.commit()

        stats = {"sources": 0, "chunks": 0, "rules_extracted": 0,
                 "rules_accepted": 0, "rules_rejected": 0, "errors": 0}
        try:
            doc_ids = self._load_regulation_doc_ids()
            _emit_agent_log(db, run.id, None, EventAgent.SEARCH,
                            "LOAD", "doc_ids_loaded", "regulation_tree",
                            {"total_doc_ids": len(doc_ids)})
            db.commit()

            chunks = _fetch_doc_chunks(db, doc_ids)
            groups = _group_by_url(chunks)
            self._ensure_semantic_cache(db)

            _emit_agent_log(db, run.id, None, EventAgent.SEARCH,
                            "GROUPED", "docs_grouped", "by_url",
                            {"unique_docs": len(groups), "total_chunks": len(chunks)})
            db.commit()

            total_docs = len(groups)
            items = list(groups.items())
            completed = [0]

            def process_one(idx_url_chunks):
                idx, url, doc_chunks = idx_url_chunks
                from database.session import SessionLocal
                thread_db = SessionLocal()
                try:
                    doc_stats = self._process_document(thread_db, run.id, url, doc_chunks)
                    completed[0] += 1
                    print(f"[{completed[0]}/{total_docs}] {url[-80:]} => extracted={doc_stats['extracted']} accepted={doc_stats['accepted']}", flush=True)
                    return doc_stats
                finally:
                    thread_db.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {
                    pool.submit(process_one, (i, url, chunks)): url
                    for i, (url, chunks) in enumerate(items, 1)
                }
                for future in as_completed(futures):
                    doc_stats = future.result()
                    stats["sources"] += 1
                    stats["chunks"] += doc_stats["chunks"]
                    stats["rules_extracted"] += doc_stats["extracted"]
                    stats["rules_accepted"] += doc_stats["accepted"]
                    stats["rules_rejected"] += doc_stats["rejected"]
                    if doc_stats.get("error"):
                        stats["errors"] += 1

                    run.sources_processed = stats["sources"]
                    run.chunks_processed = stats["chunks"]
                    run.events_created = stats["rules_accepted"]
                    db.commit()

            run.status = EventRunStatus.COMPLETED
            run.completed_at = func.now()
            _emit_agent_log(db, run.id, None, EventAgent.ORCHESTRATOR,
                            "DONE", "run_completed", "all_docs_processed", stats)
            db.commit()

        except Exception as exc:
            db.rollback()
            run.status = EventRunStatus.FAILED
            run.error_message = str(exc)
            run.completed_at = func.now()
            _emit_agent_log(db, run.id, None, EventAgent.ORCHESTRATOR,
                            "FAILED", "run_failed", "exception", {"error": str(exc)})
            db.commit()
            logger.exception("Rule extraction run failed", exc_info=exc)
            raise

        db.refresh(run)
        return {"run_id": str(run.id), **stats}

    # ------------------------------------------------------------------
    # Per-document processing
    # ------------------------------------------------------------------

    def _process_document(
        self,
        db: Session,
        run_id: Any,
        url: str,
        chunks: list[dict],
    ) -> dict:
        source_key = hash_text(url)[:64]
        chunk_ids = [c["id"] for c in chunks]
        title = _document_title(chunks)
        document_type = _infer_document_type(url, title)
        full_text = "\n\n".join(
            normalize_text(c["content"]) for c in chunks if c["content"].strip()
        )

        # Log source start
        src_log = EventSourceLog(
            run_id=run_id,
            source_key=source_key,
            source_url=url,
            category="regulation",
            parent_category="regulations",
            status=EventSourceStatus.PENDING,
            reason="starting",
            chunk_count=len(chunks),
        )
        db.add(src_log)
        db.flush()

        if not full_text.strip():
            src_log.status = EventSourceStatus.SKIPPED
            src_log.reason = "empty_content"
            db.commit()
            return {"chunks": len(chunks), "extracted": 0, "accepted": 0, "rejected": 0}

        if document_type == "form_template":
            src_log.status = EventSourceStatus.SKIPPED
            src_log.reason = "form_template"
            _emit_agent_log(
                db, run_id, url, EventAgent.ORCHESTRATOR,
                "SKIP", "form_template", "document_type_filter",
                {"url": url, "title": title, "document_type": document_type},
            )
            db.commit()
            return {"chunks": len(chunks), "extracted": 0, "accepted": 0, "rejected": 0}

        self._ensure_semantic_cache(db)

        t0 = time.perf_counter()

        # --- Pass 1: extract ---
        pass1_prompt = PASS1_PROMPT.format(
            current_date=self.current_date,
            title=title or "Untitled document",
            document_type=document_type,
            url=url,
            text=full_text[:12000],
        )
        _emit_agent_log(db, run_id, url, EventAgent.REASONING,
                        "PASS1_START", "extracting", "llm_pass1",
                        {"url": url, "text_chars": len(full_text)})
        db.commit()

        raw_rules, err1 = _call_llm_with_retry(
            url=self.outlier_url, model=self.outlier_model,
            system=SYSTEM, prompt=pass1_prompt, timeout=self.llm_timeout,
        )

        if err1 or not isinstance(raw_rules, list):
            _emit_agent_log(db, run_id, url, EventAgent.REASONING,
                            "PASS1_FAILED", "llm_error", err1 or "not_a_list",
                            {"url": url})
            src_log.status = EventSourceStatus.FAILED
            src_log.reason = f"pass1_error: {err1}"
            db.commit()
            return {"chunks": len(chunks), "extracted": 0, "accepted": 0, "rejected": 0, "error": True}

        _emit_agent_log(db, run_id, url, EventAgent.REASONING,
                        "PASS1_DONE", "extracted", "rules_from_pass1",
                        {"url": url, "rule_count": len(raw_rules),
                         "elapsed_ms": round((time.perf_counter() - t0) * 1000)})
        db.commit()

        # --- Pass 2: review ---
        pass2_prompt = PASS2_PROMPT.format(
            current_date=self.current_date,
            title=title or "Untitled document",
            document_type=document_type,
            url=url,
            text=full_text[:8000],
            rules=json.dumps(raw_rules, ensure_ascii=False, indent=2),
        )
        _emit_agent_log(db, run_id, url, EventAgent.REASONING,
                        "PASS2_START", "reviewing", "llm_pass2", {"url": url})
        db.commit()

        review_result, err2 = _call_llm_with_retry(
            url=self.outlier_url, model=self.outlier_model,
            system=SYSTEM, prompt=pass2_prompt, timeout=self.llm_timeout,
        )
        normalized_review = _normalize_review_result(review_result)

        if err2 or normalized_review is None:
            # pass 2 failed — still use pass 1 results, flag them needs_review
            _emit_agent_log(db, run_id, url, EventAgent.REASONING,
                            "PASS2_FAILED", "llm_error", err2 or "bad_response",
                            {"url": url, "falling_back_to_pass1": True})
            reviewed_rules = raw_rules
            pass2_failed = True
        else:
            reviewed_rules, pass2_failed = self._apply_review(raw_rules, normalized_review)
            _emit_agent_log(db, run_id, url, EventAgent.REASONING,
                            "PASS2_DONE", "reviewed", "rules_after_review",
                            {"url": url,
                                 "kept": sum(1 for r in reviewed_rules if r.get("_action") != "remove"),
                                 "removed": sum(1 for r in reviewed_rules if r.get("_action") == "remove"),
                                 "missed_added": len(normalized_review.get("missed_rules", [])),
                                 "elapsed_ms": round((time.perf_counter() - t0) * 1000)})
            db.commit()

        # --- Persist ---
        accepted = 0
        rejected = 0
        for raw_rule in reviewed_rules:
            rule = _normalize_action_rule(raw_rule)
            action = rule.get("_action", "keep")
            candidate_hash = hash_text(
                f"{url}|{normalize_text(rule.get('rule_text', '')).lower()}"
            )[:64]
            fingerprint = hash_text(
                f"{normalize_text(rule.get('rule_text', '')).lower()}|{rule.get('target_role','all')}"
            )[:64]

            if action == "remove":
                rejected += 1
                db.add(EventCandidateLog(
                    run_id=run_id,
                    source_key=source_key,
                    source_url=url,
                    category="regulation",
                    parent_category="regulations",
                    target_role=rule.get("target_role", "all"),
                    candidate_hash=candidate_hash,
                    candidate_text=rule.get("rule_text", ""),
                    normalized_text=normalize_text(rule.get("rule_text", "")).lower(),
                    decision=EventCandidateDecision.REJECT_QUALITY,
                    reason_code=(rule.get("_reason") or "pass2_removed")[:64],
                    metrics={"pass2_action": "remove"},
                ))
                continue

            specificity_issue = _specificity_issue(rule)
            if specificity_issue:
                rejected += 1
                db.add(EventCandidateLog(
                    run_id=run_id,
                    source_key=source_key,
                    source_url=url,
                    category="regulation",
                    parent_category="regulations",
                    target_role=rule.get("target_role", "all"),
                    candidate_hash=candidate_hash,
                    candidate_text=rule.get("rule_text", ""),
                    normalized_text=normalize_text(rule.get("rule_text", "")).lower(),
                    decision=EventCandidateDecision.REJECT_QUALITY,
                    reason_code=specificity_issue[:64],
                    metrics={"filter": "specificity"},
                ))
                continue

            semantic_duplicate = self._semantic_duplicate_info(
                _rule_dedup_text(rule.get("rule_text", ""), rule.get("applies_to", ""))
            )
            if semantic_duplicate:
                rejected += 1
                db.add(EventCandidateLog(
                    run_id=run_id,
                    source_key=source_key,
                    source_url=url,
                    category="regulation",
                    parent_category="regulations",
                    target_role=rule.get("target_role", "all"),
                    candidate_hash=candidate_hash,
                    candidate_text=rule.get("rule_text", ""),
                    normalized_text=normalize_text(rule.get("rule_text", "")).lower(),
                    decision=EventCandidateDecision.REJECT_DUPLICATE,
                    reason_code="duplicate_semantic",
                    metrics=semantic_duplicate,
                ))
                continue

            # dedup check
            existing = db.query(RegulationRule.id).filter(
                RegulationRule.fingerprint == fingerprint
            ).first()
            if existing:
                rejected += 1
                db.add(EventCandidateLog(
                    run_id=run_id,
                    source_key=source_key,
                    source_url=url,
                    category="regulation",
                    parent_category="regulations",
                    target_role=rule.get("target_role", "all"),
                    candidate_hash=candidate_hash,
                    candidate_text=rule.get("rule_text", ""),
                    normalized_text=normalize_text(rule.get("rule_text", "")).lower(),
                    decision=EventCandidateDecision.REJECT_DUPLICATE,
                    reason_code="duplicate_fingerprint",
                    metrics={"fingerprint": fingerprint},
                ))
                continue

            status = RuleStatus.NEEDS_REVIEW if pass2_failed else RuleStatus.ACTIVE
            db.add(RegulationRule(
                run_id=run_id,
                source_doc_url=url,
                source_chunk_ids=chunk_ids,
                evidence_quote=normalize_text(rule.get("evidence_quote", "")),
                rule_text=normalize_text(rule.get("rule_text", "")),
                applies_to=normalize_text(rule.get("applies_to", "")),
                trigger=normalize_text(rule.get("trigger", "")),
                deadline=_normalized_optional(rule.get("deadline")),
                valid_from=_normalized_date(rule.get("valid_from")),
                valid_until=_normalized_date(rule.get("valid_until")),
                blocking=_normalized_bool(rule.get("blocking")),
                consequence=_normalized_optional(rule.get("consequence")),
                authority=_normalized_optional(rule.get("authority")),
                exceptions=_normalized_optional(rule.get("exceptions")),
                target_role=_map_role(rule.get("target_role", "all")),
                match_type=_map_match_type(rule.get("match_type", "contextual")),
                sql_condition=_normalized_optional(rule.get("sql_condition")),
                status=status,
                pass2_notes=_normalized_optional(rule.get("_pass2_notes")),
                confidence=_normalized_optional(rule.get("confidence")) or "explicit",
                fingerprint=fingerprint,
            ))
            db.add(EventCandidateLog(
                run_id=run_id,
                source_key=source_key,
                source_url=url,
                category="regulation",
                parent_category="regulations",
                target_role=rule.get("target_role", "all"),
                candidate_hash=candidate_hash,
                candidate_text=rule.get("rule_text", ""),
                normalized_text=normalize_text(rule.get("rule_text", "")).lower(),
                decision=EventCandidateDecision.ACCEPT_PENDING,
                reason_code="accepted",
                metrics={"match_type": rule.get("match_type"), "confidence": rule.get("confidence")},
            ))
            accepted += 1

        src_log.status = EventSourceStatus.DONE
        src_log.reason = f"accepted={accepted} rejected={rejected}"
        src_log.completed_at = func.now()
        db.commit()

        _emit_agent_log(db, run_id, url, EventAgent.EVENT_CREATOR,
                        "PERSIST_DONE", "persisted", "rules_stored",
                        {"url": url, "accepted": accepted, "rejected": rejected,
                         "total_ms": round((time.perf_counter() - t0) * 1000)})
        db.commit()

        return {
            "chunks": len(chunks),
            "extracted": len(raw_rules),
            "accepted": accepted,
            "rejected": rejected,
        }

    # ------------------------------------------------------------------
    # Apply pass 2 review onto the pass 1 list
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_review(
        raw_rules: list[dict],
        review: dict[str, list[dict]],
    ) -> tuple[list[dict], bool]:
        reviewed_items: list[dict] = review.get("reviewed", [])
        missed: list[dict] = review.get("missed_rules", [])

        result: list[dict] = list(raw_rules)  # copy

        for item in reviewed_items:
            idx = item.get("index")
            if not isinstance(idx, int) or idx >= len(result):
                continue
            action = str(item.get("action", "keep")).lower()
            reason = str(item.get("reason", ""))
            if action == "remove":
                result[idx] = {**result[idx], "_action": "remove", "_reason": reason}
            elif action == "fix" and isinstance(item.get("fixed_rule"), dict):
                result[idx] = {**item["fixed_rule"], "_action": "keep",
                               "_pass2_notes": reason}
            else:
                result[idx] = {**result[idx], "_action": "keep"}

        for m in missed:
            if isinstance(m, dict) and m.get("rule_text"):
                result.append({**m, "_action": "keep", "_pass2_notes": "added_by_pass2"})

        return result, False

    # ------------------------------------------------------------------
    # Load regulation doc IDs from step 12 output
    # ------------------------------------------------------------------

    def _load_regulation_doc_ids(self) -> list[str]:
        path = Path(self.regulation_tree_path)
        if not path.exists():
            raise FileNotFoundError(f"Regulation tree not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        tree = data.get("tree", data)
        reg = tree.get("regulations", {})

        ids: list[str] = []
        seen: set[str] = set()
        for sub_data in reg.get("sub_levels", {}).values():
            for leaf_data in sub_data.get("leaves", {}).values():
                for doc_id in leaf_data.get("doc_ids", []):
                    if doc_id not in seen:
                        seen.add(doc_id)
                        ids.append(doc_id)
        return ids
