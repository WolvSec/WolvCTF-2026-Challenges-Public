#!/bin/sh
set -eu

cd "$(dirname "$0")"
cd challenge
DOCKER_DEFAULT_PLATFORM=linux/amd64 scuba build
docker build --platform linux/amd64 . -t comment-card:1.0
cid=
cleanup() { [ -z "$cid" ] || docker rm "$cid" >/dev/null; }
trap cleanup EXIT
cid=$(docker create comment-card:1.0)
docker cp "$cid:/chroot/home/user/chal" chal
docker rm "$cid"
cid=
cd ..

cp challenge/chal healthcheck/chal
cp solution/solve.py healthcheck/solve.py
cp flag.txt healthcheck/flag.txt
docker build --platform linux/amd64 healthcheck -t comment-card-healthcheck:1.0
tar -czf dis.tar.gz -C challenge chal
echo "Built dis.tar.gz"
