
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

import app


class TranscriptionApiTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = app.DB_PATH
        app.DB_PATH = Path(self.temp_dir.name) / "test.db"

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_create_update_and_delete_transcription(self):
        created = app.create_transcription(
            app.TranscriptionCreate(
                text="  Hello world  ",
                language="hi-IN"
            )
        )
        self.assertEqual(created["text"], "Hello world")
        self.assertEqual(created["language"], "hi-IN")
        self.assertTrue(created["created_at"].endswith("Z"))

        updated = app.update_transcription(
            created["id"],
            app.TranscriptionUpdate(text="  Namaste  ")
        )
        self.assertEqual(updated["text"], "Namaste")
        self.assertEqual(updated["language"], "hi-IN")
        self.assertEqual(app.list_transcriptions()[0]["id"], created["id"])

        app.delete_transcription(created["id"])
        self.assertEqual(app.list_transcriptions(), [])

    def test_blank_text_is_rejected(self):
        with self.assertRaises(ValidationError):
            app.TranscriptionCreate(text="   ")

        with self.assertRaises(ValidationError):
            app.TranscriptionUpdate(text="   ")

    def test_missing_transcription_returns_not_found(self):
        with self.assertRaises(HTTPException) as error:
            app.delete_transcription(1)

        self.assertEqual(error.exception.status_code, 404)

    def test_unsupported_language_is_rejected(self):
        with self.assertRaises(ValidationError):
            app.TranscriptionCreate(
                text="Hello world",
                language="invalid-language"
            )

        with self.assertRaises(ValidationError):
            app.TranscriptionUpdate(
                text="Hello world",
                language="invalid-language"
            )

    def test_text_exceeding_maximum_length_is_rejected(self):
        long_text = "A" * 10001

        with self.assertRaises(ValidationError):
            app.TranscriptionCreate(text=long_text)

        with self.assertRaises(ValidationError):
            app.TranscriptionUpdate(text=long_text)


if __name__ == "__main__":
    unittest.main()
