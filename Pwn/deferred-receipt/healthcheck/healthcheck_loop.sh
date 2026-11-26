#!/bin/bash
set -Eeuo pipefail
while true; do
  if timeout 20 python3 /home/user/healthcheck.py; then
    echo ok > /tmp/healthz
  else
    echo err > /tmp/healthz
  fi
  sleep 30
done
