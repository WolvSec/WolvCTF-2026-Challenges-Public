# Desync Delivery — organizer solution

## Intended path

1. Browse the tracking app, then inspect `/robots.txt` and `/handoff.txt`.
   These reveal the hidden admin route, the batch intake endpoint, and the
   difference between the intake desk's length-based parser and the depot's
   chunk-based parser.
2. Request `/internal/admin/flag` normally. The edge adds
   `X-Proxy-Verified: 1`, so the depot returns `403`.
3. Submit a `POST /intake` whose body is a complete inner HTTP request stream.
   The stream contains an outer `POST /` with both `Content-Length` and
   `Transfer-Encoding: chunked`. Set the inner `Content-Length` to the byte
   length of `0\r\n\r\n` followed immediately by a complete
   `GET /internal/admin/flag` request.
4. The gateway forwards the intake body byte-for-byte to the edge. The edge
   consumes and forwards the outer body by `Content-Length`, adding its marker
   only to the outer request headers. The depot consumes the zero-sized chunk
   using `Transfer-Encoding`, then parses the remaining bytes as a second
   request on the same connection. That inner request has no marker and returns
   the flag as the second response in the intake response body.

The parser disagreement, authorization check, hidden admin path, and flag
retrieval objective are unchanged. The gateway only carries the crafted byte
stream inside the ordinary HTTP request Cloud Run accepts.

## Run the solve script

Start the local service with the instructions in `challenge/README.md`, then
run:

```sh
python3 solution/solve.py http://localhost:8080
```

The same script accepts the KCTF HTTPS URL after deployment. The canonical answer for this
checkout is in `flag.txt`. The expected format is `wctf{` followed by 32
lowercase hexadecimal characters and `}`. Docker Compose mounts the flag
read-only; the KCTF image copies the canonical flag at build time. The old
Cloud Run setup uses a separate Secret Manager value and must match `flag.txt`
if it is reused.

## Implementation note

The ingress gateway accepts normal HTTP and has a fixed TCP target:
the challenge edge. Only `POST /intake` forwards an opaque request body. The
edge still applies the intentional Content-Length parser, and the backend
still prefers chunked framing. The relay has a 16 KiB request limit, an 8
second upstream timeout, and no caller-controlled destination.
