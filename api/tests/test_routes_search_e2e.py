import json
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.models import User, UserType
from database.session import get_db
from dependencies import get_current_active_user
from routes import search as search_routes


class _FakeRAG:
    def process_query(self, message, _db):
        yield f"chunk:{message}:1"
        yield f"chunk:{message}:2"

    def search_courses(self, q, _db, limit):
        return (
            [{"id": "1", "title": "Course", "url": None, "code": "CS101", "type": "course", "score": 0.9, "snippet": q}],
            {"total": 1.2, "limit": float(limit)},
        )

    def stream_answer(self, q, _db, limit):
        def _gen():
            yield f"answer:{q}:{limit}:1"
            yield f"answer:{q}:{limit}:2"

        return _gen(), [{"id": "1", "title": "Course", "url": None, "code": "CS101", "type": "course", "score": 0.9}]


def _app():
    app = FastAPI()
    app.include_router(search_routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: iter([object()])
    app.dependency_overrides[get_current_active_user] = lambda: User(
        id=1,
        email="x@bilgiedu.net",
        password_hash="x",
        first_name="X",
        last_name="Y",
        user_type=UserType.STUDENT,
        is_active=True,
    )
    return app


def test_chat_streams_chunks(monkeypatch):
    monkeypatch.setattr(search_routes, "rag", _FakeRAG())
    client = TestClient(_app())
    res = client.post("/api/chat", json={"message": "hello"})
    assert res.status_code == 200
    assert "chunk:hello:1" in res.text
    assert "chunk:hello:2" in res.text
    assert res.headers["content-type"].startswith("text/event-stream")


def test_search_returns_payload(monkeypatch):
    monkeypatch.setattr(search_routes, "rag", _FakeRAG())
    client = TestClient(_app())
    res = client.get("/api/search", params={"q": "algorithms", "limit": 3})
    assert res.status_code == 200
    payload = res.json()
    assert payload["query"] == "algorithms"
    assert payload["count"] == 1
    assert payload["results"][0]["code"] == "CS101"
    assert payload["timings_ms"]["limit"] == 3.0


def test_ask_streams_courses_chunks_done(monkeypatch):
    monkeypatch.setattr(search_routes, "rag", _FakeRAG())
    client = TestClient(_app())
    res = client.get("/api/ask", params={"q": "oop", "limit": 2})
    assert res.status_code == 200
    lines = [line.removeprefix("data: ") for line in res.text.splitlines() if line.startswith("data: ")]
    events = [json.loads(line) for line in lines]
    assert events[0]["type"] == "courses"
    assert events[1] == {"type": "chunk", "text": "answer:oop:2:1"}
    assert events[2] == {"type": "chunk", "text": "answer:oop:2:2"}
    assert events[3] == {"type": "done"}


def test_search_requires_auth():
    app = FastAPI()
    app.include_router(search_routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: iter([object()])
    client = TestClient(app)
    res = client.get("/api/search", params={"q": "x"})
    assert res.status_code in {401, 403}
