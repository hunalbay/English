"""Gerçek süreç üzerinden uçtan uca testler: başlatma, tek kopya, kalıcılık, kapanış."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SMOKE = Path(__file__).with_name("smoke.cjs")


def _env(data_dir: Path, content_db: Path) -> dict[str, str]:
    return {
        **os.environ,
        "ENGLISH_MASTER_DATA_DIR": str(data_dir),
        "ENGLISH_MASTER_CONTENT_DB": str(content_db),
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
    }


def _start(env: dict[str, str]) -> tuple[subprocess.Popen, str]:
    process = subprocess.Popen(
        [sys.executable, "-m", "app", "--no-browser", "--no-tray", "--port", "0"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
    )
    line = process.stdout.readline()
    assert "çalışıyor:" in line, line
    return process, line.strip().rsplit(" ", 1)[-1]


def _json(url: str, method: str = "GET", token: str | None = None, body: dict | None = None) -> dict:
    request = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("X-EM-Token", token)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        return json.load(response)


@pytest.fixture()
def env(tmp_path, settings):
    return _env(tmp_path / "userdata-e2e", settings.content_db_path)


def test_start_single_instance_persist_and_shutdown(env):
    process, url = _start(env)
    try:
        assert url.startswith("http://127.0.0.1:")
        assert _json(url + "api/v1/health")["status"] == "ok"

        # ikinci kopya yeni sunucu açmaz, çalışan kopyayı bildirir
        second = subprocess.run(
            [sys.executable, "-m", "app", "--no-browser", "--no-tray", "--port", "0"],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert second.returncode == 0
        assert "zaten çalışıyor" in second.stdout and url in second.stdout

        token = _json(url + "api/v1/session")["token"]
        _json(url + "api/v1/settings/theme", "PUT", token, {"value": "dark"})
        assert _json(url + "api/v1/system/shutdown", "POST", token) == {"stopping": True}
        assert process.wait(timeout=15) == 0
    finally:
        if process.poll() is None:
            process.kill()

    data_dir = Path(env["ENGLISH_MASTER_DATA_DIR"])
    assert not (data_dir / "instance.json").exists()

    # yeniden açıldığında kayıt korunur
    process, url = _start(env)
    try:
        assert _json(url + "api/v1/settings")["settings"]["theme"] == "dark"
        token = _json(url + "api/v1/session")["token"]
        _json(url + "api/v1/system/shutdown", "POST", token)
        assert process.wait(timeout=15) == 0
    finally:
        if process.poll() is None:
            process.kill()


@pytest.mark.e2e
def test_browser_smoke(env):
    if shutil.which("node") is None:
        pytest.skip("Node.js yok")
    probe = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip("Playwright kurulu değil")

    process, url = _start(env)
    try:
        args = ["node", str(SMOKE), url]
        if os.environ.get("EM_SCREENSHOT_PREFIX"):
            args.append(os.environ["EM_SCREENSHOT_PREFIX"])
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        # duman testi programı arayüzden kapatır; süreç düzgün sonlanmalı
        assert process.wait(timeout=15) == 0
    finally:
        if process.poll() is None:
            process.kill()
