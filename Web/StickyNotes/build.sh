#!/bin/sh
set -eu

challenge_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$challenge_dir"

cp flag.txt challenge/flag.txt
cp flag.txt healthcheck/flag.txt
cp solution/solve.py healthcheck/solve.py
handout_dir=$(mktemp -d)
trap 'rm -rf "$handout_dir"' EXIT
mkdir "$handout_dir/challenge"
cp description.md "$handout_dir/"
cp challenge/app.py challenge/Dockerfile challenge/requirements.txt "$handout_dir/challenge/"
printf 'wctf{sample_flag}\n' > "$handout_dir/challenge/flag.txt"
tar -czf dis.tar.gz -C "$handout_dir" description.md challenge
printf 'Created %s/dis.tar.gz\n' "$challenge_dir"
