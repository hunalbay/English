"""Uygulama başlatıcısı.

Sorumlulukları:
- Programın aynı anda yalnızca bir kez çalışmasını sağlamak (kilit dosyası).
  İkinci kez açılırsa yeni sunucu başlatmaz, çalışan kopyanın arayüzünü açar.
- Sunucuyu yalnızca 127.0.0.1 üzerinde başlatmak ve arayüzü tarayıcıda açmak.
- Sunucuyu düzgün biçimde kapatmak (tepsi menüsü, arayüzdeki "Programı kapat"
  düğmesi veya Ctrl+C).

Sistem tepsisi simgesi `pystray` kuruluysa (Windows paketinde kuruludur)
gösterilir; kurulu değilse uygulama konsoldan aynı şekilde çalışır.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import IO

import uvicorn

from app.core.config import DEFAULT_HOST, DEFAULT_PORT, Settings, load_settings
from app.core.logging import get_logger, setup_logging
from app.services.migrations import MigrationError

LOCK_FILENAME = "app.lock"
INSTANCE_FILENAME = "instance.json"


class SingleInstanceLock:
    """İşletim sistemi düzeyinde dosya kilidi; süreç ölünce kendiliğinden kalkar."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: IO[str] | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+", encoding="utf-8")
        try:
            if sys.platform == "win32":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self._handle.close()
        self._handle = None


def find_free_port(preferred: int, host: str = DEFAULT_HOST) -> int:
    """Tercih edilen port doluysa işletim sisteminden boş bir port ister."""
    for candidate in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, candidate))
            except OSError:
                continue
            return sock.getsockname()[1]
    raise RuntimeError("Kullanılabilir bir port bulunamadı.")


def write_instance_info(data_dir: Path, port: int) -> None:
    info = {"port": port, "pid": os.getpid()}
    (data_dir / INSTANCE_FILENAME).write_text(json.dumps(info), encoding="utf-8")


def read_running_url(data_dir: Path) -> str | None:
    """Çalışan kopyanın adresini döndürür; yanıt vermiyorsa None."""
    try:
        info = json.loads((data_dir / INSTANCE_FILENAME).read_text(encoding="utf-8"))
        port = int(info["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    url = f"http://{DEFAULT_HOST}:{port}/"
    try:
        # Sistem vekil sunucusu (proxy) ayarları yerel adres için kullanılmaz.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{url}api/v1/health", timeout=3) as response:
            if json.load(response).get("status") == "ok":
                return url
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return None


def _run_tray(url: str, stop: threading.Event, on_quit) -> bool:  # noqa: ANN001
    """Tepsi simgesini ana iş parçacığında çalıştırır. Kullanılamıyorsa False döner."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except Exception:  # pystray yok ya da grafik ortam yok
        return False

    image = Image.new("RGB", (64, 64), "#2f5fd0")
    draw = ImageDraw.Draw(image)
    draw.rectangle((14, 16, 22, 48), fill="white")
    for y in (16, 29, 42):
        draw.rectangle((14, y, 34, y + 6), fill="white")
    draw.polygon([(40, 48), (40, 16), (47, 16), (51, 30), (55, 16), (62, 16), (62, 48),
                  (56, 48), (56, 28), (53, 40), (49, 40), (46, 28), (46, 48)], fill="white")

    def quit_app(icon, _item) -> None:  # noqa: ANN001
        on_quit()
        icon.stop()

    icon = pystray.Icon(
        "EnglishMaster",
        image,
        "English Master",
        menu=pystray.Menu(
            pystray.MenuItem("English Master'ı aç", lambda *_: webbrowser.open(url), default=True),
            pystray.MenuItem("Çıkış", quit_app),
        ),
    )

    def watch() -> None:  # sunucu başka yoldan kapanırsa simgeyi de kaldır
        stop.wait()
        icon.stop()

    threading.Thread(target=watch, daemon=True).start()
    try:
        icon.run()
    except Exception:
        return False
    return True


def run(settings: Settings, open_browser: bool = True, use_tray: bool = True) -> int:
    settings.ensure_dirs()
    setup_logging(settings.logs_dir)
    log = get_logger("launcher")

    lock = SingleInstanceLock(settings.data_dir / LOCK_FILENAME)
    if not lock.acquire():
        url = read_running_url(settings.data_dir)
        if url:
            print(f"English Master zaten çalışıyor: {url}")
            if open_browser:
                webbrowser.open(url)
            return 0
        print(
            "HATA: English Master zaten açık görünüyor ancak yanıt vermiyor. "
            "Programı kapatıp yeniden deneyin.",
            file=sys.stderr,
        )
        return 2

    try:
        from app.main import create_app

        try:
            app = create_app(settings)
        except MigrationError as exc:
            print(f"HATA: {exc}", file=sys.stderr)
            return 1

        config = uvicorn.Config(
            app, host=settings.host, port=settings.port, log_config=None, access_log=False
        )
        server = uvicorn.Server(config)
        stopped = threading.Event()

        def request_stop() -> None:
            server.should_exit = True

        app.state.request_shutdown = request_stop

        def serve() -> None:
            try:
                server.run()
            finally:
                stopped.set()

        thread = threading.Thread(target=serve, name="server", daemon=True)
        thread.start()

        # Sunucu bağlantı kabul etmeye başlayana kadar bekle; adres ancak o zaman duyurulur.
        while not server.started and not stopped.wait(0.05):
            pass
        if not server.started:
            print("HATA: Yerel sunucu başlatılamadı. Ayrıntılar log dosyasındadır.", file=sys.stderr)
            return 1

        url = f"http://{settings.host}:{settings.port}/"
        write_instance_info(settings.data_dir, settings.port)
        log.info("Sunucu adresi: %s", url)
        print(f"English Master çalışıyor: {url}", flush=True)
        if open_browser:
            webbrowser.open(url)

        try:
            if not (use_tray and _run_tray(url, stopped, request_stop)):
                while not stopped.wait(0.5):
                    pass
        except KeyboardInterrupt:
            pass
        request_stop()
        thread.join(timeout=10)
        return 0
    finally:
        (settings.data_dir / INSTANCE_FILENAME).unlink(missing_ok=True)
        lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="english-master")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="Tarayıcıyı otomatik açma")
    parser.add_argument("--no-tray", action="store_true", help="Tepsi simgesini gösterme")
    args = parser.parse_args(argv)
    settings = load_settings(port=find_free_port(args.port))
    return run(settings, open_browser=not args.no_browser, use_tray=not args.no_tray)


if __name__ == "__main__":
    raise SystemExit(main())
