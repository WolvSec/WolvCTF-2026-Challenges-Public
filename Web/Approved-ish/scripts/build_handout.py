#!/usr/bin/env python3
"""Build a black-box player handout without server source or the real flag."""

import io
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ROOT / "challenge"
FILES = ("static/app.js", "static/style.css", "templates/index.html")
PLAYER_README = """Approved-ish — player handout

The live service is the target. Use its browser UI and network requests to
explore the data catalog, aliases, backup/restore, manifests, approvals, and
snapshots. Legacy alias backups may use different ID casing.
Workspaces last up to six hours and may reset during maintenance. New
workspaces may be unavailable at capacity.

This attachment contains the client interface only. The server source and
real flag are not distributed.

Challenge-specific rule: solve Approved-ish without AI assistance. Do not use
chatbots, coding assistants, autonomous agents, or model APIs to analyze the
service, screenshots, or attachment, generate requests, or derive the solution.
Do not ask someone else to relay prompts to an AI for you.
"""


def build(output):
    real_flag = (ROOT / "flag.txt").read_text().strip().encode()
    entries = {f"approved-ish/{name}": (CHALLENGE / name).read_bytes() for name in FILES}
    entries["approved-ish/README.txt"] = PLAYER_README.encode()
    for name, content in entries.items():
        if real_flag in content:
            raise SystemExit(f"Refusing to build: real flag found in {name}")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        for name, content in sorted(entries.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
    return output


if __name__ == "__main__":
    path = build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dis.tar.gz")
    print(f"Wrote {path}")
