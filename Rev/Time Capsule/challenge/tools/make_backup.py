#!/usr/bin/env python3
"""Build the player backup. This file is an organizer-side build tool."""

from pathlib import Path
import sys


MASK = 0xFFFFFFFF
SLOTS = (53, 167, 18, 233)

# Two independent 32-bit rolling paths make the four-byte input a 64-bit check.
CONFIGS = (
    {
        "acc": 0,
        "key": 1,
        "tmp": 2,
        "seed": 0x6A09E667,
        "salts": (0x243F6A88, 0x85A308D3, 0x13198A2E, 0x03707344),
        "xors": (0xA4093822, 0x299F31D0, 0x082EFA98, 0xEC4E6C89),
        "rotates": (7, 13, 21, 11),
        "multipliers": (0x85EBCA6B, 0xC2B2AE35, 0x27D4EB2F, 0x165667B1),
        "shifts": (11, 15, 9, 13),
        "odd": (0x9E3779B9, 0x7F4A7C15, 0xD1B54A35, 0x94D049BB),
        "even": (0xA5A5A5A5, 0x3C6EF372, 0xBB67AE85, 0x6A09E667),
    },
    {
        "acc": 4,
        "key": 5,
        "tmp": 6,
        "seed": 0xBB67AE85,
        "salts": (0x452821E6, 0x38D01377, 0xBE5466CF, 0x34E90C6C),
        "xors": (0xC0AC29B7, 0xC97C50DD, 0x3F84D5B5, 0xB5470917),
        "rotates": (5, 17, 9, 23),
        "multipliers": (0x9E3779B1, 0x7F4A7C15, 0x94D049BB, 0x369DEA0F),
        "shifts": (13, 7, 17, 11),
        "odd": (0x243F6A88, 0x85A308D3, 0x13198A2E, 0x03707344),
        "even": (0xC2B2AE35, 0x27D4EB2F, 0x165667B1, 0xA4093822),
    },
)

# Bytecode: (XOR slot, ADD immediate, ROL, XOR state byte, SUB immediate,
# ADD state byte, XOR slot, XOR state byte, XOR index product, ROL).
DECODE_PROGRAM = (
    (0x41, 0),
    (0x52, 0x31),
    (0x63, 5),
    (0x74, 2),
    (0x85, 0x17),
    (0x96, 1),
    (0x41, 3),
    (0x74, 0),
    (0xA7, 0x3D),
    (0x63, 1),
)


# Post-check seed mix: after both CHECKs pin the key, fold every key slot back
# into the two accumulators so the decoder seed is taken from key-derived state
# that never appears in the file. This stops the seed from being read off the
# CHECK immediates, and because the result mixes all four slots it also stops the
# key from being recovered one slot at a time from a known plaintext prefix.
SEED_MIX = (
    {
        "acc": 0,
        "key": 1,
        "salts": (0x9E3779B9, 0x7F4A7C15, 0xD1B54A35, 0x94D049BB),
        "rotates": (6, 19, 11, 27),
        "xors": (0xDEADBEEF, 0xFEEDFACE, 0x0BADF00D, 0xCAFEBABE),
    },
    {
        "acc": 4,
        "key": 5,
        "salts": (0xA5A5F00F, 0x3C6EF372, 0xBB67AE85, 0x6A09E667),
        "rotates": (9, 14, 22, 5),
        "xors": (0x1337C0DE, 0x8BADF00D, 0xABAD1DEA, 0xB16B00B5),
    },
)


def instruction(opcode: int, a: int = 0, b: int = 0, immediate: int = 0) -> bytes:
    return bytes((opcode, a, b)) + (immediate & MASK).to_bytes(4, "little")


def rotate_left(value: int, amount: int) -> int:
    amount &= 31
    if amount == 0:
        return value & MASK
    value &= MASK
    return ((value << amount) | (value >> (32 - amount))) & MASK


def make_validator_prefix() -> list[bytes]:
    code = []
    for cfg in CONFIGS:
        acc, key, tmp = cfg["acc"], cfg["key"], cfg["tmp"]
        code.append(instruction(0x10, acc, immediate=cfg["seed"]))
        for index in range(4):
            code.extend(
                (
                    instruction(0x11, key, index),
                    instruction(0x26, key, immediate=cfg["salts"][index]),
                    instruction(0x20, acc, key),
                    instruction(0x27, acc, immediate=cfg["xors"][index]),
                    instruction(0x24, acc, immediate=cfg["rotates"][index]),
                    instruction(0x28, acc, immediate=cfg["multipliers"][index]),
                    instruction(0x12, tmp, acc),
                    instruction(0x25, tmp, immediate=cfg["shifts"][index]),
                    instruction(0x21, acc, tmp),
                    instruction(0x12, tmp, key),
                    instruction(0x29, tmp, immediate=1),
                    instruction(0x30, tmp, immediate=2),
                    instruction(0x27, acc, immediate=cfg["odd"][index]),
                    instruction(0x32, immediate=1),
                    instruction(0x26, acc, immediate=cfg["even"][index]),
                )
            )
    return code


def run_prefix(code: list[bytes], slots: tuple[int, ...]) -> list[int]:
    regs = [0] * 8
    pc = 0
    steps = 0
    while pc < len(code):
        steps += 1
        if steps > len(code) * 4 + 16:
            raise ValueError("validation program exceeded its instruction budget")
        raw = code[pc]
        op, a, b = raw[:3]
        imm = int.from_bytes(raw[3:7], "little")
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
        elif op == 0x24:
            regs[a] = rotate_left(regs[a], imm)
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
        elif op == 0x30:
            if regs[a] == 0:
                next_pc = pc + 1 + imm
        elif op == 0x32:
            next_pc = pc + 1 + imm
        else:
            raise ValueError(f"unexpected opcode in generated prefix: {op:#x}")
        pc = next_pc
    return regs


def make_seed_mix() -> list[bytes]:
    code = []
    for cfg in SEED_MIX:
        acc, key = cfg["acc"], cfg["key"]
        for index in range(4):
            code.extend(
                (
                    instruction(0x11, key, index),
                    instruction(0x26, key, immediate=cfg["salts"][index]),
                    instruction(0x20, acc, key),
                    instruction(0x24, acc, immediate=cfg["rotates"][index]),
                    instruction(0x27, acc, immediate=cfg["xors"][index]),
                )
            )
    return code


def rotate_byte_left(value: int, amount: int) -> int:
    amount &= 7
    if amount == 0:
        return value & 0xFF
    return ((value << amount) | (value >> (8 - amount))) & 0xFF


def rotate_byte_right(value: int, amount: int) -> int:
    amount &= 7
    if amount == 0:
        return value & 0xFF
    return ((value >> amount) | (value << (8 - amount))) & 0xFF


def encode_payload(plain: bytes, seed: int) -> bytes:
    state = seed & MASK
    encrypted = bytearray()
    for index, original in enumerate(plain):
        index_mix = SLOTS[index & 3] ^ ((index * 0x9E3779B9) & MASK)
        state = rotate_left((state + index_mix) & MASK, index % 11 + 5)
        byte_state = state
        value = original
        for opcode, operand in reversed(DECODE_PROGRAM):
            state_byte = (byte_state >> (8 * (operand & 3))) & 0xFF
            if opcode == 0x41:
                value ^= SLOTS[operand]
            elif opcode == 0x52:
                value -= operand
            elif opcode == 0x63:
                value = rotate_byte_right(value, operand)
            elif opcode == 0x74:
                value ^= state_byte
            elif opcode == 0x85:
                value += operand
            elif opcode == 0x96:
                value -= state_byte
            elif opcode == 0xA7:
                value ^= (index * operand) & 0xFF
            value &= 0xFF
        cipher = value
        encrypted.append(cipher)
        state = rotate_left(state ^ ((original + index * 0x45D9F3B) & MASK), 7)
        state = (state + cipher + 0xA341316C) & MASK
    return bytes(encrypted)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} flag.txt output.tc")
    flag = Path(sys.argv[1]).read_bytes().strip()
    if len(flag) > 0xFFFF:
        raise SystemExit("flag is too long for the backup format")

    prefix = make_validator_prefix()
    regs_pre = run_prefix(prefix, SLOTS)
    postmix = make_seed_mix()
    regs_final = run_prefix(prefix + postmix, SLOTS)

    code = list(prefix)
    code.extend((
        instruction(0x40, 0, immediate=regs_pre[0]),
        instruction(0x40, 4, immediate=regs_pre[4]),
    ))
    code.extend(postmix)
    code.append(instruction(0xFE))
    if len(code) > 255:
        raise SystemExit("validation bytecode exceeds the format limit")

    # Seed is taken from the post-CHECK accumulators (key-derived, not any file
    # constant); the CHECK immediates remain the pre-mix chain outputs.
    seed = regs_final[0] ^ rotate_left(regs_final[4], 11)
    code_bytes = b"".join(code)
    decode_bytes = bytes(byte for pair in DECODE_PROGRAM for byte in pair)
    header = (
        b"TCAP"
        + bytes((2, len(code), len(DECODE_PROGRAM), 0xC3))
        + len(flag).to_bytes(2, "little")
    )
    payload = encode_payload(flag, seed)
    Path(sys.argv[2]).write_bytes(header + code_bytes + decode_bytes + payload)


if __name__ == "__main__":
    main()
