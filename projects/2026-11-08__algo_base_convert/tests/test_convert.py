import pytest

from baseconv import parse_base, to_base
from baseconv.convert import InvalidBase, InvalidDigit

SAMPLES = [0, 1, 7, 8, 9, 255, 1000, 65535, 2 ** 31 - 1, -1, -1000]
BASES = [2, 3, 8, 10, 16, 32, 36]


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("n", SAMPLES)
def test_roundtrip(n: int, base: int) -> None:
    assert parse_base(to_base(n, base), base) == n


def test_known_values() -> None:
    assert to_base(9, 2) == "1001"
    assert to_base(1000, 3) == "1101001"
    assert to_base(1000, 16) == "3e8"
    assert to_base(-255, 16) == "-ff"
    assert to_base(35, 36) == "z"


def test_parse_tolerates_spaces_and_sign() -> None:
    assert parse_base("FF", 16) == 255
    assert parse_base("  ff  ", 16) == 255
    assert parse_base("-101", 2) == -5
    assert parse_base("+101", 2) == 5


def test_zero() -> None:
    assert to_base(0, 36) == "0"
    assert parse_base("0", 2) == 0


@pytest.mark.parametrize("base", [0, 1, 37, -2])
def test_invalid_base(base: int) -> None:
    with pytest.raises(InvalidBase):
        to_base(10, base)
    with pytest.raises(InvalidBase):
        parse_base("1", base)


@pytest.mark.parametrize(
    "text,base", [("2", 2), ("", 10), ("   ", 10), ("-", 10), ("1g", 16), ("z", 35)]
)
def test_invalid_digit(text: str, base: int) -> None:
    with pytest.raises(InvalidDigit):
        parse_base(text, base)


def test_type_errors() -> None:
    with pytest.raises(TypeError):
        to_base(3.5, 2)
    with pytest.raises(TypeError):
        parse_base(10, 2)
