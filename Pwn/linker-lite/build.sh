#!/bin/sh
set -eu
cd "$(dirname "$0")"

image=wolvctf-2026-linker-lite-build
tmp=$(mktemp -d)
cid=
cleanup() {
    if [ -n "$cid" ]; then docker rm "$cid" >/dev/null; fi
    rm -r "$tmp"
}
trap cleanup EXIT

docker build --platform linux/amd64 --target build -t "$image" challenge
cid=$(docker create "$image")
docker cp "$cid:/build/linker-lite" "$tmp/linker-lite"
docker cp -L "$cid:/bin/dash" "$tmp/sh"
docker cp -L "$cid:/bin/cat" "$tmp/cat"
cp challenge/ld-linux-x86-64.so.2 "$tmp/ld-linux-x86-64.so.2"
cp challenge/libc.so.6 "$tmp/libc.so.6"
test -s "$tmp/linker-lite" && test -s "$tmp/ld-linux-x86-64.so.2" && test -s "$tmp/libc.so.6"
mkdir -p healthcheck
mkdir -p challenge/runtime/bin
cp "$tmp/linker-lite" challenge/chal
cp "$tmp/linker-lite" healthcheck/linker-lite
cp "$tmp/linker-lite" linker-lite
chmod 755 challenge/chal healthcheck/linker-lite linker-lite
cp "$tmp/sh" challenge/runtime/bin/sh
cp "$tmp/cat" challenge/runtime/bin/cat
cp solve.py healthcheck/solve.py
cp challenge/flag.txt healthcheck/flag.txt
tar -czf "$tmp/dis.tar.gz" -C "$tmp" linker-lite ld-linux-x86-64.so.2 libc.so.6
mv "$tmp/dis.tar.gz" dis.tar.gz
