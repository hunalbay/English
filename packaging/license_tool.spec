# Lisans aracı (yalnızca program sahibi için): `pyinstaller packaging/license_tool.spec --noconfirm`
# Çıktı: tek dosya, konsol programı. Kurulum paketine GİRMEZ; ayrı bir yapıt olarak üretilir.
# Araç gizli anahtar içermez; gizli anahtar sahibinin bilgisayarında, araç ilk çalıştırıldığında üretilir.
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821
sys.path.insert(0, str(ROOT))

a = Analysis(  # noqa: F821
    [str(ROOT / "scripts" / "license_tool.py")],
    pathex=[str(ROOT)],
    hiddenimports=["app.core.license_format", "app.core.license_keys"],
    excludes=["tkinter", "pytest", "yaml", "fastapi", "starlette", "uvicorn", "sqlalchemy", "alembic", "pydantic",
              "PIL", "pystray"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="EnglishMaster-LisansAraci",
    console=True,
    upx=False,
)
