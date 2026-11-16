import pytest

from cnvalid import uscc_check_digit, uscc_valid


def test_check_digit_known_code() -> None:
    assert uscc_check_digit("91350100M000100Y4") == "3"


def test_valid_known_code() -> None:
    assert uscc_valid("91350100M000100Y43") is True


def test_tampered_code_rejected() -> None:
    assert uscc_valid("91350211M000100Y43") is False


def test_wrong_length_rejected() -> None:
    assert uscc_valid("91350100M000100Y4") is False
    assert uscc_valid("91350100M000100Y433") is False


def test_lowercase_normalised() -> None:
    assert uscc_valid("91350100m000100y43") is True


def test_forbidden_letters_rejected() -> None:
    for bad in ("I", "O", "Z", "S", "V"):
        assert uscc_valid(bad + "1350100M000100Y43") is False


def test_check_digit_validation() -> None:
    with pytest.raises(ValueError):
        uscc_check_digit("9135")
    with pytest.raises(ValueError):
        uscc_check_digit("91350100M000100YI")


def test_remainder_zero_lands_on_zero() -> None:
    """31 - 0 = 31 必须落回 0, 否则索引越界。"""
    assert uscc_check_digit("00000000000000000") == "0"
