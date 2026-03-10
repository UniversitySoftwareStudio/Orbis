from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.models import User, UserType
from database.session import get_db
from dependencies import get_current_active_user
import routes.search as search_routes


class _StressRAG:
    def process_query(self, message, _db):
        yield f"ok:{message}"

    def search_courses(self, q, _db, _limit):
        return ([{"id": "1", "title": q, "url": None, "code": "CS", "type": "course", "score": 1.0, "snippet": q}], {"total": 1.0})

    def stream_answer(self, q, _db, _limit):
        def _gen():
            yield q

        return _gen(), []


def _search_app():
    app = FastAPI()
    app.include_router(search_routes.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: iter([object()])
    app.dependency_overrides[get_current_active_user] = lambda: User(
        id=1,
        email="s@bilgiedu.net",
        password_hash="x",
        first_name="S",
        last_name="T",
        user_type=UserType.STUDENT,
        is_active=True,
    )
    search_routes.rag = _StressRAG()
    return app


def test_stress_search_concurrent():
    app = _search_app()

    def _req(i: int) -> int:
        client = TestClient(app)
        res = client.get("/api/search", params={"q": f"q{i}", "limit": 3})
        return res.status_code

    total = 200
    with ThreadPoolExecutor(max_workers=30) as pool:
        futures = [pool.submit(_req, i) for i in range(total)]
        statuses = [f.result() for f in as_completed(futures)]

    assert len(statuses) == total
    assert all(code == 200 for code in statuses)
