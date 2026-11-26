#!/bin/sh
set -eu
cd "$(dirname "$0")"

image=wolvctf-2026-no-open-door-build
tmp=$(mktemp -d)
cid=
cleanup() {
    if [ -n "$cid" ]; then docker rm "$cid" >/dev/null; fi
    rm -r "$tmp"
}
trap cleanup EXIT

docker build --platform linux/amd64 --target build -t "$image" challenge
cid=$(docker create "$image")
docker cp "$cid:/build/no-open-door" "$tmp/no-open-door"
test -s "$tmp/no-open-door"
mkdir -p healthcheck
cp "$tmp/no-open-door" challenge/chal
cp "$tmp/no-open-door" healthcheck/no-open-door
cp "$tmp/no-open-door" no-open-door
chmod 755 challenge/chal healthcheck/no-open-door no-open-door
cp solve.py healthcheck/solve.py
tar -czf "$tmp/dis.tar.gz" -C "$tmp" no-open-door
mv "$tmp/dis.tar.gz" dis.tar.gz
