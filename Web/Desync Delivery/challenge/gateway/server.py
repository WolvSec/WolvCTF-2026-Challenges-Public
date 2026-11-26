#!/usr/bin/env python3
"""HTTP ingress and fixed-target byte relay for the Cloud Run deployment."""

from __future__ import annotations

import http.client
import logging
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


HOST = "0.0.0.0"
PORT = int(os.environ.get("LISTEN_PORT", "8080"))
EDGE_HOST = os.environ.get("EDGE_HOST", "edge")
EDGE_PORT = int(os.environ.get("EDGE_PORT", "8081"))
MAX_REQUEST_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
SOCKET_TIMEOUT = 8

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("parcel-gateway")


class BadRequest(Exception):
    pass


def read_outer_body(handler: BaseHTTPRequestHandler) -> bytes:
    """Read the ordinary HTTP envelope body, including chunked Cloud Run hops."""

    transfer_encodings = handler.headers.get_all("Transfer-Encoding", [])
    content_lengths = handler.headers.get_all("Content-Length", [])
    if transfer_encodings and content_lengths:
        raise BadRequest("ambiguous envelope framing")

    if transfer_encodings:
        if len(transfer_encodings) != 1 or transfer_encodings[0].strip().lower() != "chunked":
            raise BadRequest("unsupported envelope transfer coding")
        body = bytearray()
        trailer_bytes = 0
        while True:
            line = handler.rfile.readline(4097)
            if len(line) > 4096 or not line.endswith(b"\r\n"):
                raise BadRequest("invalid envelope chunk size")
            token = line[:-2].split(b";", 1)[0].strip()
            try:
                size = int(token, 16)
            except ValueError as exc:
                raise BadRequest("invalid envelope chunk size") from exc
            if size < 0 or len(body) + size > MAX_REQUEST_BYTES:
                raise BadRequest("envelope too large")
            if size == 0:
                while True:
                    trailer = handler.rfile.readline(4097)
                    trailer_bytes += len(trailer)
                    if len(trailer) > 4096 or not trailer.endswith(b"\r\n") or trailer_bytes > 8192:
                        raise BadRequest("invalid envelope trailer")
                    if trailer == b"\r\n":
                        return bytes(body)
                    if b":" not in trailer:
                        raise BadRequest("invalid envelope trailer")
            chunk = handler.rfile.read(size)
            if len(chunk) != size or handler.rfile.read(2) != b"\r\n":
                raise BadRequest("truncated envelope chunk")
            body.extend(chunk)

    if len(content_lengths) > 1:
        raise BadRequest("multiple envelope lengths")
    length = 0
    if content_lengths:
        value = content_lengths[0].strip()
        if not value.isdecimal():
            raise BadRequest("invalid envelope length")
        try:
            length = int(value)
        except ValueError as exc:
            raise BadRequest("invalid envelope length") from exc
    if length > MAX_REQUEST_BYTES:
        raise BadRequest("envelope too large")
    body = handler.rfile.read(length)
    if len(body) != length:
        raise BadRequest("truncated envelope")
    return body


def exchange(payload: bytes) -> bytes:
    """Forward bytes to the sole configured edge and collect its response stream."""

    if not payload or len(payload) > MAX_REQUEST_BYTES:
        raise BadRequest("parcel batch must be between 1 and 16384 bytes")
    chunks = bytearray()
    with socket.create_connection((EDGE_HOST, EDGE_PORT), timeout=SOCKET_TIMEOUT) as upstream:
        upstream.settimeout(SOCKET_TIMEOUT)
        upstream.sendall(payload)
        upstream.shutdown(socket.SHUT_WR)
        while True:
            block = upstream.recv(8192)
            if not block:
                break
            chunks.extend(block)
            if len(chunks) > MAX_RESPONSE_BYTES:
                raise BadRequest("depot response too large")
    return bytes(chunks)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ParcelGateway/1.0"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(SOCKET_TIMEOUT)

    def _send(self, status: int, body: bytes, content_type: str, reason: str | None = None) -> None:
        self.send_response(status, reason)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def _read_body_or_400(self) -> bytes | None:
        try:
            return read_outer_body(self)
        except (BadRequest, OSError, TimeoutError) as exc:
            LOG.info("rejected envelope from %s: %s", self.client_address[0], exc)
            self._send(400, b"Bad request\n", "text/plain; charset=utf-8")
            return None

    def _normal_request(self, body: bytes) -> None:
        parts = urlsplit(self.path)
        target = parts.path or "/"
        if parts.query:
            target += "?" + parts.query
        if any(char in target for char in "\r\n"):
            self._send(400, b"Bad request\n", "text/plain; charset=utf-8")
            return

        try:
            wire = bytearray(f"{self.command} {target} HTTP/1.1\r\nHost: depot.local\r\n".encode("ascii"))
        except UnicodeEncodeError:
            self._send(400, b"Bad request\n", "text/plain; charset=utf-8")
            return
        hop_headers = {
            "connection", "content-length", "expect", "host", "keep-alive",
            "proxy-connection", "te", "trailer", "transfer-encoding", "upgrade",
        }
        for name, value in self.headers.items():
            lower = name.lower()
            if lower in hop_headers or lower.startswith("x-proxy-"):
                continue
            if "\r" not in value and "\n" not in value:
                wire.extend(f"{name}: {value}\r\n".encode("latin-1"))
        wire.extend(f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii"))
        wire.extend(body)

        try:
            with socket.create_connection((EDGE_HOST, EDGE_PORT), timeout=SOCKET_TIMEOUT) as upstream:
                upstream.settimeout(SOCKET_TIMEOUT)
                upstream.sendall(wire)
                upstream.shutdown(socket.SHUT_WR)
                response = http.client.HTTPResponse(upstream)
                response.begin()
                response_body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(response_body) > MAX_RESPONSE_BYTES:
                    raise BadRequest("depot response too large")
                content_type = response.getheader("Content-Type", "application/octet-stream")
                self._send(response.status, response_body, content_type, response.reason)
        except (OSError, http.client.HTTPException, BadRequest, TimeoutError) as exc:
            LOG.warning("depot request failed: %s", exc)
            if not self.wfile.closed:
                self._send(502, b"Intake unavailable\n", "text/plain; charset=utf-8")

    def _handle(self) -> None:
        body = self._read_body_or_400()
        if body is None:
            return
        try:
            path = urlsplit(self.path).path
        except ValueError:
            self._send(400, b"Bad request\n", "text/plain; charset=utf-8")
            return
        if self.command == "POST" and path == "/intake":
            try:
                response_stream = exchange(body)
            except (BadRequest, OSError, TimeoutError) as exc:
                LOG.info("intake batch failed: %s", exc)
                self._send(400 if isinstance(exc, BadRequest) else 502, b"Intake could not process batch\n", "text/plain; charset=utf-8")
                return
            self._send(200, response_stream, "application/octet-stream")
            return
        self._normal_request(body)

    do_GET = _handle
    do_HEAD = _handle
    do_POST = _handle

    def log_message(self, format: str, *args) -> None:
        LOG.info("%s - %s", self.client_address[0], format % args)


if __name__ == "__main__":
    with ThreadingHTTPServer((HOST, PORT), Handler) as server:
        server.daemon_threads = True
        server.request_queue_size = 64
        LOG.info("HTTP gateway listening on %s:%d -> %s:%d", HOST, PORT, EDGE_HOST, EDGE_PORT)
        server.serve_forever(poll_interval=0.5)
