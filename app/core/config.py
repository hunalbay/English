"""Uygulama yapılandırması ve dosya yolları.

Kullanıcı verisi kurulum klasöründen bağımsızdır: Windows'ta
%LOCALAPPDATA%\\EnglishMaster altında tutulur. Eğitim içeriği (content.db)
ise uygulamayla birlikte gelir ve salt okunurdur.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from app.core.license_keys import PUBLIC_KEYS

APP_NAME = "EnglishMaster"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

ENV_DATA_DIR = "ENGLISH_MASTER_DATA_DIR"
ENV_CONTENT_DB = "ENGLISH_MASTER_CONTENT_DB"
ENV_AUDIO_DIR = "ENGLISH_MASTER_AUDIO_DIR"


def resource_root() -> Path:
    """Paketle gelen salt okunur dosyaların kökü (frontend, migrations, içerik)."""
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def default_data_dir() -> Path:
    """Kullanıcı verisinin tutulacağı klasör (işletim sistemine göre)."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    content_db_path: Path
    audio_dir: Path
    frontend_dir: Path
    migrations_dir: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    # Lisans anahtarlarını doğrulayan açık anahtarlar (app/core/license_keys.py).
    license_public_keys: tuple[str, ...] = PUBLIC_KEYS
    # Yalnızca testler içindir; ortam değişkeniyle değiştirilemez.
    machine_id_override: str | None = None

    @property
    def user_db_path(self) -> Path:
        return self.data_dir / "user.db"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def license_path(self) -> Path:
        return self.data_dir / "license.json"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.backups_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings(
    data_dir: Path | None = None,
    content_db_path: Path | None = None,
    port: int = DEFAULT_PORT,
) -> Settings:
    root = resource_root()
    content_override = os.environ.get(ENV_CONTENT_DB)
    audio_override = os.environ.get(ENV_AUDIO_DIR)
    return Settings(
        data_dir=data_dir or default_data_dir(),
        content_db_path=content_db_path
        or (Path(content_override) if content_override else root / "data" / "build" / "content.db"),
        audio_dir=Path(audio_override) if audio_override else root / "data" / "audio",
        frontend_dir=root / "frontend",
        migrations_dir=root / "migrations",
        port=port,
    )
