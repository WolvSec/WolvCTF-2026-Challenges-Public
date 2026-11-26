#!/usr/bin/env python3
"""Reject incomplete Jurassic HTTP captures before packaging them."""

import hashlib
import struct
import sys
from collections import defaultdict
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def reassemble(segments, syns, fins, peer_acks, label, limit):
    require(len(syns) == 1 and len(fins) <= 1, f"{label}: missing SYN or conflicting FIN")
    start = next(iter(syns)) + 1
    fin = next(iter(fins)) if fins else None
    ack_end = max(peer_acks, default=start)
    if fin is not None and ack_end == fin + 1:
        ack_end = fin
    end = max(ack_end, fin or start, *(seq + len(payload) for seq, payload in segments))
    require(start <= end <= start + limit, f"{label}: invalid sequence range")
    data = bytearray(end - start)
    seen = bytearray(end - start)
    for seq, payload in segments:
        offset = seq - start
        require(0 <= offset <= len(data) and offset + len(payload) <= len(data), f"{label}: payload outside SYN/FIN range")
        for pos, byte in enumerate(payload, offset):
            require(not seen[pos] or data[pos] == byte, f"{label}: conflicting retransmission at byte {pos}")
            data[pos] = byte
            seen[pos] = 1
    require(all(seen), f"{label}: {len(data) - sum(seen)} missing TCP bytes")
    return bytes(data)


def extract_http(pcap):
    raw = Path(pcap).read_bytes()
    require(len(raw) >= 24 and raw[:4] == b"\xd4\xc3\xb2\xa1", "expected little-endian PCAP")
    require(struct.unpack_from("<I", raw, 20)[0] == 1, "expected Ethernet PCAP")
    streams = defaultdict(lambda: {side: {"segments": [], "syns": set(), "fins": set(), "acks": set()} for side in ("request", "response")})
    offset = 24
    packets = 0
    while offset < len(raw):
        require(offset + 16 <= len(raw), "truncated PCAP record header")
        _, _, included, original = struct.unpack_from("<IIII", raw, offset)
        offset += 16
        require(included == original and offset + included <= len(raw), "truncated PCAP packet")
        frame = raw[offset:offset + included]
        offset += included
        packets += 1
        # shortcut: generated captures use short, non-wrapping Ethernet/IPv4 TCP streams; extend if the capture format changes.
        require(len(frame) >= 54 and frame[12:14] == b"\x08\x00", "unexpected non-IPv4 frame")
        ip = frame[14:]
        ihl = (ip[0] & 15) * 4
        total = struct.unpack_from("!H", ip, 2)[0]
        require(ip[0] >> 4 == 4 and ihl >= 20 and len(ip) >= total and ip[9] == 6, "invalid IPv4/TCP packet")
        require(struct.unpack_from("!H", ip, 6)[0] & 0x3FFF == 0, "fragmented IPv4 packet")
        tcp = ip[ihl:total]
        require(len(tcp) >= 20, "short TCP header")
        src, dst, seq = struct.unpack_from("!HHI", tcp)
        header_len = (tcp[12] >> 4) * 4
        require(header_len >= 20 and header_len <= len(tcp), "invalid TCP header length")
        require(src == 8080 or dst == 8080, "unexpected TCP port")
        client = (ip[12:16], src) if dst == 8080 else (ip[16:20], dst)
        side = "request" if dst == 8080 else "response"
        stream = streams[client][side]
        flags = tcp[13]
        if flags & 2:
            stream["syns"].add(seq)
        payload = tcp[header_len:]
        if flags & 1:
            stream["fins"].add(seq + len(payload))
        if flags & 16:
            stream["acks"].add(struct.unpack_from("!I", tcp, 8)[0])
        if payload:
            stream["segments"].append((seq, payload))
    require(offset == len(raw), "trailing PCAP bytes")

    found = {}
    for client, directions in streams.items():
        request = reassemble(directions["request"]["segments"], directions["request"]["syns"], directions["request"]["fins"], directions["response"]["acks"], f"{client} request", len(raw))
        response = reassemble(directions["response"]["segments"], directions["response"]["syns"], directions["response"]["fins"], directions["request"]["acks"], f"{client} response", len(raw))
        request_line = request.split(b"\r\n", 1)[0].split()
        require(len(request_line) == 3 and request_line[0] == b"GET" and request_line[2] == b"HTTP/1.1", "unexpected HTTP request")
        path = request_line[1].decode("ascii")
        require(path not in found, f"duplicate request {path}")
        header, separator, body = response.partition(b"\r\n\r\n")
        require(separator, f"{path}: missing HTTP headers")
        lines = header.split(b"\r\n")
        require(lines[0].startswith(b"HTTP/1.1 "), f"{path}: bad HTTP status")
        lengths = [line.split(b":", 1)[1].strip() for line in lines[1:] if line.lower().startswith(b"content-length:")]
        require(len(lengths) == 1 and lengths[0].isdigit(), f"{path}: missing or bad Content-Length")
        require(len(body) == int(lengths[0]), f"{path}: {len(body)}/{int(lengths[0])} HTTP body bytes")
        found[path] = (lines[0], body)
    return found, packets


def validate(pcap, image_dir, output_dir):
    found, packets = extract_http(pcap)
    image_dir = Path(image_dir)
    images = {f"/static/images/{p.name}": p for p in image_dir.glob("*.jpg")}
    expected = {"/": 200, "/robots.txt": 404, "/static/css/style.css": 200, **dict.fromkeys(images, 200)}
    require(len(images) == 7 and set(found) == set(expected), "missing or unexpected HTTP request/image")
    for path, (status, body) in found.items():
        require(status == f"HTTP/1.1 {expected[path]}".encode() + (b" OK" if expected[path] == 200 else b" NOT FOUND"), f"{path}: bad HTTP status")
        if path in images:
            source = images[path].read_bytes()
            require(body.startswith(b"\xff\xd8") and body.endswith(b"\xff\xd9"), f"{path}: incomplete JPEG")
            require(hashlib.sha256(body).digest() == hashlib.sha256(source).digest(), f"{path}: JPEG hash mismatch")
            if path.endswith(("stegosaurus.jpg", "archaeopteryx.jpg")):
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                (Path(output_dir) / Path(path).name).write_bytes(body)
        elif path == "/static/css/style.css":
            require(body == (image_dir.parent / "css/style.css").read_bytes(), "CSS mismatch")
    print(f"validated {packets} packets, {len(found)} HTTP bodies, {len(images)} JPEG hashes")


if __name__ == "__main__":
    try:
        validate(*sys.argv[1:])
    except (OSError, ValueError) as error:
        sys.exit(str(error))
