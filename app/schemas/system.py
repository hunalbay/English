from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ContentInfo(BaseModel):
    available: bool
    version: str | None = None
    built_at: str | None = None


class UserDbInfo(BaseModel):
    schema_revision: str | None


class HealthResponse(BaseModel):
    status: str
    version: str
    content: ContentInfo
    user_db: UserDbInfo


class SessionResponse(BaseModel):
    token: str


class SettingsResponse(BaseModel):
    settings: dict[str, Any]


class SettingUpdate(BaseModel):
    value: Any


class SettingValue(BaseModel):
    key: str
    value: Any


class ShutdownResponse(BaseModel):
    stopping: bool
