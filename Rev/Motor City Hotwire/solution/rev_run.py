#!/usr/bin/env python3
"""
rev_run.py - emulate the ECU firmware and talk UDS to it.
Loads firmware.bin, feeds the UDS request lines you pass, prints what the ECU emits.

    python3 rev_run.py firmware.bin "27 01" "27 02 1B869BC58E96B90B"

  27 01            -> ECU returns the seed (67 01 <8 bytes>)
  27 02 <8 bytes>  -> ECU decrypts with your key; the correct key prints the flag,
                      a wrong key prints garbage (it is decrypt-gated, no oracle).

Needs: pip install unicorn pyelftools   (both are pure wheels - no compiler/Xcode)
"""
import sys
from unicorn import *
from unicorn.arm_const import (UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
                               UC_ARM_REG_R0, UC_ARM_REG_R1, UC_CPU_ARM_CORTEX_M4)
from elftools.elf.elffile import ELFFile

# Function entry points in this firmware build (stable).
UDS_READ = 0x8724       # int  uds_read_line(char *buf, int max)
UDS_WRITE = 0x8728      # void uds_write(const char *s)
UDS_WRITE_HEX = 0x8760  # void uds_write_hex(const uint8_t *b, int n)
ENTRY = 0x8000          # main()
STACK, STACK_SZ, STOP = 0x70000000, 0x10000, 0x5a5a5000
BXLR = b"\x70\x47"      # thumb 'bx lr' - we stub the I/O funcs with this

def run(path, lines):
    inq = list(lines) + [None]          # None => uds_read_line returns 0 (EOF)
    out = bytearray()
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)   # v7-M: needed for the firmware's UDIV etc.
    mu.mem_map(0x8000, 0x8000)
    with open(path, "rb") as f:
        for seg in ELFFile(f).iter_segments():
            if seg["p_type"] == "PT_LOAD":
                mu.mem_write(seg["p_vaddr"], seg.data())
    for a in (UDS_READ, UDS_WRITE, UDS_WRITE_HEX):
        mu.mem_write(a, BXLR)           # replace each I/O function body with 'bx lr'
    mu.mem_map(STACK, STACK_SZ)
    mu.reg_write(UC_ARM_REG_SP, STACK + STACK_SZ - 0x100)
    mu.reg_write(UC_ARM_REG_LR, STOP)   # main returns here -> emu stops cleanly

    def hook(mu, addr, size, _):
        pc = addr & ~1
        if pc == UDS_READ:              # fill the caller's buffer, set return length
            buf = mu.reg_read(UC_ARM_REG_R0); mx = mu.reg_read(UC_ARM_REG_R1)
            line = inq.pop(0) if inq else None
            if line is None:
                mu.reg_write(UC_ARM_REG_R0, 0)
            else:
                b = line.encode()[:mx - 1]
                mu.mem_write(buf, b + b"\x00"); mu.reg_write(UC_ARM_REG_R0, len(b))
        elif pc == UDS_WRITE:           # capture a C string
            p = mu.reg_read(UC_ARM_REG_R0); s = bytearray()
            while True:
                c = mu.mem_read(p, 1)
                if c == b"\x00": break
                s += c; p += 1
            out.extend(s)
        elif pc == UDS_WRITE_HEX:       # capture n bytes as hex
            p = mu.reg_read(UC_ARM_REG_R0); n = mu.reg_read(UC_ARM_REG_R1)
            out.extend(("".join("%02X " % x for x in mu.mem_read(p, n))).encode())

    mu.hook_add(UC_HOOK_CODE, hook)
    try:
        mu.emu_start(ENTRY | 1, STOP, count=50_000_000)
    except UcError:
        if mu.reg_read(UC_ARM_REG_PC) & ~1 != STOP:   # anything other than the clean stop
            raise
    return out.decode("latin-1")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('usage: python3 rev_run.py firmware.bin "27 01" "27 02 <16 hex>"', file=sys.stderr)
        sys.exit(2)
    sys.stdout.write(run(sys.argv[1], sys.argv[2:]))
