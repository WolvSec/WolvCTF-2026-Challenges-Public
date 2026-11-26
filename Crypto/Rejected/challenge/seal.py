#!/usr/bin/env python3
"""Flag envelope. The signing key's s1, not the full key, is the password."""

import hashlib
import hmac
import json
import os
from pathlib import Path
import sys


def main():
    secret = Path(sys.argv[1]).read_bytes()
    flag = Path(sys.argv[2]).read_bytes().rstrip(b"\n")
    if len(secret) != 1024 or any(x > 4 for x in secret):
        raise ValueError("bad s1 serialization")
    master = hashlib.sha3_256(b"Rejected/flag-key/v1" + secret).digest()
    nonce = os.urandom(24)
    stream = hashlib.shake_256(b"Rejected/stream/v1" + master + nonce).digest(len(flag))
    ciphertext = bytes(a ^ b for a, b in zip(flag, stream))
    auth_key = hashlib.sha3_256(b"Rejected/auth/v1" + master).digest()
    tag = hmac.digest(auth_key, nonce + ciphertext, "sha256")
    Path(sys.argv[3]).write_text(json.dumps({
        "nonce": nonce.hex(), "ciphertext": ciphertext.hex(), "tag": tag.hex()
    }, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
