#!/usr/bin/env python3
"""Verify the player archive and reject damaged metadata/images."""

import hashlib
import shutil
import subprocess
import sys
import tarfile
import unittest
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parent.parent
SOLVER = ROOT / "Solution" / "solve.py"
NAMES = [f"pictures/{name}.png" for name in ("eight", "five", "four", "nine", "one", "seven", "six", "ten", "three", "two")]


def edit_chunk(path, kind, edit):
    png = bytearray(path.read_bytes())
    marker = png.index(kind)
    size = int.from_bytes(png[marker - 4:marker], "big")
    start, end = marker + 4, marker + 4 + size
    data = bytearray(png[start:end])
    edit(data)
    png[start:end] = data
    png[end:end + 4] = zlib.crc32(kind + data).to_bytes(4, "big")
    path.write_bytes(png)


def replace_chunk(path, kind, payload):
    png = path.read_bytes()
    marker = png.index(kind)
    size = int.from_bytes(png[marker - 4:marker], "big")
    chunk = len(payload).to_bytes(4, "big") + kind + payload
    chunk += zlib.crc32(kind + payload).to_bytes(4, "big")
    path.write_bytes(png[:marker - 4] + chunk + png[marker + size + 8:])


class SolveTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pictures = self.root / "pictures"
        shutil.copytree(ROOT / "pictures", self.pictures)
        (self.root / "flag.txt").write_text("keep this", encoding="ascii")

    def run_solver(self):
        return subprocess.run([sys.executable, str(SOLVER), str(self.pictures)], cwd=self.root,
                              capture_output=True, text=True, check=False)

    def assert_rejected(self, reason):
        result = self.run_solver()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(reason, result.stderr)
        self.assertEqual((self.root / "flag.txt").read_text(encoding="ascii"), "keep this")

    def test_real_player_images_and_sentinel(self):
        result = self.run_solver()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), (ROOT / "Solution" / "flag.txt").read_text().strip())
        self.assertEqual((self.root / "flag.txt").read_text(encoding="ascii"), "keep this")

    def test_missing_extra_and_replaced_filename(self):
        (self.pictures / "two.png").unlink()
        self.assert_rejected("expected the ten named PNGs")
        shutil.copy2(ROOT / "pictures" / "two.png", self.pictures / "two.png")
        shutil.copy2(ROOT / "pictures" / "one.png", self.pictures / "extra.png")
        self.assert_rejected("expected the ten named PNGs")
        (self.pictures / "two.png").unlink()
        self.assert_rejected("expected the ten named PNGs")

    def test_bad_crc_dimensions_and_pixel_length(self):
        path = self.pictures / "one.png"
        png = bytearray(path.read_bytes())
        png[205] ^= 1
        path.write_bytes(png)
        self.assert_rejected("CRC")
        shutil.copy2(ROOT / "pictures" / "one.png", path)
        edit_chunk(path, b"IHDR", lambda data: data.__setitem__(slice(0, 4), (401).to_bytes(4, "big")))
        self.assert_rejected("unsupported PNG dimensions")
        shutil.copy2(ROOT / "pictures" / "one.png", path)
        replace_chunk(path, b"IDAT", zlib.compress(b"\0" * 480401))
        self.assert_rejected("invalid image data")

    def test_malformed_exif_offset_tag_type_prefix_and_hex(self):
        path = self.pictures / "one.png"
        def invalid(mutator, reason):
            shutil.copy2(ROOT / "pictures" / "one.png", path)
            edit_chunk(path, b"eXIf", mutator)
            self.assert_rejected(reason)
        invalid(lambda data: data.__setitem__(slice(4, 8), b"\xff" * 4), "error:")
        invalid(lambda data: data.__setitem__(data.index(b"\x92\x86\x00\x07"), 0x93), "missing EXIF tag")
        invalid(lambda data: data.__setitem__(slice(data.index(b"\x92\x86\x00\x07") + 2,
                                                   data.index(b"\x92\x86\x00\x07") + 4), b"\x00\x02"), "UserComment type")
        invalid(lambda data: data.__setitem__(slice(data.index(b"\xa0\x00\x00\x07"),
                                                   data.index(b"\xa0\x00\x00\x07") + 2), b"\x92\x86"), "duplicate EXIF tag")
        invalid(lambda data: data.__setitem__(data.index(b"ASCII\0\0\0"), ord("X")), "UserComment encoding")
        invalid(lambda data: data.__setitem__(data.index(b"ASCII\0\0\0") + 8, ord("G")), "UserComment hex")
        invalid(lambda data: data.__setitem__(data.index(b"ASCII\0\0\0") + 8, 0xff), "UserComment hex")

    def test_duplicate_exif_and_wrong_flag(self):
        path = self.pictures / "one.png"
        png = path.read_bytes()
        marker = png.index(b"eXIf")
        size = int.from_bytes(png[marker - 4:marker], "big")
        chunk = png[marker - 4:marker + size + 8]
        idat = png.index(b"IDAT") - 4
        path.write_bytes(png[:idat] + chunk + png[idat:])
        self.assert_rejected("duplicate eXIf")
        def wrong_start(data):
            start = data.index(b"ASCII\0\0\0") + 8
            data[start:start + 4] = b"6161"
        edit_chunk(self.pictures / "eight.png", b"eXIf", wrong_start)
        shutil.copy2(ROOT / "pictures" / "one.png", path)
        self.assert_rejected("does not form a flag")


class BuildTests(unittest.TestCase):
    def test_exact_reproducible_archive_and_failed_rebuild(self):
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            shutil.copytree(ROOT / "pictures", project / "pictures")
            for name in ("build.py", "description.md"):
                shutil.copy2(ROOT / name, project / name)
            (project / "main").write_text("organizer binary")
            (project / "Solution").mkdir()
            for name in ("flag.txt", "solve.py"):
                shutil.copy2(ROOT / "Solution" / name, project / "Solution" / name)
            def build():
                return subprocess.run([sys.executable, str(project / "build.py")], capture_output=True, text=True)
            result = build()
            self.assertEqual(result.returncode, 0, result.stderr)
            handout = project / "dist.tar.gz"
            first = hashlib.sha256(handout.read_bytes()).hexdigest()
            with tarfile.open(handout, "r:gz") as archive:
                members = archive.getmembers()
                self.assertEqual([member.name for member in members], ["description.md", *NAMES])
                for member in members:
                    self.assertEqual(archive.extractfile(member).read(), (project / member.name).read_bytes())
                    self.assertEqual((member.uid, member.gid, member.mtime), (0, 0, 0))
            self.assertEqual(build().returncode, 0)
            self.assertEqual(hashlib.sha256(handout.read_bytes()).hexdigest(), first)
            def different_valid_flag(data):
                start = data.index(b"ASCII\0\0\0") + 8
                self.assertEqual(data[start:start + 4], b"6831")
                data[start:start + 4] = b"6832"
            edit_chunk(project / "pictures" / "nine.png", b"eXIf", different_valid_flag)
            self.assertNotEqual(build().returncode, 0)
            self.assertEqual(hashlib.sha256(handout.read_bytes()).hexdigest(), first)
            shutil.copy2(ROOT / "pictures" / "nine.png", project / "pictures" / "nine.png")
            (project / "pictures" / "one.png").unlink()
            self.assertNotEqual(build().returncode, 0)
            self.assertEqual(hashlib.sha256(handout.read_bytes()).hexdigest(), first)


if __name__ == "__main__":
    unittest.main()
