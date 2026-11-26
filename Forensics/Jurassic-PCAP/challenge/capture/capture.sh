#!/bin/bash
set -euo pipefail
tcpdump --immediate-mode -Ui eth0 -w jurassic.pcap 'port 8080' &
tcpdump_pid=$!
trap 'kill -TERM "$tcpdump_pid" 2>/dev/null || true; wait "$tcpdump_pid" 2>/dev/null || true' EXIT
sleep 1
kill -0 "$tcpdump_pid"
wget --page-requisites --retry-connrefused --tries=5 --waitretry=1 "http://$WEBSITE:8080"
kill -TERM "$tcpdump_pid"
wait "$tcpdump_pid" || [ "$?" -eq 143 ]
trap - EXIT
