"""E2E tests for the 'My Regulations' endpoints (routes/regulations.py)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import models
from database.session import get_db
from dependencies import get_current_active_user
from routes.regulations import router as regulations_router


def _seed_user_with_rule(db, status=models.AssignmentStatus.ACTIVE):
    user = models.User(
        email="reg@bilgiedu.net", password_hash="x",
        first_name="Reg", last_name="User",
        user_type=models.UserType.STUDENT, is_active=True,
    )
    db.add(user)
    db.flush()

    rule = models.RegulationRule(
        source_doc_url="http://example.com/reg",
        source_chunk_ids=[],
        evidence_quote="Students with GPA below 1.80 must meet their advisor.",
        rule_text="Meet your advisor if your GPA falls below 1.80.",
        applies_to="undergraduate students",
        trigger="GPA below 1.80",
        deadline="within 2 weeks",
        consequence="registration hold",
        authority="faculty board",
        blocking=True,
        target_role=models.EventTargetRole.STUDENT,
        match_type=models.RuleMatchType.SQL,
        status=models.RuleStatus.ACTIVE,
        fingerprint="fp-reg-1",
    )
    db.add(rule)
    db.flush()

    assignment = models.UserRuleAssignment(
        user_id=user.id, rule_id=rule.id,
        match_type=models.RuleMatchType.SQL,
        urgency=models.AssignmentUrgency.HIGH,
        status=status,
        reason="Your GPA is below threshold.",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return user, assignment


def _authed_app(db, user):
    app = FastAPI()
    app.include_router(regulations_router, prefix="/api")

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_active_user] = lambda: user
    return app


def test_regulations_me_lists_assignments(db_session):
    user, _ = _seed_user_with_rule(db_session)
    client = TestClient(_authed_app(db_session, user))
    res = client.get("/api/regulations/me")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["urgency"] == "high"
    assert body[0]["status"] == "active"
    assert "advisor" in body[0]["rule_text"].lower()
    assert body[0]["blocking"] is True


def test_regulations_patch_marks_actioned(db_session):
    user, assignment = _seed_user_with_rule(db_session)
    client = TestClient(_authed_app(db_session, user))
    res = client.patch(
        f"/api/regulations/assignments/{assignment.id}",
        json={"status": "actioned"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "actioned"


def test_regulations_patch_rejects_invalid_status(db_session):
    user, assignment = _seed_user_with_rule(db_session)
    client = TestClient(_authed_app(db_session, user))
    res = client.patch(
        f"/api/regulations/assignments/{assignment.id}",
        json={"status": "banana"},
    )
    assert res.status_code == 400


def test_regulations_patch_unknown_id_404(db_session):
    user, _ = _seed_user_with_rule(db_session)
    client = TestClient(_authed_app(db_session, user))
    res = client.patch(
        "/api/regulations/assignments/00000000-0000-0000-0000-000000000000",
        json={"status": "dismissed"},
    )
    assert res.status_code == 404


def test_regulations_require_auth(db_session):
    app = FastAPI()
    app.include_router(regulations_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: iter([db_session])
    client = TestClient(app)
    assert client.get("/api/regulations/me").status_code in {401, 403}
