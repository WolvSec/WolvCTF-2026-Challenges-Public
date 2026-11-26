#!/usr/bin/env python3
"""Emulate the capsule VM after recovering its four input bytes."""

from pathlib import Path
import sys


MASK = 0xFFFFFFFF
VALIDATOR_INSTRUCTION_SIZE = 7


def rol32(value: int, amount: int) -> int:
    amount &= 31
    value &= MASK
    if amount == 0:
        return value
    return ((value << amount) | (value >> (32 - amount))) & MASK


def rol8(value: int, amount: int) -> int:
    amount &= 7
    if amount == 0:
        return value & 0xFF
    return ((value << amount) | (value >> (8 - amount))) & 0xFF


def run_validator(code: bytes, count: int, slots: tuple[int, ...]) -> int:
    regs = [0] * 8
    pc = 0
    steps = 0
    checks = 0
    while pc < count and steps < count * 4 + 16:
        steps += 1
        off = pc * VALIDATOR_INSTRUCTION_SIZE
        op, a, b = code[off : off + 3]
        imm = int.from_bytes(code[off + 3 : off + 7], "little")
        next_pc = pc + 1
        if op == 0x10:
            regs[a] = imm
        elif op == 0x11:
            regs[a] = slots[b]
        elif op == 0x12:
            regs[a] = regs[b]
        elif op == 0x20:
            regs[a] = (regs[a] + regs[b]) & MASK
        elif op == 0x21:
            regs[a] ^= regs[b]
        elif op == 0x22:
            regs[a] = (regs[a] * regs[b]) & MASK
        elif op == 0x23:
            regs[a] = (regs[a] - regs[b]) & MASK
        elif op == 0x24:
            regs[a] = rol32(regs[a], imm)
        elif op == 0x25:
            regs[a] >>= imm & 31
        elif op == 0x26:
            regs[a] = (regs[a] + imm) & MASK
        elif op == 0x27:
            regs[a] ^= imm
        elif op == 0x28:
            regs[a] = (regs[a] * imm) & MASK
        elif op == 0x29:
            regs[a] &= imm
        elif op == 0x30 and regs[a] == 0:
            offset = imm if imm < 0x80000000 else imm - 0x100000000
            next_pc = pc + 1 + offset
        elif op == 0x31 and regs[a] != 0:
            offset = imm if imm < 0x80000000 else imm - 0x100000000
            next_pc = pc + 1 + offset
        elif op == 0x32:
            offset = imm if imm < 0x80000000 else imm - 0x100000000
            next_pc = pc + 1 + offset
        elif op == 0x40:
            if regs[a] != imm:
                raise SystemExit("input rejected by VM check")
            checks += 1
        elif op == 0xFE:
            if checks != 2:
                raise SystemExit("validator halted before both checks")
            return regs[0] ^ rol32(regs[4], 11)
        elif op not in (0x30, 0x31):
            raise SystemExit(f"unknown validation opcode {op:#x}")
        pc = next_pc
    raise SystemExit("validator did not halt cleanly")


def decode(raw: bytes, slots: tuple[int, ...]) -> bytes:
    if raw[:4] != b"TCAP" or raw[4] != 2 or raw[7] != 0xC3:
        raise SystemExit("bad capsule header")
    instruction_count, decode_count = raw[5], raw[6]
    payload_length = int.from_bytes(raw[8:10], "little")
    code_start = 10
    decode_start = code_start + instruction_count * VALIDATOR_INSTRUCTION_SIZE
    payload_start = decode_start + decode_count * 2
    if len(raw) != payload_start + payload_length:
        raise SystemExit("bad capsule length")

    code = raw[code_start:decode_start]
    state = run_validator(code, instruction_count, slots)
    program = [tuple(raw[decode_start + 2 * i : decode_start + 2 * i + 2])
               for i in range(decode_count)]

    output = bytearray()
    for index, cipher in enumerate(raw[payload_start:]):
        index_mix = slots[index & 3] ^ ((index * 0x9E3779B9) & MASK)
        state = rol32((state + index_mix) & MASK, index % 11 + 5)
        byte_state = state
        value = cipher
        for opcode, operand in program:
            state_byte = (byte_state >> (8 * (operand & 3))) & 0xFF
            if opcode == 0x41:
                value ^= slots[operand]
            elif opcode == 0x52:
                value = (value + operand) & 0xFF
            elif opcode == 0x63:
                value = rol8(value, operand)
            elif opcode == 0x74:
                value ^= state_byte
            elif opcode == 0x85:
                value = (value - operand) & 0xFF
            elif opcode == 0x96:
                value = (value + state_byte) & 0xFF
            elif opcode == 0xA7:
                value ^= (index * operand) & 0xFF
            else:
                raise SystemExit(f"unknown data opcode {opcode:#x}")
        output.append(value)
        state = rol32(state ^ ((value + index * 0x45D9F3B) & MASK), 7)
        state = (state + cipher + 0xA341316C) & MASK
    return bytes(output)


def main() -> None:
    if len(sys.argv) not in (2, 6):
        raise SystemExit(f"usage: {sys.argv[0]} backup.tc [slot1 slot2 slot3 slot4]")
    slots = tuple(map(int, sys.argv[2:])) if len(sys.argv) == 6 else (53, 167, 18, 233)
    if len(slots) != 4 or any(value < 0 or value > 255 for value in slots):
        raise SystemExit("each slot must be a decimal byte (0..255)")
    print(decode(Path(sys.argv[1]).read_bytes(), slots).decode())


if __name__ == "__main__":
    main()
