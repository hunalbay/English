"""Lisans kilidi ve lisans / geri bildirim uçları."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import BASE_URL

API = "/api/v1"


@pytest.fixture()
def locked(unlicensed_settings):
    with TestClient(create_app(unlicensed_settings), base_url=BASE_URL) as client:
        client.headers["X-EM-Token"] = client.get(f"{API}/session").json()["token"]
        yield client


def test_without_license_learning_api_is_locked(locked):
    for path in ("/levels", "/lessons/gram.a1.to-be-present", "/vocabulary/word.book", "/dashboard",
                 "/profile", "/reports/progress", "/search?q=book"):
        response = locked.get(API + path)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "license_required"
    assert locked.put(f"{API}/profile/level", json={"level": "A1"}).json()["error"]["code"] == "license_required"


def test_without_license_the_license_screen_still_works(locked, signer):
    assert locked.get(f"{API}/health").json()["status"] == "ok"
    assert locked.get(f"{API}/settings").status_code == 200
    assert locked.put(f"{API}/settings/theme", json={"value": "dark"}).status_code == 200
    status = locked.get(f"{API}/license").json()
    assert status["state"] == "missing" and not status["licensed"]
    assert status["machine_code"] == signer.machine_code
    assert status["contact_email"] == "onurgulcicek@hotmail.com"
    feedback = locked.get(f"{API}/feedback").json()
    assert feedback["email"] == "onurgulcicek@hotmail.com"
    assert "Seviye" not in feedback["diagnostics"]
    assert locked.get("/").status_code == 200  # arayüz açılır


def test_installing_a_key_unlocks_the_program(locked, signer):
    bad = locked.post(f"{API}/license", json={"key": "EM1.yanlis.anahtar"})
    assert bad.status_code == 422 and "anahtar" in bad.json()["error"]["message"]
    expires = date.today() + timedelta(days=60)
    ok = locked.post(f"{API}/license", json={"key": signer.key(expires=expires, name="Ayşe")})
    assert ok.status_code == 200
    body = ok.json()
    assert body["licensed"] and body["name"] == "Ayşe" and body["expires"] == expires.isoformat()
    assert body["days_left"] == 60 and not body["warn"]
    assert locked.get(f"{API}/levels").status_code == 200
    feedback = locked.get(f"{API}/feedback").json()["diagnostics"]
    assert feedback["Lisans durumu"].startswith("geçerli") and feedback["Tamamlanan ders"] == "0"


def test_license_install_requires_session_token(unlicensed_settings, signer):
    with TestClient(create_app(unlicensed_settings), base_url=BASE_URL) as client:
        response = client.post(f"{API}/license", json={"key": signer.key()})
        assert response.status_code == 403 and response.json()["error"]["code"] == "invalid_token"


def test_oversized_key_is_rejected(locked):
    assert locked.post(f"{API}/license", json={"key": "x" * 5000}).status_code == 422


def test_expired_license_locks_again_but_keeps_user_data(unlicensed_settings, signer):
    import json

    unlicensed_settings.data_dir.mkdir(parents=True, exist_ok=True)
    yesterday = date.today() - timedelta(days=1)
    key = signer.key(expires=yesterday, issued=yesterday - timedelta(days=90))
    unlicensed_settings.license_path.write_text(json.dumps({"key": key}), encoding="utf-8")
    with TestClient(create_app(unlicensed_settings), base_url=BASE_URL) as client:
        status = client.get(f"{API}/license").json()
        assert status["state"] == "expired" and "korunuyor" in status["message"]
        assert client.get(f"{API}/levels").json()["error"]["code"] == "license_required"
    assert unlicensed_settings.user_db_path.is_file()


def test_every_endpoint_except_the_open_ones_is_locked(locked):
    """Yeni eklenen uçlar da otomatik olarak lisans kilidine girer."""
    from app.core.license_gate import OPEN_PATHS, OPEN_PREFIXES
    from tests.integration.test_security_routes import _concrete, _routes

    checked = 0
    for path, methods in _routes(locked.app):
        rest = path[len(API):]
        if rest in OPEN_PATHS or rest.startswith(OPEN_PREFIXES):
            continue
        for method in methods:
            response = locked.request(method, _concrete(path), json={})
            assert response.status_code == 403, f"{method} {path} lisanssız açıldı"
            assert response.json()["error"]["code"] == "license_required"
            checked += 1
    assert checked >= 30
