from pathlib import Path

from app.core import config


def test_data_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_DATA_DIR, str(tmp_path / "x"))
    assert config.default_data_dir() == tmp_path / "x"


def test_windows_data_dir_uses_localappdata(monkeypatch):
    monkeypatch.delenv(config.ENV_DATA_DIR, raising=False)
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
    assert config.default_data_dir() == Path(r"C:\Users\test\AppData\Local") / "EnglishMaster"


def test_user_data_is_separate_from_install_dir(settings):
    root = config.resource_root()
    assert root not in settings.user_db_path.parents
    assert settings.user_db_path.parent == settings.data_dir
    assert settings.backups_dir.parent == settings.data_dir


def test_default_host_is_loopback(settings):
    assert settings.host == "127.0.0.1"
