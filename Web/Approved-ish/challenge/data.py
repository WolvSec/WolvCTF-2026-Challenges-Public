"""Dataset catalog shared by independent workspaces."""

from dataclasses import dataclass
from flask import abort, current_app


@dataclass(frozen=True)
class Shard:
    id: str
    name: str
    restricted: bool
    content: str


def catalog():
    return [
        {"id": "sample-v1", "name": "Training sample v1", "restricted": False},
        {"id": "sample-v2", "name": "Training sample v2", "restricted": False},
        {"id": "restricted-v1", "name": "Curator evaluation set", "restricted": True},
    ]


def get_shard(shard_id):
    if not isinstance(shard_id, str):
        abort(400, description="Shard ID must be a string.")
    for item in catalog():
        if item["id"] == shard_id:
            contents = {
                "sample-v1": "feature,label\n0.1,0\n0.9,1\n",
                "sample-v2": "feature,label\n0.2,0\n0.8,1\n",
                "restricted-v1": current_app.config["FLAG"],
            }
            return Shard(**item, content=contents[shard_id])
    abort(404)
