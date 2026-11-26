# Split Directory

Upload a compact ZIP_STORED archive with exactly two entries, in order: `archive.note` and `manifest.txt`. Use no ZIP or file comments, extra fields, data descriptors, prepended bytes, or trailing bytes. The archive must have one central directory covering both local records. The ZIP may be at most 8192 bytes, and each entry may be at most 128 bytes.

The manifest's first line is `EXPORT public/<name>`, where `<name>` is 1–16 lowercase letters, digits, or hyphens. Bytes after the newline are an opaque receipt note. The public catalog contains `public/welcome` and `public/rules`; the protected document is `sealed/report`.

The workflow is `POST /api/upload` with `Content-Type: application/zip` and the raw ZIP body, then `POST /api/approve/<id>`, then `GET /api/export/<id>`. The upload response is the ID. A browser interface is available at `/`.
Upload IDs expire after ten minutes and are lost when the service restarts; reupload the same archive to get a new ID. If an upload is rate-limited (HTTP 429), wait briefly before retrying.

Approval and export operate on the same uploaded bytes. Approval binds the manifest's uncompressed length and CRC32 as a receipt; export checks that receipt before serving a document.
