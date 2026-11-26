#!/usr/bin/env python3
import os
import subprocess

os.chdir("/home/user")
result = subprocess.run(
    ["python3", "/home/user/solve.py", "127.0.0.1", "1337"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    timeout=20,
)
raise SystemExit(result.returncode)
