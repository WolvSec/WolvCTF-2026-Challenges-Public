#!/usr/bin/env python3
import subprocess
from pathlib import Path


def flag_matches(stdout: bytes, expected: bytes) -> bool:
    lines = stdout.splitlines()
    return lines[-1:] == [expected] and sum(b"wctf{" in line for line in lines) == 1


if __name__ == "__main__":
    expected = Path("/home/user/flag.txt").read_bytes().strip()
    result = subprocess.run(
        ["python3", "/home/user/solve.py"],
        cwd="/home/user",
        capture_output=True,
        timeout=15,
    )
    if result.returncode or not flag_matches(result.stdout, expected):
        raise SystemExit(1)
