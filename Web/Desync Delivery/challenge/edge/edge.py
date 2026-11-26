#!/usr/bin/env python3
"""Small, intentionally CL-framed HTTP/1.1 reverse proxy for the challenge."""

from __future__ import annotations

import logging
import os
import socket
import socketserver
import threading


HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
PORT = int(os.environ.get("LISTEN_PORT", "8081"))
BACKEND_HOST = os.environ.get("BACKEND_HOST", "backend")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "5000"))
MAX_HEADER_BYTES = 16 * 1024
MAX_BODY_BYTES = 64 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("parcel-edge")


class BadRequest(Exception):
    pass


def read_exact(reader, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        part = reader.read(length - len(chunks))
        if not part:
            raise BadRequest("truncated request body")
        chunks.extend(part)
    return bytes(chunks)


def read_request(reader):
    first = reader.readline(MAX_HEADER_BYTES + 1)
    if not first:
        return None
    if len(first) > MAX_HEADER_BYTES or not first.endswith(b"\r\n"):
        raise BadRequest("invalid request line")

    lines = [first]
    total = len(first)
    while True:
        line = reader.readline(MAX_HEADER_BYTES + 1)
        if not line:
            raise BadRequest("incomplete headers")
        total += len(line)
        if total > MAX_HEADER_BYTES or not line.endswith(b"\r\n"):
            raise BadRequest("invalid headers")
        if line == b"\r\n":
            break
        lines.append(line)

    try:
        method, target, version = first[:-2].decode("ascii").split(" ")
    except (UnicodeDecodeError, ValueError) as exc:
        raise BadRequest("invalid request line") from exc
    if version not in ("HTTP/1.0", "HTTP/1.1") or not method or not target:
        raise BadRequest("unsupported request line")

    fields: list[tuple[bytes, bytes]] = []
    for line in lines[1:]:
        name, separator, value = line[:-2].partition(b":")
        if not separator or not name or any(c <= 32 or c >= 127 or c == 58 for c in name):
            raise BadRequest("invalid header field")
        fields.append((name, value.strip()))

    lengths = [value for name, value in fields if name.lower() == b"content-length"]
    if len(lengths) > 1:
        raise BadRequest("multiple Content-Length fields")
    body_length = 0
    if lengths:
        try:
            raw_length = lengths[0].decode("ascii")
            if not raw_length.isdecimal():
                raise ValueError
            body_length = int(raw_length)
        except (UnicodeDecodeError, ValueError) as exc:
            raise BadRequest("invalid Content-Length") from exc
    if body_length > MAX_BODY_BYTES:
        raise BadRequest("request body too large")

    # The deliberate vulnerability: intake consumes by Content-Length, even
    # when Transfer-Encoding is also present, and forwards the ambiguity intact.
    body = read_exact(reader, body_length) if body_length else b""

    forwarded = bytearray(first)
    for name, value in fields:
        lower_name = name.lower()
        # A player cannot forge the proxy's marker. The edge replaces it on
        # the outer request only; bytes inside that request body stay opaque.
        if lower_name in (b"x-proxy-verified", b"connection"):
            continue
        forwarded.extend(name + b": " + value + b"\r\n")
    forwarded.extend(b"Connection: keep-alive\r\n")
    forwarded.extend(b"X-Proxy-Verified: 1\r\n\r\n")
    forwarded.extend(body)
    return bytes(forwarded), method, target, body_length


def relay_responses(upstream: socket.socket, client: socket.socket) -> None:
    try:
        while True:
            block = upstream.recv(16 * 1024)
            if not block:
                break
            client.sendall(block)
    except OSError:
        pass
    finally:
        try:
            client.shutdown(socket.SHUT_WR)
        except OSError:
            pass


class Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        client = self.request
        client.settimeout(30)
        upstream = None
        response_thread = None
        reader = client.makefile("rb")
        try:
            upstream = socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=3)
            upstream.settimeout(None)
            response_thread = threading.Thread(
                target=relay_responses, args=(upstream, client), daemon=True
            )
            response_thread.start()

            while True:
                request = read_request(reader)
                if request is None:
                    break
                wire, method, target, body_length = request
                upstream.sendall(wire)
                LOG.info("forwarded %s %s (Content-Length bytes=%d)", method, target, body_length)
        except (BadRequest, OSError, TimeoutError) as exc:
            LOG.info("closing client connection: %s", exc)
            try:
                client.sendall(
                    b"HTTP/1.1 400 Bad Request\r\nContent-Length: 12\r\n"
                    b"Connection: close\r\nContent-Type: text/plain\r\n\r\nBad Request\n"
                )
            except OSError:
                pass
        finally:
            try:
                reader.close()
            except OSError:
                pass
            if upstream is not None:
                try:
                    upstream.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                if response_thread is not None:
                    response_thread.join(timeout=5)
                upstream.close()


class ThreadedServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 64


if __name__ == "__main__":
    with ThreadedServer((HOST, PORT), Handler) as server:
        LOG.info("CL-framed edge listening on %s:%d -> %s:%d", HOST, PORT, BACKEND_HOST, BACKEND_PORT)
        server.serve_forever(poll_interval=0.5)
