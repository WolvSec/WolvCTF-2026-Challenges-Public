import json
import re
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    reply = b"{}"
    status = 200

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path != "/login" or self.headers["Content-Type"] != "application/json" or body != b'{"user":"admin","token":[]}':
            self.send_error(400)
            return
        self.send_response(self.status)
        self.end_headers()
        self.wfile.write(self.reply)

    def log_message(self, *_args):
        pass


class SolveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()

    def run_solve(self):
        return subprocess.run(
            [sys.executable, str(ROOT / "solution/solve.py"), f"http://127.0.0.1:{self.server.server_port}"],
            capture_output=True, timeout=5,
        )

    def test_exact_flag_required(self):
        expected = (ROOT / "flag.txt").read_text().strip()
        self.assertTrue(re.fullmatch(r"wctf\{[0-9a-f]{32}\}", expected))
        self.assertTrue(all((ROOT / path).read_text().strip() == expected for path in ("challenge/flag.txt", "healthcheck/flag.txt")))
        Handler.reply = json.dumps({"flag": expected}).encode()
        self.assertEqual(self.run_solve().returncode, 0)
        Handler.reply = json.dumps({"flag": expected + "wrong"}).encode()
        self.assertNotEqual(self.run_solve().returncode, 0)
        Handler.reply = b'{"message":"no flag"}'
        self.assertNotEqual(self.run_solve().returncode, 0)
        Handler.status = 403
        self.assertNotEqual(self.run_solve().returncode, 0)
        Handler.status = 200


if __name__ == "__main__":
    unittest.main()
