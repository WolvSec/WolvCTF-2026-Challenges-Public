#!/bin/bash
set -e

cd "$(dirname "$0")"
cd challenge
DOCKER_DEFAULT_PLATFORM=linux/amd64 scuba build
docker build --platform linux/amd64 . -t blue-market:1.0
cid=$(docker create blue-market:1.0)
trap 'docker rm "$cid" >/dev/null' EXIT
docker cp "$cid:/chroot/home/user/chal" chal
cd ..

cp challenge/chal healthcheck/chal
cp solution/solve.py healthcheck/solve.py
cp challenge/flag.txt healthcheck/flag.txt
tar -czf dis.tar.gz -C challenge chal
echo "Built dis.tar.gz"
