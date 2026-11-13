from fastapi.testclient import TestClient

from app import __version__
from app.core.config import load_settings
from app.main import create_app
from tests.conftest import BASE_URL


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["content"]["available"] is True
    assert body["content"]["version"]
    assert body["user_db"]["schema_revision"] == "0002"
    assert response.headers["cache-control"] == "no-store"


def test_health_reports_missing_content(tmp_path):
    settings = load_settings(data_dir=tmp_path / "u", content_db_path=tmp_path / "yok.db")
    with TestClient(create_app(settings), base_url=BASE_URL) as client:
        assert client.get("/api/v1/health").json()["content"] == {
            "available": False, "version": None, "built_at": None,
        }


def test_frontend_is_served_with_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "English Master" in response.text
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in response.headers


def test_foreign_host_header_rejected(client):
    for host in ("evil.example.com", "evil.example.com:8765", "192.168.1.10:8765", ""):
        response = client.get("/api/v1/health", headers={"Host": host})
        assert response.status_code == 400, host
        assert response.json()["error"]["code"] == "invalid_host"


def test_localhost_host_header_allowed(client):
    assert client.get("/api/v1/health", headers={"Host": "localhost:8765"}).status_code == 200


def test_write_requires_token(client):
    response = client.put("/api/v1/settings/theme", json={"value": "dark"})
    assert response.status_code == 403
    response = client.put("/api/v1/settings/theme", json={"value": "dark"}, headers={"X-EM-Token": "yanlis"})
    assert response.status_code == 403
    assert client.get("/api/v1/settings").json()["settings"]["theme"] == "system"


def test_settings_roundtrip(client, auth):
    response = client.put("/api/v1/settings/daily_goal_minutes", json={"value": 45}, headers=auth)
    assert response.status_code == 200
    assert response.json() == {"key": "daily_goal_minutes", "value": 45}
    assert client.get("/api/v1/settings").json()["settings"]["daily_goal_minutes"] == 45


def test_settings_validation_errors_are_turkish_and_safe(client, auth):
    response = client.put("/api/v1/settings/theme", json={"value": "pink"}, headers=auth)
    assert response.status_code == 422
    assert "Tema" in response.json()["error"]["message"]
    assert client.put("/api/v1/settings/yok", json={"value": 1}, headers=auth).status_code == 404
    response = client.put("/api/v1/settings/theme", content=b"{bozuk", headers={**auth, "Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_api_path_returns_json_404(client):
    response = client.get("/api/v1/yok")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_404"


def test_settings_survive_restart(settings):
    with TestClient(create_app(settings), base_url=BASE_URL) as first:
        token = first.get("/api/v1/session").json()["token"]
        first.put("/api/v1/settings/theme", json={"value": "dark"}, headers={"X-EM-Token": token})
    with TestClient(create_app(settings), base_url=BASE_URL) as second:
        assert second.get("/api/v1/settings").json()["settings"]["theme"] == "dark"
        # yeniden başlatmada belirteç değişir; eski belirteç geçersizdir
        assert second.get("/api/v1/session").json()["token"] != token


def test_unexpected_error_does_not_leak_details(settings):
    app = create_app(settings)

    @app.get("/api/v1/_boom")
    def boom():
        raise RuntimeError("gizli-ayrinti /home/user/secret")

    # test rotasını genel /api yakalayıcısının önüne al
    routes = app.router.routes
    routes.insert(0, routes.pop(next(i for i, r in enumerate(routes) if getattr(r, "path", "") == "/api/v1/_boom")))
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "gizli-ayrinti" not in response.text
    assert "gizli-ayrinti" in (settings.logs_dir / "app.log").read_text(encoding="utf-8")


def test_shutdown_unavailable_without_launcher(client, auth):
    assert client.post("/api/v1/system/shutdown").status_code == 403
    assert client.post("/api/v1/system/shutdown", headers=auth).status_code == 409


def test_openapi_docs_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
