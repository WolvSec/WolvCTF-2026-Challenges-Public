# Motor City Hotwire — Writeup

**Flag:** `wctf{5M0OTH_0P3R4TORRRRR_6ef709d1ac21}`
**Category / difficulty:** rev / hard

> This writeup follows the path independent blind solvers actually took (no prior
> knowledge of the design). `solve.py` automates the end result.

## 1. Triage
`file` / `readelf -h`: despite the `.bin` name it's a **stripped ELF32 ARM, EABI5,
Thumb** (entry `0x8001`, odd ⇒ Thumb/Cortex-M). Sections: `.text` @0x8000,
`.rodata` @0x87cc, `.bss` @0x9920. Disassemble with `objdump -d -M force-thumb`
(or Ghidra/Cortex-M).

## 2. First footholds (.rodata)
- Strings `"67 02"`, `"7F 27 35"`, and a `"0123456789ABCDEF"` LUT → **UDS
  SecurityAccess (service 0x27)**: `67 01 <seed>` = requestSeed response,
  `67 02` = sendKey positive, `7F 27 35` = negative response NRC 0x35 (invalidKey).
- A 256-byte table of **SHA-256 round constants** (`98 2f 8a 42 …` = 0x428a2f98…),
  then a **38-byte blob** at `0x88f8` — the flag ciphertext.

So: a seed→key automotive immobilizer whose output is produced with SHA-256.

## 3. Map the code
- `0x8010` — round function `F(x,i) = X[i] ^ ( rol( sbox(T[i]*x), R[i] ) + A[i] )`,
  over four 16-entry word tables and a 256-byte S-box, all in `.bss`.
- `0x8070` — SHA-256 (recognizable σ0/σ1 + Σ0/Σ1 and the IV).
- `0x8234` — `main`: an **xorshift64\* PRNG + Fisher-Yates** fills the S-box and the
  per-round tables at init (the multiplier tables are forced **odd** via `orr #1`),
  then a request/response loop. The seed is a fixed constant: `67 01 1A 2B 3C 4D 5E
  6F 77 88` ⇒ **seed = 0x1A2B3C4D5E6F7788**.
- `0x8724/0x8728/0x8760` — read-line / puts / print-hex I/O stubs.

## 4. Drive it (emulation)
The read stub returns 0, so the raw binary "does nothing" if just run — you must
**supply input**. Emulate with Unicorn:
- Use the **Cortex-M4 CPU model** (`ctl_set_cpu_model`) or the firmware's `UDIV`
  throws `UC_ERR_INSN_INVALID` on a generic core.
- To stub the I/O funcs, **patch each entry to `bx lr` (`70 47`)** and fill the
  return registers in a hook — do *not* rewrite PC yourself, or you drop the Thumb
  bit and crash. (Both of these bit multiple blind solvers.)

`27 01` returns the seed. `27 02 <key>` always prints `67 02` + a 38-byte buffer
that *changes with the key* → there is **no comparison branch**; the output is
`ciphertext XOR keystream(key)`, decrypt-gated.

## 5. The crux
The keystream is `SHA256( MAC ‖ key ‖ counter )` in CTR mode, where
`MAC = (seed_lo XOR r7, seed_hi XOR r3)` and `(r7, r3)` is the output of a
**16-round invertible network** `mix()` applied to the 64-bit key. Known-plaintext
on `wctf{` is a dead end (SHA is one-way). The real observation: the intended key
is the one that makes **`MAC = 0`**, i.e. `mix(key) == seed`. So the "key routine"
is simply `key = mix⁻¹(seed)`.

`mix` is a bijection (every multiplier is odd → invertible mod 2³²; the S-box is a
permutation), so it inverts cleanly: reverse the rounds, undo each odd multiply with
its modular inverse.

## 6. Recover the key and flag
Dump the PRNG-generated tables from the emulator (or reimplement the init), rebuild
`F`/`mix`, invert from the seed:

`key = mix⁻¹(seed) = 0x1B869BC58E96B90B`   (send `27 02 1B869BC58E96B90B`)

Feed it back to the ECU (or decrypt the `.rodata` ciphertext offline with
`SHA256(0 ‖ key ‖ ctr)`):
```
67 02
wctf{5M0OTH_0P3R4TORRRRR_6ef709d1ac21}
```

## Traps blind solvers hit (and caught)
- **Round-function 2nd argument is the round index `i` (0..15)**, not the per-round
  control byte (which only selects the Feistel branch). Getting this wrong desyncs
  the schedule; caught by matching the Python model to an emulator register trace.
- **Endianness in the hash:** the key is serialized **little-endian** into the
  SHA input (`MAC ‖ reverse(key) ‖ LE32(ctr)`). First hand-derived layouts gave
  garbage until the real 20-byte hashed message was captured from the emulator.
- **Key packing:** `r3 = BE(key[0:4])`, `r7 = BE(key[4:8])`.
- The read-stub "does nothing" and the Thumb/CPU-model emulation pitfalls above.

## Automated solver
`solve.py firmware.bin` — reconstructs the init, inverts the network, recovers the
key, locates the ciphertext in the binary, and prints the flag. stdlib only:
```
recovered key : 0x1B869BC58E96B90B   (send: 27 02 1B869BC58E96B90B)
flag          : wctf{5M0OTH_0P3R4TORRRRR_6ef709d1ac21}
```
`rev_run.py firmware.bin "27 01" "27 02 1B869BC58E96B90B"` verifies against the real
firmware via emulation.
