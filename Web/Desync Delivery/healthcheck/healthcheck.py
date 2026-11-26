#!/usr/bin/env python3
"""Periodically solve the local service and expose the result to KCTF."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from subprocess import DEVNULL, PIPE, TimeoutExpired, run
from threading import Thread
from time import sleep

healthy = False
expected_flag = Path(__file__).with_name("flag.txt").read_bytes().strip()


def check_forever():
    global healthy
    while True:
        try:
            result = run(
                ["python3", str(Path(__file__).with_name("solve.py")), "http://127.0.0.1:8080"],
                stdout=PIPE, stderr=DEVNULL, timeout=20,
            )
            healthy = result.returncode == 0 and result.stdout.splitlines()[-1:] == [expected_flag]
        except (TimeoutExpired, OSError):
            healthy = False
        sleep(30)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"ok" if healthy else b"err"
        status = 404 if self.path != "/healthz" else 200 if healthy else 503
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


Thread(target=check_forever, daemon=True).start()
HTTPServer(("0.0.0.0", 45281), Handler).serve_forever()
