"""İçerik veri tabanı (content.db): salt okunur eğitim içeriği.

Bu dosya `scripts/build_content.py` ile `data/` altındaki kaynak dosyalardan
üretilir ve uygulamayla birlikte dağıtılır. Uygulama bu dosyaya hiç yazmaz.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ContentStatus:
    available: bool
    version: str | None = None
    built_at: str | None = None


def connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def read_content_status(path: Path) -> ContentStatus:
    if not path.is_file():
        return ContentStatus(available=False)
    try:
        conn = connect_readonly(path)
        try:
            rows = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM content_meta")}
        finally:
            conn.close()
    except sqlite3.Error:
        return ContentStatus(available=False)
    return ContentStatus(
        available=True,
        version=rows.get("content_version"),
        built_at=rows.get("built_at"),
    )
