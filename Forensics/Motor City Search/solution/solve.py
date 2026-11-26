#!/usr/bin/env python3
"""Recover the flashed image from a SocketCAN log. Usage: solve.py capture.log"""

import io
import re
import sys
import zipfile
import zlib

LINE = re.compile(rb"\((\d+)\.(\d{6})\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]*)$")
FLAG = re.compile(rb"wctf\{[0-9A-Za-z_]+\}")


def messages(capture):
    frames = []
    for line in capture.splitlines():
        match = LINE.fullmatch(line)
        if not match:
            raise ValueError(f"invalid candump line: {line[:80]!r}")
        sec, usec, arb, data = match.groups()
        frames.append((int(sec) * 1_000_000 + int(usec), int(arb, 16), bytes.fromhex(data.decode())))
    frames.sort(key=lambda frame: frame[0])

    open_messages = {}
    result = []
    for timestamp, arb, data in frames:
        if arb not in (0x7E0, 0x7E8) or not data:
            continue
        kind = data[0] >> 4
        if kind == 0:  # ISO-TP single frame
            length = data[0] & 15
            if length > 7 or len(data) < length + 1:
                raise ValueError("invalid single frame")
            result.append((timestamp, arb, data[1:1 + length]))
        elif kind == 1:  # first frame
            length = ((data[0] & 15) << 8) | data[1]
            if length <= 7 or arb in open_messages:
                raise ValueError("invalid or overlapping first frame")
            open_messages[arb] = [length, bytearray(data[2:]), 1]
        elif kind == 2:  # consecutive frame
            if arb not in open_messages:
                raise ValueError("orphan consecutive frame")
            length, payload, expected = open_messages[arb]
            if data[0] & 15 != expected:
                raise ValueError("ISO-TP sequence mismatch")
            payload.extend(data[1:])
            if len(payload) >= length:
                result.append((timestamp, arb, bytes(payload[:length])))
                del open_messages[arb]
            else:
                open_messages[arb][2] = (expected + 1) & 15
        elif kind != 3:  # flow-control frames are transport metadata
            raise ValueError("unknown ISO-TP frame type")
    if open_messages:
        raise ValueError("incomplete ISO-TP message")
    return sorted(result)


def recover(capture):
    attempts = []
    current = None
    for _, arb, msg in messages(capture):
        if not msg:
            continue
        sid = msg[0]
        if arb == 0x7E0 and sid == 0x34:
            if len(msg) < 4 or msg[1] != 0x10:
                raise ValueError("unexpected download format")
            address_bytes, size_bytes = msg[2] & 15, msg[2] >> 4
            if len(msg) != 3 + address_bytes + size_bytes or not size_bytes:
                raise ValueError("invalid RequestDownload length")
            memory_size = int.from_bytes(msg[3 + address_bytes:], "big")
            current = {"memory_size": memory_size, "maximum": None, "blocks": [],
                       "next_counter": 1, "duplicates": 0, "aborted": False,
                       "crc": None, "exit_confirmed": False}
            attempts.append(current)
        elif arb == 0x7E8 and sid == 0x74:
            if current is None or len(msg) < 3:
                raise ValueError("orphan download response")
            width = msg[1] >> 4
            if width == 0 or len(msg) != 2 + width:
                raise ValueError("invalid block-length response")
            current["maximum"] = int.from_bytes(msg[2:], "big")
        elif arb == 0x7E0 and sid == 0x36:
            if current is None or current["aborted"] or current["maximum"] is None:
                raise ValueError("TransferData outside an active download")
            if len(msg) < 3 or len(msg) > current["maximum"]:
                raise ValueError("invalid TransferData block length")
            counter, data = msg[1], msg[2:]
            if counter == current["next_counter"]:
                current["blocks"].append((counter, data))
                current["next_counter"] = (counter + 1) & 255
            elif current["blocks"] and (counter, data) == current["blocks"][-1]:
                current["duplicates"] += 1
            else:
                raise ValueError("block counter or retransmission mismatch")
        elif arb == 0x7E8 and msg == b"\x7f\x36\x71":
            if current is None:
                raise ValueError("orphan transfer suspension")
            current["aborted"] = True
        elif arb == 0x7E0 and sid == 0x37:
            if current is None or current["aborted"] or len(msg) != 5:
                raise ValueError("invalid RequestTransferExit")
            current["crc"] = int.from_bytes(msg[1:], "big")
        elif arb == 0x7E8 and msg == b"\x77":
            if current is None or current["crc"] is None:
                raise ValueError("orphan transfer-exit response")
            current["exit_confirmed"] = True

    completed = [attempt for attempt in attempts if attempt["exit_confirmed"]]
    if len(completed) != 1 or len(attempts) != 2 or not attempts[0]["aborted"]:
        raise ValueError("expected one aborted and one completed download")
    chosen = completed[0]
    stream = b"".join(data for _, data in chosen["blocks"])
    inflater = zlib.decompressobj()
    image = inflater.decompress(stream) + inflater.flush()
    if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError("incomplete or trailing compressed data")
    if len(image) != chosen["memory_size"] or zlib.crc32(image) != chosen["crc"]:
        raise ValueError("image length or CRC32 mismatch")

    start = image.find(b"PK\x03\x04")
    end_record = image.find(b"PK\x05\x06", start + 4)
    if start < 0 or end_record < 0 or end_record + 22 > len(image):
        raise ValueError("embedded ZIP not found")
    comment_length = int.from_bytes(image[end_record + 20:end_record + 22], "little")
    archive = image[start:end_record + 22 + comment_length]
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        names = zipped.namelist()
        if len(names) != 1:
            raise ValueError("unexpected firmware resource count")
        payload = zipped.read(names[0])
    if not FLAG.fullmatch(payload):
        raise ValueError("resource is not a flag")
    return payload, {"attempts": attempts, "stream": stream, "image": image,
                     "zip_offset": start, "zip_bytes": archive}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "capture.log"
    with open(path, "rb") as source:
        print(recover(source.read())[0].decode())
