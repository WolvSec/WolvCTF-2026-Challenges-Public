#!/usr/bin/env python3
"""Extract the two stego JPEGs from the player PCAP."""

import sys
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from validate import extract_http, require


def extract(archive, output_dir):
    with TemporaryDirectory() as temporary:
        with tarfile.open(archive, "r:gz") as handout:
            require(handout.getnames() == ["jurassic.pcap"], "unexpected handout contents")
            member = handout.getmember("jurassic.pcap")
            require(member.isfile() and member.size <= 10_000_000, "invalid PCAP member")
            Path(temporary, "jurassic.pcap").write_bytes(handout.extractfile(member).read())
        objects, _ = extract_http(Path(temporary, "jurassic.pcap"))
    output_dir = Path(output_dir)
    extracted = {}
    for name in ("stegosaurus.jpg", "archaeopteryx.jpg"):
        status, body = objects[f"/static/images/{name}"]
        require(status == b"HTTP/1.1 200 OK" and body.startswith(b"\xff\xd8") and body.endswith(b"\xff\xd9"), f"incomplete {name}")
        require(not (output_dir / name).exists(), f"output already exists: {name}")
        extracted[name] = body
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, body in extracted.items():
        (output_dir / name).write_bytes(body)
    print(f"extracted stegosaurus.jpg and archaeopteryx.jpg to {output_dir}")


if __name__ == "__main__":
    try:
        require(len(sys.argv) == 3, "usage: python3 extract.py dist.tar.gz output_dir")
        extract(sys.argv[1], sys.argv[2])
    except (KeyError, OSError, ValueError, tarfile.TarError) as error:
        sys.exit(str(error))
