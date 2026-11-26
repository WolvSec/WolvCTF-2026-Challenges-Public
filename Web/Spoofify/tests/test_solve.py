import importlib.util
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "solution"))
from solve import solve


class Handler(BaseHTTPRequestHandler):
    free_cookie = True
    free_body = b"<title>Spoofify</title>"
    premium_body = b'<div class="flagbox"><code>wctf{sample}</code></div>'

    def do_GET(self):
        premium = self.headers.get("Cookie") == "sid=premium"
        body = self.premium_body if premium else self.free_body
        self.send_response(200)
        if not premium and self.free_cookie:
            self.send_header("Set-Cookie", "sid=free; Path=/")
        self.end_headers()
        self.wfile.write(body)

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

    def setUp(self):
        Handler.free_cookie = True
        Handler.free_body = b"<title>Spoofify</title>"
        Handler.premium_body = b'<div class="flagbox"><code>wctf{sample}</code></div>'
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def test_cookie_tamper_and_free_view(self):
        self.assertEqual(solve(self.base), "wctf{sample}")
        Handler.free_body = b"wctf{sample}"
        with self.assertRaises(RuntimeError):
            solve(self.base)
        Handler.free_body = b"<title>Spoofify</title>"
        Handler.free_cookie = False
        with self.assertRaises(RuntimeError):
            solve(self.base)

    def test_healthcheck_requires_exact_flag(self):
        copies = [ROOT / path for path in ("flag.txt", "challenge/flag", "healthcheck/flag")]
        self.assertTrue(all(path.read_bytes() == copies[0].read_bytes() for path in copies))
        self.assertTrue((ROOT / "solution/solve.py").read_bytes() == (ROOT / "healthcheck/solve.py").read_bytes())
        spec = importlib.util.spec_from_file_location("spoof_healthcheck", ROOT / "healthcheck/healthcheck.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.Path, "read_text", return_value="wctf{sample}\n"):
            with patch.object(module, "solve", return_value="wctf{sample}"):
                self.assertEqual(module.main(), 0)
            with patch.object(module, "solve", return_value="wctf{different}"):
                self.assertEqual(module.main(), 1)


if __name__ == "__main__":
    unittest.main()
