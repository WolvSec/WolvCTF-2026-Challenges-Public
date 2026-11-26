#!/usr/bin/env python3
"""Recover ML-DSA-44 s1 from rejected z-bound telemetry."""

import argparse
import hashlib
import hmac
import json
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix

N = 256
GAMMA1 = 1 << 17
BETA = 78


def sample_in_ball(seed):
    # FIPS 204 Algorithm 29: SHAKE256 signs, then rejection-sampled swaps.
    stream = hashlib.shake_256(seed).digest(1024)
    signs = int.from_bytes(stream[:8], "little")
    pos = 8
    c = np.zeros(N, dtype=np.int8)
    for i in range(N - 39, N):
        while stream[pos] > i:
            pos += 1
        j = stream[pos]
        pos += 1
        c[i] = c[j]
        c[j] = 1 - 2 * (signs & 1)
        signs >>= 1
    return c


def load_rows(path):
    groups = [([], [], []) for _ in range(4)]
    indices = np.arange(N)
    with path.open() as handle:
        for line in handle:
            seed_hex, p_text, t_text, z_text = line.split()
            p, t, z = int(p_text), int(t_text), int(z_text)
            if not (0 <= p < 4 and 0 <= t < N and abs(z) >= GAMMA1 - BETA):
                raise ValueError("invalid telemetry row")
            c = sample_in_ball(bytes.fromhex(seed_hex))
            row = c[(t - indices) % N].copy()
            row[indices > t] *= -1
            rows, lower, upper = groups[p]
            rows.append(row)
            lower.append(max(-78, z - GAMMA1))
            upper.append(min(78, z + GAMMA1 - 1))
    return groups


def recover(groups):
    result = []
    for p, (rows, lower, upper) in enumerate(groups):
        a = csr_matrix(np.asarray(rows, dtype=np.float64))
        constraints = LinearConstraint(a, lower, upper)
        fit = milp(np.zeros(N), integrality=np.ones(N),
                   bounds=Bounds(np.full(N, -2), np.full(N, 2)),
                   constraints=constraints,
                   options={"time_limit": 1800})
        if fit.x is None or not fit.success:
            raise RuntimeError(f"polynomial {p}: {fit.message}")
        solution = np.rint(fit.x).astype(np.int8)
        if np.any(a @ solution < lower) or np.any(a @ solution > upper):
            raise RuntimeError(f"polynomial {p}: numerical constraint error")
        print(f"polynomial {p}: recovered from {len(rows)} rejects", flush=True)
        result.extend(solution.tolist())
    return bytes(x + 2 for x in result)


def decrypt(secret, envelope):
    master = hashlib.sha3_256(b"Rejected/flag-key/v1" + secret).digest()
    nonce = bytes.fromhex(envelope["nonce"])
    ciphertext = bytes.fromhex(envelope["ciphertext"])
    tag = bytes.fromhex(envelope["tag"])
    auth_key = hashlib.sha3_256(b"Rejected/auth/v1" + master).digest()
    expected = hmac.digest(auth_key, nonce + ciphertext, "sha256")
    if not hmac.compare_digest(tag, expected):
        raise RuntimeError("recovered key failed the ciphertext check")
    stream = hashlib.shake_256(b"Rejected/stream/v1" + master + nonce).digest(len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, stream))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path, help="directory containing rejected.log and flag.json")
    args = parser.parse_args()
    secret = recover(load_rows(args.directory / "rejected.log"))
    envelope = json.loads((args.directory / "flag.json").read_text())
    print(decrypt(secret, envelope).decode())


if __name__ == "__main__":
    main()
