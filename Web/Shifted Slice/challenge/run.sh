#!/bin/bash
set -euo pipefail

mkdir -p /tmp/nginx/body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi
python3 /app/app.py &
app_pid=$!
nginx -c /app/nginx.conf -g 'daemon off;' &
nginx_pid=$!
trap 'kill "$app_pid" "$nginx_pid" 2>/dev/null || true' EXIT TERM INT
wait -n "$app_pid" "$nginx_pid"
