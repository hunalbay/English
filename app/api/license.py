"""Lisans ve geri bildirim uçları (lisans olmadan da açıktır)."""

from __future__ import annotations

import platform

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_settings, get_user_session
from app.core.config import Settings
from app.database.content_db import read_content_status
from app.models.user import LessonProgress, UserProfile
from app.schemas.license import FeedbackInfo, LicenseInstall, LicenseStatusResponse
from app.services.license import FEEDBACK_EMAIL, STATE_LABELS, LicenseError, LicenseManager

router = APIRouter(tags=["license"])


def get_license_manager(request: Request) -> LicenseManager:
    return request.app.state.license


@router.get("/license", response_model=LicenseStatusResponse)
def license_status(manager: LicenseManager = Depends(get_license_manager)) -> dict:
    return manager.status().to_dict()


@router.post("/license", response_model=LicenseStatusResponse)
def install_license(body: LicenseInstall, manager: LicenseManager = Depends(get_license_manager)) -> dict:
    try:
        return manager.install(body.key).to_dict()
    except LicenseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/feedback", response_model=FeedbackInfo)
def feedback_info(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_user_session),
    manager: LicenseManager = Depends(get_license_manager),
) -> FeedbackInfo:
    """Geri bildirim e-postasına kullanıcı isterse eklenecek bilgiler.

    Bu uç hiçbir şey göndermez; arayüz metni kullanıcıya gösterir, kullanıcı
    kendi e-posta programıyla gönderir. Kişisel bilgi, yanıtlar veya dosya yolu içermez.
    """
    content = read_content_status(settings.content_db_path)
    status = manager.status()
    diagnostics = {
        "Program sürümü": __version__,
        "İçerik sürümü": content.version or "yok",
        "İşletim sistemi": f"{platform.system()} {platform.release()}".strip(),
        "Lisans durumu": STATE_LABELS[status.state] + (f" (bitiş {status.expires})" if status.licensed else ""),
        "Bilgisayar kodu": status.machine_code,
    }
    if status.licensed:
        profile = session.get(UserProfile, 1)
        completed = session.scalar(
            select(func.count()).select_from(LessonProgress).where(LessonProgress.status == "completed")
        )
        diagnostics["Seviye"] = (profile.current_level if profile else None) or "seçilmedi"
        diagnostics["Tamamlanan ders"] = str(completed or 0)
    return FeedbackInfo(email=FEEDBACK_EMAIL, diagnostics=diagnostics)
