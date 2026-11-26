#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

os.chdir("/home/user")
result = subprocess.run(
    ["python3", "/home/user/solve.py", "127.0.0.1", "1337"],
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
)
expected = Path("flag.txt").read_bytes().strip()
flags = [line for line in result.stdout.splitlines() if b"wctf{" in line]
raise SystemExit(result.returncode or flags != [expected])
