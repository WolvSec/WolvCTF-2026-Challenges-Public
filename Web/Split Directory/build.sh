#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
cp flag.txt challenge/flag.txt
cp flag.txt healthcheck/flag.txt
cp solution/solve.py healthcheck/solve.py
docker build --platform linux/amd64 -t wolvctf-split-directory challenge
tar -czf dis.tar.gz -C challenge README.md -C "$PWD" description.md
