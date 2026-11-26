#!/bin/bash
# Build the firmware in Docker and package the player handout.
# Produces challenge/firmware.bin (not committed) and dis.tar.gz.
set -e
cd "$(dirname "$0")"
docker build -t motor-city-hotwire .
cid=$(docker create motor-city-hotwire)
mkdir -p challenge
docker cp "$cid:/chal/firmware.bin" challenge/firmware.bin
docker rm "$cid" >/dev/null
tar -czf dis.tar.gz -C challenge firmware.bin
echo "built challenge/firmware.bin and dis.tar.gz"
