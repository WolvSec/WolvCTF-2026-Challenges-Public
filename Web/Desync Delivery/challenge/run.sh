#!/bin/sh
set -eu

app_root="$(dirname "$0")"
backend_port="${BACKEND_PORT:-5000}"
edge_port="${EDGE_PORT:-8081}"
gateway_port="${LISTEN_PORT:-8080}"
FLAG_FILE="${FLAG_FILE:-/flag}" LISTEN_HOST=127.0.0.1 LISTEN_PORT="$backend_port" sh "$app_root/backend/entrypoint.sh" &
backend=$!
LISTEN_HOST=127.0.0.1 LISTEN_PORT="$edge_port" BACKEND_HOST=127.0.0.1 BACKEND_PORT="$backend_port" python3 "$app_root/edge/edge.py" &
edge=$!
LISTEN_PORT="$gateway_port" EDGE_HOST=127.0.0.1 EDGE_PORT="$edge_port" python3 "$app_root/gateway/server.py" &
gateway=$!

trap 'kill "$backend" "$edge" "$gateway" 2>/dev/null || true; wait 2>/dev/null || true' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
while kill -0 "$backend" "$edge" "$gateway" 2>/dev/null; do
    sleep 1
done
exit 1
