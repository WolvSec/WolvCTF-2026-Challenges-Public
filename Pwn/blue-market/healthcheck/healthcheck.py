#!/usr/bin/env python3
from pathlib import Path
from subprocess import check_output

expected = Path("/home/user/flag.txt").read_bytes()
output = check_output(
    ["python3", "/home/user/solve.py", "127.0.0.1", "1337"],
    cwd="/home/user",
    timeout=15,
)
if output != expected:
    raise SystemExit("wrong flag")
