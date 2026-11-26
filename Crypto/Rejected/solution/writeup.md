# Intended solve

Inspired by Zhou, Wang, Sun, and Yu, ["Rejected Signatures' Challenges Pose New Challenges"](https://eprint.iacr.org/2025/214). This handout gives exact signed `z` values, so its constraint strength and solve time are measured on the included instance rather than inferred from the paper's side-channel experiment.

The leak is the discarded `z`, not an accepted signature. For each row, reconstruct `c = SampleInBall(ctilde)` exactly as in FIPS 204. The signer computes `z = y + c*s1` in `Z[x]/(x^256+1)`, with every coefficient of `y` in `[-gamma1+1, gamma1]`, where `gamma1=131072`. Each coefficient of `c*s1` lies in `[-78,78]` because `c` has 39 nonzero signs and `s1` coefficients lie in `[-2,2]`.

For a recorded coefficient `z`, its corresponding `u=(c*s1)[t]` is therefore constrained by

`max(-78, z-131072) <= u <= min(78, z+131071)`.

Expand the negacyclic product into a linear row over the 256 unknown coefficients of the indicated `s1` polynomial. Each of the four polynomials is an independent bounded integer feasibility problem. With the supplied rows, an integer linear programming solver recovers them. Serialize the four recovered polynomials as byte values `s1+2` and use the public envelope routine to authenticate and decrypt the flag. `solve.py` implements this path with SciPy/HiGHS; install `numpy` and `scipy` first.

The telemetry prints one offending coefficient from the first failed polynomial and never prints the mask `y`, private seed, or secret key. The public key is included as the standard ML-DSA artifact; the attack does not need to reconstruct the full private key.

`./build.sh` packages the committed, playtested instance. `./build.sh --regenerate` needs NumPy and SciPy, generates a fresh random instance, and checks that the reference solver recovers `flag.txt` before replacing public data.
