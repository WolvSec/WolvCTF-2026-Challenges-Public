"""Manifest review and approval records."""

import hashlib
import json

from flask import abort

from data import get_shard
from permissions import can_read
from storage import database, own_alias


def manifest_digest(manifest):
    document = {key: manifest[key] for key in ("id", "workspace_id", "version", "alias_ids")}
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def preview(manifest):
    result = []
    for alias_id in manifest["alias_ids"]:
        alias = own_alias(alias_id)
        shard = get_shard(alias["target_shard_id"])
        if not can_read(shard):
            abort(403, description="The current dataset contains a restricted shard.")
        result.append({"alias_id": alias_id, "shard_id": shard.id, "content": shard.content})
    return result


def approve(manifest):
    preview(manifest)
    digest = manifest_digest(manifest)
    database().execute(
        "INSERT INTO approvals(manifest_id,version,digest) VALUES (?,?,?) "
        "ON CONFLICT(manifest_id) DO UPDATE SET version=excluded.version,digest=excluded.digest",
        (manifest["id"], manifest["version"], digest))
    return {"manifest_id": manifest["id"], "version": manifest["version"], "digest": digest}
