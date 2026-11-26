import os
import struct
import subprocess
import tarfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from validate import reassemble, validate


ROOT = Path(__file__).parent
IMAGES = ROOT / "challenge/website/static/images"


class CaptureValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tarfile.open(ROOT / "dist.tar.gz", "r:gz") as archive:
            cls.pcap = archive.extractfile("jurassic.pcap").read()

    def check_pcap(self, data):
        with TemporaryDirectory() as temporary:
            pcap = Path(temporary, "jurassic.pcap")
            pcap.write_bytes(data)
            validate(pcap, IMAGES, Path(temporary, "extracted"))
            self.assertTrue(Path(temporary, "extracted/stegosaurus.jpg").is_file())
            self.assertTrue(Path(temporary, "extracted/archaeopteryx.jpg").is_file())

    def test_complete_capture(self):
        self.check_pcap(self.pcap)

    def test_wrong_content_length(self):
        bad = self.pcap.replace(b"Content-Length: 335711", b"Content-Length: 335712", 1)
        self.assertNotEqual(bad, self.pcap)
        with self.assertRaisesRegex(ValueError, "HTTP body bytes"):
            self.check_pcap(bad)

    def test_missing_tcp_packet(self):
        offset = 24
        while offset < len(self.pcap):
            included = struct.unpack_from("<I", self.pcap, offset + 8)[0]
            end = offset + 16 + included
            if b"Content-Length: 335711" in self.pcap[offset:end]:
                break
            offset = end
        else:
            self.fail("stegosaurus response header not found")
        with self.assertRaisesRegex(ValueError, "missing TCP bytes"):
            self.check_pcap(self.pcap[:offset] + self.pcap[end:])

    def test_untrusted_ack_cannot_allocate_unbounded_stream(self):
        with self.assertRaisesRegex(ValueError, "invalid sequence range"):
            reassemble([], {1}, set(), {2**32 - 1}, "malformed", len(self.pcap))

    def test_failed_build_preserves_preexisting_files(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("jurassic.pcap", "dist.tar.gz.new", "dist.tar.gz"):
                (root / name).write_bytes(name.encode())
            fake_bin = root / "bin"
            fake_bin.mkdir()
            docker = fake_bin / "docker"
            docker.write_text("#!/bin/sh\nexit 42\n")
            docker.chmod(0o755)
            result = subprocess.run(["bash", str(ROOT / "build.sh")], cwd=root, env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            for name in ("jurassic.pcap", "dist.tar.gz.new", "dist.tar.gz"):
                self.assertEqual((root / name).read_bytes(), name.encode())
            self.assertEqual(list(root.glob(".jurassic-build.*")), [])


if __name__ == "__main__":
    unittest.main()
