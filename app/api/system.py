"""Sistem uçları: durum, oturum belirteci, ayarlar."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_settings, get_user_session
from app.core.config import Settings
from app.database.content_db import read_content_status
from app.schemas.system import (
    ContentInfo,
    ShutdownResponse,
    HealthResponse,
    SessionResponse,
    SettingsResponse,
    SettingUpdate,
    SettingValue,
    UserDbInfo,
)
from app.services import settings as settings_service
from app.services.migrations import current_revision

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    content = read_content_status(settings.content_db_path)
    return HealthResponse(
        status="ok",
        version=__version__,
        content=ContentInfo(
            available=content.available, version=content.version, built_at=content.built_at
        ),
        user_db=UserDbInfo(schema_revision=current_revision(settings.user_db_path)),
    )


@router.get("/session", response_model=SessionResponse)
def session_token(request: Request) -> SessionResponse:
    """Arayüzün veri değiştiren isteklerde kullanacağı belirteç.

    Başka bir kaynaktan (origin) gelen sayfalar bu yanıtı okuyamaz; CORS kapalıdır.
    """
    return SessionResponse(token=request.app.state.session_token)


@router.get("/settings", response_model=SettingsResponse)
def read_settings(session: Session = Depends(get_user_session)) -> SettingsResponse:
    return SettingsResponse(settings=settings_service.get_all(session))


@router.put("/settings/{key}", response_model=SettingValue)
def update_setting(
    key: str, body: SettingUpdate, session: Session = Depends(get_user_session)
) -> SettingValue:
    try:
        value = settings_service.set_value(session, key, body.value)
    except KeyError:
        raise HTTPException(status_code=404, detail="Böyle bir ayar yok.") from None
    except settings_service.SettingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return SettingValue(key=key, value=value)


@router.post("/system/shutdown", response_model=ShutdownResponse)
def shutdown(request: Request) -> ShutdownResponse:
    """Arayüzdeki "Programı kapat" düğmesi: sunucuyu düzgün biçimde sonlandırır."""
    request_shutdown = getattr(request.app.state, "request_shutdown", None)
    if request_shutdown is None:
        raise HTTPException(status_code=409, detail="Program bu çalışma biçiminde arayüzden kapatılamaz.")
    request_shutdown()
    return ShutdownResponse(stopping=True)
