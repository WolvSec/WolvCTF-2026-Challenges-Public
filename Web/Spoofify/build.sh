#!/bin/bash
set -e
cd "$(dirname "$0")"

cp flag.txt challenge/flag
cp flag.txt healthcheck/flag
cp solution/solve.py healthcheck/solve.py
docker build -t spoofify:1.0 challenge
echo "Built spoofify:1.0"
echo "Local test: docker run --rm -p 8080:1337 spoofify:1.0"
echo "kCTF deploy (from a kctf workspace): kctf chal start"
