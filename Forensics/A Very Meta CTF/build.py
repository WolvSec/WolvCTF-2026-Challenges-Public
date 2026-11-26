#!/usr/bin/env python3
"""Build a byte-reproducible player archive without organizer materials."""

import gzip
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from Solution.solve import solve


root = Path(__file__).resolve().parent
names = ("eight", "five", "four", "nine", "one", "seven", "six", "ten", "three", "two")
expected = {f"{name}.png" for name in names}
pictures = root / "pictures"
if {path.name for path in pictures.glob("*.png")} != expected:
    raise SystemExit("expected exactly the ten challenge PNGs")
if solve(pictures) != (root / "Solution" / "flag.txt").read_text(encoding="ascii").strip():
    raise SystemExit("player images do not decode to the organizer flag")
files = [root / "description.md", *(pictures / name for name in sorted(expected))]

with TemporaryDirectory(dir=root) as temporary:
    candidate = Path(temporary) / "dist.tar.gz"
    with candidate.open("wb") as output, gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for path in files:
                info = archive.gettarinfo(path, arcname=path.relative_to(root).as_posix())
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                with path.open("rb") as source:
                    archive.addfile(info, source)
    candidate.replace(root / "dist.tar.gz")
