from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings, load_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from scripts.build_content import build as build_content  # noqa: E402

BASE_URL = "http://127.0.0.1:8765"


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    content_db = tmp_path / "content" / "content.db"
    build_content(content_db)
    return load_settings(data_dir=tmp_path / "userdata", content_db_path=content_db)


@pytest.fixture()
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app, base_url=BASE_URL) as test_client:
        yield test_client


@pytest.fixture()
def auth(client) -> dict[str, str]:
    token = client.get("/api/v1/session").json()["token"]
    return {"X-EM-Token": token}
