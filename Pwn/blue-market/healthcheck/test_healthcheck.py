import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("healthcheck.py")
EXPECTED = b"wctf{test_flag}\n"


class HealthcheckTest(unittest.TestCase):
    def run_check(self, output):
        with patch.object(Path, "read_bytes", return_value=EXPECTED), patch(
            "subprocess.check_output", return_value=output
        ):
            runpy.run_path(str(SCRIPT))

    def test_exact_flag(self):
        self.run_check(EXPECTED)

    def test_wrong_flag(self):
        with self.assertRaises(SystemExit):
            self.run_check(b"wctf{wrong}\n")

    def test_expected_prefix_with_suffix(self):
        with self.assertRaises(SystemExit):
            self.run_check(EXPECTED[:-1] + b"suffix\n")


if __name__ == "__main__":
    unittest.main()
