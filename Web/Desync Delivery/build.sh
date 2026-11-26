#!/usr/bin/env bash
set -euo pipefail

CHALLENGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -s "$CHALLENGE_ROOT/flag.txt" ]]; then
    printf 'flag.txt is missing or empty\n' >&2
    exit 1
fi
flag="$(cat "$CHALLENGE_ROOT/flag.txt")"
if [[ ! "$flag" =~ ^wctf\{[0-9a-f]{32}\}$ ]]; then
    printf 'flag.txt must contain wctf{32 lowercase hex characters}\n' >&2
    exit 1
fi

printf '%s\n' "$flag" > "$CHALLENGE_ROOT/challenge/flag.txt"
printf '%s\n' "$flag" > "$CHALLENGE_ROOT/healthcheck/flag.txt"
cp "$CHALLENGE_ROOT/solution/solve.py" "$CHALLENGE_ROOT/healthcheck/solve.py"
tar -czf "$CHALLENGE_ROOT/dis.tar.gz" -C "$CHALLENGE_ROOT" description.md

printf 'Prepared KCTF build inputs and %s/dis.tar.gz\n' "$CHALLENGE_ROOT"
