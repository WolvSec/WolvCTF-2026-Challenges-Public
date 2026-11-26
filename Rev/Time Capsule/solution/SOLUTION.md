# The Broken Time Capsule

The executable takes four decimal bytes. The misleading backup error is reached when the VM rejects those bytes, so first trace argument parsing into the VM rather than treating the message as a file-integrity diagnosis.

## Backup structure

The file begins with a ten-byte header:

```text
TCAP | version | validator instruction count | decoder op count | marker | payload length (little-endian)
```

The validator program follows. Each instruction is seven bytes: `opcode`, register `a`, register `b`, and a 32-bit little-endian immediate. After it are two-byte decoder operations, then the payload.

The validator has eight 32-bit registers. Useful instructions include:

| Opcode | Meaning |
| --- | --- |
| `10` | Set register `a` to the immediate |
| `11` | Load input slot `b` into register `a` |
| `12` | Copy register `b` into register `a` |
| `20` / `21` / `22` / `23` | Add / XOR / multiply / subtract registers |
| `24` / `25` | Rotate left / shift right by the immediate |
| `26` / `27` / `28` / `29` | Add / XOR / multiply / AND immediate |
| `30` / `31` / `32` | Jump if zero / jump if nonzero / unconditional relative jump |
| `40` | Require register `a` to equal the immediate |
| `FE` | Halt and return the decoder seed |

Relative jumps are measured in instructions from the instruction after the jump. Arithmetic wraps at 32 bits. The program maintains two rolling states, in `r0` and `r4`, and mixes each input slot into both. Parity branches select different mixing constants. The two `CHECK` instructions compare both states with their targets to pin the input. After the checks pass, the program folds the input slots back into `r0` and `r4` once more, and only then does the halt form the decoder seed from those final states. The `CHECK` targets are therefore *not* the seed: recovering it requires the actual input, so you must solve the checks first rather than reading the seed out of the file.

## Recover the input

Each candidate slot is one byte, giving a 2^32 search space. The rolling transformations are reversible when a candidate slot is known: add, XOR, rotate, multiplication by an odd constant, and `x ^= x >> n` all have inverses over 32 bits. This makes a meet-in-the-middle search practical:

1. Emulate the validator forward for every pair `(slot-1, slot-2)` and store the two intermediate states.
2. Starting from the two target states, run the validator stages backward for every pair `(slot-3, slot-4)`, following the parity branch for each candidate.
3. Match the two-state pairs, then confirm each candidate by running the full validator.

The accepted sequence is:

```text
53 167 18 233
```

## Decode the payload

The second program is a per-byte instruction stream. Its operations XOR a slot, add or subtract an immediate, rotate a byte, combine it with one byte of the rolling state, or XOR an index-derived value. After each payload byte, the VM updates its 32-bit state using both the plaintext and the original byte. Keep that feedback update in the same order when emulating.

Run the challenge with the recovered sequence:

```sh
./time_capsule 53 167 18 233 backup.tc
```

The organizer-side emulator is in `solution/solve.py`; it runs both VM stages once the slots are known.
