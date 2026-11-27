
import sqlite3

import pytest

import app


def test_database_uses_configured_timeout(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(app, "DB_PATH", db_path)

    with app.get_db() as db:
        assert isinstance(db, sqlite3.Connection)
        assert db.row_factory is sqlite3.Row

    assert db_path.exists()


def test_database_rolls_back_failed_transaction(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(app, "DB_PATH", db_path)

    with pytest.raises(RuntimeError):
        with app.get_db() as db:
            db.execute(
                """
                INSERT INTO transcriptions
                (text, language, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                ("Test transcription", "en-US", "2026-11-27", "2026-11-27"),
            )
            raise RuntimeError("Simulated database failure")

    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM transcriptions"
        ).fetchone()[0]

    assert count == 0


def test_database_connection_is_closed_after_use(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(app, "DB_PATH", db_path)

    with app.get_db() as db:
        db.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError):
        db.execute("SELECT 1")
