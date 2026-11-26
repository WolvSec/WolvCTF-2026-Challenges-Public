"""Build the FAT12 camera card distributed to players."""

import struct
import sys
from pathlib import Path


SECTOR = 512
CLUSTER = 4 * SECTOR
image = bytearray(2880 * SECTOR)
scan = Path(sys.argv[1]).read_bytes()
if not scan.startswith(b"\x89PNG\r\n\x1a\n") or len(scan) > CLUSTER:
    raise SystemExit("scan.png must be a PNG that fits in one cluster")

# Standard 1.44 MB FAT12 layout: boot, two FATs, root directory, then data.
image[:3] = b"\xeb\x3c\x90"
image[3:11] = b"MSDOS5.0"
struct.pack_into("<H", image, 11, SECTOR)
image[13] = 4  # sectors per cluster
struct.pack_into("<H", image, 14, 1)  # reserved sectors
image[16] = 2  # FAT copies
struct.pack_into("<H", image, 17, 224)  # root entries
struct.pack_into("<H", image, 19, 2880)  # total sectors
image[21] = 0xF0
struct.pack_into("<H", image, 22, 9)  # sectors per FAT
struct.pack_into("<H", image, 24, 18)  # sectors per track
struct.pack_into("<H", image, 26, 2)  # heads
image[38] = 0x29
struct.pack_into("<I", image, 39, 0x20260003)
image[43:54] = b"CARD03     "
image[54:62] = b"FAT12   "
image[510:512] = b"\x55\xaa"

for first_sector in (1, 10):
    image[first_sector * SECTOR:first_sector * SECTOR + 3] = b"\xf0\xff\xff"

# Deletion changes the first filename byte to E5 and frees its cluster.
root = 19 * SECTOR
image[root:root + 11] = b"\xe5CAN0003PNG"
image[root + 11] = 0x20  # regular file
struct.pack_into("<H", image, root + 26, 2)  # first data cluster
struct.pack_into("<I", image, root + 28, len(scan))
data = 33 * SECTOR
image[data:data + len(scan)] = scan

Path(sys.argv[2]).write_bytes(image)
