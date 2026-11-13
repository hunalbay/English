"""Uygulama ayarları: yalnızca tanımlı anahtarlar, doğrulanmış değerlerle saklanır."""

from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import ApplicationSetting


class SettingError(ValueError):
    pass


def _theme(value: Any) -> str:
    if value not in ("system", "light", "dark"):
        raise SettingError("Tema 'system', 'light' veya 'dark' olmalıdır.")
    return value


def _daily_goal(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 5 <= value <= 240:
        raise SettingError("Günlük hedef 5 ile 240 dakika arasında bir tam sayı olmalıdır.")
    return value


# anahtar -> (varsayılan değer, doğrulayıcı)
SETTING_DEFINITIONS: dict[str, tuple[Any, Callable[[Any], Any]]] = {
    "theme": ("system", _theme),
    "daily_goal_minutes": (20, _daily_goal),
}


def get_all(session: Session) -> dict[str, Any]:
    values = {key: default for key, (default, _) in SETTING_DEFINITIONS.items()}
    for row in session.scalars(select(ApplicationSetting)):
        if row.key in values:
            values[row.key] = json.loads(row.value)
    return values


def set_value(session: Session, key: str, value: Any) -> Any:
    if key not in SETTING_DEFINITIONS:
        raise KeyError(key)
    clean = SETTING_DEFINITIONS[key][1](value)
    row = session.get(ApplicationSetting, key)
    if row is None:
        session.add(ApplicationSetting(key=key, value=json.dumps(clean)))
    else:
        row.value = json.dumps(clean)
    session.commit()
    return clean
