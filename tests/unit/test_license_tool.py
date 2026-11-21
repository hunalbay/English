"""Lisans aracı: anahtar çifti oluşturma, anahtar üretme, kayıt defteri."""

from __future__ import annotations

import csv
from datetime import date

import pytest

from app.core import license_format as lf
from scripts import license_tool as tool

CODE = lf.machine_code_from_id("arkadas-bilgisayari")


def test_init_issue_and_check(tmp_path):
    public = tool.cmd_init(tmp_path)
    assert public.startswith("em-pub-1:")
    assert (tmp_path / "private_key.pem").read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")

    text, out = tool.cmd_issue(tmp_path, CODE.lower(), "Ayşe Yılmaz", date(2027, 3, 1), today=date(2026, 11, 21))
    assert out.read_text(encoding="utf-8").strip() == text
    data = lf.verify(text, [lf.load_public_key(public)])
    assert (data.machine_code, data.name, data.expires) == (CODE, "Ayşe Yılmaz", date(2027, 3, 1))
    assert tool.cmd_check(tmp_path, text) == data

    with (tmp_path / "verilen_lisanslar.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    assert rows[0][0] == "verilis" and rows[1][1:4] == ["Ayşe Yılmaz", CODE, "2027-03-01"]


def test_init_never_overwrites_existing_private_key(tmp_path):
    tool.cmd_init(tmp_path)
    before = (tmp_path / "private_key.pem").read_bytes()
    with pytest.raises(tool.ToolError, match="Üzerine yazılmadı"):
        tool.cmd_init(tmp_path)
    assert (tmp_path / "private_key.pem").read_bytes() == before


def test_issue_validates_input(tmp_path):
    with pytest.raises(tool.ToolError, match="Gizli anahtar bulunamadı"):
        tool.cmd_issue(tmp_path, CODE, "Ali", date(2027, 1, 1))
    tool.cmd_init(tmp_path)
    with pytest.raises(ValueError, match="Bilgisayar kodu"):
        tool.cmd_issue(tmp_path, "ABCD-EFGH-IJKL-MNOP", "Ali", date(2027, 1, 1))
    with pytest.raises(ValueError, match="Bitiş"):
        tool.cmd_issue(tmp_path, CODE, "Ali", date(2026, 1, 1), today=date(2026, 11, 21))


@pytest.mark.parametrize("text", ["01.03.2027", "2027-03-01", "1/3/2027", " 01-03-2027 "])
def test_date_formats(text):
    assert tool.parse_date(text) == date(2027, 3, 1)


def test_bad_date():
    with pytest.raises(tool.ToolError):
        tool.parse_date("31.02.2027")


def test_command_line(tmp_path, capsys):
    assert tool.main(["--klasor", str(tmp_path), "init"]) == 0
    assert tool.main(["--klasor", str(tmp_path), "issue", "--kod", CODE, "--isim", "Can", "--bitis", "01.03.2099"]) == 0
    key = capsys.readouterr().out.strip().splitlines()[-1]
    assert key.startswith("EM1.")
    assert tool.main(["--klasor", str(tmp_path), "check", key]) == 0
    assert "Can" in capsys.readouterr().out
    assert tool.main(["--klasor", str(tmp_path), "issue", "--kod", "yanlis", "--isim", "Can", "--bitis", "01.03.2099"]) == 1
