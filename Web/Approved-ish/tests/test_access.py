"""Protect sessions, workspace boundaries, metadata, and persistent state."""

import hashlib
import sqlite3
import time
from contextlib import closing
from unittest.mock import patch

from support import AppCase, TEST_FLAG

from app import create_app


class AccessTests(AppCase):
    def test_accessible_data_and_restricted_denial(self):
        self.assertEqual(self.client.get("/api/shards/sample-v1").status_code, 200)
        denied = self.client.get("/api/shards/restricted-v1")
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn(TEST_FLAG, denied.text)
        self.assertEqual(self.client.get("/api/shards/missing").status_code, 404)

    def test_anonymous_and_forged_sessions_are_rejected(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get("/api/shards").status_code, 401)
        anonymous.set_cookie("workspace", self.workspace)
        self.assertEqual(anonymous.get("/api/shards").status_code, 401)
        response = self.client.get("/api/shards/restricted-v1?role=admin", headers={"X-Role": "admin"})
        self.assertEqual(response.status_code, 403)

    def test_metadata_never_contains_content(self):
        response = self.client.get("/api/shards")
        self.assertEqual(response.status_code, 200)
        for row in response.json["shards"]:
            self.assertEqual(set(row), {"id", "name", "restricted", "can_read"})
        self.assertNotIn(TEST_FLAG, response.text)

    def test_cross_workspace_reads_writes_and_restore_are_rejected(self):
        alias_id = self.alias()
        manifest_id = self.manifest([alias_id])
        other = self.app.test_client()
        other_workspace = other.post("/api/session").json["workspace_id"]
        for path in [f"/aliases/{alias_id}", f"/manifests/{manifest_id}",
                     f"/manifests/{manifest_id}/preview", f"/manifests/{manifest_id}/approval"]:
            self.assertEqual(other.get("/api" + path).status_code, 404)
        for suffix in ["approve", "snapshot"]:
            self.assertEqual(other.post(f"/api/manifests/{manifest_id}/{suffix}").status_code, 404)
        self.assertEqual(other.patch(f"/api/aliases/{alias_id}", json={"target_shard_id": "sample-v2"}).status_code, 404)
        self.assertEqual(other.post("/api/manifests", json={"alias_ids": [alias_id]}).status_code, 404)
        backup = self.backup(alias_id)
        self.assertEqual(other.post("/api/aliases/restore", json=backup).status_code, 400)
        backup["workspace_id"] = other_workspace
        self.assertEqual(other.post("/api/aliases/restore", json=backup).status_code, 404)
        self.assertEqual(self.client.get(f"/api/aliases/{alias_id}").json["target_shard_id"], "sample-v1")

    def test_session_survives_application_restart(self):
        alias_id = self.alias()
        restarted = create_app(self.config).test_client()
        restarted.set_cookie("workspace", self.client.get_cookie("workspace").value)
        self.assertEqual(restarted.get(f"/api/aliases/{alias_id}").status_code, 200)

    def test_delete_session_cascades_only_its_own_objects(self):
        alias_id = self.alias()
        manifest_id = self.manifest([alias_id])
        self.client.post(f"/api/manifests/{manifest_id}/approve")
        other = self.app.test_client()
        other.post("/api/session")
        other_alias = self.alias(client=other)
        self.assertEqual(self.client.delete("/api/session").status_code, 200)
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(other.get(f"/api/aliases/{other_alias}").status_code, 200)
        self.assertEqual(self.sql("SELECT count(*) FROM approvals")[0][0], 0)
        self.assertEqual(self.sql("SELECT count(*) FROM manifests")[0][0], 0)

    def test_expired_session_is_rejected_and_cleaned(self):
        self.alias()
        with patch("app.time.time", return_value=4000000000):
            self.assertEqual(self.client.get("/api/me").status_code, 401)
            self.assertEqual(self.client.post("/api/session").status_code, 201)
        self.assertEqual(self.sql("SELECT count(*) FROM aliases")[0][0], 0)

    def test_pages_health_and_source_paths(self):
        for path in ["/", "/static/app.js", "/static/style.css", "/healthz"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(TEST_FLAG, response.text)
            response.close()
        for path in ["/flag.txt", "/app.py", "/instance/approved.sqlite3", "/static/../app.py"]:
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_workspace_capacity(self):
        self.app.config["MAX_WORKSPACES"] = 1
        other = self.app.test_client()
        self.assertEqual(other.post("/api/session").status_code, 201)
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(other.get("/api/me").status_code, 200)

    def test_workspace_capacity_preserves_active_workspaces(self):
        alias_id = self.alias()
        manifest_id = self.manifest([alias_id])
        self.assertEqual(self.client.post(f"/api/manifests/{manifest_id}/approve").status_code, 200)
        self.app.config["MAX_WORKSPACES"] = 2
        other = self.app.test_client()
        self.assertEqual(other.post("/api/session").status_code, 201)
        other_alias = self.alias(client=other)
        newcomer = self.app.test_client()
        self.assertEqual(newcomer.post("/api/session").status_code, 429)
        self.assertEqual(self.client.get(f"/api/aliases/{alias_id}").status_code, 200)
        self.assertEqual(other.get(f"/api/aliases/{other_alias}").status_code, 200)
        self.assertEqual(self.sql("SELECT count(*) FROM aliases")[0][0], 2)
        self.assertEqual(self.sql("SELECT count(*) FROM approvals")[0][0], 1)

    def test_peer_quota_blocks_attacker_without_eviction_or_forwarded_header_trust(self):
        self.app.config.update(MAX_WORKSPACES=4, MAX_WORKSPACES_PER_PEER=2)
        own_alias = self.alias()
        attacker_addr = "198.51.100.9"
        attackers = []
        for _ in range(2):
            attacker = self.app.test_client()
            self.assertEqual(attacker.post("/api/session", environ_overrides={"REMOTE_ADDR": attacker_addr})
                             .status_code, 201)
            attackers.append((attacker, self.alias(client=attacker)))
        blocked = self.app.test_client().post(
            "/api/session", environ_overrides={"REMOTE_ADDR": attacker_addr},
            headers={"X-Forwarded-For": "203.0.113.2"})
        self.assertEqual(blocked.status_code, 429)
        other = self.app.test_client()
        self.assertEqual(other.post("/api/session", environ_overrides={"REMOTE_ADDR": "203.0.113.2"})
                         .status_code, 201)
        other_alias = self.alias(client=other)
        self.assertEqual(self.app.test_client().post(
            "/api/session", environ_overrides={"REMOTE_ADDR": "203.0.113.3"}).status_code, 429)
        self.assertEqual(self.client.get(f"/api/aliases/{own_alias}").status_code, 200)
        self.assertEqual(other.get(f"/api/aliases/{other_alias}").status_code, 200)
        for attacker, alias_id in attackers:
            self.assertEqual(attacker.get(f"/api/aliases/{alias_id}").status_code, 200)

    def test_peer_quota_can_replace_own_empty_workspace(self):
        self.app.config["MAX_WORKSPACES_PER_PEER"] = 1
        newcomer = self.app.test_client()
        self.assertEqual(newcomer.post("/api/session").status_code, 201)
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(newcomer.get("/api/me").status_code, 200)

    def test_existing_database_gains_peer_column_without_losing_session(self):
        legacy_path = self.config["DATABASE"] + ".legacy"
        token = "legacy-session-token"
        with closing(sqlite3.connect(legacy_path)) as db, db:
            db.execute("CREATE TABLE workspaces (id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, "
                       "expires INTEGER NOT NULL)")
            db.execute("INSERT INTO workspaces VALUES (?,?,?)",
                       ("legacy-workspace", hashlib.sha256(token.encode()).hexdigest(), int(time.time()) + 3600))
        app = create_app({**self.config, "DATABASE": legacy_path})
        old_client = app.test_client()
        old_client.set_cookie("workspace", token)
        self.assertEqual(old_client.get("/api/me").status_code, 200)
        self.assertEqual(app.test_client().post("/api/session").status_code, 201)
        with closing(sqlite3.connect(legacy_path)) as db, db:
            self.assertEqual(db.execute("SELECT peer_addr FROM workspaces WHERE id='legacy-workspace'")
                             .fetchone()[0], "legacy")

    def test_cookie_security_attributes(self):
        self.app.config["COOKIE_SECURE"] = True
        cookie = self.app.test_client().post("/api/session").headers["Set-Cookie"]
        for attribute in ["HttpOnly", "Secure", "SameSite=Lax", "Path=/"]:
            self.assertIn(attribute, cookie)
