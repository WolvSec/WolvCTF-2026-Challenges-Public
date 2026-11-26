import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.SecureRandom;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipInputStream;

public final class SplitDirectory {
    private static final int MAX_ZIP = 8192;
    private static final int MAX_MANIFEST = 128;
    private static final int MAX_UPLOADS = 4096;
    private static final long UPLOAD_TTL_NS = 10L * 60 * 1_000_000_000;
    private static final Pattern ID = Pattern.compile("[0-9a-f]{32}");
    private static final Pattern PUBLIC = Pattern.compile("EXPORT public/[a-z0-9-]{1,16}");
    private static final String ATTACHMENT = "archive.note";
    private static final String MANIFEST = "manifest.txt";
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final Map<String, Upload> UPLOADS = new LinkedHashMap<>();
    private static final String PAGE = """
        <!doctype html><html lang="en"><meta charset="utf-8"><title>Split Directory</title>
        <style>body{font:16px system-ui;max-width:760px;margin:3rem auto;background:#101820;color:#e5edf1}button,input{font:inherit;padding:.5rem;margin:.3rem}pre{white-space:pre-wrap;background:#26333c;padding:1rem}</style>
        <h1>Split Directory</h1><p>Submit an archive, get it approved, then stream its report.</p>
        <p>The public catalog has <code>public/welcome</code> and <code>public/rules</code>. Upload format and API are in the handout.</p>
        <input type="file" id="zip"><button onclick="upload()">Upload</button>
        <input id="id" placeholder="upload ID"><button onclick="approve()">Approve</button><button onclick="exportReport()">Export</button>
        <pre id="out">Ready.</pre>
        <script>
        const out=document.getElementById('out'), id=document.getElementById('id');
        async function upload(){const f=document.getElementById('zip').files[0];if(!f)return;
          const r=await fetch('/api/upload',{method:'POST',headers:{'Content-Type':'application/zip'},body:f});
          const t=await r.text();if(r.ok)id.value=t.trim();out.textContent=r.status+' '+t}
        async function approve(){const r=await fetch('/api/approve/'+id.value,{method:'POST'});out.textContent=r.status+' '+await r.text()}
        async function exportReport(){const r=await fetch('/api/export/'+id.value);out.textContent=r.status+' '+await r.text()}
        </script></html>
        """;

    private static final class Upload {
        final byte[] data;
        final long createdAt = System.nanoTime();
        volatile boolean approved;
        volatile long receipt;
        volatile int length;
        Upload(byte[] data) { this.data = data; }
    }

    private static void expireUploads(long now) {
        UPLOADS.values().removeIf(upload -> now - upload.createdAt >= UPLOAD_TTL_NS);
    }

    private static void respond(HttpExchange exchange, int status, String text) throws IOException {
        byte[] body = text.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "text/plain; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.getResponseHeaders().set("X-Content-Type-Options", "nosniff");
        exchange.sendResponseHeaders(status, body.length);
        try (var out = exchange.getResponseBody()) { out.write(body); }
    }

    private static String newId() {
        byte[] bytes = new byte[16];
        RANDOM.nextBytes(bytes);
        return java.util.HexFormat.of().formatHex(bytes);
    }

    private static byte[] readManifest(java.io.InputStream in) throws IOException {
        byte[] bytes = in.readNBytes(MAX_MANIFEST + 1);
        if (bytes.length > MAX_MANIFEST) throw new IOException("manifest too long");
        return bytes;
    }

    private static String directive(byte[] bytes) throws IOException {
        int end = 0;
        while (end < bytes.length && bytes[end] != '\n') ++end;
        if (end == bytes.length) throw new IOException("directive line missing");
        return new String(bytes, 0, end, StandardCharsets.UTF_8);
    }

    private static long receipt(byte[] bytes) {
        CRC32 crc = new CRC32();
        crc.update(bytes);
        return crc.getValue();
    }

    private static int u16(byte[] data, int at) {
        return (data[at] & 255) | ((data[at + 1] & 255) << 8);
    }

    private static long u32(byte[] data, int at) {
        return (u16(data, at) & 0xffffL) | ((long) u16(data, at + 2) << 16);
    }

    private static boolean localRecord(byte[] data, int at, int end, long crc,
                                       int length, int nameLength) {
        int size = 30 + nameLength + length;
        return at >= 0 && at <= data.length - size && end == at + size &&
               u32(data, at) == 0x04034b50L && u16(data, at + 6) == 0 &&
               u16(data, at + 8) == 0 && u32(data, at + 14) == crc &&
               u32(data, at + 18) == length && u32(data, at + 22) == length &&
               u16(data, at + 26) == nameLength && u16(data, at + 28) == 0;
    }

    private static boolean compactZip(byte[] data) {
        if (data.length < 22 + 2 * 46 + 2 * 30) return false;
        int eocd = data.length - 22;
        if (u32(data, eocd) != 0x06054b50L || u16(data, eocd + 4) != 0 ||
            u16(data, eocd + 6) != 0 || u16(data, eocd + 8) != 2 ||
            u16(data, eocd + 10) != 2 || u16(data, eocd + 20) != 0) return false;
        long centralSize = u32(data, eocd + 12);
        long centralOffset = u32(data, eocd + 16);
        if (centralOffset < 0 || centralSize < 0 || centralOffset + centralSize != eocd) return false;
        int cen = (int) centralOffset;
        String[] names = {ATTACHMENT, MANIFEST};
        int[] offsets = new int[2], lengths = new int[2];
        long[] crcs = new long[2];
        for (int i = 0; i < 2; ++i) {
            if (cen + 46 > eocd || u32(data, cen) != 0x02014b50L ||
                u16(data, cen + 8) != 0 || u16(data, cen + 10) != 0 ||
                u32(data, cen + 20) != u32(data, cen + 24) ||
                u32(data, cen + 20) > MAX_MANIFEST ||
                u16(data, cen + 28) != names[i].length() ||
                u16(data, cen + 30) != 0 || u16(data, cen + 32) != 0 ||
                u16(data, cen + 34) != 0) return false;
            int next = cen + 46 + names[i].length();
            if (next > eocd || !new String(data, cen + 46, names[i].length(),
                    StandardCharsets.US_ASCII).equals(names[i])) return false;
            if (u32(data, cen + 42) > Integer.MAX_VALUE) return false;
            offsets[i] = (int) u32(data, cen + 42);
            lengths[i] = (int) u32(data, cen + 20);
            crcs[i] = u32(data, cen + 16);
            cen = next;
        }
        if (cen != eocd || offsets[0] != 0 || offsets[1] <= 0) return false;
        return localRecord(data, offsets[0], offsets[1], crcs[0], lengths[0],
                           ATTACHMENT.length()) &&
               localRecord(data, offsets[1], (int) centralOffset, crcs[1], lengths[1],
                           MANIFEST.length());
    }

    private static byte[] approvedView(byte[] data) {
        Path temp = null;
        try {
            temp = Files.createTempFile("split-directory-", ".zip");
            Files.write(temp, data);
            try (ZipFile zip = new ZipFile(temp.toFile())) {
                if (zip.size() != 2) return null;
                ZipEntry entry = zip.getEntry(MANIFEST);
                if (entry == null || entry.isDirectory() ||
                        entry.getSize() < 0 || entry.getSize() > MAX_MANIFEST) return null;
                try (var input = zip.getInputStream(entry)) {
                    byte[] bytes = readManifest(input);
                    return PUBLIC.matcher(directive(bytes)).matches() ? bytes : null;
                }
            }
        } catch (IOException | RuntimeException error) {
            return null;
        } finally {
            if (temp != null) try { Files.deleteIfExists(temp); } catch (IOException ignored) {}
        }
    }

    private static byte[] streamedView(byte[] data) throws IOException {
        try (var zip = new ZipInputStream(new ByteArrayInputStream(data))) {
            for (int i = 0; i < 8; ++i) {
                ZipEntry entry = zip.getNextEntry();
                if (entry == null) break;
                if (entry.getName().equals(MANIFEST)) return readManifest(zip);
                byte[] discarded = zip.readNBytes(MAX_MANIFEST + 1);
                if (discarded.length > MAX_MANIFEST) throw new IOException("entry too large");
            }
        }
        throw new IOException("manifest missing");
    }

    private static String document(String request) throws IOException {
        if (request.equals("EXPORT public/welcome"))
            return "Welcome to the archive.\n";
        if (request.equals("EXPORT public/rules"))
            return "Approved archives can export public documents.\n";
        if (request.equals("EXPORT sealed/report"))
            return Files.readString(Path.of("/flag"), StandardCharsets.UTF_8);
        throw new IOException("unknown document");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        try (exchange) {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();
            if (method.equals("GET") && path.equals("/healthz")) { respond(exchange, 200, "ok\n"); return; }
            if (method.equals("GET") && path.equals("/")) {
                byte[] page = PAGE.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "text/html; charset=utf-8");
                exchange.getResponseHeaders().set("Cache-Control", "no-store");
                exchange.sendResponseHeaders(200, page.length);
                try (var out = exchange.getResponseBody()) { out.write(page); }
                return;
            }
            if (method.equals("POST") && path.equals("/api/upload")) {
                if (!"application/zip".equals(exchange.getRequestHeaders().getFirst("Content-Type"))) {
                    respond(exchange, 415, "ZIP required\n"); return;
                }
                String length = exchange.getRequestHeaders().getFirst("Content-Length");
                if (length == null || !length.matches("[0-9]{1,5}")) {
                    respond(exchange, 411, "length required\n"); return;
                }
                int size = Integer.parseInt(length);
                if (size == 0 || size > MAX_ZIP) { respond(exchange, 413, "archive too large\n"); return; }
                byte[] data = exchange.getRequestBody().readNBytes(size + 1);
                if (data.length != size) { respond(exchange, 400, "bad length\n"); return; }
                if (!compactZip(data)) { respond(exchange, 422, "compact ZIP required\n"); return; }
                String id = newId();
                boolean capacityReached;
                synchronized (UPLOADS) {
                    expireUploads(System.nanoTime());
                    capacityReached = UPLOADS.size() >= MAX_UPLOADS;
                    if (!capacityReached) UPLOADS.put(id, new Upload(data));
                }
                if (capacityReached) { respond(exchange, 503, "upload capacity reached\n"); return; }
                respond(exchange, 201, id + "\n");
                return;
            }
            String id = path.startsWith("/api/approve/") ? path.substring(13) :
                        path.startsWith("/api/export/") ? path.substring(12) : "";
            if (!ID.matcher(id).matches()) { respond(exchange, 404, "not found\n"); return; }
            Upload upload;
            synchronized (UPLOADS) {
                expireUploads(System.nanoTime());
                upload = UPLOADS.get(id);
            }
            if (upload == null) { respond(exchange, 404, "not found\n"); return; }
            if (method.equals("POST") && path.startsWith("/api/approve/")) {
                byte[] approved = approvedView(upload.data);
                if (approved == null) { respond(exchange, 422, "approval rejected\n"); return; }
                upload.length = approved.length;
                upload.receipt = receipt(approved);
                upload.approved = true;
                respond(exchange, 200, "approved\n");
                return;
            }
            if (method.equals("GET") && path.startsWith("/api/export/")) {
                if (!upload.approved) { respond(exchange, 403, "approval required\n"); return; }
                try {
                    byte[] streamed = streamedView(upload.data);
                    if (streamed.length != upload.length || receipt(streamed) != upload.receipt) {
                        respond(exchange, 422, "receipt mismatch\n"); return;
                    }
                    respond(exchange, 200, document(directive(streamed)));
                }
                catch (IOException | IllegalArgumentException error) {
                    respond(exchange, 422, "export rejected\n");
                }
                return;
            }
            respond(exchange, 405, "method not allowed\n");
        }
    }

    public static void main(String[] args) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 8081), 64);
        server.createContext("/", SplitDirectory::handle);
        server.setExecutor(java.util.concurrent.Executors.newFixedThreadPool(12));
        server.start();
    }
}
