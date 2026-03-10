from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.session import get_db
from routes.auth import router as auth_router
from routes.logout import router as logout_router
from tests.conftest import SessionLocal


def _app():
    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    app.include_router(logout_router, prefix="/api")

    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    return app


def test_register_duplicate_returns_400():
    client = TestClient(_app())
    payload = {"first_name": "Jane", "last_name": "Doe", "password": "secret123", "user_type": "student"}
    first = client.post("/api/auth/register", json=payload)
    second = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 400
    assert "already exists" in second.json()["detail"].lower()


def test_register_blank_names_returns_400():
    client = TestClient(_app())
    res = client.post(
        "/api/auth/register",
        json={"first_name": "   ", "last_name": "Doe", "password": "secret123", "user_type": "student"},
    )
    assert res.status_code == 400
    assert "required" in res.json()["detail"].lower()


def test_me_refresh_logout_unauthorized_without_cookie():
    client = TestClient(_app())
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/refresh").status_code == 401
    assert client.post("/api/auth/logout").status_code == 401


def test_login_stress_concurrent():
    app = _app()
    setup_client = TestClient(app)
    register = setup_client.post(
        "/api/auth/register",
        json={"first_name": "Stress", "last_name": "User", "password": "secret123", "user_type": "student"},
    )
    assert register.status_code == 201
    email = register.json()["email"]

    def _login_once() -> int:
        client = TestClient(app)
        res = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
        return res.status_code

    total = 120
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(_login_once) for _ in range(total)]
        statuses = [f.result() for f in as_completed(futures)]

    assert len(statuses) == total
    assert all(code == 200 for code in statuses)
