#!/bin/sh
set -eu
cd "$(dirname "$0")"

"${PYTHON:-python3}" scripts/build_handout.py dis.tar.gz
cp solve/solve.py healthcheck/solve.py
# flag.txt at the challenge root is the only tracked copy; build contexts get generated copies.
cp flag.txt challenge/flag.txt
cp flag.txt healthcheck/flag.txt
