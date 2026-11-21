# PyInstaller tanımı: `pyinstaller packaging/english_master.spec --noconfirm`
# Çıktı: dist/EnglishMaster/ (tek klasör; kurulum paketi bu klasörü kurar).
# Önce içerik veri tabanı üretilmiş olmalıdır: python scripts/build_content.py
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (PyInstaller tanımlar)
sys.path.insert(0, str(ROOT))
from app import __version__  # noqa: E402

content_db = ROOT / "data" / "build" / "content.db"
if not content_db.is_file():
    raise SystemExit("data/build/content.db yok. Önce: python scripts/build_content.py")

WINDOWS = sys.platform == "win32"
icon_path = ROOT / "build" / "icon.ico"
if WINDOWS:
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    from app.core.icon import write_ico
    write_ico(icon_path)

datas = [
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / "migrations"), "migrations"),
    (str(content_db), "data/build"),
    (str(ROOT / "data" / "audio" / "clips"), "data/audio/clips"),
    (str(ROOT / "data" / "audio" / "manifest.json"), "data/audio"),
    (str(ROOT / "build" / "licenses"), "licenses"),
    (str(ROOT / "docs" / "AUDIO.md"), "docs"),
]

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("app")
    + ["sqlalchemy.dialects.sqlite", "alembic.runtime.migration", "alembic.ddl.sqlite"]
)
if WINDOWS:
    hiddenimports += ["pystray._win32", "PIL.Image", "PIL.ImageDraw"]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "yaml", "httpx", "IPython", "numpy"],
    # pystray LGPL-3.0 lisanslıdır: derlenmiş arşive değil, kullanıcının değiştirebileceği
    # kaynak dosyaları olarak pakete konur (_internal/pystray/).
    module_collection_mode={"pystray": "py"},
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

version_file = None
if WINDOWS:
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )
    numbers = tuple(int(part) for part in __version__.split(".")) + (0,) * (4 - len(__version__.split(".")))
    version_file = VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[
            StringFileInfo([StringTable("041f04b0", [
                StringStruct("ProductName", "English Master"),
                StringStruct("FileDescription", "English Master - çevrimdışı İngilizce eğitim programı"),
                StringStruct("FileVersion", __version__),
                StringStruct("ProductVersion", __version__),
                StringStruct("OriginalFilename", "EnglishMaster.exe"),
                StringStruct("InternalName", "EnglishMaster"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x041F, 1200])]),
        ],
    )

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EnglishMaster",
    console=False,          # pencereli: konsol penceresi açılmaz
    icon=str(icon_path) if WINDOWS else None,
    version=version_file,
    upx=False,              # UPX bazı virüs tarayıcılarında yanlış alarma yol açar
)
coll = COLLECT(exe, a.binaries, a.datas, name="EnglishMaster", upx=False)  # noqa: F821
