"""Paketlenmiş programı (ya da kurulu programı) gerçekten çalıştırıp temel işlevleri dener.

Kullanım:
    python packaging/smoke_test.py <EnglishMaster çalıştırılabilir dosyası> [--data-dir KLASÖR] [--keep-data]

--data-dir verilmezse geçici bir klasör kullanılır (ENGLISH_MASTER_DATA_DIR ile).
--use-default-data-dir: ortam değişkeni verilmez; program gerçek kullanıcı klasörünü kullanır
(kurulum / kaldırma testinde verinin korunduğunu doğrulamak için).
Yalnızca standart kütüphane kullanır; çıkış kodu 0 ise bütün denetimler geçmiştir.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def default_data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "EnglishMaster"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "EnglishMaster"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--use-default-data-dir", action="store_true")
    parser.add_argument("--port", type=int, default=8817)
    args = parser.parse_args()

    env = dict(os.environ)
    if args.use_default_data_dir:
        env.pop("ENGLISH_MASTER_DATA_DIR", None)
        data_dir = default_data_dir()
    else:
        data_dir = args.data_dir or Path(tempfile.mkdtemp(prefix="em-smoke-"))
        env["ENGLISH_MASTER_DATA_DIR"] = str(data_dir)
    failures: list[str] = []

    def check(ok: bool, message: str) -> None:
        print(("  ok   " if ok else "  HATA ") + message, flush=True)
        if not ok:
            failures.append(message)

    command = [str(args.exe), "--port", str(args.port), "--no-browser", "--no-tray"]
    print("Başlatılıyor:", " ".join(command), "| veri klasörü:", data_dir, flush=True)
    started = time.monotonic()
    process = subprocess.Popen(command, env=env)  # noqa: S603
    instance = data_dir / "instance.json"
    port = None
    for _ in range(600):  # en çok 60 sn
        if process.poll() is not None:
            break
        try:
            port = json.loads(instance.read_text(encoding="utf-8"))["port"]
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=2)  # noqa: S310
            break
        except Exception:  # noqa: BLE001
            port = None
            time.sleep(0.1)
    check(port is not None, f"program açıldı ve yanıt veriyor ({time.monotonic() - started:.1f} sn)")
    if port is None:
        process.kill()
        print("BAŞARISIZ")
        return 1
    base = f"http://127.0.0.1:{port}"

    def get(path: str):  # noqa: ANN202
        with urllib.request.urlopen(base + path, timeout=10) as response:  # noqa: S310
            return response.status, response.headers.get("content-type", ""), response.read()

    status, _, body = get("/api/v1/health")
    health = json.loads(body)
    check(status == 200 and health.get("content", {}).get("available") is True, f"içerik veri tabanı yüklü: {health.get('content')}")
    # Lisans yokken: lisans ekranı çalışır, eğitim API'leri kilitlidir
    status, _, body = get("/api/v1/license")
    lic = json.loads(body)
    check(status == 200 and len(lic.get("machine_code", "")) == 19, f"lisans durumu ve bilgisayar kodu: {lic.get('state')} {lic.get('machine_code')}")
    check(lic.get("state") in ("missing", "unconfigured") or args.use_default_data_dir, "temiz kurulumda lisans yok")
    if not lic.get("licensed"):
        try:
            get("/api/v1/levels")
            locked = False
        except urllib.error.HTTPError as error:
            locked = error.code == 403 and json.loads(error.read())["error"]["code"] == "license_required"
        check(locked, "lisans yokken eğitim API'leri kilitli")
    status, _, body = get("/api/v1/feedback")
    check(status == 200 and "@" in json.loads(body)["email"], "geri bildirim bilgisi sunuluyor")

    # Ses dosyaları paketle gelir ve sunulur
    clips_dir = args.exe.parent / "_internal" / "data" / "audio" / "clips"
    sample = next(iter(sorted(clips_dir.rglob("*.mp3"))), None) if clips_dir.is_dir() else None
    check(sample is not None, "pakette ses dosyası var")
    if sample is not None:
        status, ctype, data = get("/media/clips/" + sample.relative_to(clips_dir).as_posix())
        check(status == 200 and ctype.startswith("audio/mpeg") and len(data) > 1000, f"ses dosyası sunuluyor ({len(data)} bayt)")
    status, ctype, body = get("/")
    check(status == 200 and b"English Master" in body and ctype.startswith("text/html"), "arayüz sayfası sunuluyor")
    status, _, body = get("/scripts/app.js")
    check(status == 200 and b"ROUTES" in body, "arayüz betikleri sunuluyor")

    # İkinci kopya açılmaz; çalışanı bildirir ve hemen çıkar
    second = subprocess.run([*command[:1], "--no-browser", "--no-tray"], env=env, timeout=30)  # noqa: S603
    check(second.returncode == 0, "ikinci kopya açılmadı, çalışan program bildirildi")

    token = json.loads(get("/api/v1/session")[2])["token"]
    request = urllib.request.Request(base + "/api/v1/settings/theme", method="PUT", data=b'{"value": "dark"}',
                                     headers={"X-EM-Token": token, "content-type": "application/json"})
    urllib.request.urlopen(request, timeout=10)  # noqa: S310
    check(json.loads(get("/api/v1/settings")[2])["settings"]["theme"] == "dark", "kullanıcı verisi yazılabiliyor")

    request = urllib.request.Request(base + "/api/v1/system/shutdown", method="POST", data=b"{}",
                                     headers={"X-EM-Token": token, "content-type": "application/json"})
    urllib.request.urlopen(request, timeout=10)  # noqa: S310
    try:
        code = process.wait(timeout=20)
        check(code == 0, f"arayüzden kapatma çalışıyor (çıkış kodu {code})")
    except subprocess.TimeoutExpired:
        process.kill()
        check(False, "program 20 saniyede kapanmadı")
    check((data_dir / "user.db").is_file(), f"kullanıcı verisi kurulum klasörü dışında: {data_dir / 'user.db'}")
    check(not instance.exists(), "kapanırken çalışma kaydı temizlendi")
    check((data_dir / "logs" / "app.log").is_file(), "log dosyası yazıldı")

    print("BAŞARISIZ: " + "; ".join(failures) if failures else "Bütün denetimler geçti.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
