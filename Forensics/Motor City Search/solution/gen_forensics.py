#!/usr/bin/env python3
"""Generate the deterministic Motor City Search reflash capture."""

import io
import os
import random
import re
import struct
from dataclasses import dataclass
from pathlib import Path
import zipfile
import zlib

from solve import recover

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FLAG = "wctf{Y0U_C4N_D0_1T_9d4427e73ff7}"
SEED = int(os.environ.get("SEED", "2026"), 0)
FLAG = os.environ.get("FLAG", DEFAULT_FLAG)
BLOCK_DATA_LEN = 16
BASE_US = 1_730_000_000_000_000
BANNER = b"WOLVSEC IMMO BOOTLOADER v3 :: image continues past this header; keep reconstructing ::\n"


@dataclass(frozen=True)
class Frame:
    timestamp: int
    arb_id: int
    data: bytes


def random_bytes(rng, count):
    return bytes(rng.getrandbits(8) for _ in range(count))


def firmware(flag, rng):
    resource = io.BytesIO()
    entry = zipfile.ZipInfo("immo_key.bin", (2026, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(resource, "w") as archive:
        archive.writestr(entry, flag.encode(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    embedded_zip = resource.getvalue()

    header = bytearray(BANNER.ljust(128, b"\x00"))
    header += struct.pack("<IIII", 0x20004000, 0x08000101, 0x08000201, 0x08000301)
    header += b"CAL_TABLE=04.11.07;PLATFORM=MC-ECU;IMAGE=IMMO;CHK=CRC32\n"
    header = header.ljust(256, b"\x00")
    prefix = bytes(header) + random_bytes(rng, 4600)
    image = prefix + embedded_zip + random_bytes(rng, 3000)
    return image, len(prefix), embedded_zip


def pad8(data):
    if len(data) > 8:
        raise ValueError("CAN frame exceeds eight bytes")
    return data.ljust(8, b"\xaa")


def emit_isotp(frames, timestamp, arb_id, flow_id, payload):
    if len(payload) <= 7:
        frames.append(Frame(timestamp, arb_id, pad8(bytes([len(payload)]) + payload)))
        return timestamp + 1000
    if len(payload) > 4095:
        raise ValueError("ISO-TP message exceeds 12-bit length")
    first = bytes([0x10 | (len(payload) >> 8), len(payload) & 255]) + payload[:6]
    frames.append(Frame(timestamp, arb_id, pad8(first)))
    timestamp += 1000
    frames.append(Frame(timestamp, flow_id, pad8(b"\x30\x00\x00")))
    timestamp += 1000
    for offset in range(6, len(payload), 7):
        sequence = 1 + (offset - 6) // 7
        frames.append(Frame(timestamp, arb_id, pad8(bytes([0x20 | (sequence & 15)]) + payload[offset:offset + 7])))
        timestamp += 1000
    return timestamp


def exchange(frames, timestamp, request, response):
    timestamp = emit_isotp(frames, timestamp, 0x7E0, 0x7E8, request)
    return emit_isotp(frames, timestamp, 0x7E8, 0x7E0, response)


def download(frames, timestamp, image_length):
    request = b"\x34\x10\x44" + (0x00400000).to_bytes(4, "big") + image_length.to_bytes(4, "big")
    return exchange(frames, timestamp, request, b"\x74\x20\x00\x12")


def block(frames, timestamp, counter, data, acknowledge=True):
    request = b"\x36" + bytes([counter]) + data
    timestamp = emit_isotp(frames, timestamp, 0x7E0, 0x7E8, request)
    if acknowledge:
        timestamp = emit_isotp(frames, timestamp, 0x7E8, 0x7E0, b"\x76" + bytes([counter]))
    return timestamp


def noise(rng, end):
    periods = ((0x0C9, 5000), (0x1A0, 10000), (0x244, 20000),
               (0x316, 35000), (0x3E9, 40000), (0x510, 70000),
               (0x18FEF100, 13000))
    frames = []
    for arb_id, period in periods:
        timestamp = BASE_US + 347 + rng.randrange(period)
        while timestamp < end:
            frames.append(Frame(timestamp, arb_id, random_bytes(rng, 8)))
            timestamp += period + rng.randrange(-period // 20, period // 20 + 1)
    return frames


def to_candump(frames, rng):
    ordered = sorted(frames, key=lambda frame: frame.timestamp)
    chunks = [ordered[index:index + 64] for index in range(0, len(ordered), 64)]
    rng.shuffle(chunks)  # recovered logger fragments are not in wire order
    lines = []
    for chunk in chunks:
        for frame in chunk:
            seconds, microseconds = divmod(frame.timestamp, 1_000_000)
            width = 8 if frame.arb_id > 0x7FF else 3
            lines.append(f"({seconds}.{microseconds:06d}) can0 {frame.arb_id:0{width}X}#{frame.data.hex().upper()}")
    return ("\n".join(lines) + "\n").encode()


def partial_decompress(data):
    inflater = zlib.decompressobj()
    output = bytearray()
    for offset in range(0, len(data), 16):
        try:
            output.extend(inflater.decompress(data[offset:offset + 16]))
        except zlib.error:
            break
    return bytes(output)


def contains_flag_resource(image, flag):
    try:
        with zipfile.ZipFile(io.BytesIO(image)) as archive:
            return any(archive.read(name) == flag for name in archive.namelist())
    except (zipfile.BadZipFile, KeyError, RuntimeError, ValueError, zlib.error):
        return False


def compressed_offset_for_output(stream, output_offset):
    inflater = zlib.decompressobj()
    produced = 0
    for index, byte in enumerate(stream):
        produced += len(inflater.decompress(bytes([byte])))
        if produced > output_offset:
            return index
    raise ValueError("output offset is outside compressed stream")


def build_instance(seed=SEED, flag=FLAG):
    if re.fullmatch(r"wctf\{[0-9A-Za-z_]+\}", flag) is None:
        raise ValueError("flag must match wctf{[0-9A-Za-z_]+}")
    rng = random.Random(seed)
    image, zip_offset, embedded_zip = firmware(flag, rng)
    stream = zlib.compress(image, level=9)
    blocks = [stream[index:index + BLOCK_DATA_LEN] for index in range(0, len(stream), BLOCK_DATA_LEN)]
    if len(blocks) <= 256:
        raise ValueError("the download must wrap its block counter")
    aborted_image = bytearray(image)
    aborted_image[256:512] = bytes(256)  # earlier calibration image, before the completed reflash
    aborted_stream = zlib.compress(aborted_image, level=9)
    aborted_blocks = [aborted_stream[index:index + BLOCK_DATA_LEN]
                      for index in range(0, 30 * BLOCK_DATA_LEN, BLOCK_DATA_LEN)]
    duplicate_index = compressed_offset_for_output(stream, zip_offset) // BLOCK_DATA_LEN
    assert duplicate_index > 256

    frames = []
    timestamp = BASE_US + 100_000
    timestamp = exchange(frames, timestamp, b"\x10\x02", b"\x50\x02\x00\x32\x01\xf4")
    timestamp = exchange(frames, timestamp, b"\x22\xf1\xc0", b"\x62\xf1\xc0COMP=ZLIB;EXIT=CRC32")
    timestamp = download(frames, timestamp, len(image))
    for index, data in enumerate(aborted_blocks):
        timestamp = block(frames, timestamp, (index + 1) & 255, data)
    timestamp = emit_isotp(frames, timestamp, 0x7E8, 0x7E0, b"\x7f\x36\x71")
    timestamp = download(frames, timestamp, len(image))
    for index, data in enumerate(blocks):
        counter = (index + 1) & 255
        if index == duplicate_index:
            timestamp = block(frames, timestamp, counter, data, acknowledge=False)
        timestamp = block(frames, timestamp, counter, data)
        if index % 64 == 63:
            timestamp = exchange(frames, timestamp, b"\x3e\x00", b"\x7e\x00")
    timestamp = exchange(frames, timestamp, b"\x37" + zlib.crc32(image).to_bytes(4, "big"), b"\x77")
    capture = to_candump(frames + noise(rng, timestamp + 100_000), rng)
    return capture, {"flag": flag.encode(), "image": image, "stream": stream,
                     "zip_offset": zip_offset, "embedded_zip": embedded_zip,
                     "block_count": len(blocks), "aborted_blocks": aborted_blocks,
                     "duplicate_index": duplicate_index}


def verify(capture, built):
    flag, image, stream = built["flag"], built["image"], built["stream"]
    assert b"wctf" not in capture.lower()
    assert b"776374667b" not in capture.lower()
    assert b"wctf" not in stream.lower()
    assert b"wctf" not in image.lower()
    assert b"wctf" not in built["embedded_zip"].lower()
    assert built["zip_offset"] > len(image) // 2
    assert built["block_count"] > 256

    pre_wrap = partial_decompress(stream[:256 * BLOCK_DATA_LEN])
    assert BANNER in pre_wrap
    assert len(pre_wrap) < built["zip_offset"] and b"PK\x03\x04" not in pre_wrap
    kept_aborted = partial_decompress(b"".join(built["aborted_blocks"]) + stream)
    assert BANNER in kept_aborted and not contains_flag_resource(kept_aborted, flag)

    # Pooling blocks across both downloads must not bypass the suspended attempt.
    pooled = []
    seen = set()
    real_blocks = [stream[index:index + BLOCK_DATA_LEN]
                   for index in range(0, len(stream), BLOCK_DATA_LEN)]
    for attempt in (built["aborted_blocks"], real_blocks):
        for index, data in enumerate(attempt):
            key = ((index + 1) & 255, data)
            if key not in seen:
                pooled.append(data)
                seen.add(key)
    pooled_output = partial_decompress(b"".join(pooled))
    assert BANNER in pooled_output and not contains_flag_resource(pooled_output, flag)

    duplicate_at = (built["duplicate_index"] + 1) * BLOCK_DATA_LEN
    with_duplicate = stream[:duplicate_at] + real_blocks[built["duplicate_index"]] + stream[duplicate_at:]
    duplicate_output = partial_decompress(with_duplicate)
    assert BANNER in duplicate_output and not contains_flag_resource(duplicate_output, flag)

    solved, details = recover(capture)
    attempts = details["attempts"]
    assert solved == flag and details["stream"] == stream and details["image"] == image
    assert len(attempts) == 2 and attempts[0]["aborted"] and len(attempts[0]["blocks"]) == 30
    assert attempts[1]["duplicates"] == 1 and attempts[1]["maximum"] == BLOCK_DATA_LEN + 2
    counters = [counter for counter, _ in attempts[1]["blocks"]]
    assert (255, 0) in list(zip(counters, counters[1:]))
    assert attempts[1]["memory_size"] == len(image)
    assert attempts[1]["crc"] == zlib.crc32(image)
    assert details["zip_offset"] == built["zip_offset"]
    with zipfile.ZipFile(io.BytesIO(details["zip_bytes"])) as archive:
        info = archive.infolist()
        assert len(info) == 1 and info[0].compress_type == zipfile.ZIP_DEFLATED
        assert archive.read(info[0]) == flag


if __name__ == "__main__":
    capture, built = build_instance()
    verify(capture, built)
    output = ROOT / "challenge" / "capture.log"
    output.write_bytes(capture)
    print(f"{output}: {len(capture.splitlines())} frames, {built['block_count']} data blocks")
