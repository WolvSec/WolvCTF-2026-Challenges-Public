import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from scipy.io import wavfile

from solve import load_wav


class SolveTests(unittest.TestCase):
    def test_load_wav_normalizes_supported_dtypes(self):
        cases = (
            (np.int16, [-32768, 0, 32767], [-1, 0, 32767 / 32768]),
            (np.int32, [-2147483648, 0, 2147483647], [-1, 0, 1]),
            (np.uint8, [0, 128, 255], [-1, 0, 127 / 128]),
            (np.float32, [-1, 0, 1], [-1, 0, 1]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.wav"
            for dtype, samples, expected in cases:
                with self.subTest(dtype=dtype):
                    wavfile.write(path, 44100, np.array(samples, dtype=dtype))
                    rate, data = load_wav(path)
                    self.assertEqual(rate, 44100)
                    self.assertEqual(data.dtype, np.float32)
                    np.testing.assert_allclose(data, expected, atol=1e-7)

    def test_zero_signal_does_not_claim_a_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            challenge = Path(tmp)
            solution = challenge / "Solution"
            solution.mkdir()
            shutil.copyfile(Path(__file__).with_name("solve.py"), solution / "solve.py")
            for name in ("wav1.wav", "wav2.wav"):
                wavfile.write(challenge / name, 100, np.zeros(256, dtype=np.int16))
            result = subprocess.run(
                [sys.executable, "-B", str(solution / "solve.py"), "--window-size", "32"],
                capture_output=True, text=True, check=True,
                env={**os.environ, "MPLBACKEND": "Agg"},
            )
            self.assertNotIn("Flag:", result.stdout)
            self.assertNotIn("wctf{", result.stdout)
            self.assertNotIn("SOLVE COMPLETE", result.stdout)
            self.assertTrue((solution / "spectrogram.png").is_file())

    def test_missing_wav_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            challenge = Path(tmp)
            solution = challenge / "Solution"
            solution.mkdir()
            shutil.copyfile(Path(__file__).with_name("solve.py"), solution / "solve.py")
            wavfile.write(challenge / "wav1.wav", 100, np.zeros(256, dtype=np.int16))
            result = subprocess.run(
                [sys.executable, "-B", str(solution / "solve.py")],
                capture_output=True, text=True,
                env={**os.environ, "MPLBACKEND": "Agg"},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Could not find 2 WAV files", result.stderr)
            self.assertFalse((solution / "spectrogram.png").exists())


if __name__ == "__main__":
    unittest.main()
