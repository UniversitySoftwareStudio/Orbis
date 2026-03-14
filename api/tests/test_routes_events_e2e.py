from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.models import User, UserType
from database.session import get_db
from dependencies import require_admin
from routes import events as events_routes


def _app(db_session):
    app = FastAPI()
    app.include_router(events_routes.router, prefix="/api")

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[require_admin] = lambda: User(
        id=1,
        email="admin@bilgi.edu.tr",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    return app


def test_trigger_creates_run_and_status_endpoint_reads_it(db_session, monkeypatch):
    monkeypatch.setattr(events_routes, "_run_pipeline_background", lambda run_id: None)
    client = TestClient(_app(db_session))

    trigger = client.post("/api/events/trigger")
    assert trigger.status_code == 200
    payload = trigger.json()
    assert payload["status"] == "running"
    assert payload["run_id"]

    status = client.get(f"/api/events/runs/{payload['run_id']}")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["run_id"] == payload["run_id"]
    assert status_payload["status"] in {"running", "completed", "failed"}
    assert "events_pending" in status_payload
    assert "events_needs_review" in status_payload

    telemetry = client.get(f"/api/events/runs/{payload['run_id']}/telemetry")
    assert telemetry.status_code == 200
    telemetry_payload = telemetry.json()
    assert len(telemetry_payload) >= 1
    assert telemetry_payload[0]["agent"] == "orchestrator"

    candidates = client.get(f"/api/events/runs/{payload['run_id']}/candidates")
    assert candidates.status_code == 200
    assert isinstance(candidates.json(), list)


def test_run_status_returns_not_found_for_missing_run(db_session):
    client = TestClient(_app(db_session))
    response = client.get("/api/events/runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_found"
