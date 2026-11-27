
import asyncio
import io
import logging
import sqlite3
import sys
import types

import pytest
from fastapi import HTTPException
from fastapi import UploadFile

import app


def test_database_error_is_logged(tmp_path, monkeypatch, caplog):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(app, "DB_PATH", db_path)

    with caplog.at_level(logging.ERROR, logger="speech_to_text"):
        with pytest.raises(sqlite3.IntegrityError):
            with app.get_db() as db:
                db.execute(
                    """
                    INSERT INTO transcriptions
                    (text, language, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (None, "en-US", "2026-11-28", "2026-11-28"),
                )

    assert "Database operation failed" in caplog.text


def test_transcription_failure_is_logged(monkeypatch, caplog):
    class FakeWhisperModel:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("Simulated transcription failure")

    class FakeWhisper:
        def __init__(self, *args, **kwargs):
            pass

    FakeWhisper.WhisperModel = lambda *args, **kwargs: FakeWhisperModel()

    fake_av = types.ModuleType("av")
    fake_av.open = lambda *args, **kwargs: None

    fake_whisper = types.ModuleType("faster_whisper")
    fake_whisper.WhisperModel = FakeWhisper.WhisperModel

    monkeypatch.setitem(sys.modules, "av", fake_av)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_whisper)
    monkeypatch.setattr(app, "whisper_model", None)

    audio = UploadFile(
        filename="test.wav",
        file=io.BytesIO(b"fake audio"),
    )

    with caplog.at_level(logging.ERROR, logger="speech_to_text"):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                app.transcribe_audio(audio=audio, language="auto")
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Audio transcription failed"
    assert "Audio transcription failed" in caplog.text
