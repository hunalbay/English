"""Lisans anahtarı biçimi ve yerel lisans durumu."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core import license_format as lf
from app.services.license import LicenseError, LicenseManager

TODAY = date(2026, 11, 21)


def test_machine_code_is_stable_grouped_and_checked():
    code = lf.machine_code_from_id("4C4C4544-0042-3510-8051-B4C04F4A4E32")
    assert code == lf.machine_code_from_id("  4c4c4544-0042-3510-8051-b4c04f4a4e32 ")
    assert len(code) == 19 and code.count("-") == 3
    assert lf.normalize_machine_code(code.lower().replace("-", " ")) == code
    # tek karakterlik yazım hatası denetim parçasıyla yakalanır
    typo = ("B" if code[0] != "B" else "C") + code[1:]
    assert lf.normalize_machine_code(typo) is None
    assert lf.normalize_machine_code("") is None
    assert lf.machine_code_from_id("başka-bilgisayar") != code


def test_sign_and_verify_roundtrip(signer):
    key = signer.key(expires=date(2027, 3, 1), name="Ayşe  Yılmaz", issued=TODAY)
    public = [lf.load_public_key(signer.public_text)]
    data = lf.verify(key, public)
    assert data.name == "Ayşe Yılmaz" and data.expires == date(2027, 3, 1)
    assert data.machine_code == signer.machine_code
    # WhatsApp gibi uygulamaların eklediği satır sonu/boşluklar sorun olmaz
    assert lf.verify(key[:40] + "\n " + key[40:], public) == data


def test_tampered_or_foreign_keys_are_rejected(signer):
    public = [lf.load_public_key(signer.public_text)]
    key = signer.key(issued=TODAY)
    prefix, payload, signature = key.split(".")
    forged = json.loads(lf._b64d(payload))
    forged["exp"] = "2099-01-01"
    forged_key = ".".join([prefix, lf._b64e(json.dumps(forged).encode()), signature])
    other_signer = Ed25519PrivateKey.generate()
    foreign = lf.sign(lf.new_license(signer.machine_code, "X", TODAY, TODAY), other_signer)
    for bad in (forged_key, foreign, key[:-3], "EM1.abc", "merhaba", "", "x" * 5000):
        with pytest.raises(lf.LicenseFormatError):
            lf.verify(bad, public)


def test_new_license_validation(signer):
    with pytest.raises(ValueError, match="Bilgisayar kodu"):
        lf.new_license("AAAA-BBBB-CCCC-DDDD", "Ali", TODAY, TODAY)
    with pytest.raises(ValueError, match="Bitiş"):
        lf.new_license(signer.machine_code, "Ali", TODAY - timedelta(days=1), TODAY)
    with pytest.raises(ValueError):
        lf.new_license(signer.machine_code, "   ", TODAY, TODAY)
    with pytest.raises(ValueError):
        lf.new_license(signer.machine_code, "a" * 61, TODAY, TODAY)


def _manager(settings) -> LicenseManager:
    return LicenseManager(settings)


def test_missing_then_install_valid_key(unlicensed_settings, signer):
    manager = _manager(unlicensed_settings)
    assert manager.status(TODAY).state == "missing"
    status = manager.install(signer.key(expires=date(2026, 12, 1), issued=TODAY), TODAY)
    assert status.licensed and status.expires == "2026-12-01" and status.days_left == 10 and status.warn
    stored = json.loads(unlicensed_settings.license_path.read_text(encoding="utf-8"))
    assert stored["last_seen"] == TODAY.isoformat()
    # yeni bir süreç (program yeniden açıldı) aynı sonucu bulur
    assert _manager(unlicensed_settings).status(TODAY).licensed


def test_expiry_is_inclusive_of_the_end_date(unlicensed_settings, signer):
    manager = _manager(unlicensed_settings)
    manager.install(signer.key(expires=date(2026, 12, 1), issued=TODAY), TODAY)
    last_day = _manager(unlicensed_settings).status(date(2026, 12, 1))
    assert last_day.licensed and last_day.days_left == 0
    after = _manager(unlicensed_settings).status(date(2026, 12, 2))
    assert after.state == "expired" and after.name == "Test Kullanıcı"


def test_key_for_another_machine_is_refused(unlicensed_settings, signer):
    other = lf.machine_code_from_id("baska-bilgisayar")
    with pytest.raises(LicenseError, match="başka bir bilgisayar"):
        _manager(unlicensed_settings).install(signer.key(machine_code=other, issued=TODAY), TODAY)
    assert not unlicensed_settings.license_path.exists()


def test_license_file_copied_to_another_machine_does_not_work(settings):
    moved = replace(settings, machine_id_override="baska-bilgisayar")
    assert _manager(moved).status().state == "other_machine"


def test_expired_or_invalid_key_does_not_replace_a_working_license(unlicensed_settings, signer):
    manager = _manager(unlicensed_settings)
    good = signer.key(issued=TODAY)
    manager.install(good, TODAY)
    with pytest.raises(LicenseError, match="süresi dolmuş"):
        manager.install(signer.key(expires=TODAY - timedelta(days=1), issued=TODAY - timedelta(days=30)), TODAY)
    with pytest.raises(LicenseError):
        manager.install("EM1.bozuk.anahtar", TODAY)
    assert json.loads(unlicensed_settings.license_path.read_text(encoding="utf-8"))["key"] == good


def test_renewal_keeps_backup_of_previous_key(unlicensed_settings, signer):
    manager = _manager(unlicensed_settings)
    first = signer.key(expires=date(2026, 12, 1), issued=TODAY)
    manager.install(first, TODAY)
    status = manager.install(signer.key(expires=date(2027, 6, 30), issued=TODAY), TODAY)
    assert status.expires == "2027-06-30"
    backup = unlicensed_settings.license_path.with_suffix(".json.bak")
    assert json.loads(backup.read_text(encoding="utf-8"))["key"] == first


def test_clock_rollback_is_detected_but_small_differences_are_tolerated(unlicensed_settings, signer):
    key = signer.key(expires=date(2027, 1, 31), issued=TODAY)
    _manager(unlicensed_settings).install(key, TODAY)
    assert _manager(unlicensed_settings).status(date(2027, 1, 20)).licensed  # son görülen tarih ileri gider
    assert _manager(unlicensed_settings).status(date(2027, 1, 18)).licensed  # 2 gün tolerans
    assert _manager(unlicensed_settings).status(date(2027, 1, 10)).state == "clock"
    # aynı anahtarı yeniden girmek saat denetimini atlatmaz
    with pytest.raises(LicenseError, match="tarihi"):
        _manager(unlicensed_settings).install(key, date(2027, 1, 10))
    # sahibinin verdiği yeni bir anahtar kaydı sıfırlar
    fresh = signer.key(expires=date(2027, 3, 1), issued=date(2027, 1, 10))
    assert _manager(unlicensed_settings).install(fresh, date(2027, 1, 10)).licensed


def test_corrupt_license_file_reports_invalid_and_is_not_deleted(unlicensed_settings):
    unlicensed_settings.data_dir.mkdir(parents=True, exist_ok=True)
    unlicensed_settings.license_path.write_text("{bozuk", encoding="utf-8")
    assert _manager(unlicensed_settings).status(TODAY).state == "invalid"
    assert unlicensed_settings.license_path.read_text(encoding="utf-8") == "{bozuk"


def test_build_without_public_key_accepts_nothing(unlicensed_settings, signer):
    bare = replace(unlicensed_settings, license_public_keys=())
    manager = _manager(bare)
    assert manager.status(TODAY).state == "unconfigured"
    with pytest.raises(LicenseError, match="yapılandırılmamış"):
        manager.install(signer.key(issued=TODAY), TODAY)


def test_shipped_public_key_list_is_valid():
    from app.core.license_keys import PUBLIC_KEYS

    for text in PUBLIC_KEYS:
        lf.load_public_key(text)
