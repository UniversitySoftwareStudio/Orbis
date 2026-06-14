"""Promote trigger-pipeline obligations into matchable regulation rules.

The deterministic trigger pipeline (`/api/events/trigger`) writes thin
`Event` rows to `regulatory_events`: an obligation sentence + a target role.
The student-facing path, however, runs through the user agent
(`events/user_agent.py`), which reasons over richer `RegulationRule` rows and
writes per-user `user_rule_assignments` that the "My Regulations" page reads.

For a long time those two halves were disconnected: the trigger pipeline's
output was read by nobody, and the rules the user agent matched against were
hand-extracted leftovers with no code path to refresh them. This module is the
missing wire. It copies accepted `Event` rows into `RegulationRule` rows so the
existing matcher — and therefore the student page — sees everything the live
pipeline found.

Promotion is intentionally conservative:
  * Only `PENDING` events (the high-confidence accepts) are promoted by
    default; `NEEDS_REVIEW` events stay in the admin queue until reviewed.
  * The `Event.fingerprint` is reused as the `RegulationRule.fingerprint`, so
    re-running promotion is idempotent and never duplicates a rule.
  * Promoted rules are `CONTEXTUAL` (the user agent decides applicability
    per-student); the pipeline does not invent SQL conditions, deadlines, or
    consequences it did not extract. Those rich fields stay empty rather than
    fabricated, which keeps the data honest.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import (
    Event,
    EventStatus,
    RegulationRule,
    RuleMatchType,
    RuleStatus,
)

# Role enum value -> human "applies_to" phrasing the matcher prompt reads.
_APPLIES_TO = {
    "student": "students",
    "staff": "staff",
    "admin": "administrators",
    "all": "all members of the university",
}


@dataclass(frozen=True)
class PromotionStats:
    promoted: int
    skipped_existing: int

    @property
    def total_seen(self) -> int:
        return self.promoted + self.skipped_existing


def promote_events_to_rules(
    db: Session,
    *,
    statuses: tuple[EventStatus, ...] = (EventStatus.PENDING,),
    commit: bool = True,
) -> PromotionStats:
    """Copy accepted `regulatory_events` into matchable `regulation_rules`.

    Deduplicated by fingerprint, so it is safe to call after every run.
    """
    events = (
        db.query(Event)
        .filter(Event.status.in_(statuses))
        .order_by(Event.created_at.asc())
        .all()
    )

    existing_fingerprints = {
        fp for (fp,) in db.query(RegulationRule.fingerprint).all()
    }

    promoted = 0
    skipped_existing = 0
    for event in events:
        if event.fingerprint in existing_fingerprints:
            skipped_existing += 1
            continue

        role_value = event.target_role.value
        db.add(
            RegulationRule(
                run_id=event.run_id,
                source_doc_url=event.source_url,
                source_chunk_ids=list(event.source_chunk_ids or []),
                evidence_quote=event.evidence_excerpt,
                rule_text=event.obligation_text,
                applies_to=_APPLIES_TO.get(role_value, role_value),
                target_role=event.target_role,
                match_type=RuleMatchType.CONTEXTUAL,
                status=RuleStatus.ACTIVE,
                confidence="explicit" if event.status == EventStatus.PENDING else "ambiguous",
                fingerprint=event.fingerprint,
            )
        )
        existing_fingerprints.add(event.fingerprint)
        promoted += 1

    if commit:
        db.commit()

    return PromotionStats(promoted=promoted, skipped_existing=skipped_existing)
