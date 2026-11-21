from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.license_format import MAX_KEY_LENGTH


class LicenseStatusResponse(BaseModel):
    state: str
    licensed: bool
    message: str
    machine_code: str
    name: str | None = None
    expires: str | None = None
    days_left: int | None = None
    warn: bool = False
    contact_email: str


class LicenseInstall(BaseModel):
    key: str = Field(min_length=1, max_length=MAX_KEY_LENGTH + 200)


class FeedbackInfo(BaseModel):
    email: str
    diagnostics: dict[str, str]
