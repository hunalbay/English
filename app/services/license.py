"""Lisans durumu: kurulu anahtarın okunması, doğrulanması ve kaydedilmesi.

Anahtar kullanıcı veri klasöründe ``license.json`` dosyasında tutulur; program
kaldırılıp yeniden kurulduğunda korunur. Doğrulama tamamen yereldir.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.core.license_format import LicenseFormatError, load_public_key, machine_code_from_id, verify
from app.core.logging import get_logger
from app.core.machine import machine_id

FEEDBACK_EMAIL = "onurgulcicek@hotmail.com"
WARN_DAYS = 14
# Saat bu kadar günden fazla geri alınmışsa lisans geçici olarak kabul edilmez.
CLOCK_TOLERANCE_DAYS = 2

log = get_logger("license")

MESSAGES = {
    "valid": "Lisansınız geçerli.",
    "missing": "Programı kullanmak için bir lisans anahtarı girin.",
    "invalid": "Kayıtlı lisans anahtarı okunamadı. Size gönderilen anahtarı yeniden girin.",
    "other_machine": "Bu lisans anahtarı başka bir bilgisayar için üretilmiş. Bu bilgisayarın kodu için yeni bir anahtar isteyin.",
    "expired": "Lisansınızın süresi doldu. Çalışmalarınız korunuyor; devam etmek için yeni bir anahtar isteyin.",
    "clock": "Bilgisayarınızın tarihi geri alınmış görünüyor. Tarih ve saati düzeltip programı yeniden açın.",
    "unconfigured": "Bu program kopyası lisans doğrulaması için yapılandırılmamış. Programın resmi kurulum dosyasını kullanın.",
}


STATE_LABELS = {
    "valid": "geçerli", "missing": "girilmedi", "invalid": "okunamadı", "other_machine": "başka bilgisayarın",
    "expired": "süresi doldu", "clock": "tarih sorunu", "unconfigured": "yapılandırılmamış",
}


class LicenseError(ValueError):
    """Girilen anahtar kabul edilmedi (mesaj kullanıcıya gösterilebilir)."""


@dataclass(frozen=True)
class LicenseStatus:
    state: str
    message: str
    machine_code: str
    name: str | None = None
    expires: str | None = None
    days_left: int | None = None
    warn: bool = False
    contact_email: str = FEEDBACK_EMAIL

    @property
    def licensed(self) -> bool:
        return self.state == "valid"

    def to_dict(self) -> dict:
        return {**asdict(self), "licensed": self.licensed}


def _today() -> date:
    return datetime.now().date()  # yerel tarih: bitiş günü sonuna kadar geçerlidir


def _last_seen(stored: dict) -> date | None:
    try:
        return date.fromisoformat(stored.get("last_seen", ""))
    except (TypeError, ValueError):
        return None


class LicenseManager:
    def __init__(self, settings: Settings) -> None:
        self.path: Path = settings.license_path
        self._keys = []
        for text in settings.license_public_keys:
            try:
                self._keys.append(load_public_key(text))
            except ValueError:
                log.error("Geçersiz açık anahtar yapılandırması yok sayıldı")
        raw_id = settings.machine_id_override or machine_id(settings.data_dir)
        self.machine_code = machine_code_from_id(raw_id)
        self._lock = threading.Lock()
        self._cache: tuple[date, LicenseStatus] | None = None

    # -- dosya ----------------------------------------------------------------
    def _read(self) -> dict | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    # -- denetim ----------------------------------------------------------------
    def _evaluate(self, key_text: str, today: date, last_seen: date | None) -> LicenseStatus:
        if not self._keys:
            return self._status("unconfigured")
        data = verify(key_text, self._keys)  # LicenseFormatError
        if data.machine_code != self.machine_code:
            return self._status("other_machine", name=data.name, expires=data.expires)
        if last_seen and today < last_seen - timedelta(days=CLOCK_TOLERANCE_DAYS):
            return self._status("clock", name=data.name, expires=data.expires)
        if today > data.expires:
            return self._status("expired", name=data.name, expires=data.expires)
        days_left = (data.expires - today).days
        return LicenseStatus(
            state="valid",
            message=MESSAGES["valid"],
            machine_code=self.machine_code,
            name=data.name,
            expires=data.expires.isoformat(),
            days_left=days_left,
            warn=days_left <= WARN_DAYS,
        )

    def _status(self, state: str, name: str | None = None, expires: date | None = None) -> LicenseStatus:
        return LicenseStatus(
            state=state, message=MESSAGES[state], machine_code=self.machine_code,
            name=name, expires=expires.isoformat() if expires else None,
        )

    def status(self, today: date | None = None) -> LicenseStatus:
        today = today or _today()
        with self._lock:
            if self._cache and self._cache[0] == today:
                return self._cache[1]
            stored = self._read()
            if stored is None:
                result = self._status("unconfigured" if not self._keys else "missing")
            elif not isinstance(stored.get("key"), str):
                result = self._status("invalid")
            else:
                last_seen = _last_seen(stored)
                try:
                    result = self._evaluate(stored["key"], today, last_seen)
                except LicenseFormatError:
                    result = self._status("invalid")
                if result.state == "valid" and (last_seen is None or today > last_seen):
                    try:
                        self._write({**stored, "last_seen": today.isoformat()})
                    except OSError:
                        log.warning("Lisans dosyası güncellenemedi")
            self._cache = (today, result)
            return result

    def install(self, key_text: str, today: date | None = None) -> LicenseStatus:
        """Yeni anahtarı denetler; yalnızca geçerliyse kaydeder (eski anahtar yedeklenir)."""
        today = today or _today()
        with self._lock:
            if not self._keys:
                raise LicenseError(MESSAGES["unconfigured"])
            previous = self._read() or {}
            compact = "".join(key_text.split())
            # Saat denetimi aynı anahtarın yeniden girilmesinde uygulanır. Yeni bir anahtar
            # (ör. saati yanlışlıkla ileri alınmış bir bilgisayar için) kaydı sıfırlar.
            last_seen = _last_seen(previous) if previous.get("key") == compact else None
            try:
                result = self._evaluate(key_text, today, last_seen)
            except LicenseFormatError as exc:
                raise LicenseError(str(exc)) from None
            if result.state == "expired":
                raise LicenseError("Bu lisans anahtarının süresi dolmuş. Yeni bir anahtar isteyin.")
            if result.state != "valid":
                raise LicenseError(result.message)
            if self.path.exists():
                try:
                    os.replace(self.path, self.path.with_suffix(".json.bak"))
                except OSError:
                    log.warning("Önceki lisans dosyası yedeklenemedi")
            self._write({
                "key": compact,
                "installed_at": datetime.now().isoformat(timespec="seconds"),
                "last_seen": max(today, last_seen or today).isoformat(),
            })
            self._cache = (today, result)
            log.info("Lisans kuruldu (bitiş %s)", result.expires)
            return result
