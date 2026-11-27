import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

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
            app.TranscriptionCreate(text="  Hello world  ", language="hi-IN")
        )
        self.assertEqual(created["text"], "Hello world")
        self.assertEqual(created["language"], "hi-IN")
        self.assertTrue(created["created_at"].endswith("Z"))

        updated = app.update_transcription(
            created["id"], app.TranscriptionUpdate(text="  Namaste  ")
        )
        self.assertEqual(updated["text"], "Namaste")
        self.assertEqual(updated["language"], "hi-IN")
        self.assertEqual(app.list_transcriptions()[0]["id"], created["id"])

        app.delete_transcription(created["id"])
        self.assertEqual(app.list_transcriptions(), [])

    def test_blank_text_is_rejected(self):
        with self.assertRaises(HTTPException) as create_error:
            app.create_transcription(app.TranscriptionCreate(text="   "))
        self.assertEqual(create_error.exception.status_code, 422)

        with self.assertRaises(HTTPException) as update_error:
            app.update_transcription(
                1, app.TranscriptionUpdate(text="   ")
            )
        self.assertEqual(update_error.exception.status_code, 422)

    def test_missing_transcription_returns_not_found(self):
        with self.assertRaises(HTTPException) as error:
            app.delete_transcription(1)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
