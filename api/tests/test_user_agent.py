from __future__ import annotations

from database import models
from events import user_agent


class _FakeLLM:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    def complete(self, _prompt: str) -> str:
        return self.raw


def _seed_user(db_session):
    user = models.User(
        email="contextual@bilgiedu.net",
        password_hash="x",
        first_name="Contextual",
        last_name="Student",
        user_type=models.UserType.STUDENT,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    db_session.add(
        models.UserProfile(
            user_id=user.id,
            department="Computer Engineering",
            faculty="Faculty of Engineering",
            program_level="undergraduate",
            semester_number=5,
        )
    )
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_contextual_rule(db_session, fingerprint: str = "contextual-fp"):
    rule = models.RegulationRule(
        source_doc_url="https://example.test/regulation",
        source_chunk_ids=[],
        evidence_quote="Students must complete internship paperwork before placement.",
        rule_text="Students must complete internship paperwork before placement.",
        applies_to="students",
        trigger="internship placement",
        deadline=None,
        consequence=None,
        authority=None,
        blocking=False,
        target_role=models.EventTargetRole.STUDENT,
        match_type=models.RuleMatchType.CONTEXTUAL,
        status=models.RuleStatus.ACTIVE,
        confidence="explicit",
        fingerprint=fingerprint,
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


def test_contextual_trace_accepts_index_alias(db_session):
    _seed_contextual_rule(db_session)

    decisions = user_agent._contextual_rule_decisions(
        db_session,
        "Role: student\nProgram level: undergraduate",
        llm_service=_FakeLLM('[{"index": 0, "applies": true, "reason": "The student is in scope."}]'),
    )

    assert len(decisions) == 1
    assert decisions[0]["applies"] is True
    assert decisions[0]["persistable"] is True
    assert "in scope" in decisions[0]["reason"]


def test_contextual_trace_prefers_ui_reason(db_session):
    _seed_contextual_rule(db_session)

    decisions = user_agent._contextual_rule_decisions(
        db_session,
        "Role: student\nProgram level: undergraduate",
        llm_service=_FakeLLM(
            '[{"rule_index": 0, "applies": true, '
            '"reason": "Verbose internal explanation that should not be displayed to the student.", '
            '"ui_reason": "Undergrad student in scope."}]'
        ),
    )

    assert len(decisions) == 1
    assert decisions[0]["applies"] is True
    assert decisions[0]["reason"] == "Undergrad student in scope."


def test_run_for_user_accepts_index_alias_from_contextual_matcher(db_session, monkeypatch):
    user = _seed_user(db_session)
    rule = _seed_contextual_rule(db_session)

    def _fake_call_llm(**_kwargs):
        return [{"index": 0, "applies": True, "ui_reason": "Student profile matches."}], None

    monkeypatch.setattr(user_agent, "_call_llm", _fake_call_llm)

    result = user_agent.run_for_user(db_session, user)

    assert result["total_matched"] == 1
    assert result["new_assignments"] == 1
    assignment = (
        db_session.query(models.UserRuleAssignment)
        .filter(models.UserRuleAssignment.user_id == user.id, models.UserRuleAssignment.rule_id == rule.id)
        .one()
    )
    assert assignment.status == models.AssignmentStatus.ACTIVE


def test_trace_keeps_existing_contextual_assignment_when_agent_omits_decision(db_session, monkeypatch):
    user = _seed_user(db_session)
    rule = _seed_contextual_rule(db_session)
    assignment = models.UserRuleAssignment(
        user_id=user.id,
        rule_id=rule.id,
        match_type=models.RuleMatchType.CONTEXTUAL,
        urgency=models.AssignmentUrgency.LOW,
        status=models.AssignmentStatus.ACTIVE,
        reason="Previously matched.",
    )
    db_session.add(assignment)
    db_session.commit()

    monkeypatch.setattr(user_agent, "get_llm_service", lambda: _FakeLLM("[]"))

    events = list(user_agent.run_for_user_trace(db_session, user))
    db_session.refresh(assignment)

    assert assignment.status == models.AssignmentStatus.ACTIVE
    assert assignment.reason == "Previously matched."
    decision_batches = [
        decision
        for event in events
        if event.get("type") == "rule_decisions"
        for decision in event.get("decisions", [])
    ]
    assert any(decision.get("persistable") is False for decision in decision_batches)
    assert not any(event.get("type") == "assignment" and event.get("action") == "retired" for event in events)
