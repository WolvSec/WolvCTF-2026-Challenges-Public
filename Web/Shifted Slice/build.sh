#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
flag="$(cat "$root/flag.txt")"
if [[ ! "$flag" =~ ^wctf\{[0-9a-f]{32}\}$ ]]; then
    printf 'flag.txt must contain wctf{32 lowercase hex characters}\n' >&2
    exit 1
fi
if [[ ! -f "$root/solution/solve.py" ]]; then
    printf 'solution/solve.py is missing\n' >&2
    exit 1
fi

printf '%s\n' "$flag" > "$root/challenge/flag.txt"
printf '%s\n' "$flag" > "$root/healthcheck/flag.txt"
cp "$root/solution/solve.py" "$root/healthcheck/solve.py"
tar -czf "$root/dis.tar.gz" -C "$root" description.md
