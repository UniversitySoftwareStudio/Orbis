from __future__ import annotations

from uuid import uuid4

from database.models import (
    EventAgent,
    EventAgentLog,
    EventCandidateDecision,
    EventCandidateLog,
    Event,
    EventStatus,
    EventRunStatus,
    EventSourceLog,
    EventSourceCheckpoint,
    KnowledgeBase,
    RegulationRule,
    RuleMatchType,
)
from events.orchestrator import EventPipelineOrchestrator
from events.promotion import promote_events_to_rules
from events.search_agent import SearchAgent
from events.utils import canonicalize_url, safe_eval_condition


def _kb_row(url: str, content: str, category: str = "regulation_document") -> KnowledgeBase:
    return KnowledgeBase(
        id=uuid4(),
        url=url,
        title="Sample Regulation",
        content=content,
        language="tr",
        type="pdf",
        category=category,
        parent_category="regulation",
        metadata_={},
    )


def test_search_agent_dedupes_http_https_variants(db_session):
    db_session.add_all(
        [
            _kb_row(
                "https://www.bilgi.edu.tr/upload/regulation-a/",
                "Students must submit petitions by Friday.",
            ),
            _kb_row(
                "http://www.bilgi.edu.tr/upload/regulation-a/",
                "Students must submit petitions by Friday.",
            ),
        ]
    )
    db_session.commit()

    sources = SearchAgent().fetch_regulation_sources(db_session)

    assert len(sources) == 1
    assert canonicalize_url(sources[0].canonical_url) == "bilgi.edu.tr/upload/regulation-a"
    assert sources[0].chunk_count == 2


def test_pipeline_creates_events_and_checkpoints_once(db_session):
    db_session.add_all(
        [
            _kb_row(
                "https://www.bilgi.edu.tr/upload/regulation-b/",
                "Students must submit course registration forms by the deadline.",
            ),
            _kb_row(
                "https://www.bilgi.edu.tr/upload/regulation-b/",
                "Academic staff are required to approve forms within 3 business days.",
            ),
            _kb_row(
                "https://www.bilgi.edu.tr/upload/regulation-c/",
                "The university values academic freedom and development.",
            ),
        ]
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()
    first_run = orchestrator.start_run(db_session)
    result = orchestrator.run_existing(db_session, first_run)

    assert result.status == EventRunStatus.COMPLETED.value
    assert result.sources_processed == 2
    assert result.events_created == 2

    checkpoints = db_session.query(EventSourceCheckpoint).count()
    assert checkpoints == 2

    created_events = db_session.query(Event).all()
    assert len(created_events) == 2
    assert {event.target_role.value for event in created_events} == {"student", "staff"}
    telemetry = db_session.query(EventAgentLog).filter(EventAgentLog.run_id == first_run.id).all()
    assert telemetry
    agents = {log.agent for log in telemetry}
    assert EventAgent.SEARCH in agents
    assert EventAgent.REASONING in agents
    assert EventAgent.EVENT_CREATOR in agents

    second_run = orchestrator.start_run(db_session)
    second_result = orchestrator.run_existing(db_session, second_run)

    assert second_result.status == EventRunStatus.COMPLETED.value
    assert second_result.sources_processed == 0
    assert second_result.events_created == 0
    assert db_session.query(Event).count() == 2


def test_pipeline_marks_run_failed_on_exception(db_session, monkeypatch):
    db_session.add(
        _kb_row(
            "https://www.bilgi.edu.tr/upload/regulation-d/",
            "Students must complete orientation before classes start.",
        )
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()

    class _Boom:
        def extract(self, _source):
            raise RuntimeError("intentional failure")

    orchestrator.reasoning_agent = _Boom()

    run = orchestrator.start_run(db_session)

    try:
        orchestrator.run_existing(db_session, run)
        assert False, "Expected run_existing to raise"
    except RuntimeError:
        db_session.refresh(run)
        assert run.status == EventRunStatus.FAILED
        assert "intentional failure" in (run.error_message or "")


def test_pipeline_rejects_non_actionable_contact_like_statements(db_session):
    db_session.add(
        _kb_row(
            "https://www.bilgi.edu.tr/upload/regulation-e/",
            "For detailed information students can contact erasmus@bilgi.edu.tr.",
        )
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()
    run = orchestrator.start_run(db_session)
    result = orchestrator.run_existing(db_session, run)

    assert result.status == EventRunStatus.COMPLETED.value
    assert result.events_created == 0
    assert db_session.query(Event).count() == 0


def test_pipeline_dedups_same_obligation_across_sources(db_session):
    statement = "Students must submit course registration forms by the deadline."
    db_session.add_all(
        [
            _kb_row("https://www.bilgi.edu.tr/upload/regulation-f1/", statement),
            _kb_row("https://www.bilgi.edu.tr/upload/regulation-f2/", statement),
        ]
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()
    run = orchestrator.start_run(db_session)
    result = orchestrator.run_existing(db_session, run)

    assert result.status == EventRunStatus.COMPLETED.value
    assert result.events_created == 1
    assert db_session.query(Event).count() == 1


def test_pipeline_skips_low_signal_regulation_sources(db_session):
    db_session.add(
        _kb_row(
            "http://www.bilgi.edu.tr/en/university/about/institutional-principles/community-services/supporters/",
            "Students must submit forms within 2 days.",
            category="regulation",
        )
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()
    run = orchestrator.start_run(db_session)
    result = orchestrator.run_existing(db_session, run)

    assert result.status == EventRunStatus.COMPLETED.value
    assert result.events_created == 0
    logs = db_session.query(EventSourceLog).filter(EventSourceLog.run_id == run.id).all()
    assert len(logs) == 1
    assert logs[0].reason == "low_regulatory_signal"


def test_pipeline_does_not_trigger_on_substring_marshall(db_session):
    db_session.add(
        _kb_row(
            "https://www.bilgi.edu.tr/upload/regulation-marshall.pdf",
            "German Marshall Fund supporter list for civil society partners.",
            category="regulation_document",
        )
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()
    run = orchestrator.start_run(db_session)
    result = orchestrator.run_existing(db_session, run)

    assert result.status == EventRunStatus.COMPLETED.value
    assert result.events_created == 0


def test_pipeline_writes_candidate_logs_and_review_status(db_session):
    db_session.add_all(
        [
            _kb_row(
                "https://www.bilgi.edu.tr/upload/regulation-review-1.pdf",
                "Students must submit the petition by Friday.",
            ),
            _kb_row(
                "https://www.bilgi.edu.tr/upload/regulation-review-2.pdf",
                "Students required to submit the petition and may include supporting documents by Friday.",
            ),
        ]
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()
    run = orchestrator.start_run(db_session)
    result = orchestrator.run_existing(db_session, run)

    assert result.status == EventRunStatus.COMPLETED.value
    assert result.events_created == 2

    statuses = {event.status for event in db_session.query(Event).filter(Event.run_id == run.id).all()}
    assert EventStatus.PENDING in statuses
    assert EventStatus.NEEDS_REVIEW in statuses

    candidate_logs = db_session.query(EventCandidateLog).filter(EventCandidateLog.run_id == run.id).all()
    assert candidate_logs
    decisions = {log.decision for log in candidate_logs}
    assert EventCandidateDecision.ACCEPT_PENDING in decisions
    assert EventCandidateDecision.ACCEPT_REVIEW in decisions


def test_pipeline_promotes_events_into_regulation_rules(db_session):
    """The trigger pipeline's output must reach the student-facing rule table."""
    db_session.add_all(
        [
            _kb_row(
                "https://www.bilgi.edu.tr/upload/regulation-promote-1/",
                "Students must submit course registration forms by the deadline.",
            ),
            _kb_row(
                "https://www.bilgi.edu.tr/upload/regulation-promote-2/",
                "Academic staff are required to approve forms within 3 business days.",
            ),
        ]
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()
    run = orchestrator.start_run(db_session)
    result = orchestrator.run_existing(db_session, run)

    assert result.status == EventRunStatus.COMPLETED.value
    assert result.events_created == 2

    # The orchestrator promoted the accepted events into matchable rules.
    rules = db_session.query(RegulationRule).all()
    assert len(rules) == 2
    assert {rule.target_role.value for rule in rules} == {"student", "staff"}
    assert all(rule.match_type == RuleMatchType.CONTEXTUAL for rule in rules)
    # Fingerprints match their source events, so promotion is traceable.
    event_fps = {e.fingerprint for e in db_session.query(Event).all()}
    assert {rule.fingerprint for rule in rules} == event_fps


def test_promotion_is_idempotent(db_session):
    db_session.add(
        _kb_row(
            "https://www.bilgi.edu.tr/upload/regulation-promote-idem/",
            "Students must complete orientation before classes start.",
        )
    )
    db_session.commit()

    orchestrator = EventPipelineOrchestrator()
    run = orchestrator.start_run(db_session)
    orchestrator.run_existing(db_session, run)

    before = db_session.query(RegulationRule).count()
    stats = promote_events_to_rules(db_session)
    assert stats.promoted == 0
    assert stats.skipped_existing == before
    assert db_session.query(RegulationRule).count() == before


def test_safe_eval_condition_handles_conditions_and_rejects_injection():
    ctx = {"gpa": 1.5, "enrolled_credits": 9, "is_active": True}
    assert safe_eval_condition("gpa < 1.80", ctx) is True
    assert safe_eval_condition("gpa < 1.0", ctx) is False
    assert safe_eval_condition("enrolled_credits < 12", ctx) is True
    assert safe_eval_condition("is_active", ctx) is True
    assert safe_eval_condition("not is_active", ctx) is False
    # missing field, malformed text, and injection attempts all return None
    assert safe_eval_condition("gpa < 1.8", {"gpa": None}) is None
    assert safe_eval_condition("__import__('os').system('x')", ctx) is None
    assert safe_eval_condition("", ctx) is None
