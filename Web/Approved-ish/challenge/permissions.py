"""Read permissions for workspace members."""


def can_read(shard):
    return not shard.restricted
