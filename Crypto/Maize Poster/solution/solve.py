"""Recover the flag from challenge/poster.png.

Blue LSBs, row-major and MSB first, are ROT13 text. Rotate letters
back by 13 to recover the flag.
"""

from __future__ import annotations

import codecs
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTER = ROOT / "challenge" / "poster.png"
FLAG_PATH = ROOT / "flag.txt"


def paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    dist_left = abs(estimate - left)
    dist_up = abs(estimate - up)
    dist_up_left = abs(estimate - up_left)
    if dist_left <= dist_up and dist_left <= dist_up_left:
        return left
    if dist_up <= dist_up_left:
        return up
    return up_left


def unfilter(raw: bytes, width: int, height: int) -> bytes:
    stride = width * 3
    rows = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset : offset + stride])
        offset += stride
        if filter_type == 1:
            for x in range(stride):
                left = row[x - 3] if x >= 3 else 0
                row[x] = (row[x] + left) & 255
        elif filter_type == 2:
            for x in range(stride):
                row[x] = (row[x] + previous[x]) & 255
        elif filter_type == 3:
            for x in range(stride):
                left = row[x - 3] if x >= 3 else 0
                row[x] = (row[x] + ((left + previous[x]) // 2)) & 255
        elif filter_type == 4:
            for x in range(stride):
                left = row[x - 3] if x >= 3 else 0
                up_left = previous[x - 3] if x >= 3 else 0
                row[x] = (row[x] + paeth(left, previous[x], up_left)) & 255
        elif filter_type != 0:
            raise SystemExit(f"unsupported PNG filter {filter_type}")
        previous = row
        rows.append(row)
    if offset != len(raw):
        raise SystemExit("PNG decompressed data has trailing bytes")
    return b"".join(rows)


def read_rgb(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit(f"{path} is not a PNG")
    pos = 8
    width = height = None
    idat = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", chunk)
            if (depth, color, comp, filt, interlace) != (8, 2, 0, 0, 0):
                raise SystemExit("poster is not an 8-bit RGB PNG")
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break
    if width is None or height is None:
        raise SystemExit("PNG is missing IHDR")
    pixels = unfilter(zlib.decompress(bytes(idat)), width, height)
    if len(pixels) != width * height * 3:
        raise SystemExit("decoded PNG has the wrong size")
    return pixels


def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for start in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[start : start + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


def extract(pixels: bytes) -> str:
    bits = [pixels[i] & 1 for i in range(2, len(pixels), 3)]
    rotated = bits_to_bytes(bits).decode("ascii", errors="ignore")
    plain = codecs.encode(rotated, "rot_13")
    start = plain.find("wctf{")
    end = plain.find("}", start)
    if start < 0 or end < 0:
        raise SystemExit("rotated text did not contain a flag")
    return plain[start : end + 1]


def main() -> None:
    flag = extract(read_rgb(POSTER))
    if FLAG_PATH.exists():
        expected = FLAG_PATH.read_text(encoding="utf-8").strip()
        if flag != expected:
            raise SystemExit(f"extracted {flag!r}, expected {expected!r}")
    print(flag)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
