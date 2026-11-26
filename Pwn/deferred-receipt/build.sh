#!/bin/sh
set -eu
cd "$(dirname "$0")"

cmp -s flag.txt challenge/flag.txt
cmp -s solution/solve.py healthcheck/solve.py
image=wolvctf-2026-deferred-receipt-build
tmp=$(mktemp -d)
cid=
cleanup() {
    if [ -n "$cid" ]; then docker rm "$cid" >/dev/null; fi
    rm -r "$tmp"
}
trap cleanup EXIT

docker build --platform linux/amd64 --target build -t "$image" challenge
cid=$(docker create "$image")
docker cp "$cid:/build/deferred-receipt" "$tmp/deferred-receipt"
test -s "$tmp/deferred-receipt"
tar -czf "$tmp/dis.tar.gz" -C "$tmp" deferred-receipt
mv "$tmp/dis.tar.gz" dis.tar.gz
