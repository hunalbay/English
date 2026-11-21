import sqlite3

import pytest

from app.services import migrations


def _tables(path):
    conn = sqlite3.connect(path)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def test_fresh_database_is_created_at_head(settings):
    head = migrations.run_migrations(settings)
    assert head == migrations.head_revision(settings) == migrations.current_revision(settings.user_db_path)
    assert {"application_settings", "user_profile", "alembic_version"} <= _tables(settings.user_db_path)
    assert list(settings.backups_dir.glob("*.db")) == []  # yeni kurulumda yedek gerekmez


def test_up_to_date_database_is_not_touched(settings):
    migrations.run_migrations(settings)
    migrations.run_migrations(settings)
    assert list(settings.backups_dir.glob("*.db")) == []


def _make_outdated_db_with_data(settings):
    migrations.run_migrations(settings)
    conn = sqlite3.connect(settings.user_db_path)
    conn.execute("INSERT INTO application_settings VALUES ('theme', '\"dark\"', '2026-01-01')")
    conn.execute("UPDATE alembic_version SET version_num = 'eski'")
    conn.commit()
    conn.close()


def test_failed_migration_restores_data(settings, monkeypatch):
    _make_outdated_db_with_data(settings)

    def broken_upgrade(_config, _target):
        conn = sqlite3.connect(settings.user_db_path)
        conn.execute("DELETE FROM application_settings")  # yarım kalmış, veri bozan güncelleme
        conn.commit()
        conn.close()
        raise RuntimeError("boom")

    monkeypatch.setattr(migrations.command, "upgrade", broken_upgrade)
    with pytest.raises(migrations.MigrationError):
        migrations.run_migrations(settings)

    backups = list(settings.backups_dir.glob("user-pre-migration-*.db"))
    assert len(backups) == 1
    conn = sqlite3.connect(settings.user_db_path)
    assert conn.execute("SELECT value FROM application_settings WHERE key='theme'").fetchone() == ('"dark"',)
    conn.close()


def test_backup_is_a_valid_database(settings):
    migrations.run_migrations(settings)
    backup = migrations.backup_database(settings.user_db_path, settings.backups_dir, "test")
    conn = sqlite3.connect(backup)
    assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    conn.close()


def test_user_db_enforces_constraints(app):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    with app.state.user_engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        with pytest.raises(IntegrityError):
            conn.execute(text(
                "INSERT INTO user_profile (id, current_level, created_at, updated_at) "
                "VALUES (1, 'Z9', '2026-01-01', '2026-01-01')"
            ))


def test_upgrade_from_0004_keeps_test_history(settings):
    """Aşama 6 kullanıcısının test geçmişi 0005'e geçerken korunur ve yeni oturum türü kullanılabilir."""
    from alembic import command

    settings.ensure_dirs()
    config = migrations.alembic_config(settings)
    command.upgrade(config, "0004")
    conn = sqlite3.connect(settings.user_db_path)
    conn.execute("INSERT INTO test_sessions (id, kind, level, question_ids, started_at) "
                 "VALUES (1, 'level', 'A1', '[\"q.x\"]', '2026-01-01 10:00:00')")
    conn.execute("INSERT INTO user_answers (session_id, question_id, lesson_id, answer_json, result, answered_at) "
                 "VALUES (1, 'q.x', 'gram.a1.to-be-present', '1', 'correct', '2026-01-01 10:01:00')")
    conn.commit()
    conn.close()

    assert migrations.run_migrations(settings) == "0006"
    assert list(settings.backups_dir.glob("*.db"))  # güncellemeden önce yedek alındı
    conn = sqlite3.connect(settings.user_db_path)
    try:
        assert conn.execute("SELECT kind, level FROM test_sessions WHERE id = 1").fetchone() == ("level", "A1")
        assert conn.execute("SELECT result FROM user_answers WHERE session_id = 1").fetchone() == ("correct",)
        conn.execute("INSERT INTO test_sessions (kind, question_ids, started_at) VALUES ('placement', '[]', '2026-01-02')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO test_sessions (kind, question_ids, started_at) VALUES ('bogus', '[]', '2026-01-02')")
    finally:
        conn.close()


def test_corrupt_user_db_stops_with_clear_message_and_is_left_untouched(settings):
    settings.ensure_dirs()
    garbage = b"bu bir veri tabani degil" * 200
    settings.user_db_path.write_bytes(garbage)
    with pytest.raises(migrations.UserDataError) as info:
        migrations.run_migrations(settings)
    assert "bozuk" in str(info.value) and str(settings.backups_dir) in str(info.value)
    assert settings.user_db_path.read_bytes() == garbage  # dosyaya dokunulmadı
    assert list(settings.backups_dir.glob("*.db")) == []
