import pytest

from app.core.security import hostname_of, new_session_token


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("127.0.0.1:8765", "127.0.0.1"),
        ("localhost:1234", "localhost"),
        ("LOCALHOST", "localhost"),
        ("evil.example.com:8765", "evil.example.com"),
        ("[::1]:8765", "[::1]:8765"),
        ("", ""),
    ],
)
def test_hostname_of(header, expected):
    assert hostname_of(header) == expected


def test_tokens_are_unique_and_long():
    a, b = new_session_token(), new_session_token()
    assert a != b and len(a) >= 40
