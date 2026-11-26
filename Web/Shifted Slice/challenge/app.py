#!/usr/bin/env python3
"""A bundle cutter with a deliberately revision-blind read capability."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SEALED = "m-sealed"
PUBLIC = "p-public"
OWNED = "z-owned"
SCRATCH = "zz-scratch"
KEY_RE = re.compile(r"[a-z][a-z0-9-]{0,15}\Z")
TEXT_RE = re.compile(r"[ -~]{1,64}\Z")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]+\Z")
FLAG = open(os.environ.get("FLAG_FILE", "/flag"), "rb").read().strip()
if not re.fullmatch(rb"wctf\{[0-9a-f]{32}\}", FLAG):
    raise RuntimeError("invalid flag")
SESSION_KEY = hmac.digest(FLAG, b"shifted-slice/session/v1", "sha256")
TICKET_KEY = hmac.digest(FLAG, b"shifted-slice/ticket/v1", "sha256")
MASK_KEY = hmac.digest(FLAG, b"shifted-slice/archive-mask/v1", "sha256")
COOKIE = "slice_session"


def encode(body, key):
    return base64.urlsafe_b64encode(body + hmac.digest(key, body, "sha256")).rstrip(b"=").decode()


def decode(token, key, maximum):
    if not isinstance(token, str) or not 40 <= len(token) <= maximum or not TOKEN_RE.fullmatch(token):
        raise ValueError("invalid token")
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except binascii.Error as error:
        raise ValueError("invalid token") from error
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode() != token or len(raw) < 33:
        raise ValueError("invalid token")
    body, mac = raw[:-32], raw[-32:]
    if not hmac.compare_digest(mac, hmac.digest(key, body, "sha256")):
        raise ValueError("invalid token")
    return body


def new_session():
    return secrets.token_bytes(16), "", "", "", False


def encode_session(session):
    sid, key, text, moved, compact = session
    key_bytes, text_bytes, moved_bytes = key.encode("ascii"), text.encode("ascii"), moved.encode("ascii")
    body = bytes([3]) + sid + bytes([len(key_bytes)]) + key_bytes + bytes([len(text_bytes)]) + text_bytes + bytes([len(moved_bytes)]) + moved_bytes + bytes([int(compact)])
    return encode(body, SESSION_KEY)


def decode_session(token):
    body = decode(token, SESSION_KEY, 200)
    if len(body) < 21 or body[0] != 3:
        raise ValueError("invalid session")
    sid = body[1:17]
    key_size = body[17]
    if len(body) < 19 + key_size:
        raise ValueError("invalid session")
    key = body[18:18 + key_size].decode("ascii")
    text_size = body[18 + key_size]
    moved_index = 19 + key_size + text_size
    if len(body) <= moved_index:
        raise ValueError("invalid session")
    text = body[19 + key_size:moved_index].decode("ascii")
    moved_size = body[moved_index]
    if len(body) != moved_index + 2 + moved_size:
        raise ValueError("invalid session")
    moved = body[moved_index + 1:-1].decode("ascii")
    if body[-1] not in (0, 1):
        raise ValueError("invalid session")
    if (key or text) and (not KEY_RE.fullmatch(key) or key in (SEALED, OWNED, PUBLIC, SCRATCH) or not TEXT_RE.fullmatch(text)):
        raise ValueError("invalid session")
    if moved and (not KEY_RE.fullmatch(moved) or moved in (SEALED, OWNED, PUBLIC, SCRATCH, key)):
        raise ValueError("invalid session")
    if bool(key) != bool(text):
        raise ValueError("invalid session")
    return sid, key, text, moved, bool(body[-1])


def records(session):
    sid, key, text, moved, compact = session
    items = [
        (SEALED, "sealed", b"FLAG:" + FLAG + b"\n"),
        (moved or PUBLIC, "public", b"INDEX/1\nordinary public record\n"),
        (OWNED, "owned", b"NOTE/1\n" + hmac.digest(SESSION_KEY, b"private-note/v1\0" + sid, "sha256")[:16].hex().encode() + b"\nowner-copy\n"),
        (SCRATCH, "owned", b"SCRATCH/1\n" + b"x" * (31 if compact else 99) + b"\n"),
    ]
    if key:
        items.append((key, "public", b"PUBLIC/1\n" + text.encode() + b"\n"))
    return sorted(items)


def manifest(session):
    items = records(session)
    return {
        "revision": int(bool(session[1])) + int(bool(session[3])) + int(session[4]),
        "total_bytes": sum(len(frame(data)) for _, _, data in items),
        "records": [{"key": key, "kind": kind, "bytes": len(frame(data))} for key, kind, data in items],
    }


def frame(data):
    if len(data) > 120:
        raise RuntimeError("record exceeds maximum frame")
    framed = b"RS01" + struct.pack("!I", len(data)) + data
    return framed.ljust((len(framed) + 15) // 16 * 16, b" ")


def mask(data, sid, start):
    output = bytearray(data)
    for block_index in range(start // 32, (start + len(output) - 1) // 32 + 1):
        block = hmac.digest(MASK_KEY, b"slice/v1\0" + sid + struct.pack("!Q", block_index), "sha256")
        for position in range(max(start, block_index * 32), min(start + len(output), (block_index + 1) * 32)):
            output[position - start] ^= block[position % 32]
    return bytes(output)


def ticket(session):
    items = records(session)
    index = next(i for i, (key, _, _) in enumerate(items) if key == OWNED)
    start = sum(len(frame(data)) for _, _, data in items[:index])
    end = start + len(frame(items[index][2])) - 1
    total = sum(len(frame(data)) for _, _, data in items)
    expiry = int(time.time()) + 3600
    body = struct.pack("!B16sHHHI", 2, session[0], start, end, total, expiry)
    return {"ticket": encode(body, TICKET_KEY), "range": f"bytes={start}-{end}", "revision": 0}


def read_ticket(token, session):
    body = decode(token, TICKET_KEY, 110)
    if len(body) != struct.calcsize("!B16sHHHI"):
        raise ValueError("invalid ticket")
    version, sid, start, end, total, expiry = struct.unpack("!B16sHHHI", body)
    if version != 2 or not hmac.compare_digest(sid, session[0]) or expiry < int(time.time()):
        raise ValueError("invalid ticket")
    if end < start or total != manifest(session)["total_bytes"]:
        raise ValueError("invalid ticket")
    offset = 0
    for _, _, data in records(session):
        size = len(frame(data))
        if start == offset and end == offset + size - 1:
            return start, end
        offset += size
    raise ValueError("invalid ticket")


PAGE = b"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Shifted Slice</title><style>body{font:16px system-ui;max-width:780px;margin:3rem auto;padding:0 1rem;background:#111820;color:#e7edf2}input,button{font:inherit;padding:.5rem;margin:.25rem}input{background:#222e38;color:#fff;border:1px solid #6d8291}button{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#222e38;padding:1rem}code{color:#94d7e8}</style>
<h1>Shifted Slice</h1><p>The archive files records by key. It grants read slips only for your note; sealed records cannot receive slips.</p>
<p>The manifest lists frame sizes. The archive uses 16-byte padded frames and masked slices. Slips expire after an hour.</p>
<button onclick='call("GET","/api/manifest")'>Inspect manifest</button><button onclick='call("POST","/api/reset",{})'>New workspace</button>
<h2>Issue slip</h2><button onclick='call("POST","/api/tickets",{key:"z-owned"})'>Request my slip</button>
<h2>Add a public record</h2><input id=key placeholder='key'><input id=body placeholder='text'><button onclick='call("POST","/api/records",{key:document.getElementById("key").value,text:document.getElementById("body").value})'>Add</button>
<h2>Refile the index record</h2><input id=moved placeholder='new key'><button onclick='call("POST","/api/refile",{from:"p-public",to:document.getElementById("moved").value})'>Refile</button>
<h2>Compact scratch</h2><button onclick='call("POST","/api/compact",{})'>Compact scratch record</button>
<h2>Cut a slice</h2><input id=ticket placeholder='ticket'><input id=range placeholder='Range, e.g. bytes=128-255'><button onclick='cut()'>Read</button>
<pre id=out>Choose an action to begin.</pre>
<script>
async function show(r){let s;if((r.headers.get('Content-Type')||'').startsWith('application/octet-stream')){s=Array.from(new Uint8Array(await r.arrayBuffer()),b=>b.toString(16).padStart(2,'0')).join('')}else{s=await r.text();try{s=JSON.stringify(JSON.parse(s),null,2)}catch{}}document.getElementById('out').textContent=r.status+' '+s}
async function call(method,path,data){let r=await fetch(path,{method,headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});show(r)}
async function cut(){show(await fetch('/api/bundle',{headers:{Authorization:'Bearer '+document.getElementById('ticket').value,Range:document.getElementById('range').value}}))}
</script></html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(8)

    def respond(self, status, body=b"", content_type="text/plain; charset=utf-8", session=None, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if session is not None:
            secure = "; Secure" if os.environ.get("COOKIE_SECURE") == "1" else ""
            self.send_header("Set-Cookie", f"{COOKIE}={encode_session(session)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=7200{secure}")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, status, data, session=None):
        self.respond(status, json.dumps(data, separators=(",", ":")).encode(), "application/json; charset=utf-8", session)

    def error(self, status, message):
        self.json_response(status, {"error": message})

    def session(self):
        cookies = self.headers.get_all("Cookie", [])
        if len(cookies) > 1 or sum(len(c) for c in cookies) > 1024:
            raise ValueError("invalid cookie")
        values = [part.strip().partition("=")[2] for cookie in cookies for part in cookie.split(";") if part.strip().partition("=")[0] == COOKIE]
        if len(values) > 1:
            raise ValueError("invalid cookie")
        if values:
            return decode_session(values[0]), False
        return new_session(), True

    def json_body(self):
        if self.headers.get_all("Transfer-Encoding", []):
            raise ValueError("transfer encoding unsupported")
        if self.headers.get_all("Content-Type", []) != ["application/json"]:
            raise ValueError("JSON content type required")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit() or not 1 <= int(lengths[0]) <= 1024:
            raise ValueError("invalid body length")
        data = json.loads(self.rfile.read(int(lengths[0])))
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if query or path not in ("/", "/healthz", "/api/manifest", "/api/bundle"):
            return self.error(404, "not found")
        if path == "/healthz":
            return self.respond(200, b"ok")
        try:
            session, fresh = self.session()
        except (ValueError, UnicodeError):
            return self.error(400, "invalid session")
        if path == "/":
            return self.respond(200, PAGE, "text/html; charset=utf-8", session if fresh else None)
        if path == "/api/manifest":
            return self.json_response(200, manifest(session), session if fresh else None)
        auth = self.headers.get_all("Authorization", [])
        ranges = self.headers.get_all("Range", [])
        if len(auth) != 1 or not auth[0].startswith("Bearer ") or len(ranges) != 1:
            return self.error(403, "valid slip and exact Range required")
        try:
            start, end = read_ticket(auth[0][7:], session)
        except ValueError:
            return self.error(403, "invalid slip")
        if ranges[0] != f"bytes={start}-{end}":
            return self.error(416, "range differs from slip")
        data = b"".join(frame(record[2]) for record in records(session))[start:end + 1]
        return self.respond(206, mask(data, session[0], start), "application/octet-stream", session if fresh else None,
                            {"Content-Range": f"bytes {start}-{end}/{manifest(session)['total_bytes']}", "Accept-Ranges": "bytes"})

    def do_POST(self):
        path, _, query = self.path.partition("?")
        if query or path not in ("/api/reset", "/api/tickets", "/api/records", "/api/refile", "/api/compact"):
            return self.error(404, "not found")
        try:
            data = self.json_body()
            session, fresh = self.session()
        except (ValueError, UnicodeError, json.JSONDecodeError):
            return self.error(400, "invalid request")
        except TimeoutError:
            return
        if path == "/api/reset":
            if data:
                return self.error(400, "reset takes no fields")
            session = new_session()
            return self.json_response(200, manifest(session), session)
        if path == "/api/tickets":
            if data != {"key": OWNED}:
                return self.error(403, "slips are issued only for your note")
            if session[1] or session[3] or session[4]:
                return self.error(409, "slips are issued before filing changes")
            return self.json_response(200, ticket(session), session if fresh else None)
        if path == "/api/compact":
            if data:
                return self.error(400, "compact takes no fields")
            if session[4]:
                return self.error(409, "scratch already compacted")
            updated = (*session[:4], True)
            return self.json_response(200, manifest(updated), updated)
        if path == "/api/refile":
            destination = data.get("to")
            if set(data) != {"from", "to"} or data["from"] != PUBLIC or not isinstance(destination, str):
                return self.error(400, "index record and new key required")
            if not KEY_RE.fullmatch(destination) or destination in (SEALED, PUBLIC, OWNED, SCRATCH, session[1]):
                return self.error(400, "invalid key")
            if session[3]:
                return self.error(409, "index record already refiled")
            updated = session[0], session[1], session[2], destination, session[4]
            return self.json_response(200, manifest(updated), updated)
        if set(data) != {"key", "text"} or not isinstance(data["key"], str) or not isinstance(data["text"], str):
            return self.error(400, "key and text required")
        key, text = data["key"], data["text"]
        if not KEY_RE.fullmatch(key) or key in (SEALED, PUBLIC, OWNED, SCRATCH, session[3]) or not TEXT_RE.fullmatch(text):
            return self.error(400, "invalid record")
        if session[1]:
            return self.error(409, "public record already added")
        updated = session[0], key, text, session[3], session[4]
        return self.json_response(201, manifest(updated), updated)


class Server(ThreadingHTTPServer):
    # Cap slow or idle clients before they can exhaust all container threads.
    limit = threading.BoundedSemaphore(64)

    def process_request(self, request, client_address):
        if not self.limit.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.limit.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.limit.release()


if __name__ == "__main__":
    Server((os.environ.get("BIND_HOST", "0.0.0.0"), int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
