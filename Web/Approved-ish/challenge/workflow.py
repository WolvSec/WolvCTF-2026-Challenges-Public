"""Workspace catalog, alias maintenance, and dataset releases."""

import json
from uuid import uuid4

from flask import Blueprint, abort, g, jsonify, request

from data import catalog, get_shard
from exporter import build_snapshot
from permissions import can_read
from review import approve, preview
from storage import (alias_locked, approval_for, database, locked_alias_ids,
                     own_alias, own_alias_nocase, own_manifest)


def body_with(*fields):
    body = request.get_json()
    if not isinstance(body, dict) or set(body) != set(fields):
        abort(400, description="Expected exactly these JSON fields: " + ", ".join(fields))
    return body


def valid_alias_ids(value):
    if (not isinstance(value, list) or not 1 <= len(value) <= 20
            or any(not isinstance(item, str) or not item for item in value)):
        abort(400, description="alias_ids must contain 1 to 20 non-empty strings.")
    if len(set(value)) != len(value):
        abort(400, description="Duplicate aliases are not allowed.")
    for alias_id in value:
        own_alias(alias_id)
    return value


def create_workflow():
    routes = Blueprint("workflow", __name__, url_prefix="/api")

    @routes.get("/shards")
    def list_shards():
        return jsonify(shards=[dict(item, can_read=not item["restricted"]) for item in catalog()])

    @routes.get("/shards/<shard_id>")
    def read_shard(shard_id):
        shard = get_shard(shard_id)
        if not can_read(shard):
            abort(403, description="You cannot read this shard.")
        return jsonify(id=shard.id, name=shard.name, content=shard.content)

    @routes.get("/aliases")
    def list_aliases():
        rows = database().execute("SELECT * FROM aliases WHERE workspace_id=? ORDER BY rowid",
                                  (g.workspace["id"],)).fetchall()
        return jsonify(aliases=[dict(row, locked=alias_locked(row["id"])) for row in rows])

    @routes.post("/aliases")
    def create_alias():
        shard = get_shard(body_with("target_shard_id")["target_shard_id"])
        count = database().execute("SELECT count(*) FROM aliases WHERE workspace_id=?",
                                   (g.workspace["id"],)).fetchone()[0]
        if count >= 64:
            abort(429, description="Workspace alias limit reached.")
        alias_id = uuid4().hex
        database().execute("INSERT INTO aliases VALUES (?,?,?)", (alias_id, g.workspace["id"], shard.id))
        return jsonify(own_alias(alias_id)), 201

    @routes.get("/aliases/<alias_id>")
    def read_alias(alias_id):
        return jsonify(own_alias(alias_id))

    @routes.patch("/aliases/<alias_id>")
    def update_alias(alias_id):
        own_alias(alias_id)
        shard = get_shard(body_with("target_shard_id")["target_shard_id"])
        if alias_locked(alias_id):
            abort(409, description="This alias is locked by an approved manifest.")
        database().execute("UPDATE aliases SET target_shard_id=? WHERE id=? AND workspace_id=?",
                           (shard.id, alias_id, g.workspace["id"]))
        return jsonify(own_alias(alias_id))

    @routes.get("/aliases/backup")
    def backup_aliases():
        rows = database().execute("SELECT id,target_shard_id FROM aliases WHERE workspace_id=? ORDER BY id",
                                  (g.workspace["id"],)).fetchall()
        return jsonify(format="approved-ish.aliases.v1", workspace_id=g.workspace["id"],
                       aliases=[dict(row) for row in rows])

    @routes.post("/aliases/restore")
    def restore_aliases():
        body = body_with("format", "workspace_id", "aliases")
        if body["format"] != "approved-ish.aliases.v1" or body["workspace_id"] != g.workspace["id"]:
            abort(400, description="Backup format or workspace does not match.")
        records = body["aliases"]
        if not isinstance(records, list) or not 1 <= len(records) <= 64:
            abort(400, description="Expected 1 to 64 alias records.")
        locked = locked_alias_ids()
        seen = set()
        for record in records:
            if not isinstance(record, dict) or set(record) != {"id", "target_shard_id"}:
                abort(400, description="Invalid alias record.")
            if not isinstance(record["id"], str) or record["id"] in seen:
                abort(400, description="Invalid or duplicate alias ID.")
            seen.add(record["id"])
            own_alias_nocase(record["id"])
            if record["id"] in locked:
                abort(409, description="This alias is locked by an approved manifest.")
            get_shard(record["target_shard_id"])
        for record in records:
            database().execute("UPDATE aliases SET target_shard_id=? WHERE id=? COLLATE NOCASE AND workspace_id=?",
                               (record["target_shard_id"], record["id"], g.workspace["id"]))
        return jsonify(restored=len(records))

    @routes.get("/manifests")
    def list_manifests():
        rows = database().execute("SELECT id FROM manifests WHERE workspace_id=? ORDER BY rowid",
                                  (g.workspace["id"],)).fetchall()
        return jsonify(manifests=[dict(own_manifest(row["id"]), approved=approval_for(row["id"]) is not None)
                                  for row in rows])

    @routes.post("/manifests")
    def create_manifest():
        ids = valid_alias_ids(body_with("alias_ids")["alias_ids"])
        count = database().execute("SELECT count(*) FROM manifests WHERE workspace_id=?",
                                   (g.workspace["id"],)).fetchone()[0]
        if count >= 64:
            abort(429, description="Workspace manifest limit reached.")
        manifest_id = uuid4().hex
        database().execute("INSERT INTO manifests VALUES (?,?,?,?)",
                           (manifest_id, g.workspace["id"], 1, json.dumps(ids)))
        return jsonify(own_manifest(manifest_id)), 201

    @routes.get("/manifests/<manifest_id>")
    def read_manifest(manifest_id):
        return jsonify(own_manifest(manifest_id))

    @routes.put("/manifests/<manifest_id>")
    def edit_manifest(manifest_id):
        own_manifest(manifest_id)
        ids = valid_alias_ids(body_with("alias_ids")["alias_ids"])
        if approval_for(manifest_id) is not None:
            abort(409, description="Approved manifests cannot be edited.")
        database().execute("UPDATE manifests SET alias_ids=?,version=version+1 WHERE id=? AND workspace_id=?",
                           (json.dumps(ids), manifest_id, g.workspace["id"]))
        return jsonify(own_manifest(manifest_id))

    @routes.get("/manifests/<manifest_id>/preview")
    def preview_manifest(manifest_id):
        manifest = own_manifest(manifest_id)
        return jsonify(manifest_id=manifest_id, version=manifest["version"], shards=preview(manifest))

    @routes.post("/manifests/<manifest_id>/approve")
    def approve_manifest(manifest_id):
        return jsonify(approve(own_manifest(manifest_id)))

    @routes.get("/manifests/<manifest_id>/approval")
    def read_approval(manifest_id):
        own_manifest(manifest_id)
        approval = approval_for(manifest_id)
        return jsonify(approved=approval is not None, approval=dict(approval) if approval else None)

    @routes.post("/manifests/<manifest_id>/snapshot")
    def snapshot(manifest_id):
        response = jsonify(build_snapshot(own_manifest(manifest_id)))
        response.headers["Content-Disposition"] = f'attachment; filename="snapshot-{manifest_id}.json"'
        return response

    return routes
