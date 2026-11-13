"""Yerel sunucu için güvenlik katmanı.

- Host başlığı yalnızca 127.0.0.1 / localhost olabilir (DNS rebinding'e karşı).
- Veri değiştiren API istekleri, uygulamanın kendi arayüzünün aldığı oturum
  belirtecini taşımak zorundadır; başka bir web sitesi yerel API'yi kullanamaz.
- Yanıtlara sıkı bir içerik güvenlik politikası eklenir; arayüz dış adreslere
  istek atamaz.
"""

from __future__ import annotations

import hmac
import json
import secrets

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOKEN_HEADER = "x-em-token"
ALLOWED_HOSTNAMES = frozenset({"127.0.0.1", "localhost"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hostname_of(host_header: str) -> str:
    """'127.0.0.1:8765' -> '127.0.0.1'."""
    host = host_header.strip().lower()
    if host.startswith("["):  # IPv6 kabul edilmez
        return host
    return host.rsplit(":", 1)[0] if ":" in host else host


class LocalSecurityMiddleware:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if hostname_of(headers.get("host", "")) not in ALLOWED_HOSTNAMES:
            await _reject(send, 400, "invalid_host", "Geçersiz istek adresi.")
            return

        path: str = scope["path"]
        is_api = path.startswith("/api/")
        if is_api and scope["method"] not in SAFE_METHODS:
            supplied = headers.get(TOKEN_HEADER, "")
            if not hmac.compare_digest(supplied.encode(), self.token.encode()):
                await _reject(send, 403, "invalid_token", "Bu işlem için yetki doğrulanamadı.")
                return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                out = MutableHeaders(scope=message)
                out["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
                out["X-Content-Type-Options"] = "nosniff"
                out["Referrer-Policy"] = "no-referrer"
                out["Cross-Origin-Resource-Policy"] = "same-origin"
                if is_api:
                    out["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _reject(send: Send, status: int, code: str, message: str) -> None:
    body = json.dumps({"error": {"code": code, "message": message}}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
