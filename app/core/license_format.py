"""Lisans anahtarı biçimi (programla lisans aracı arasında ortak).

Deneme sürümünde lisans anahtarı çevrim dışı doğrulanır:

- Program, bilgisayarın kimliğinden geri çevrilemeyen kısa bir "bilgisayar kodu"
  üretir (ör. ``7KQ2-M9XA-P4TD-WR3H``). Son dört karakter, yanlış yazımı yakalayan
  bir denetim parçasıdır.
- Lisans aracı; bilgisayar kodu, kişi adı ve bitiş tarihini içeren küçük bir JSON
  belgesini Ed25519 gizli anahtarıyla imzalar:
  ``EM1.<base64url(belge)>.<base64url(imza)>``
- Program yalnızca açık anahtarı taşır; imzayı, bilgisayar kodunu ve tarihi
  yerelde denetler. İnternet bağlantısı gerekmez, IP adresi kullanılmaz.

Bu katman bilgisayardaki kararlı birinin programı değiştirmesini önleyemez; amacı
anahtarın paylaşılmasını ve sahte anahtar üretilmesini önlemektir.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import date

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

KEY_PREFIX = "EM1"
PUBLIC_KEY_PREFIX = "em-pub-1:"
FORMAT_VERSION = 1
MAX_KEY_LENGTH = 2000
MAX_NAME_LENGTH = 60

_MACHINE_SALT = b"EnglishMaster/machine/v1:"
_B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_CODE_RE = re.compile(r"^[A-Z2-7]{16}$")


class LicenseFormatError(ValueError):
    """Anahtar okunamıyor ya da imzası geçersiz (mesaj kullanıcıya gösterilebilir)."""


def _b32(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").rstrip("=")


def _check_part(body: str) -> str:
    return _b32(hashlib.sha256(b"check:" + body.encode("ascii")).digest())[:4]


def _group(code: str) -> str:
    return "-".join(code[i : i + 4] for i in range(0, 16, 4))


def machine_code_from_id(raw_id: str) -> str:
    """Bilgisayar kimliğinden (ör. Windows MachineGuid) gösterilecek kodu üretir."""
    digest = hashlib.sha256(_MACHINE_SALT + raw_id.strip().lower().encode("utf-8")).digest()
    body = _b32(digest)[:12]
    return _group(body + _check_part(body))


def normalize_machine_code(text: str) -> str | None:
    """Kullanıcının yazdığı kodu biçimlendirir; geçersizse (yazım hatası dâhil) None."""
    compact = re.sub(r"[\s\-]", "", text or "").upper()
    if not _CODE_RE.match(compact) or _check_part(compact[:12]) != compact[12:]:
        return None
    return _group(compact)


@dataclass(frozen=True)
class LicenseData:
    machine_code: str
    name: str
    expires: date
    issued: date
    license_id: str

    def payload(self) -> bytes:
        document = {
            "v": FORMAT_VERSION,
            "mc": self.machine_code,
            "n": self.name,
            "exp": self.expires.isoformat(),
            "iat": self.issued.isoformat(),
            "id": self.license_id,
        }
        return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def clean_name(name: str) -> str:
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise ValueError("Kişi adı boş olamaz.")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValueError(f"Kişi adı en çok {MAX_NAME_LENGTH} karakter olabilir.")
    if any(ord(ch) < 32 for ch in cleaned):
        raise ValueError("Kişi adında geçersiz karakter var.")
    return cleaned


def new_license(machine_code: str, name: str, expires: date, issued: date) -> LicenseData:
    code = normalize_machine_code(machine_code)
    if code is None:
        raise ValueError("Bilgisayar kodu geçersiz. Kodu kontrol edin (ör. 7KQ2-M9XA-P4TD-WR3H).")
    if expires < issued:
        raise ValueError("Bitiş tarihi bugünden önce olamaz.")
    return LicenseData(code, clean_name(name), expires, issued, secrets.token_hex(6))


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(data: LicenseData, private_key: Ed25519PrivateKey) -> str:
    payload = data.payload()
    return f"{KEY_PREFIX}.{_b64e(payload)}.{_b64e(private_key.sign(payload))}"


def public_key_text(public_key: Ed25519PublicKey) -> str:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return PUBLIC_KEY_PREFIX + base64.b64encode(raw).decode("ascii")


def load_public_key(text: str) -> Ed25519PublicKey:
    text = text.strip()
    if not text.startswith(PUBLIC_KEY_PREFIX):
        raise ValueError("Açık anahtar biçimi tanınmadı.")
    try:
        raw = base64.b64decode(text[len(PUBLIC_KEY_PREFIX) :], validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Açık anahtar bozuk.") from exc


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise LicenseFormatError("Lisans anahtarı bozuk.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise LicenseFormatError("Lisans anahtarı bozuk.") from None


def _decode_payload(payload: bytes) -> LicenseData:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise LicenseFormatError("Lisans anahtarı bozuk.") from None
    if not isinstance(document, dict) or document.get("v") != FORMAT_VERSION:
        raise LicenseFormatError("Bu lisans anahtarı programın bu sürümüyle uyumlu değil.")
    code = normalize_machine_code(str(document.get("mc", "")))
    name = document.get("n")
    license_id = document.get("id")
    if code is None or not isinstance(name, str) or not isinstance(license_id, str):
        raise LicenseFormatError("Lisans anahtarı bozuk.")
    return LicenseData(code, name, _parse_date(document.get("exp")), _parse_date(document.get("iat")), license_id)


def verify(text: str, public_keys: list[Ed25519PublicKey]) -> LicenseData:
    """Anahtarın imzasını denetler ve içeriğini döndürür.

    Bilgisayar kodu ve bitiş tarihi burada denetlenmez (çağıran bilir).
    """
    compact = re.sub(r"\s", "", text or "")
    if not compact:
        raise LicenseFormatError("Lisans anahtarı boş.")
    if len(compact) > MAX_KEY_LENGTH:
        raise LicenseFormatError("Lisans anahtarı çok uzun; yalnızca size gönderilen anahtarı yapıştırın.")
    parts = compact.split(".")
    if len(parts) != 3 or parts[0] != KEY_PREFIX:
        raise LicenseFormatError("Bu bir English Master lisans anahtarı değil. Anahtarı eksiksiz yapıştırdığınızdan emin olun.")
    try:
        payload, signature = _b64d(parts[1]), _b64d(parts[2])
    except (binascii.Error, ValueError):
        raise LicenseFormatError("Lisans anahtarı bozuk. Eksiksiz kopyaladığınızdan emin olun.") from None
    for key in public_keys:
        try:
            key.verify(signature, payload)
        except InvalidSignature:
            continue
        return _decode_payload(payload)
    raise LicenseFormatError("Lisans anahtarı doğrulanamadı. Anahtar eksik kopyalanmış ya da değiştirilmiş olabilir.")
