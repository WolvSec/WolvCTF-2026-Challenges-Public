#!/bin/sh
set -eu

if [ -z "${FLAG:-}" ]; then
    : "${FLAG_FILE:=/run/secrets/flag.txt}"
    if [ ! -r "$FLAG_FILE" ]; then
        echo "FLAG must be set or FLAG_FILE must be readable" >&2
        exit 1
    fi
    FLAG="$(tr -d '\r\n' < "$FLAG_FILE")"
else
    # Secret Manager environment values preserve the source secret's trailing newline.
    FLAG="$(printf '%s' "$FLAG" | tr -d '\r\n')"
fi

if ! python3 -c 'import re,sys; sys.exit(0 if re.fullmatch(r"wctf\{[0-9a-f]{32}\}", sys.argv[1]) else 1)' "$FLAG"; then
    echo "FLAG must use the wctf{32 lowercase hex characters} format" >&2
    exit 1
fi
export FLAG
exec python3 "$(dirname "$0")/server.py"
