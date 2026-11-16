import pytest

from cnvalid import luhn_check_digit, luhn_valid


@pytest.mark.parametrize("number", ["79927398713", "4111111111111111", "5500005555555559"])
def test_known_valid(number: str) -> None:
    assert luhn_valid(number) is True


@pytest.mark.parametrize("number", ["79927398710", "79927398711", "4111111111111112"])
def test_known_invalid(number: str) -> None:
    assert luhn_valid(number) is False


def test_check_digit_recovers_last_digit() -> None:
    assert luhn_check_digit("7992739871") == "3"
    assert luhn_check_digit("411111111111111") == "1"


def test_every_prefix_gets_a_valid_digit() -> None:
    for prefix in ("7992739871", "411111111111111", "62"):
        assert luhn_valid(prefix + luhn_check_digit(prefix))


def test_rejects_non_digits_and_tiny_input() -> None:
    assert luhn_valid("4111-1111") is False
    assert luhn_valid("") is False
    assert luhn_valid("7") is False


def test_check_digit_rejects_bad_prefix() -> None:
    with pytest.raises(ValueError):
        luhn_check_digit("")
    with pytest.raises(ValueError):
        luhn_check_digit("12a4")


def test_spaces_ignored() -> None:
    assert luhn_valid("4111 1111 1111 1111") is True
