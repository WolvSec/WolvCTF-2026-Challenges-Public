"""Build approved snapshots using the dataset service's read authority."""

from flask import abort

from data import get_shard
from review import manifest_digest
from storage import approval_for, own_alias


def build_snapshot(manifest):
    approval = approval_for(manifest["id"])
    if approval is None:
        abort(409, description="Review this manifest before building a snapshot.")
    if approval["version"] != manifest["version"] or approval["digest"] != manifest_digest(manifest):
        abort(409, description="Approval does not match this manifest.")
    shards = []
    for alias_id in manifest["alias_ids"]:
        alias = own_alias(alias_id)
        shard = get_shard(alias["target_shard_id"])
        shards.append({"alias_id": alias_id, "shard_id": shard.id, "content": shard.content})
    return {"manifest_id": manifest["id"], "version": manifest["version"], "shards": shards}
