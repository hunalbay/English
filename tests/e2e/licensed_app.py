"""Uçtan uca testler için başlatıcı: programı test açık anahtarıyla çalıştırır.

Yalnızca testlerde kullanılır; Windows paketine girmez. Gerçek programda açık
anahtar listesi koda gömülüdür ve ortam değişkeniyle değiştirilemez.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app.core.license_keys as license_keys  # noqa: E402
import app.core.machine as machine  # noqa: E402

license_keys.PUBLIC_KEYS = (os.environ["EM_TEST_PUBLIC_KEY"],)
machine.machine_id = lambda _data_dir: os.environ["EM_TEST_MACHINE_ID"]

from app.launcher import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
