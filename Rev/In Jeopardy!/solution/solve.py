#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path

binary = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "in-jeopardy"
try:
    output = subprocess.check_output([str(binary.resolve())], input=b"What is the flag?!\n", timeout=5)
except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
    raise SystemExit(f"solve failed: {exc}") from exc

flag = re.search(rb"wctf\{[^}\r\n]+\}", output)
if flag is None:
    raise SystemExit("binary did not print a flag")
print(flag.group().decode())
