#!/bin/sh
set -eu
cd "$(dirname "$0")"

image=wolvctf-2026-gate7-build
tmp=$(mktemp -d)
cid=
cleanup() {
    if [ -n "$cid" ]; then docker rm "$cid" >/dev/null; fi
    rm -r "$tmp"
}
trap cleanup EXIT

docker build --platform linux/amd64 --target build -t "$image" challenge
cid=$(docker create "$image")
docker cp "$cid:/build/gate7" "$tmp/gate7"
docker cp -L "$cid:/lib64/ld-linux-x86-64.so.2" "$tmp/ld-linux-x86-64.so.2"
docker cp -L "$cid:/usr/lib/x86_64-linux-gnu/libc.so.6" "$tmp/libc.so.6"
test -s "$tmp/gate7" && test -s "$tmp/ld-linux-x86-64.so.2" && test -s "$tmp/libc.so.6"
mkdir -p healthcheck
mkdir -p challenge/runtime/lib64 challenge/runtime/lib/x86_64-linux-gnu
cp "$tmp/gate7" challenge/chal
cp "$tmp/gate7" healthcheck/gate7
cp "$tmp/gate7" gate7
chmod 755 challenge/chal healthcheck/gate7 gate7
cp "$tmp/ld-linux-x86-64.so.2" challenge/runtime/lib64/ld-linux-x86-64.so.2
cp "$tmp/libc.so.6" challenge/runtime/lib/x86_64-linux-gnu/libc.so.6
cp solve.py healthcheck/solve.py
tar -czf "$tmp/dis.tar.gz" -C "$tmp" gate7
mv "$tmp/dis.tar.gz" dis.tar.gz
