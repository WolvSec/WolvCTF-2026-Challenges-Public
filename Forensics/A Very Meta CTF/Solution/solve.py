#!/usr/bin/env python3
"""Read the flag from the ten PNG UserComment fields, in filename order."""

import re
import struct
import sys
import zlib
from pathlib import Path


EXPECTED = {f"{name}.png" for name in ("eight", "five", "four", "nine", "one", "seven", "six", "ten", "three", "two")}


def user_comment(path):
    png = path.read_bytes()
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"{path.name}: invalid PNG signature")

    exif = None
    image_data = bytearray()
    size = None
    offset = 8
    while offset + 12 <= len(png):
        length = int.from_bytes(png[offset:offset + 4], "big")
        end = offset + length + 12
        if end > len(png):
            raise ValueError(f"{path.name}: truncated PNG chunk")
        kind = png[offset + 4:offset + 8]
        data = png[offset + 8:end - 4]
        crc = int.from_bytes(png[end - 4:end], "big")
        if zlib.crc32(kind + data) != crc:
            raise ValueError(f"{path.name}: invalid {kind.decode('ascii', 'replace')} CRC")
        if kind == b"IHDR":
            if offset != 8 or len(data) != 13 or data[8:] != b"\x08\x02\x00\x00\x00":
                raise ValueError(f"{path.name}: unsupported PNG image")
            size = struct.unpack(">II", data[:8])
            if size != (400, 400):
                raise ValueError(f"{path.name}: unsupported PNG dimensions")
        elif kind == b"eXIf":
            if exif is not None:
                raise ValueError(f"{path.name}: duplicate eXIf chunk")
            exif = data
        elif kind == b"IDAT":
            image_data.extend(data)
        elif kind == b"IEND":
            if length or end != len(png):
                raise ValueError(f"{path.name}: invalid PNG end")
            break
        offset = end
    else:
        raise ValueError(f"{path.name}: missing PNG end")
    if size is None or exif is None or not image_data:
        raise ValueError(f"{path.name}: missing image header, EXIF, or image data")
    row_size = 1 + size[0] * 3
    expected_bytes = size[1] * row_size
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(image_data, expected_bytes + 1)
    if (len(pixels) != expected_bytes or not decoder.eof or decoder.unused_data
            or any(pixels[row * row_size] > 4 for row in range(size[1]))):
        raise ValueError(f"{path.name}: invalid image data")

    byte_order = {b"II": "<", b"MM": ">"}.get(exif[:2])
    if byte_order is None:
        raise ValueError(f"{path.name}: invalid TIFF byte order")

    def read(fmt, offset):
        return struct.unpack_from(byte_order + fmt, exif, offset)[0]

    if read("H", 2) != 42:
        raise ValueError(f"{path.name}: invalid TIFF header")

    def entry(ifd_offset, tag):
        count = read("H", ifd_offset)
        if ifd_offset + 2 + 12 * count + 4 > len(exif):
            raise ValueError(f"{path.name}: truncated EXIF directory")
        found = None
        for index in range(count):
            at = ifd_offset + 2 + 12 * index
            if read("H", at) == tag:
                if found is not None:
                    raise ValueError(f"{path.name}: duplicate EXIF tag {tag:#x}")
                found = read("H", at + 2), read("I", at + 4), read("I", at + 8)
        if found is None:
            raise ValueError(f"{path.name}: missing EXIF tag {tag:#x}")
        return found

    pointer_type, pointer_count, exif_ifd = entry(read("I", 4), 0x8769)
    if (pointer_type, pointer_count) != (4, 1):
        raise ValueError(f"{path.name}: invalid EXIF pointer")
    comment_type, comment_count, comment_offset = entry(exif_ifd, 0x9286)
    if comment_type != 7 or comment_count < 10:
        raise ValueError(f"{path.name}: invalid UserComment type")
    comment = exif[comment_offset:comment_offset + comment_count]
    if len(comment) != comment_count or not comment.startswith(b"ASCII\0\0\0"):
        raise ValueError(f"{path.name}: invalid UserComment encoding")
    hex_part = comment[8:]
    if not re.fullmatch(rb"[0-9a-fA-F]+", hex_part) or len(hex_part) % 2:
        raise ValueError(f"{path.name}: invalid UserComment hex")
    return hex_part.decode("ascii")


def solve(pictures):
    files = sorted(pictures.glob("*.png"))
    if {path.name for path in files} != EXPECTED:
        raise ValueError("expected the ten named PNGs")
    parts = [user_comment(path) for path in files]
    flag = bytes.fromhex("".join(parts)).decode("ascii")
    if not re.fullmatch(r"wctf\{[A-Za-z0-9_@]+\}", flag):
        raise ValueError("metadata does not form a flag")
    return flag


if __name__ == "__main__":
    try:
        if len(sys.argv) > 2:
            raise ValueError("usage: solve.py [pictures-directory]")
        directory = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).resolve().parent.parent / "pictures"
        print(solve(directory))
    except (OSError, ValueError, UnicodeError, struct.error, zlib.error) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
