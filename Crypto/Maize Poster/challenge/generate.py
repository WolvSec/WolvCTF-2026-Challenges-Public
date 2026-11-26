"""Build the Maize handout.

The flag from ../flag.txt is ROT13'd, then written MSB-first into
the blue LSB of every pixel, row-major.
"""

from __future__ import annotations

import codecs
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLAG_PATH = ROOT / "flag.txt"
OUT_PATH = ROOT / "challenge" / "poster.png"

W, H = 960, 740
MAIZE = (255, 203, 5)
BLUE = (0, 39, 76)

# 5x7 glyphs, row strings of "0" and "1".
FONT = {
    "M": ("10001", "11011", "10101", "10001", "10001", "10001", "10001"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
}


def fill_rect(buf: bytearray, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(color) * (x1 - x0)
    for y in range(y0, y1):
        i = (y * W + x0) * 3
        buf[i : i + len(row)] = row


def stroke_rect(buf: bytearray, x0: int, y0: int, x1: int, y1: int, thickness: int, color: tuple[int, int, int]) -> None:
    fill_rect(buf, x0, y0, x1, y0 + thickness, color)
    fill_rect(buf, x0, y1 - thickness, x1, y1, color)
    fill_rect(buf, x0, y0, x0 + thickness, y1, color)
    fill_rect(buf, x1 - thickness, y0, x1, y1, color)


def text_width(text: str, scale: int, gap: int) -> int:
    return len(text) * (5 * scale + gap) - gap


def draw_text(buf: bytearray, text: str, x: int, y: int, scale: int, gap: int, color: tuple[int, int, int]) -> None:
    cursor = x
    for ch in text:
        glyph = FONT[ch]
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    fill_rect(
                        buf,
                        cursor + col * scale,
                        y + row * scale,
                        cursor + (col + 1) * scale,
                        y + (row + 1) * scale,
                        color,
                    )
        cursor += 5 * scale + gap


def segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy
    return ((px - nearest_x) ** 2 + (py - nearest_y) ** 2) ** 0.5


def draw_block_m(buf: bytearray, x0: int, y0: int, mw: int, mh: int) -> None:
    """A heavy block M: two legs plus a V cut down from the top."""
    leg = int(mw * 0.20)
    radius = mw * 0.115
    apex_x = x0 + mw / 2
    apex_y = y0 + mh * 0.62
    left = (x0 + leg * 0.85, float(y0))
    right = (x0 + mw - leg * 0.85, float(y0))
    for y in range(y0, y0 + mh):
        for x in range(x0, x0 + mw):
            local_x = x - x0
            if local_x < leg or local_x >= mw - leg:
                i = (y * W + x) * 3
                buf[i : i + 3] = bytes(BLUE)
                continue
            cx, cy = x + 0.5, y + 0.5
            on_left = segment_distance(cx, cy, left[0], left[1], apex_x, apex_y) <= radius
            on_right = segment_distance(cx, cy, right[0], right[1], apex_x, apex_y) <= radius
            if on_left or on_right:
                i = (y * W + x) * 3
                buf[i : i + 3] = bytes(BLUE)


def paint() -> bytearray:
    buf = bytearray(bytes(MAIZE) * (W * H))
    stroke_rect(buf, 0, 0, W, H, 32, BLUE)
    stroke_rect(buf, 50, 50, W - 50, H - 50, 8, BLUE)

    title = "MAIZE"
    scale, gap = 8, 6
    title_w = text_width(title, scale, gap)
    title_x = (W - title_w) // 2
    title_y = 78
    draw_text(buf, title, title_x, title_y, scale, gap, BLUE)
    fill_rect(buf, title_x, title_y + 7 * scale + 8, title_x + title_w, title_y + 7 * scale + 12, BLUE)

    draw_block_m(buf, (W - 420) // 2, 176, 420, 360)

    year = "2026"
    year_scale, year_gap = 6, 4
    year_w = text_width(year, year_scale, year_gap)
    draw_text(buf, year, (W - year_w) // 2, 568, year_scale, year_gap, BLUE)
    return buf


def payload_bits(flag: str) -> list[int]:
    cipher = codecs.encode(flag, "rot_13").encode("ascii")
    bits: list[int] = []
    for byte in cipher:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def embed(buf: bytearray, bits: list[int]) -> None:
    if len(bits) > (len(buf) // 3):
        raise SystemExit("ciphertext does not fit in the blue channel")
    for index, bit in enumerate(bits):
        channel = index * 3 + 2
        buf[channel] = (buf[channel] & 0xFE) | bit


def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for start in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[start : start + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


def assert_not_trivial(buf: bytearray, flag: str) -> None:
    """A linear LSB dump, including bit shifts, must not already be the flag."""
    target = flag.encode("ascii")
    streams = [
        [buf[i] & 1 for i in range(0, len(buf), 3)],
        [buf[i + 1] & 1 for i in range(0, len(buf), 3)],
        [buf[i + 2] & 1 for i in range(0, len(buf), 3)],
    ]
    interleaved: list[int] = []
    gold: list[int] = []
    for i in range(0, len(buf), 3):
        interleaved.append(buf[i] & 1)
        interleaved.append(buf[i + 1] & 1)
        interleaved.append(buf[i + 2] & 1)
        if buf[i] == 255 and buf[i + 1] == 203 and buf[i + 2] in (4, 5):
            gold.append(buf[i + 2] & 1)
    streams.extend((interleaved, gold))
    for bits in streams:
        for offset in range(8):
            if target in bits_to_bytes(bits[offset:]):
                raise SystemExit("flag is visible in a linear LSB dump; stride did not stick")


def assert_palette(buf: bytearray) -> None:
    allowed = {MAIZE, (255, 203, 4), BLUE, (BLUE[0], BLUE[1], BLUE[2] | 1)}
    for i in range(0, len(buf), 3):
        pixel = (buf[i], buf[i + 1], buf[i + 2])
        if pixel not in allowed:
            raise SystemExit(f"unexpected color {pixel} at pixel {i // 3}")


def write_png(path: Path, buf: bytearray) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter None
        start = y * stride
        raw += buf[start : start + stride]

    comment = b"Comment\x00Maize poster, 2026."
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"tEXt", comment)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def main() -> None:
    flag = FLAG_PATH.read_text(encoding="utf-8").strip()
    if not flag.startswith("wctf{") or not flag.endswith("}"):
        raise SystemExit(f"flag.txt does not look like a wctf flag: {flag!r}")

    buf = paint()
    embed(buf, payload_bits(flag))
    assert_palette(buf)
    assert_not_trivial(buf, flag)
    write_png(OUT_PATH, buf)
    print(f"wrote {OUT_PATH}", flush=True)

    check = subprocess.run([sys.executable, str(ROOT / "solution" / "solve.py")], check=False)
    if check.returncode != 0:
        raise SystemExit("solver could not recover the flag from the poster")


if __name__ == "__main__":
    main()
