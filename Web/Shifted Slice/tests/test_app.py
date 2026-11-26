"""The intended stale slice and the boundaries around it."""

import copy
import importlib.util
import json
import os
import re
import threading
import unittest
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from http.server import ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[1]
os.environ["FLAG_FILE"] = str(ROOT / "flag.txt")
spec = importlib.util.spec_from_file_location("shifted_slice_app", ROOT / "challenge" / "app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class SliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.cookies = CookieJar()
        self.client = build_opener(HTTPCookieProcessor(self.cookies))

    def request(self, method, path, body=None, headers=None, client=None, include_headers=False):
        headers = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            response = (client or self.client).open(req, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            result = response.status, response.read()
            return (*result, response.headers) if include_headers else result

    def issue(self):
        status, raw = self.request("POST", "/api/tickets", {"key": "z-owned"})
        self.assertEqual(status, 200)
        return json.loads(raw)

    def cut(self, slip, **headers):
        base = {"Authorization": "Bearer " + slip["ticket"], "Range": slip["range"]}
        base.update(headers)
        return self.request("GET", "/api/bundle", headers=base)

    def recover(self, known, sealed):
        self.assertEqual(len(known), 64)
        self.assertEqual(len(sealed), 64)
        for offset in range(25):
            window = bytes(a ^ b ^ ord("x") for a, b in zip(known[offset:offset + 40], sealed[offset:offset + 40]))
            match = re.search(rb"\{[0-9a-f]{32}\}", window)
            if match:
                return b"wctf" + match.group()
        return None

    def test_only_stale_owned_slip_reaches_sealed_record(self):
        slip = self.issue()
        self.assertEqual(slip["range"], "bytes=112-175")
        status, raw = self.request("GET", "/api/manifest")
        self.assertEqual(status, 200)
        initial = json.loads(raw)
        self.assertEqual(initial["total_bytes"], 304)
        self.assertEqual([record["bytes"] for record in initial["records"]], [64, 48, 64, 128])
        self.assertEqual(self.request("GET", "/api/note")[0], 404)
        status, before = self.cut(slip)
        self.assertEqual(status, 206)
        self.assertNotIn(app.FLAG, before)
        pristine_cookie = copy.copy(next(iter(self.cookies)))
        status, _ = self.request("POST", "/api/records", {"key": "q-public", "text": "x" * 40})
        self.assertEqual(status, 201)
        self.assertEqual(self.cut(slip)[0], 403)
        self.assertEqual(self.request("POST", "/api/compact", {})[0], 200)
        known_layout = json.loads(self.request("GET", "/api/manifest")[1])
        self.assertEqual([record["key"] for record in known_layout["records"]],
                         ["m-sealed", "p-public", "q-public", "z-owned", "zz-scratch"])
        self.assertEqual(known_layout["total_bytes"], 304)
        status, known = self.cut(slip)
        self.assertEqual(status, 206)

        self.cookies.set_cookie(pristine_cookie)
        status, _ = self.request("POST", "/api/records", {"key": "a-public", "text": "x" * 40})
        self.assertEqual(status, 201)
        self.assertEqual(self.cut(slip)[0], 403)
        status, _ = self.request("POST", "/api/refile", {"from": "p-public", "to": "b-public"})
        self.assertEqual(status, 200)
        self.assertEqual(self.cut(slip)[0], 403)
        status, _ = self.request("POST", "/api/compact", {})
        self.assertEqual(status, 200)
        self.assertEqual(self.request("POST", "/api/compact", {})[0], 409)
        final = json.loads(self.request("GET", "/api/manifest")[1])
        self.assertEqual(final["total_bytes"], 304)
        self.assertEqual([record["bytes"] for record in final["records"]], [64, 48, 64, 64, 64])
        status, after = self.cut(slip)
        self.assertEqual(status, 206)
        self.assertEqual(len(after), 64)
        self.assertNotIn(app.FLAG, after)
        self.assertNotIn(app.FLAG, bytes(a ^ b for a, b in zip(before, after)))
        self.assertEqual(self.recover(known, after), app.FLAG)
        self.assertEqual(self.request("POST", "/api/tickets", {"key": "z-owned"})[0], 409)

    def test_sealed_direct_forgery_and_cross_session_fail(self):
        self.assertEqual(self.request("POST", "/api/tickets", {"key": "m-sealed"})[0], 403)
        self.assertEqual(self.request("GET", "/api/bundle")[0], 403)
        self.assertEqual(self.request("GET", "/api/note")[0], 404)
        slip = self.issue()
        forged = dict(slip, ticket=slip["ticket"][:-1] + ("A" if slip["ticket"][-1] != "A" else "B"))
        self.assertEqual(self.cut(forged)[0], 403)
        other = build_opener(HTTPCookieProcessor(CookieJar()))
        self.assertEqual(self.request("GET", "/api/manifest", client=other)[0], 200)
        self.assertEqual(self.request("GET", "/api/bundle", headers={"Authorization": "Bearer " + slip["ticket"], "Range": slip["range"]}, client=other)[0], 403)
        self.assertEqual(self.cut(slip, Range="bytes=0-63")[0], 416)
        self.request("POST", "/api/reset", {})
        self.assertEqual(self.cut(slip)[0], 403)

    def test_one_public_record_and_input_bounds(self):
        slip = self.issue()
        self.assertEqual(self.request("POST", "/api/records", {"key": "m-sealed", "text": "x"})[0], 400)
        self.assertEqual(self.request("POST", "/api/records", {"key": "p-public", "text": "x"})[0], 400)
        self.assertEqual(self.request("POST", "/api/records", {"key": "a", "text": "x" * 65})[0], 400)
        self.assertEqual(self.request("POST", "/api/refile", {"from": "m-sealed", "to": "b"})[0], 400)
        self.assertEqual(self.request("POST", "/api/refile", {"from": "p-public", "to": "b"})[0], 200)
        self.assertEqual(self.request("POST", "/api/refile", {"from": "p-public", "to": "c"})[0], 409)
        self.assertEqual(self.cut(slip)[0], 206)
        self.assertEqual(self.request("POST", "/api/records", {"key": "a", "text": "x" * 40})[0], 201)
        self.assertEqual(self.request("POST", "/api/records", {"key": "c", "text": "x"})[0], 409)
        self.assertEqual(self.cut(slip)[0], 403)
        self.assertEqual(self.request("POST", "/api/compact", {"unexpected": 1})[0], 400)
        self.assertEqual(self.request("POST", "/api/compact", {})[0], 200)
        self.assertEqual(self.cut(slip)[0], 206)
        self.assertNotIn(app.FLAG, self.cut(slip)[1])

    def test_incomplete_cookie_branch_does_not_reach_sealed(self):
        slip = self.issue()
        original_cookie = f"{app.COOKIE}={next(iter(self.cookies)).value}"
        self.assertEqual(self.request("POST", "/api/refile", {"from": "p-public", "to": "b-public"})[0], 200)
        self.assertEqual(self.request("POST", "/api/tickets", {"key": "z-owned"})[0], 409)
        status, _, headers = self.request(
            "POST", "/api/records", {"key": "a-public", "text": "x" * 40},
            headers={"Cookie": original_cookie}, client=build_opener(), include_headers=True,
        )
        self.assertEqual(status, 201)
        branch_cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, _, headers = self.request(
            "POST", "/api/compact", {}, headers={"Cookie": branch_cookie},
            client=build_opener(), include_headers=True,
        )
        self.assertEqual(status, 200)
        branch_cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, payload = self.request(
            "GET", "/api/bundle",
            headers={"Cookie": branch_cookie, "Authorization": "Bearer " + slip["ticket"], "Range": slip["range"]},
            client=build_opener(),
        )
        self.assertEqual(status, 403)
        self.assertNotIn(app.FLAG, payload)

    def test_oversized_shift_cannot_replace_refile(self):
        slip = self.issue()
        self.assertEqual(self.request("POST", "/api/records", {"key": "a-public", "text": "x" * 64})[0], 201)
        self.assertEqual(self.request("POST", "/api/compact", {})[0], 200)
        self.assertEqual(self.cut(slip)[0], 403)

    def test_mask_is_stable_by_absolute_position(self):
        data = bytes(range(128))
        sid = b"\x12" * 16
        masked = app.mask(data, sid, 17)
        self.assertEqual(app.mask(masked, sid, 17), data)
        self.assertEqual(masked, app.mask(data[:50], sid, 17) + app.mask(data[50:], sid, 67))


if __name__ == "__main__":
    unittest.main()
