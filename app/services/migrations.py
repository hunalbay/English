"""user.db şema güncellemeleri.

Mevcut bir veri tabanı yükseltilmeden önce yedeklenir. Yükseltme başarısız
olursa yedek geri konur ve hata yukarı iletilir; kullanıcı verisi kaybolmaz.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import Settings
from app.core.logging import get_logger
from app.database.user_db import sqlite_url

log = get_logger("migrations")


class MigrationError(RuntimeError):
    """Şema güncellemesi başarısız oldu; veri tabanı önceki hâline döndürüldü."""


def alembic_config(settings: Settings) -> Config:
    config = Config()
    config.set_main_option("script_location", settings.migrations_dir.as_posix())
    config.set_main_option("sqlalchemy.url", sqlite_url(settings.user_db_path).replace("%", "%%"))
    return config


def head_revision(settings: Settings) -> str | None:
    return ScriptDirectory.from_config(alembic_config(settings)).get_current_head()


def current_revision(db_path: Path) -> str | None:
    if not db_path.is_file():
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def backup_database(db_path: Path, backups_dir: Path, label: str) -> Path:
    """SQLite yedekleme API'siyle tutarlı bir kopya alır (WAL içeriği dâhil)."""
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = backups_dir / f"user-{label}-{stamp}.db"
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def _restore(backup: Path, db_path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    shutil.copyfile(backup, db_path)


def run_migrations(settings: Settings) -> str | None:
    """Veri tabanını en güncel şemaya getirir; güncel revizyonu döndürür."""
    settings.ensure_dirs()
    db_path = settings.user_db_path
    head = head_revision(settings)
    current = current_revision(db_path)
    if current == head and db_path.is_file():
        return head

    backup: Path | None = None
    existed = db_path.is_file()
    if existed:
        backup = backup_database(db_path, settings.backups_dir, f"pre-migration-{current or 'none'}")
        log.info("Şema güncellemesi öncesi yedek alındı: %s", backup.name)

    try:
        command.upgrade(alembic_config(settings), "head")
    except Exception as exc:
        log.exception("Şema güncellemesi başarısız oldu")
        if backup is not None:
            _restore(backup, db_path)
            log.info("Veri tabanı yedekten geri yüklendi")
        elif not existed:
            db_path.unlink(missing_ok=True)
        raise MigrationError("Veri tabanı güncellenemedi; verileriniz önceki hâliyle korundu.") from exc

    log.info("Şema revizyonu: %s -> %s", current, head)
    return head
