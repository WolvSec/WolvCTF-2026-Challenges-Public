# Intended solve

Approval enumerates `ZipFile` central-directory entries and reads the public `manifest.txt`. Export uses `ZipInputStream`, which starts at local file headers and executes the first local `manifest.txt` it sees. The two parsers may disagree about an entry's name. The approval receipt binds only the manifest's length and CRC32, which can collide.

Make a two-entry ZIP_STORED archive whose central names are `archive.note` and `manifest.txt`. The first entry contains a sealed directive; the second contains a public directive. Patch the first *local* filename to `manifest.txt` while keeping its central filename `archive.note` (both are 12 bytes). `ZipFile` sees the safe central manifest; `ZipInputStream` sees the sealed local manifest first. Give the two manifests equal lengths and use the four opaque note bytes to make their CRC32 values collide, so the receipt check accepts the substituted directive. `solve.py` constructs this archive with Python's standard library and uses only public endpoints.

The service validates complete local-record coverage and never extracts archive paths to the filesystem. The exploit is a parser identity mismatch combined with a weak receipt, not path traversal or a timing race. [Oracle documents that `ZipInputStream` reads local headers without the central directory](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/zip/ZipInputStream.html).

## Deployment notes

Upload IDs live in one Java process for at most ten minutes. A pod restart invalidates them, so an in-progress player must reupload. The current manifest requests no autoscaler; local kind ran one replica. A rolling update or any future multi-pod setup can briefly send related requests to different processes. Plan rollout/draining around that state boundary if uninterrupted uploads are required.

Nginx limits /api/upload by $binary_remote_addr at four requests per second with burst 32 and returns 429 when the bucket is exhausted (challenge/nginx.conf:10-11,27-28). [Nginx documents that this key is the client address seen by Nginx](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html). Local kind port-forward showed loopback. If the public HTTPS ingress presents one shared proxy address, multiple players share the bucket; the event routing is unverified. Check the actual peer address at the public ingress before release, and do not trust a forwarded-IP header without a configured trusted proxy.
