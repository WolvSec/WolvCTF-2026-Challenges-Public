import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


os.environ["FLAG"] = "wctf{test_flag}"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "challenge"))
import app as challenge  # noqa: E402


class StickyNotesTests(unittest.TestCase):
    def test_concurrent_notes_keep_unique_ids(self):
        def create(index):
            with challenge.app.test_client() as client:
                client.post("/", data={"username": f"player{index}"})
                response = client.post("/notes", data={"title": "test", "body": "test"})
                self.assertEqual(response.status_code, 200)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(create, range(100)))
        self.assertEqual(len(challenge.notes), 102)
        self.assertEqual(challenge.next_id, 103)

    def test_large_post_is_rejected(self):
        with challenge.app.test_client() as client:
            client.post("/", data={"username": "player"})
            response = client.post("/notes", data={"title": "test", "body": "x" * 5000})
            self.assertEqual(response.status_code, 413)

    def test_note_limit_preserves_existing_notes(self):
        with challenge.app.test_client() as client, patch.object(challenge, "notes", dict.fromkeys(range(5000))):
            client.post("/", data={"username": "player"})
            response = client.post("/notes", data={"title": "test", "body": "test"})
            self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
