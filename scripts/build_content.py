"""data/ altındaki içerik dosyalarını doğrular ve content.db üretir.

Kullanım:
    python scripts/build_content.py            # doğrula ve üret
    python scripts/build_content.py --check    # yalnızca doğrula
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.content import builder  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "build" / "content.db")
    parser.add_argument("--check", action="store_true", help="Yalnızca doğrula, dosya üretme")
    args = parser.parse_args(argv)

    try:
        if args.check:
            content = builder.load(args.data)
            print(f"İçerik geçerli: {len(content.lessons)} ders, {len(content.words)} benzersiz temel kelime")
            return 0
        counts = builder.build(args.data, args.output)
    except builder.ContentError as exc:
        print(f"İçerik doğrulanamadı — {len(exc.errors)} hata:", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"content.db üretildi: {args.output} (içerik sürümü {builder.CONTENT_VERSION})")
    for table, count in counts.items():
        print(f"  {table}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
