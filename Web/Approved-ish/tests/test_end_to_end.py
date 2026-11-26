"""Run the solver, healthcheck and handout builder against real HTTP servers."""

import io
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from werkzeug.serving import WSGIRequestHandler, make_server

from support import ROOT, TEST_FLAG, AppCase

import build_handout
from solve import solve


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


class LiveServer(AppCase):
    def setUp(self):
        super().setUp()
        self.server = make_server("127.0.0.1", 0, self.app, threaded=True, request_handler=QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def test_reference_solver_returns_flag(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(solve(self.base), TEST_FLAG)

    def test_healthcheck_script(self):
        self.app.config["COOKIE_SECURE"] = True  # KCTF terminates HTTPS before the local healthcheck.
        script = ROOT / "healthcheck" / "healthcheck.py"
        ok = subprocess.run([sys.executable, str(script), self.base, TEST_FLAG], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        bad = subprocess.run([sys.executable, str(script), self.base, "wctf{wrong}"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)

    def test_concurrent_solvers_stay_isolated(self):
        results, errors = [], []

        def run():
            try:
                results.append(solve(self.base, verbose=False))
            except Exception as error:  # surfaced in the assertion below
                errors.append(error)

        threads = [threading.Thread(target=run) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(results, [TEST_FLAG] * 8)
        self.assertEqual(self.sql("SELECT count(*) FROM aliases")[0][0], 0)

    def test_full_active_capacity_fails_healthcheck_without_eviction(self):
        alias_id = self.alias()
        self.app.config["MAX_WORKSPACES"] = 2
        other = self.app.test_client()
        self.assertEqual(other.post("/api/session").status_code, 201)
        other_alias = self.alias(client=other)
        script = ROOT / "healthcheck" / "healthcheck.py"
        result = subprocess.run([sys.executable, str(script), self.base, TEST_FLAG],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("429", result.stdout)
        self.assertEqual(self.client.get(f"/api/aliases/{alias_id}").status_code, 200)
        self.assertEqual(other.get(f"/api/aliases/{other_alias}").status_code, 200)

    def test_failed_healthchecks_clean_up_workspace_after_alias_creation(self):
        self.app.config["MAX_WORKSPACES_PER_PEER"] = 2
        original = self.app.view_functions["workflow.create_manifest"]
        self.app.view_functions["workflow.create_manifest"] = lambda: ({"error": "injected"}, 503)
        self.addCleanup(self.app.view_functions.__setitem__, "workflow.create_manifest", original)
        script = ROOT / "healthcheck" / "healthcheck.py"
        for _ in range(3):
            result = subprocess.run([sys.executable, str(script), self.base, TEST_FLAG],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("POST /api/manifests: expected 201, got 503", result.stdout)
            self.assertEqual(self.sql("SELECT count(*) FROM workspaces")[0][0], 1)
            self.assertEqual(self.sql("SELECT count(*) FROM aliases")[0][0], 0)

    def test_cleanup_failure_preserves_original_solve_error(self):
        self.app.view_functions["workflow.create_manifest"] = lambda: ({"error": "injected"}, 503)
        self.app.view_functions["delete_session"] = lambda: ({"error": "cleanup injected"}, 503)
        script = ROOT / "healthcheck" / "healthcheck.py"
        result = subprocess.run([sys.executable, str(script), self.base, TEST_FLAG],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("POST /api/manifests: expected 201, got 503", result.stdout)
        self.assertNotIn("DELETE /api/session", result.stdout)

    def test_successful_solve_reports_cleanup_failure(self):
        self.app.view_functions["delete_session"] = lambda: ({"error": "cleanup injected"}, 503)
        script = ROOT / "healthcheck" / "healthcheck.py"
        result = subprocess.run([sys.executable, str(script), self.base, TEST_FLAG],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("DELETE /api/session: expected 200, got 503", result.stdout)


class HandoutTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)
        with redirect_stdout(io.StringIO()):
            self.tar_path = build_handout.build(self.tmp / "handout.tar.gz")

    def test_contents_and_no_real_flag(self):
        real_flag = (ROOT / "flag.txt").read_text().strip()
        with tarfile.open(self.tar_path) as archive:
            names = set(archive.getnames())
            for name in names:
                self.assertNotIn(real_flag.encode(), archive.extractfile(name).read(), name)
        for required in ["static/app.js", "static/style.css", "templates/index.html", "README.txt"]:
            self.assertIn("approved-ish/" + required, names)
        self.assertFalse(any(name.endswith(".py") or "flag.txt" in name for name in names))

    def test_production_mode_requires_flag_file(self):
        code = "import sys; sys.path.insert(0, '.'); from app import create_app; create_app()"
        env = {"REQUIRE_FLAG_FILE": "1", "DATABASE": str(self.tmp / "p.db"), "PATH": "/usr/bin:/bin"}
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "challenge", env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FLAG_FILE must be configured", result.stderr)


if __name__ == "__main__":
    unittest.main()
