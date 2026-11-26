from healthcheck import flag_matches


def test_exact_flag_only():
    expected = b"wctf{expected}"
    assert flag_matches(b"solver log\nwctf{expected}\n", expected)
    assert not flag_matches(b"solver log\nwctf{wrong}\n", expected)
    assert not flag_matches(b"solver log\nwctf{expected}suffix\n", expected)
    assert not flag_matches(b"wctf{wrong}\nwctf{expected}\n", expected)
    assert not flag_matches(b"wctf{expected}\nwctf{wrong}\n", expected)
    assert not flag_matches(b"", expected)


if __name__ == "__main__":
    test_exact_flag_only()
