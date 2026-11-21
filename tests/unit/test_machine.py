"""Bilgisayar kimliği: işletim sistemi kimliği okunamazsa veri klasöründe kalıcı bir kimlik üretilir."""

from __future__ import annotations

import sys

import pytest

from app.core import machine


def test_fallback_id_is_created_once_and_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(machine, "system_machine_id", lambda: None)
    first = machine.machine_id(tmp_path)
    assert first and (tmp_path / machine.FALLBACK_FILENAME).read_text(encoding="ascii") == first
    assert machine.machine_id(tmp_path) == first


def test_system_id_is_preferred(tmp_path, monkeypatch):
    monkeypatch.setattr(machine, "system_machine_id", lambda: "SISTEM-KIMLIGI")
    assert machine.machine_id(tmp_path) == "SISTEM-KIMLIGI"
    assert not (tmp_path / machine.FALLBACK_FILENAME).exists()


@pytest.mark.skipif(sys.platform != "win32", reason="yalnızca Windows")
def test_windows_machine_guid_is_readable_without_admin():
    value = machine._windows_machine_guid()
    assert value and len(value) >= 32
