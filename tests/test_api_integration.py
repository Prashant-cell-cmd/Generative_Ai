
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app


class TranscriptionApiIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = app.DB_PATH
        app.DB_PATH = Path(self.temp_dir.name) / "test.db"
        self.client = TestClient(app.app)

    def tearDown(self):
        self.client.close()
        app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_create_and_list_transcription(self):
        response = self.client.post(
            "/api/transcriptions",
            json={"text": "Hello world", "language": "en-US"}
        )

        self.assertEqual(response.status_code, 201)
        created = response.json()
        self.assertEqual(created["text"], "Hello world")
        self.assertEqual(created["language"], "en-US")

        list_response = self.client.get("/api/transcriptions")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)
        self.assertEqual(list_response.json()[0]["id"], created["id"])

    def test_update_transcription(self):
        create_response = self.client.post(
            "/api/transcriptions",
            json={"text": "Original text", "language": "en-US"}
        )
        transcription_id = create_response.json()["id"]

        update_response = self.client.put(
            f"/api/transcriptions/{transcription_id}",
            json={"text": "Updated text", "language": "hi-IN"}
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["text"], "Updated text")
        self.assertEqual(update_response.json()["language"], "hi-IN")

    def test_delete_transcription(self):
        create_response = self.client.post(
            "/api/transcriptions",
            json={"text": "Text to delete", "language": "en-US"}
        )
        transcription_id = create_response.json()["id"]

        delete_response = self.client.delete(
            f"/api/transcriptions/{transcription_id}"
        )

        self.assertEqual(delete_response.status_code, 204)

        list_response = self.client.get("/api/transcriptions")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json(), [])

    def test_empty_text_returns_validation_error(self):
        response = self.client.post(
            "/api/transcriptions",
            json={"text": "", "language": "en-US"}
        )

        self.assertEqual(response.status_code, 422)

    def test_missing_transcription_returns_404(self):
        response = self.client.put(
            "/api/transcriptions/9999",
            json={"text": "Updated text", "language": "en-US"}
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
