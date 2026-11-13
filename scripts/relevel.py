"""C1/C2 dosyalarına yazılmış olup CEFR-J listesinde A1–B2 seviyesi bulunan kelimeleri
CEFR-J seviyesindeki `<seviye>-extra.psv` dosyasına taşır (geliştirme aracı).

    python scripts/relevel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from vocab_tools import cefrj  # noqa: E402

from app.content.text import lemma_key  # noqa: E402

VOCAB = ROOT / "data" / "vocabulary"
HEADER = "#! level: {level}\n#! source: original-cefrj\n#! review_status: auto_checked\n"


def main() -> int:
    reference = cefrj()
    moved: dict[str, list[str]] = {}
    for path in sorted(VOCAB.glob("c[12]-*.psv")):
        kept: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            key = lemma_key(line.split("|")[0]) if "|" in line and not line.startswith("#") else None
            if key and key in reference:
                moved.setdefault(reference[key][0], []).append(line)
            else:
                kept.append(line)
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    for level, lines in sorted(moved.items()):
        target = VOCAB / f"{level.lower()}-extra.psv"
        existing = target.read_text(encoding="utf-8") if target.exists() else HEADER.format(level=level)
        target.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")
        print(f"{level}: {len(lines)} kelime {target.name} dosyasına taşındı")
    return 0


if __name__ == "__main__":
    sys.exit(main())
