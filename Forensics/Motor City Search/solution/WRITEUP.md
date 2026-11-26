# Motor City Search — author solution

**Category / difficulty:** Forensics / Hard. The player receives only `capture.log`.

## Recover the download

Each line is a SocketCAN `candump` frame. Sort by its timestamp: the recovered logger
fragments are not in wire order. The periodic CAN IDs are background traffic; `7E0`
and `7E8` carry a UDS diagnostic conversation. Reassemble ISO-TP on **both** IDs.
Single frames use PCI `0L`; first frames use `1H LL` for the 12-bit message length;
consecutive frames use `2S` with a sequence nibble that wraps `F → 0`. Ignore flow
control frames after accounting for the direction change.

The tester enters programming session (`10 02`), reads a vendor DID whose value is
`COMP=ZLIB;EXIT=CRC32`, and requests a download with `34 10 44 ...`. The `10` data
format identifies compression without encryption. The four-byte memory size is the
*uncompressed* firmware length. ECU response `74 20 00 12` allows at most 18 bytes
per `TransferData` message, including the `36` service byte and counter.

The first transfer stops after 30 blocks with `7F 36 71` (transfer suspended). A new
`34` starts the real download and restarts the counter at `01`; discard the aborted
attempt. Extract the 16 data bytes after `36 <counter>` from each reassembled request.
Check the counter in timestamp order, including `FF → 00`; one byte-identical block
is retransmitted and must be included only once. The real attempt has 496 unique
blocks in the committed capture.

## Validate and inspect the image

Concatenate the unique block data and decompress it with zlib. The image length must
equal the `34` memory size, and its CRC-32 must equal the four-byte record in the
`37` transfer-exit request. These are independent checkpoints before looking for the
token. A partial reconstruction of the first 256 blocks decompresses to a readable
bootloader banner telling the player to keep reconstructing, but it stops before the
embedded resource. Keeping the aborted attempt or losing the wrap corrupts the stream.

The full image contains a `PK\x03\x04` ZIP local header after its midpoint. Carve
through the `PK\x05\x06` end-of-central-directory record, open the ZIP, and extract
its sole DEFLATED file, `immo_key.bin`. That file contains the flag. The flag is absent
from the raw log, the compressed download stream, and the decompressed image's
ordinary strings; it appears after inflating the ZIP entry.

Run `python3 solution/solve.py challenge/capture.log` to reproduce every stage with
only Python's standard library. `solution/gen_forensics.py` builds and checks the
deterministic instance; `build.sh` packages only `capture.log` in `dis.tar.gz`.

In a real UDS reflash, a tester selects a programming session, negotiates a download,
streams numbered blocks, and exits the transfer. The capture records that process,
including a failed first try and a retransmission.
