#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "--regenerate" ]]; then
  python_bin="${PYTHON:-/usr/bin/python3}"
  "$python_bin" -c 'import numpy, scipy' || {
    echo "--regenerate needs numpy and scipy to playtest the new instance" >&2
    exit 1
  }
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT
  "${CC:-cc}" -O3 -std=c99 -DMLD_CONFIG_PARAMETER_SET=44 \
    -DMLD_CONFIG_NO_RANDOMIZED_API -DMLD_REJECTED_TELEMETRY \
    -I challenge/vendor/mldsa challenge/vendor/mldsa/mldsa_native.c \
    challenge/record.c -o "$tmp_dir/record"
  "$tmp_dir/record" "$tmp_dir" 120000
  "$python_bin" challenge/seal.py "$tmp_dir/s1.tmp" flag.txt "$tmp_dir/flag.json"
  playtest_output="$("$python_bin" solution/solve.py "$tmp_dir")"
  [[ "${playtest_output##*$'\n'}" == "$(<flag.txt)" ]] || {
    echo "regenerated instance failed the reference solve" >&2
    exit 1
  }
  cp "$tmp_dir/public.key" "$tmp_dir/rejected.log" "$tmp_dir/flag.json" challenge/
elif [[ -n "${1:-}" ]]; then
  echo "usage: ./build.sh [--regenerate]" >&2
  exit 2
fi

for file in public.key rejected.log flag.json; do
  [[ -s "challenge/$file" ]] || { echo "missing challenge/$file" >&2; exit 1; }
done
tar -czf dis.tar.gz -C challenge README.md record.c seal.py vendor \
  public.key rejected.log flag.json
echo "wrote dis.tar.gz"
