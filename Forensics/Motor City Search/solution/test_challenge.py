#!/usr/bin/env python3
"""Regression checks for the generator, handout, and reference reconstruction."""

import sys
import unittest
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_forensics as generator
import solve


class MotorCitySearchTests(unittest.TestCase):
    def test_committed_capture_matches_generator_and_solves(self):
        capture, built = generator.build_instance()
        self.assertEqual(capture, (generator.ROOT / "challenge" / "capture.log").read_bytes())
        generator.verify(capture, built)
        self.assertEqual(solve.recover(capture)[0], generator.FLAG.encode())

    def test_seed_and_flag_override_are_deterministic(self):
        first = generator.build_instance(47, "wctf{alternate_0123}")
        second = generator.build_instance(47, "wctf{alternate_0123}")
        self.assertEqual(first, second)
        generator.verify(*first)
        for seed in range(20):
            with self.subTest(seed=seed):
                generator.verify(*generator.build_instance(seed, "wctf{alternate_0123}"))
        generator.verify(*generator.build_instance(2026, "wctf{Y0U_C4N_D0_1T_9d4427e73ff8}"))
        with self.assertRaises(ValueError):
            generator.build_instance(47, "wrong-format")

    def test_dropped_or_corrupted_transfer_frame_fails(self):
        capture, _ = generator.build_instance()
        events = solve.messages(capture)
        downloads = [time for time, arb, msg in events if arb == 0x7E0 and msg[:1] == b"\x34"]
        target = next(time for time, arb, msg in events
                      if arb == 0x7E0 and msg[:1] == b"\x36" and time > downloads[1])
        timestamp = f"({target // 1_000_000}.{target % 1_000_000:06d})".encode()
        lines = capture.splitlines()
        index = next(index for index, line in enumerate(lines) if line.startswith(timestamp + b" can0 7E0#"))

        dropped = b"\n".join(lines[:index] + lines[index + 1:]) + b"\n"
        with self.assertRaises(ValueError):
            solve.recover(dropped)

        changed = lines.copy()
        header, payload = changed[index].split(b"#", 1)
        data = bytearray.fromhex(payload.decode())
        data[4] ^= 1  # change firmware data, not the UDS service byte
        changed[index] = header + b"#" + data.hex().upper().encode()
        corrupted = b"\n".join(changed) + b"\n"
        with self.assertRaises((ValueError, zlib.error, zipfile.BadZipFile)):
            solve.recover(corrupted)


if __name__ == "__main__":
    unittest.main()
