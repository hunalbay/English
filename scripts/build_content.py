"""data/ altındaki içerik dosyalarından content.db üretir.

Kullanım:  python scripts/build_content.py [--output data/build/content.db]

Aşama 1'de yalnızca sürüm bilgisini içeren iskelet veri tabanı üretilir.
İçerik tabloları ve doğrulayıcı Aşama 2'de eklenecektir.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT_VERSION = "0.1.0"


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        conn.execute("CREATE TABLE content_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.executemany(
            "INSERT INTO content_meta (key, value) VALUES (?, ?)",
            [
                ("content_version", CONTENT_VERSION),
                ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    tmp.replace(output)  # yarım kalmış bir dosya asla content.db olarak kalmaz


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "build" / "content.db")
    args = parser.parse_args(argv)
    build(args.output)
    print(f"content.db üretildi: {args.output} (içerik sürümü {CONTENT_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
