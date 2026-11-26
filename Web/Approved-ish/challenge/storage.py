"""SQLite storage with workspace-scoped lookups."""

import json
import sqlite3
from pathlib import Path

from flask import abort, current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, expires INTEGER NOT NULL,
    peer_addr TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS aliases (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    target_shard_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manifests (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    version INTEGER NOT NULL, alias_ids TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    manifest_id TEXT PRIMARY KEY REFERENCES manifests(id) ON DELETE CASCADE,
    version INTEGER NOT NULL, digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS aliases_workspace ON aliases(workspace_id);
CREATE INDEX IF NOT EXISTS manifests_workspace ON manifests(workspace_id);
CREATE INDEX IF NOT EXISTS workspace_expiry ON workspaces(expires);
"""


def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        if "peer_addr" not in {row[1] for row in conn.execute("PRAGMA table_info(workspaces)")}:
            conn.execute("ALTER TABLE workspaces ADD COLUMN peer_addr TEXT NOT NULL DEFAULT 'legacy'")
        conn.execute("CREATE INDEX IF NOT EXISTS workspace_peer ON workspaces(peer_addr,expires)")
        conn.commit()
    finally:
        conn.close()


def database():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def own_alias(alias_id):
    row = database().execute("SELECT * FROM aliases WHERE id=? AND workspace_id=?",
                             (alias_id, g.workspace["id"])).fetchone()
    if row is None:
        abort(404)
    return dict(row)


def own_alias_nocase(alias_id):
    # Older backups exported alias IDs with inconsistent casing, so restore looks
    # them up case-insensitively to stay compatible with them.
    row = database().execute("SELECT * FROM aliases WHERE id=? COLLATE NOCASE AND workspace_id=?",
                             (alias_id, g.workspace["id"])).fetchone()
    if row is None:
        abort(404)
    return dict(row)


def own_manifest(manifest_id):
    row = database().execute("SELECT * FROM manifests WHERE id=? AND workspace_id=?",
                             (manifest_id, g.workspace["id"])).fetchone()
    if row is None:
        abort(404)
    result = dict(row)
    result["alias_ids"] = json.loads(result["alias_ids"])
    return result


def approval_for(manifest_id):
    return database().execute("SELECT * FROM approvals WHERE manifest_id=?", (manifest_id,)).fetchone()


def locked_alias_ids():
    rows = database().execute(
        "SELECT m.alias_ids FROM manifests m JOIN approvals a ON a.manifest_id=m.id "
        "WHERE m.workspace_id=?", (g.workspace["id"],))
    ids = set()
    for row in rows:
        ids.update(json.loads(row["alias_ids"]))
    return ids


def alias_locked(alias_id):
    return alias_id in locked_alias_ids()
