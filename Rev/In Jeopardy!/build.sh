#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

docker run --rm --platform linux/amd64 \
  -v "$root:/src:ro" -v "$tmp:/out" -w /src gcc:11-bullseye \
  g++ -std=c++17 -O0 -static -o /out/in-jeopardy main.cpp
test -s "$tmp/in-jeopardy"

docker run --rm --platform linux/amd64 \
  -v "$root:/src:ro" -v "$tmp:/out:ro" -w /src gcc:11-bullseye \
  python3 -B solution/solve.py /out/in-jeopardy > "$tmp/solved.txt"
cmp -s "$root/flag.txt" "$tmp/solved.txt" || {
  echo 'Linux solve does not match flag.txt' >&2
  exit 1
}

COPYFILE_DISABLE=1 tar -czf "$tmp/dis.tar.gz" -C "$tmp" in-jeopardy
cp "$tmp/in-jeopardy" "$root/in-jeopardy"
cp "$tmp/dis.tar.gz" "$root/dis.tar.gz"
echo 'Built in-jeopardy and dis.tar.gz'
