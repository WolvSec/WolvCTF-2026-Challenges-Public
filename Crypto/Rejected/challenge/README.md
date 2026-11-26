# Rejected

This is a static ML-DSA-44 (FIPS 204) challenge. `public.key` is a 1312-byte public key. `rejected.log` contains one row per signing candidate whose `z` norm check failed. The signer used the same secret key throughout, fresh randomness for each signing call, and the pure ML-DSA empty context. Accepted signatures and other rejection reasons are not recorded.

Each row is `ctilde_hex polynomial coefficient z_value`. The coefficient is the one with greatest absolute value in the first `z` polynomial that failed. `ctilde` is the 32-byte seed for FIPS 204 `SampleInBall`, the polynomial and coefficient indices are zero-based, and `z_value` is a centered integer. The upstream signer code is in `vendor/mldsa`; the intentionally unsafe telemetry addition is in `vendor/mldsa/src/sign.c`. `record.c` shows how the log was produced.

`flag.json` uses the envelope in `seal.py`. The password is the 1024-byte sequence of `s1` coefficients in polynomial-major order, encoded as one byte per coefficient by adding 2. No signer seed or private key is part of this handout.

The implementation is [mldsa-native v2.0.0](https://github.com/pq-code-package/mldsa-native/tree/v2.0.0), with the sole telemetry change described above. Its Apache-2.0 OR ISC OR MIT license is in `vendor/LICENSE`. The signing arithmetic and key format are ML-DSA-44; exposing rejected intermediate values is deliberately unsafe and is not part of FIPS 204.
