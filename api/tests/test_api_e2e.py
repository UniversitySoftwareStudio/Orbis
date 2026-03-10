from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.session import get_db
from routes.auth import router as auth_router
from routes.logout import router as logout_router


def _app_with_db(db_session):
    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    app.include_router(logout_router, prefix="/api")

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    return app


def test_auth_flow_e2e(db_session):
    app = _app_with_db(db_session)
    client = TestClient(app)

    register_payload = {
        "first_name": "Alice",
        "last_name": "Doe",
        "password": "secret123",
        "user_type": "student",
    }
    register = client.post("/api/auth/register", json=register_payload)
    assert register.status_code == 201
    user = register.json()
    assert user["email"] == "a.doe@bilgiedu.net"
    assert user["user_type"] == "student"
    assert "access_token" in register.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "a.doe@bilgiedu.net"

    refresh = client.post("/api/auth/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["email"] == "a.doe@bilgiedu.net"
    assert "access_token" in refresh.cookies

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["message"] == "Successfully logged out"

    me_after_logout = client.get("/api/auth/me")
    assert me_after_logout.status_code == 401


def test_login_e2e(db_session):
    app = _app_with_db(db_session)
    client = TestClient(app)

    register = client.post(
        "/api/auth/register",
        json={
            "first_name": "Bob",
            "last_name": "Stone",
            "password": "pass123",
            "user_type": "instructor",
        },
    )
    assert register.status_code == 201
    email = register.json()["email"]

    client.cookies.clear()
    bad_login = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert bad_login.status_code == 401

    good_login = client.post("/api/auth/login", json={"email": email, "password": "pass123"})
    assert good_login.status_code == 200
    assert good_login.json()["email"] == email
