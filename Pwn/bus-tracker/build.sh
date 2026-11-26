#!/bin/sh
set -eu
cd "$(dirname "$0")"

image=wolvctf-bus-tracker-build
tmp=$(mktemp -d)
cid=
cleanup() {
    if [ -n "$cid" ]; then docker rm "$cid" >/dev/null; fi
    rm -r "$tmp"
}
trap cleanup EXIT

cp flag.txt challenge/flag.txt
docker build --platform linux/amd64 --target build -t "$image" challenge
cid=$(docker create "$image")
docker cp "$cid:/build/chal" "$tmp/chal"
test -s "$tmp/chal"
cp "$tmp/chal" healthcheck/chal
cp flag.txt healthcheck/flag.txt
cp solution/solve.py healthcheck/solve.py
docker build --platform linux/amd64 -t wolvctf-bus-tracker challenge
tar -czf "$tmp/dis.tar.gz" -C "$tmp" chal
mv "$tmp/dis.tar.gz" dis.tar.gz
