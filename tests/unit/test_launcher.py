import pytest
import socket

from app import launcher


def test_single_instance_lock(tmp_path):
    first = launcher.SingleInstanceLock(tmp_path / "app.lock")
    second = launcher.SingleInstanceLock(tmp_path / "app.lock")
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_find_free_port_falls_back_when_busy():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        taken = busy.getsockname()[1]
        port = launcher.find_free_port(taken)
        assert port != taken and port > 0


def test_running_url_none_without_instance_file(tmp_path):
    assert launcher.read_running_url(tmp_path) is None


def test_running_url_none_when_instance_dead(tmp_path):
    launcher.write_instance_info(tmp_path, launcher.find_free_port(0))
    assert launcher.read_running_url(tmp_path) is None


def test_icon_is_drawn_and_saved_as_ico(tmp_path):
    pytest.importorskip("PIL")
    from app.core.icon import draw_icon, write_ico

    image = draw_icon(64)
    assert image.size == (64, 64) and image.getpixel((32, 4))[:3] == (0x2F, 0x5F, 0xD0)
    path = tmp_path / "icon.ico"
    write_ico(path)
    assert path.read_bytes()[:4] == b"\x00\x00\x01\x00"  # ICO dosya imzası
