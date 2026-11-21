from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings, load_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.content import builder  # noqa: E402
from app.core import license_format  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

BASE_URL = "http://127.0.0.1:8765"
TEST_MACHINE_ID = "test-machine-0001"


class Signer:
    """Testler için geçici bir lisans imzalayıcısı (gerçek gizli anahtar kullanılmaz)."""

    def __init__(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.public_text = license_format.public_key_text(self.private_key.public_key())
        self.machine_code = license_format.machine_code_from_id(TEST_MACHINE_ID)

    def key(self, expires: date | None = None, machine_code: str | None = None, name: str = "Test Kullanıcı",
            issued: date | None = None) -> str:
        issued = issued or date.today()
        data = license_format.new_license(
            machine_code or self.machine_code, name, expires or issued + timedelta(days=365), issued
        )
        return license_format.sign(data, self.private_key)


@pytest.fixture(scope="session")
def signer() -> Signer:
    return Signer()


@pytest.fixture(scope="session")
def content_db(tmp_path_factory) -> Path:
    """Depodaki gerçek içerikten üretilmiş content.db (oturum boyunca bir kez)."""
    path = tmp_path_factory.mktemp("content") / "content.db"
    builder.build(ROOT / "data", path)
    return path


@pytest.fixture()
def unlicensed_settings(tmp_path: Path, content_db: Path, signer: Signer) -> Settings:
    """Test açık anahtarıyla yapılandırılmış, henüz lisans girilmemiş kurulum."""
    base = load_settings(data_dir=tmp_path / "userdata", content_db_path=content_db)
    return replace(base, license_public_keys=(signer.public_text,), machine_id_override=TEST_MACHINE_ID)


@pytest.fixture()
def settings(unlicensed_settings: Settings, signer: Signer) -> Settings:
    """Geçerli lisansı kurulu kurulum (testlerin çoğu bunu kullanır)."""
    unlicensed_settings.data_dir.mkdir(parents=True, exist_ok=True)
    unlicensed_settings.license_path.write_text(json.dumps({"key": signer.key()}), encoding="utf-8")
    return unlicensed_settings


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
