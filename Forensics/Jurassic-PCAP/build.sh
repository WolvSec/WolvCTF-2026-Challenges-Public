#!/bin/bash
set -euo pipefail
OUTPUT=$(mktemp -d .jurassic-build.XXXXXXXX)
PREFIX="jurassic_pcap_$$_$(printf '%s' "${OUTPUT##*.}" | tr '[:upper:]' '[:lower:]')_"
NETWORK="${PREFIX}network"
WEBSITE="${PREFIX}website"
CAPTURE="${PREFIX}capture"
NETWORK_ID=
WEBSITE_ID=
CAPTURE_ID=
WEBSITE_BUILT=0
CAPTURE_BUILT=0

cleanup() {
  [ -z "$CAPTURE_ID" ] || docker rm -f "$CAPTURE_ID" >/dev/null 2>&1 || true
  [ -z "$WEBSITE_ID" ] || docker rm -f "$WEBSITE_ID" >/dev/null 2>&1 || true
  [ "$CAPTURE_BUILT" -eq 0 ] || docker rmi "$CAPTURE" >/dev/null 2>&1 || true
  [ "$WEBSITE_BUILT" -eq 0 ] || docker rmi "$WEBSITE" >/dev/null 2>&1 || true
  [ -z "$NETWORK_ID" ] || docker network rm "$NETWORK_ID" >/dev/null 2>&1 || true
  rm -rf -- "$OUTPUT"
}
trap cleanup EXIT

NETWORK_ID=$(docker network create "$NETWORK")

docker build -t "$WEBSITE" challenge/website
WEBSITE_BUILT=1
docker build -t "$CAPTURE" challenge/capture
CAPTURE_BUILT=1

WEBSITE_ID=$(docker run -d --network="$NETWORK" --name "$WEBSITE" "$WEBSITE")
IPADDR=$(docker inspect \
  -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$WEBSITE_ID")

CAPTURE_ID=$(docker run -d -e WEBSITE="$IPADDR" --network="$NETWORK" --name "$CAPTURE" "$CAPTURE")
status=$(docker container wait "$CAPTURE_ID")
if [ "$status" -ne 0 ]; then
  docker logs "$CAPTURE_ID" >&2
  exit "$status"
fi
docker cp "$CAPTURE_ID:/capture/jurassic.pcap" "$OUTPUT/jurassic.pcap" > /dev/null

docker run --rm -v "$PWD:/review:ro" -v "$PWD/$OUTPUT:/output:ro" "$CAPTURE" sh -euc '
  python3 /review/validate.py /output/jurassic.pcap /review/challenge/website/static/images /tmp/extracted
  steghide extract -sf /tmp/extracted/stegosaurus.jpg -p "" -xf /tmp/hint.txt -f >/dev/null
  cmp -s /tmp/hint.txt /review/challenge/hint.txt
  steghide extract -sf /tmp/extracted/archaeopteryx.jpg -p "$(cat /review/challenge/pass.txt)" -xf /tmp/flag.txt -f >/dev/null
  cmp -s /tmp/flag.txt /review/flag.txt
'

tar -czf "$OUTPUT/dist.tar.gz" -C "$OUTPUT" jurassic.pcap
mv "$OUTPUT/dist.tar.gz" dist.tar.gz
