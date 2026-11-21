"""Paketlenmiş program (EnglishMaster.exe) giriş noktası."""

import sys

# Pencereli (konsolsuz) Windows paketinde stdout / stderr yoktur. Yazma girişimleri sessizce yok sayılsın.
if sys.stdout is None or sys.stderr is None:
    import io

    sys.stdout = sys.stdout or io.StringIO()
    sys.stderr = sys.stderr or io.StringIO()

from app.launcher import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
