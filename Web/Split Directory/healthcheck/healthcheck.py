#!/usr/bin/env python3
"""KCTF sidecar: periodically run the public-API solve."""

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from solve import solve

expected = Path("/home/user/flag.txt").read_text().strip()
healthy = False


def probe():
    global healthy
    while True:
        try:
            healthy = solve("http://127.0.0.1:8080") == expected
        except Exception as error:
            healthy = False
            print(f"healthcheck failed: {error}", flush=True)
        time.sleep(30)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status = 200 if self.path == "/healthz" and healthy else 503
        body = b"ok" if status == 200 else b"not ready"
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    threading.Thread(target=probe, daemon=True).start()
    HTTPServer(("0.0.0.0", 45281), Handler).serve_forever()
