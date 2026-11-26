#!/usr/bin/env python3
from pathlib import Path
from runpy import run_path
from subprocess import CompletedProcess
from unittest.mock import patch


def check(output, returncode=0):
    with patch("os.chdir"), patch.object(Path, "read_bytes", return_value=b"wctf{expected}\n"), patch(
        "subprocess.run", return_value=CompletedProcess([], returncode, output)
    ):
        try:
            run_path(str(Path(__file__).with_name("healthcheck.py")))
        except SystemExit as result:
            return result.code
    raise AssertionError("healthcheck did not exit")


assert check(b"\nwctf{expected}\n") == 0
assert check(b"\nwctf{wrong}\n") != 0
assert check(b"\nwctf{expected}suffix\n") != 0
assert check(b"\nwctf{expected}\nwctf{wrong}\n") != 0
assert check(b"\nwctf{expected}\n", returncode=1) != 0
