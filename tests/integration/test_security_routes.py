"""Güvenlik denetimleri: bütün uçlar otomatik olarak taranır (yeni uç eklendiğinde de geçerlidir)."""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

API = "/api/v1"
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
SECURITY_HEADERS = ("Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Cross-Origin-Resource-Policy")


def _routes(app):
    """(yol, yöntemler) çiftleri. Yeni FastAPI sürümlerindeki iç içe yönlendiricileri de açar."""
    for route in app.routes:
        if isinstance(route, APIRoute):
            candidates = [("", route)]
        elif hasattr(route, "original_router"):
            prefix = route.include_context.prefix
            candidates = [(prefix, sub) for sub in route.original_router.routes if isinstance(sub, APIRoute)]
        else:
            continue
        for prefix, sub in candidates:
            path = prefix + sub.path
            if path.startswith(API):
                yield path, sub.methods


def _concrete(path: str) -> str:
    """Yol parametrelerini geçerli biçimli örnek değerlerle doldurur."""
    return (path.replace("{session_id}", "1").replace("{lesson_id}", "gram.a1.to-be-present")
            .replace("{word_id}", "word.book").replace("{code}", "A1").replace("{track}", "reading")
            .replace("{form}", "books").replace("{id}", "1"))


def test_every_mutating_endpoint_requires_token(app, client):
    checked = 0
    for path, methods in _routes(app):
        for method in methods & MUTATING:
            response = client.request(method, _concrete(path), json={})
            assert response.status_code == 403, f"{method} {path} belirteçsiz kabul edildi"
            assert response.json()["error"]["code"] == "invalid_token"
            checked += 1
    assert checked >= 15


def test_wrong_token_is_rejected(client):
    response = client.put(f"{API}/profile/level", json={"level": "A2"}, headers={"X-EM-Token": "x" * 43})
    assert response.status_code == 403


def test_get_endpoints_do_not_change_state(app, client):
    """GET istekleri hiçbir kaydı değiştirmemelidir (belirteç gerektirmedikleri için)."""
    before = client.get(f"{API}/dashboard").json()
    count = 0
    for path, methods in _routes(app):
        if "GET" in methods:
            client.get(_concrete(path))
            count += 1
    assert count >= 20
    after = client.get(f"{API}/dashboard").json()
    assert before == after


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1.evil.example", "192.168.1.5", "[::1]", ""])
def test_foreign_host_header_rejected(app, host):
    with TestClient(app, base_url="http://127.0.0.1:8765") as other:
        response = other.get(f"{API}/session", headers={"host": host})
        assert response.status_code == 400
        assert "token" not in response.text


@pytest.mark.parametrize("path", [
    "/../app/main.py", "/%2e%2e/app/main.py", "/scripts/../../app/core/security.py",
    "/media/clips/../manifest.json", "/media/clips/%2e%2e/%2e%2e/build/content.db",
    "/media/clips/..%2f..%2fbuild%2fcontent.db", "/data/build/content.db", "/.git/config",
])
def test_static_paths_cannot_escape(client, path):
    response = client.get(path)
    assert response.status_code == 404, path
    assert b"SQLite format" not in response.content and b"import" not in response.content[:200]


def test_security_headers_on_pages_api_and_media(client):
    media = client.get(f"{API}/vocabulary/word.book").json()["audio"]["url"]
    for path in ("/", f"{API}/levels", media, "/yok"):
        response = client.get(path)
        for header in SECURITY_HEADERS:
            assert header in response.headers, (path, header)
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
    assert client.get(f"{API}/levels").headers["Cache-Control"] == "no-store"


def test_api_documentation_is_not_exposed(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_validation_errors_do_not_leak_internals(client, auth):
    response = client.post(f"{API}/tests/sessions", json={"size": "çok"}, headers=auth)
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "validation_error", "message": "Gönderilen veri geçersiz."}}
    response = client.post(f"{API}/tests/sessions/1/answers", content=b"{bozuk json", headers={**auth, "content-type": "application/json"})
    assert response.status_code == 422 and "Traceback" not in response.text


def test_oversized_answers_are_rejected(client, auth):
    test = client.post(f"{API}/tests/sessions", json={"lesson_id": "write.a1.introducing-yourself", "seed": 1}, headers=auth).json()
    task = next(q for q in test["questions"] if q["type"] == "written_answer")
    response = client.post(f"{API}/tests/sessions/{test['session_id']}/answers",
                           json={"question_id": task["id"], "answer": "a" * 5000}, headers=auth)
    assert response.status_code == 422


def test_search_handles_hostile_input(client):
    for query in ['"', "*", "OR AND NOT", "a" * 200, "'; DROP TABLE vocabulary; --", "NEAR(", "\u0000", "üğışçö"]:
        response = client.get(f"{API}/search", params={"q": query})
        assert response.status_code in (200, 422), query
    assert client.get(f"{API}/vocabulary", params={"q": "'; DROP TABLE vocabulary; --"}).status_code == 200
    assert client.get(f"{API}/vocabulary?page_size=1").json()["total"] >= 5000
