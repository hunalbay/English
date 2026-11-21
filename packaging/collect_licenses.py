"""Pakete giren üçüncü taraf bileşenlerin lisans metinlerini build/licenses/ klasörüne toplar.

Lisanslar kurulu paketlerin kendi meta verilerinden (dist-info) okunur; elle yazılmaz.
Kullanım: python packaging/collect_licenses.py
"""

from __future__ import annotations

import shutil
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "licenses"

# Çalışma zamanında pakete giren dağıtımlar (requirements.txt ve onların bağımlılıkları)
RUNTIME = ["fastapi", "starlette", "pydantic", "pydantic-core", "typing-extensions", "typing-inspection",
           "annotated-types", "annotated-doc", "anyio", "idna", "sniffio", "uvicorn", "h11", "click",
           "SQLAlchemy", "greenlet", "alembic", "Mako", "MarkupSafe", "cryptography", "cffi", "pycparser"]
if sys.platform == "win32":
    RUNTIME += ["pystray", "six", "pillow", "colorama"]

LICENSE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    summary = []
    missing = []
    for name in RUNTIME:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue  # bu platformda kurulu değil (ör. greenlet yalnızca bazı sistemlerde)
        meta = dist.metadata
        license_name = meta.get("License-Expression") or meta.get("License") or ""
        if len(license_name) > 80 or not license_name.strip():
            classifiers = [c.split(" :: ")[-1] for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
            license_name = ", ".join(classifiers) or "(meta veride belirtilmemiş)"
        files = [f for f in dist.files or [] if Path(str(f)).name.upper().startswith(LICENSE_NAMES)]
        target = OUT / f"{meta['Name']}-{dist.version}"
        target.mkdir()
        for file in files:
            source = Path(dist.locate_file(file))
            if source.is_file():
                shutil.copyfile(source, target / Path(str(file)).name)
        if not files:
            missing.append(meta["Name"])
        summary.append(f"{meta['Name']} {dist.version} — {license_name}")

    notice = (ROOT / "packaging" / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    (OUT / "THIRD_PARTY_NOTICES.txt").write_text(
        notice + "\n\nPakete giren Python bileşenleri (sürüm — lisans):\n" + "\n".join(f"  - {line}" for line in summary) + "\n",
        encoding="utf-8",
    )
    # Kurulum sihirbazındaki sözleşme sayfası: NSIS düz metni UTF-16 (BOM'lu) olarak en güvenilir okur.
    eula = (ROOT / "packaging" / "EULA.txt").read_text(encoding="utf-8")
    (OUT / "EULA.txt").write_text(eula, encoding="utf-8")
    (ROOT / "build" / "EULA-installer.txt").write_text(eula.replace("\n", "\r\n"), encoding="utf-16")
    print(f"{len(summary)} bileşenin lisansı toplandı: {OUT}")
    if missing:
        print("Lisans dosyası bulunamayanlar (meta veri özeti yazıldı):", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
