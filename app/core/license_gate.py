"""Lisans kilidi: geçerli lisans yoksa eğitim API'leri kapalıdır.

Lisans ekranının çalışması için gereken uçlar (durum, oturum belirteci,
lisans, geri bildirim, görünüm ayarları, programı kapatma) her zaman açıktır.
Arayüz dosyaları ve ses dosyaları kilitlenmez; içerik API'den gelir.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.security import _reject

OPEN_PATHS = frozenset({"/health", "/session", "/license", "/feedback", "/system/shutdown"})
OPEN_PREFIXES = ("/settings",)


class LicenseGateMiddleware:
    def __init__(self, app: ASGIApp, api_prefix: str, manager) -> None:  # noqa: ANN001
        self.app = app
        self.prefix = api_prefix
        self.manager = manager

    def _is_open(self, path: str) -> bool:
        if not path.startswith(self.prefix + "/"):
            return True  # arayüz, ses dosyaları, bilinmeyen /api adresleri (404)
        rest = path[len(self.prefix) :].rstrip("/") or "/"
        return rest in OPEN_PATHS or rest.startswith(OPEN_PREFIXES)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not self._is_open(scope["path"]):
            status = self.manager.status()
            if not status.licensed:
                await _reject(send, 403, "license_required", status.message)
                return
        await self.app(scope, receive, send)
