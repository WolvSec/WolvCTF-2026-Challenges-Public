"""Isolated workspaces and temporary databases for request-level tests."""

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in ("challenge", "solve", "scripts"):
    sys.path.insert(0, str(ROOT / folder))

from app import create_app  # noqa: E402

TEST_FLAG = "wctf{test_only_do_not_distribute}"


class AppCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = {"TESTING": True, "DATABASE": str(Path(self.directory.name) / "test.sqlite3"),
                       "FLAG": TEST_FLAG, "COOKIE_SECURE": False}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.workspace = self.client.post("/api/session").json["workspace_id"]

    def alias(self, target="sample-v1", client=None):
        response = (client or self.client).post("/api/aliases", json={"target_shard_id": target})
        self.assertEqual(response.status_code, 201)
        return response.json["id"]

    def manifest(self, aliases, client=None):
        response = (client or self.client).post("/api/manifests", json={"alias_ids": aliases})
        self.assertEqual(response.status_code, 201)
        return response.json["id"]

    def backup(self, alias_id, target="restricted-v1"):
        return {"format": "approved-ish.aliases.v1", "workspace_id": self.workspace,
                "aliases": [{"id": alias_id, "target_shard_id": target}]}

    def sql(self, statement, params=()):
        with closing(sqlite3.connect(self.config["DATABASE"])) as db, db:
            return db.execute(statement, params).fetchall()
