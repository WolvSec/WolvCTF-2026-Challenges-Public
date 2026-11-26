#!/bin/sh
set -eu
cd "$(dirname "$0")"

expected_flag=$(cat flag.txt)
if [ "${FLAG:-$expected_flag}" != "$expected_flag" ]; then
    echo 'FLAG must match flag.txt when building the player handout' >&2
    exit 1
fi

FLAG="$expected_flag" python3 solution/gen_forensics.py
test "$(python3 solution/solve.py challenge/capture.log)" = "$expected_flag"
tar -czf dis.tar.gz -C challenge capture.log
tar -xOzf dis.tar.gz capture.log | cmp - challenge/capture.log
