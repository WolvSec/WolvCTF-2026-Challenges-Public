#!/usr/bin/env python3
from pathlib import Path

from solve import solve


def main():
    expected = Path("/home/user/flag").read_text().strip()
    return 0 if solve("http://127.0.0.1:1337") == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
