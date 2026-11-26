#!/bin/sh
set -eu
PATH=/usr/bin:/bin:$PATH
cd "$(dirname "$0")"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
python3 challenge/build_image.py challenge/scan.png "$work/card.img"
tar -czf dis.tar.gz -C "$work" card.img
