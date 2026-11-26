#!/usr/bin/env bash
set -euo pipefail

CHALLENGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHALLENGE_DIR="$CHALLENGE_ROOT/challenge"
DIST_DIR="$CHALLENGE_DIR/dist"
BUILD_DIR="$DIST_DIR/build"

mkdir -p "$BUILD_DIR"
python3 "$CHALLENGE_DIR/tools/make_backup.py" \
    "$CHALLENGE_ROOT/flag.txt" "$DIST_DIR/backup.tc"
docker build --target artifact \
    --output "type=local,dest=$BUILD_DIR" \
    -f "$CHALLENGE_DIR/Dockerfile" "$CHALLENGE_DIR"
mv "$BUILD_DIR/time_capsule" "$DIST_DIR/time_capsule"
rmdir "$BUILD_DIR"
chmod 755 "$DIST_DIR/time_capsule"
tar -czf "$CHALLENGE_ROOT/dis.tar.gz" \
    -C "$DIST_DIR" time_capsule backup.tc

printf 'Built player bundle: %s/dis.tar.gz\n' "$CHALLENGE_ROOT"
