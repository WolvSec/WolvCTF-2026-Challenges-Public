#!/usr/bin/env python3
"""Minimal HTTP/1.1 depot that deliberately prefers chunked framing."""

from __future__ import annotations

import html
import logging
import os
import re
import socket
import socketserver
import urllib.parse


HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
PORT = int(os.environ.get("LISTEN_PORT", "5000"))
MAX_HEADER_BYTES = 16 * 1024
MAX_BODY_BYTES = 64 * 1024
FLAG = os.environ.get("FLAG", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("parcel-depot")


class BadRequest(Exception):
    pass


class SocketReader:
    """Buffered reader for HTTP request framing."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.buffer = bytearray()
        self.eof = False

    def _fill(self) -> bool:
        if self.eof:
            return False
        block = self.sock.recv(4096)
        if not block:
            self.eof = True
            return False
        self.buffer.extend(block)
        return True

    def readline(self, limit: int) -> bytes:
        while True:
            index = self.buffer.find(b"\n")
            if index >= 0:
                if index + 1 > limit:
                    raise BadRequest("line too long")
                result = bytes(self.buffer[: index + 1])
                del self.buffer[: index + 1]
                return result
            if len(self.buffer) >= limit:
                raise BadRequest("line too long")
            if not self._fill():
                if not self.buffer:
                    return b""
                result = bytes(self.buffer)
                self.buffer.clear()
                return result

    def readexact(self, length: int) -> bytes:
        while len(self.buffer) < length:
            if not self._fill():
                raise BadRequest("truncated body")
        result = bytes(self.buffer[:length])
        del self.buffer[:length]
        return result


def parse_headers(reader: SocketReader):
    request_line = reader.readline(4096)
    if not request_line:
        return None
    if not request_line.endswith(b"\r\n"):
        raise BadRequest("invalid request line")
    try:
        method, target, version = request_line[:-2].decode("ascii").split(" ")
    except (UnicodeDecodeError, ValueError) as exc:
        raise BadRequest("invalid request line") from exc
    if version not in ("HTTP/1.0", "HTTP/1.1") or not method or not target:
        raise BadRequest("unsupported request line")

    headers: dict[str, list[str]] = {}
    consumed = len(request_line)
    while True:
        line = reader.readline(MAX_HEADER_BYTES + 1)
        if not line or not line.endswith(b"\r\n"):
            raise BadRequest("incomplete headers")
        consumed += len(line)
        if consumed > MAX_HEADER_BYTES:
            raise BadRequest("headers too large")
        if line == b"\r\n":
            break
        name, separator, value = line[:-2].partition(b":")
        if not separator or not name or any(c <= 32 or c >= 127 or c == 58 for c in name):
            raise BadRequest("invalid header field")
        try:
            key = name.decode("ascii").lower()
            field_value = value.strip().decode("latin-1")
        except UnicodeDecodeError as exc:
            raise BadRequest("invalid header encoding") from exc
        headers.setdefault(key, []).append(field_value)
    return method, target, version, headers


def read_chunked_body(reader: SocketReader) -> bytes:
    body = bytearray()
    trailer_bytes = 0
    while True:
        line = reader.readline(8192)
        if not line.endswith(b"\r\n"):
            raise BadRequest("invalid chunk size")
        size_token = line[:-2].split(b";", 1)[0].strip()
        try:
            size = int(size_token, 16)
        except ValueError as exc:
            raise BadRequest("invalid chunk size") from exc
        if size < 0 or len(body) + size > MAX_BODY_BYTES:
            raise BadRequest("chunked body too large")
        if size == 0:
            while True:
                trailer = reader.readline(8192)
                trailer_bytes += len(trailer)
                if not trailer.endswith(b"\r\n") or trailer_bytes > MAX_HEADER_BYTES:
                    raise BadRequest("invalid trailer")
                if trailer == b"\r\n":
                    return bytes(body)
                if b":" not in trailer:
                    raise BadRequest("invalid trailer")
        body.extend(reader.readexact(size))
        if reader.readexact(2) != b"\r\n":
            raise BadRequest("invalid chunk terminator")


def read_request(reader: SocketReader):
    parsed = parse_headers(reader)
    if parsed is None:
        return None
    method, target, version, headers = parsed

    transfer_encodings = headers.get("transfer-encoding", [])
    if transfer_encodings:
        # Deliberate backend behavior: Transfer-Encoding takes precedence over
        # Content-Length, leaving bytes after the terminal chunk for the next
        # request on this same upstream connection.
        if len(transfer_encodings) != 1 or transfer_encodings[0].lower() != "chunked":
            raise BadRequest("unsupported transfer coding")
        body = read_chunked_body(reader)
    else:
        lengths = headers.get("content-length", [])
        if len(lengths) > 1:
            raise BadRequest("multiple Content-Length fields")
        length = 0
        if lengths:
            try:
                if not lengths[0].isdecimal():
                    raise ValueError
                length = int(lengths[0])
            except ValueError as exc:
                raise BadRequest("invalid Content-Length") from exc
        if length > MAX_BODY_BYTES:
            raise BadRequest("body too large")
        body = reader.readexact(length) if length else b""

    return method, target, version, headers, body


def respond(sock: socket.socket, status: int, reason: str, body: bytes, content_type: str, close: bool):
    connection = b"close" if close else b"keep-alive"
    response = (
        f"HTTP/1.1 {status} {reason}\r\n".encode("ascii")
        + b"Server: ParcelDepot/1.0\r\n"
        + b"Content-Type: " + content_type.encode("ascii") + b"\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"Connection: " + connection + b"\r\n\r\n"
        + body
    )
    sock.sendall(response)


def route(method: str, target: str, headers: dict[str, list[str]]):
    parsed = urllib.parse.urlsplit(target)
    path = parsed.path or "/"
    verified = headers.get("x-proxy-verified", [None])[-1]

    if method not in ("GET", "HEAD", "POST"):
        return 405, "Method Not Allowed", b"Method not allowed\n", "text/plain; charset=utf-8"

    if path == "/internal/admin/flag":
        if verified == "1":
            return 403, "Forbidden", b"Operations records are available only to depot-side requests.\n", "text/plain; charset=utf-8"
        return 200, "OK", (FLAG + "\n").encode("ascii"), "text/plain; charset=utf-8"

    if path == "/robots.txt":
        body = b"User-agent: *\nDisallow: /internal/admin/flag\nDisallow: /handoff.txt\nDisallow: /intake\n"
        return 200, "OK", body, "text/plain; charset=utf-8"

    if path == "/handoff.txt":
        body = (
            "Shift handoff\n"
            "Bulk intake is available at /intake. The desk and depot share a connection,\n"
            "but their ledgers sometimes disagree about where a parcel ends.\n"
            "The desk stamps each request it checks with X-Proxy-Verified: 1.\n"
        ).encode("ascii")
        return 200, "OK", body, "text/plain; charset=utf-8"

    if path == "/track":
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        tracking_id = query.get("id", [""])[0][:48]
        safe_id = html.escape(tracking_id or "(missing)")
        body = (
            "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Parcel status</title>"
            "<body><main><h1>Parcel status</h1><p>Reference: <code>" + safe_id + "</code></p>"
            "<p>Status: held for routine depot review.</p><a href=\"/\">Return to tracking</a></main></body></html>"
        ).encode("utf-8")
        return 200, "OK", body, "text/html; charset=utf-8"

    if path == "/" and method in ("GET", "HEAD", "POST"):
        body = (
            "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Desync Delivery | Parcel tracking</title>"
            "<style>body{font:16px system-ui;max-width:48rem;margin:4rem auto;padding:0 1rem;color:#202a35}"
            "main{border:1px solid #ccd3da;border-radius:12px;padding:2rem}label,input,button{font:inherit}"
            "input{padding:.55rem;width:min(22rem,70%)}button{padding:.6rem 1rem}small{color:#55616e}</style>"
            "<body><main><h1>Desync Delivery</h1><p>Find the latest public update for a parcel.</p>"
            "<form action=\"/track\" method=\"get\"><label for=\"id\">Tracking number</label> "
            "<input id=\"id\" name=\"id\" autocomplete=\"off\" required> <button>Track</button></form>"
            "<p><small>For parcel handling notes, see <a href=\"/handoff.txt\">shift handoff</a>.</small></p>"
            "</main></body></html>"
        ).encode("utf-8")
        return 200, "OK", body, "text/html; charset=utf-8"

    return 404, "Not Found", b"Not found\n", "text/plain; charset=utf-8"


class Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(30)
        reader = SocketReader(self.request)
        while True:
            try:
                request = read_request(reader)
            except (BadRequest, OSError, TimeoutError) as exc:
                LOG.info("invalid request from %s: %s", self.client_address[0], exc)
                try:
                    respond(self.request, 400, "Bad Request", b"Bad request\n", "text/plain; charset=utf-8", True)
                except OSError:
                    pass
                return
            if request is None:
                return

            method, target, _version, headers, _body = request
            connection_tokens = ",".join(headers.get("connection", [])).lower()
            close = "close" in (token.strip() for token in connection_tokens.split(","))
            try:
                status, reason, body, content_type = route(method, target, headers)
                if method == "HEAD":
                    body = b""
                respond(self.request, status, reason, body, content_type, close)
            except OSError:
                return
            LOG.info("%s %s -> %d", method, target, status)
            if close:
                return


class ThreadedServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 64


if __name__ == "__main__":
    if not re.fullmatch(r"wctf\{[0-9a-f]{32}\}", FLAG):
        raise SystemExit("FLAG must use the wctf{32 lowercase hex characters} format")
    with ThreadedServer((HOST, PORT), Handler) as server:
        LOG.info("depot listening on %s:%d", HOST, PORT)
        server.serve_forever(poll_interval=0.5)
