"""FastAPI uygulama fabrikası."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import learning, study, system, vocabulary
from app.core.config import Settings, load_settings
from app.core.logging import get_logger, setup_logging
from app.core.security import LocalSecurityMiddleware, new_session_token
from app.database.user_db import create_session_factory, create_user_engine
from app.services.migrations import run_migrations

API_PREFIX = "/api/v1"

# FastAPI'nin yerleşik OpenTelemetry desteği tamamen kapalıdır:
# uygulama hiçbir kullanım verisi toplamaz veya göndermez.
_TELEMETRY_OFF = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.ensure_dirs()
    setup_logging(settings.logs_dir)
    log = get_logger("app")

    run_migrations(settings)
    engine = create_user_engine(settings.user_db_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        log.info("English Master %s başlatıldı", __version__)
        yield
        engine.dispose()
        log.info("English Master kapatıldı")

    app = FastAPI(
        title="English Master",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
        telemetry=_TELEMETRY_OFF,
    )
    app.state.settings = settings
    app.state.session_token = new_session_token()
    app.state.user_engine = engine
    app.state.user_sessions = create_session_factory(engine)

    app.add_middleware(LocalSecurityMiddleware, token=app.state.session_token)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "İstek işlenemedi."
        if exc.status_code == 404 and message == "Not Found":
            message = "İstenen kaynak bulunamadı."
        return _error(exc.status_code, f"http_{exc.status_code}", message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _error(422, "validation_error", "Gönderilen veri geçersiz.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Ayrıntı yalnızca yerel log dosyasına yazılır; kullanıcıya gösterilmez.
        log.error("Beklenmeyen hata: %s %s", request.method, request.url.path, exc_info=exc)
        return _error(500, "internal_error", "Beklenmeyen bir hata oluştu. Ayrıntılar log dosyasına yazıldı.")

    for module in (system, learning, vocabulary, study):
        app.include_router(module.router, prefix=API_PREFIX)

    @app.api_route(
        "/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False
    )
    async def api_not_found(rest: str) -> JSONResponse:
        return _error(404, "http_404", "İstenen kaynak bulunamadı.")

    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app
