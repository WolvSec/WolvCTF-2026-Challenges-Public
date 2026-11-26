#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer


class Healthz(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/healthz":
            self.send_error(404)
            return
        try:
            with open("/tmp/healthz", "rb") as status:
                healthy = status.read().strip() == b"ok"
        except OSError:
            healthy = False
        body = b"ok" if healthy else b"err"
        self.send_response(200 if healthy else 503)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("", 45281), Healthz).serve_forever()
