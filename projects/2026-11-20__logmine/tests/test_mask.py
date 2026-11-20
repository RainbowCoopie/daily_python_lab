import pytest

from logmine import mask_line, mask_token, tokenize


def test_tokenize_collapses_whitespace() -> None:
    assert tokenize("  connected   to\t10.0.0.1 ") == ["connected", "to", "10.0.0.1"]


def test_tokenize_empty() -> None:
    assert tokenize("") == []
    assert tokenize("   ") == []


@pytest.mark.parametrize(
    "token,expected",
    [
        ("10.0.0.1", "<IP>"),
        ("192.168.1.254", "<IP>"),
        ("0xDEADBEAF", "<HEX>"),
        ("0x10000", "<HEX>"),
        ("12345", "<NUM>"),
        ("550e8400-e29b-41d4-a716-446655440000", "<UUID>"),
    ],
)
def test_mask_token_recognises_variables(token: str, expected: str) -> None:
    assert mask_token(token) == expected


@pytest.mark.parametrize("token", ["davidoh", "connected", "10.0.0.1.5", "abc123", "<IP>"])
def test_mask_token_leaves_words_alone(token: str) -> None:
    assert mask_token(token) == token


def test_mask_line_end_to_end() -> None:
    assert mask_line("user 123 connected from 10.0.0.1") == "user <NUM> connected from <IP>"


def test_mask_line_keeps_punctuation_tokens() -> None:
    assert mask_line("retry=3 ok") == "retry=3 ok"
