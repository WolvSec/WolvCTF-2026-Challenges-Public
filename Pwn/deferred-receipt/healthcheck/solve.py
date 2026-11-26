#!/usr/bin/env python3
import re
import socket
import sys


def solve(host, port):
    with socket.create_connection((host, port), timeout=8) as connection:
        connection.settimeout(8)
        stream = connection.makefile("rb")

        def until(marker):
            data = bytearray()
            while not data.endswith(marker):
                ch = stream.read(1)
                if not ch or len(data) > 65536:
                    raise RuntimeError(f"Expected {marker!r}; got {bytes(data[-200:])!r}")
                data.extend(ch)
            return bytes(data)

        def send(value):
            connection.sendall(str(value).encode() + b"\n")

        until(b"Choice: ")
        send(1)
        public = int(re.search(rb"Receipt ID: (\d+)", until(b"Choice: ")).group(1))

        send(2)
        until(b"Public receipt ID: ")
        send(public)
        until(b"Amendment (hex): ")
        send("4c414553")
        until(b"Choice: ")

        send(3)
        until(b"Public receipt ID: ")
        send(public)
        until(b"Choice: ")

        send(4)
        sealed = int(re.search(rb"Receipt ID: (\d+)", until(b"Choice: ")).group(1))

        send(5)
        until(b"Choice: ")

        send(6)
        until(b"Sealed receipt ID: ")
        send(sealed)
        until(b"wctf{")
        return b"wctf{" + until(b"}")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 1337
    print(solve(host, port).decode())
