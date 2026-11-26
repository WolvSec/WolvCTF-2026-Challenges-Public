#!/usr/bin/env python3
"""Deployment healthcheck: /healthz responds and the intended solve still works.

Usage: python3 healthcheck.py [BASE_URL] [EXPECTED_FLAG]
  BASE_URL       default http://127.0.0.1:8000
  EXPECTED_FLAG  default: contents of ../flag.txt
Exit status 0 means healthy and solvable.
"""

import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "solve"))
from solve import solve  # noqa: E402


def main(base="http://127.0.0.1:8000", expected=None):
    base = base.rstrip("/")
    if expected is None:
        expected = (ROOT / "flag.txt").read_text().strip()
    try:
        with urlopen(base + "/healthz", timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(f"/healthz returned {response.status}")
        flag = solve(base, verbose=False)
    except Exception as error:  # report any failure as unhealthy
        print(f"UNHEALTHY: {error}")
        return 1
    if flag != expected:
        print("UNHEALTHY: solver result did not match the configured flag")
        return 1
    print("HEALTHY: intended solve returns the expected flag")
    return 0


def serve():
    status = {"healthy": False}

    def probe():
        while True:
            status["healthy"] = main() == 0
            time.sleep(30)

    class Healthz(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/healthz":
                self.send_error(404)
                return
            body = b"ok" if status["healthy"] else b"err"
            self.send_response(200 if status["healthy"] else 503)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    threading.Thread(target=probe, daemon=True).start()
    HTTPServer(("", 45281), Healthz).serve_forever()


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve"]:
        serve()
    else:
        sys.exit(main(*sys.argv[1:]))
