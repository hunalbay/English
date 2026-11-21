"""Bilgisayar kimliği: lisans anahtarını tek bir bilgisayara bağlamak için.

Windows'ta işletim sisteminin kurulumda ürettiği MachineGuid değeri okunur
(yönetici izni gerekmez). Bu değer program kaldırılıp kurulunca değişmez;
Windows yeniden kurulursa değişir. Değerin kendisi hiçbir yere gönderilmez:
kullanıcıya yalnızca bundan türetilen ve geri çevrilemeyen bilgisayar kodu
gösterilir.
"""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

FALLBACK_FILENAME = "machine-id"


def _windows_machine_guid() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value) or None
    except OSError:
        return None


def _linux_machine_id() -> str | None:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            value = Path(path).read_text(encoding="ascii").strip()
        except OSError:
            continue
        if value:
            return value
    return None


def _mac_platform_uuid() -> str | None:
    try:
        output = subprocess.run(  # noqa: S603
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in output.splitlines():
        if "IOPlatformUUID" in line:
            return line.split("=", 1)[-1].strip().strip('"') or None
    return None


def system_machine_id() -> str | None:
    if sys.platform == "win32":
        return _windows_machine_guid()
    if sys.platform == "darwin":
        return _mac_platform_uuid()
    return _linux_machine_id()


def machine_id(data_dir: Path) -> str:
    """İşletim sisteminin kimliği; okunamazsa veri klasöründe bir kez üretilen rastgele kimlik."""
    value = system_machine_id()
    if value:
        return value
    path = data_dir / FALLBACK_FILENAME
    try:
        existing = path.read_text(encoding="ascii").strip()
        if existing:
            return existing
    except OSError:
        pass
    value = str(uuid.uuid4())
    try:
        path.write_text(value, encoding="ascii")
    except OSError:
        pass
    return value
