"""English Master lisans aracı — yalnızca program sahibinin bilgisayarında çalışır.

Komutlar:
    init                         İmza anahtar çiftini bir kez oluşturur.
    issue --kod K --isim A --bitis TARİH
                                 Bir bilgisayar için lisans anahtarı üretir.
    check ANAHTAR                Bir anahtarın içeriğini gösterir.
Komut verilmezse (ör. çift tıklanınca) Türkçe menü açılır.

Gizli anahtar (private_key.pem) varsayılan olarak kullanıcı klasöründeki
"EnglishMaster-Lisans" klasöründe tutulur. Bu dosyayı kimseyle paylaşmayın,
GitHub'a koymayın ve bir yedeğini (ör. USB bellekte) saklayın: kaybolursa
yeni anahtar üretilemez, başkasının eline geçerse herkes anahtar üretebilir.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from app.core import license_format as lf  # noqa: E402

PRIVATE_NAME = "private_key.pem"
PUBLIC_NAME = "public_key.txt"
LEDGER_NAME = "verilen_lisanslar.csv"
KEYS_DIR = "anahtarlar"


class ToolError(Exception):
    pass


def default_dir() -> Path:
    return Path(os.environ.get("EM_LICENSE_DIR") or Path.home() / "EnglishMaster-Lisans")


def parse_date(text: str) -> date:
    text = text.strip()
    for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ToolError("Tarih anlaşılamadı. Örnek: 01.03.2027 ya da 2027-03-01")


def load_private(folder: Path) -> Ed25519PrivateKey:
    path = folder / PRIVATE_NAME
    if not path.is_file():
        raise ToolError(f"Gizli anahtar bulunamadı: {path}\nÖnce 'init' ile oluşturun ya da yedeğinizi bu klasöre koyun.")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ToolError("Gizli anahtar dosyası tanınmadı.")
    return key


def cmd_init(folder: Path) -> str:
    private_path = folder / PRIVATE_NAME
    if private_path.exists():
        raise ToolError(
            f"Zaten bir gizli anahtar var: {private_path}\n"
            "Üzerine yazılmadı (yazılsaydı daha önce verilen bütün lisanslar geçersiz olurdu)."
        )
    folder.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pem)
    public = lf.public_key_text(key.public_key())
    (folder / PUBLIC_NAME).write_text(public + "\n", encoding="utf-8")
    return public


def cmd_issue(folder: Path, code: str, name: str, expires: date, today: date | None = None) -> tuple[str, Path]:
    key = load_private(folder)
    today = today or date.today()
    data = lf.new_license(code, name, expires, today)  # ValueError: açıklayıcı mesaj
    text = lf.sign(data, key)
    lf.verify(text, [key.public_key()])  # kendi kendini doğrula

    ledger = folder / LEDGER_NAME
    new_file = not ledger.exists()
    with ledger.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        if new_file:
            writer.writerow(["verilis", "isim", "bilgisayar_kodu", "bitis", "lisans_no"])
        writer.writerow([data.issued.isoformat(), data.name, data.machine_code, data.expires.isoformat(), data.license_id])

    keys_dir = folder / KEYS_DIR
    keys_dir.mkdir(exist_ok=True)
    safe = re.sub(r"[^\w\-]+", "_", data.name, flags=re.UNICODE).strip("_") or "lisans"
    out = keys_dir / f"{safe}_{data.expires.isoformat()}_{data.license_id}.txt"
    out.write_text(text + "\n", encoding="utf-8")
    return text, out


def cmd_check(folder: Path, text: str) -> lf.LicenseData:
    public_keys = []
    public_path = folder / PUBLIC_NAME
    if public_path.is_file():
        public_keys.append(lf.load_public_key(public_path.read_text(encoding="utf-8")))
    from app.core.license_keys import PUBLIC_KEYS

    public_keys += [lf.load_public_key(item) for item in PUBLIC_KEYS]
    if not public_keys:
        raise ToolError("Doğrulamak için açık anahtar yok.")
    return lf.verify(text, public_keys)


def describe(data: lf.LicenseData) -> str:
    return (f"  Kişi           : {data.name}\n  Bilgisayar kodu: {data.machine_code}\n"
            f"  Veriliş        : {data.issued:%d.%m.%Y}\n  Bitiş          : {data.expires:%d.%m.%Y} (bu gün dâhil)\n"
            f"  Lisans no      : {data.license_id}")


def print_public(public: str, folder: Path) -> None:
    print("\nAnahtar çifti oluşturuldu.")
    print(f"  Gizli anahtar: {folder / PRIVATE_NAME}  (PAYLAŞMAYIN, yedekleyin)")
    print("\nAşağıdaki AÇIK anahtarı programa eklenmek üzere geliştiriciye iletin (bunu paylaşmak güvenlidir):\n")
    print("  " + public + "\n")


def interactive(folder: Path) -> int:
    print("English Master lisans aracı")
    print(f"Klasör: {folder}\n")
    while True:
        print("1) Anahtar çifti oluştur (yalnızca ilk kez)")
        print("2) Lisans anahtarı üret")
        print("3) Bir lisans anahtarını kontrol et")
        print("4) Çıkış")
        choice = input("Seçiminiz: ").strip()
        try:
            if choice == "1":
                print_public(cmd_init(folder), folder)
            elif choice == "2":
                code = input("Bilgisayar kodu (ör. 7KQ2-M9XA-P4TD-WR3H): ")
                name = input("Kişinin adı: ")
                expires = parse_date(input("Bitiş tarihi (GG.AA.YYYY): "))
                text, out = cmd_issue(folder, code, name, expires)
                print(f"\nLisans anahtarı ({expires:%d.%m.%Y} gününün sonuna kadar geçerli):\n\n{text}\n")
                print(f"Anahtar şu dosyaya da kaydedildi: {out}\n")
            elif choice == "3":
                print(describe(cmd_check(folder, input("Anahtar: "))) + "\n")
            elif choice == "4":
                return 0
        except (ToolError, ValueError) as exc:
            print(f"\nHATA: {exc}\n")


def _utf8_output() -> None:
    """Çıktı bir dosyaya/borulara yönlendirildiğinde Türkçe karakterler hata vermesin (Windows cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    parser = argparse.ArgumentParser(description="English Master lisans aracı")
    parser.add_argument("--klasor", type=Path, default=None, help="anahtarların tutulduğu klasör")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="imza anahtar çiftini oluştur")
    issue = sub.add_parser("issue", help="lisans anahtarı üret")
    issue.add_argument("--kod", required=True, help="kullanıcının bilgisayar kodu")
    issue.add_argument("--isim", required=True, help="kişinin adı")
    issue.add_argument("--bitis", required=True, help="bitiş tarihi (GG.AA.YYYY ya da YYYY-AA-GG), bu gün dâhil")
    check = sub.add_parser("check", help="lisans anahtarını kontrol et")
    check.add_argument("anahtar")
    args = parser.parse_args(argv)
    folder = args.klasor or default_dir()

    if args.command is None:
        try:
            return interactive(folder)
        except (EOFError, KeyboardInterrupt):
            return 0
    try:
        if args.command == "init":
            print_public(cmd_init(folder), folder)
        elif args.command == "issue":
            text, out = cmd_issue(folder, args.kod, args.isim, parse_date(args.bitis))
            print(text)
            print(f"(kaydedildi: {out})", file=sys.stderr)
        elif args.command == "check":
            print(describe(cmd_check(folder, args.anahtar)))
    except (ToolError, ValueError) as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
