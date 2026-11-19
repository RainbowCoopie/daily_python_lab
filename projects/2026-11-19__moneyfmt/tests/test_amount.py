from decimal import Decimal

import pytest

from moneyfmt import (
    format_amount,
    from_cents,
    parse_amount,
    round_half_up,
    split_cents,
    sum_cents,
    to_cents,
)


def test_parse_plain_string() -> None:
    assert parse_amount("1234.5") == Decimal("1234.5")


def test_parse_with_grouping_and_currency() -> None:
    assert parse_amount("\uffe51,234.56") == Decimal("1234.56")
    assert parse_amount("$ 1,234.56") == Decimal("1234.56")


def test_parse_fullwidth_digits() -> None:
    assert parse_amount("\uff11\uff12\uff13\uff14.\uff15") == Decimal("1234.5")


def test_parse_accounting_parentheses_is_negative() -> None:
    assert parse_amount("(1234.56)") == Decimal("-1234.56")


def test_parse_int_and_decimal() -> None:
    assert parse_amount(7) == Decimal(7)
    assert parse_amount(Decimal("0.1")) == Decimal("0.1")


def test_parse_float_goes_through_str() -> None:
    assert parse_amount(0.1) == Decimal("0.1")


def test_parse_rejects_junk() -> None:
    for bad in ("", "   ", "abc", "12abc", "NaN", "inf", "-inf"):
        with pytest.raises(ValueError):
            parse_amount(bad)


def test_parse_rejects_bool() -> None:
    with pytest.raises(TypeError):
        parse_amount(True)


def test_builtin_round_is_banker_rounding() -> None:
    # 这就是不能直接用 round 的原因
    assert round(2.5) == 2
    assert round(3.5) == 4


def test_round_half_up_differs_from_builtin() -> None:
    assert round_half_up("2.5", 0) == Decimal("3")
    assert round_half_up("2.675") == Decimal("2.68")


def test_round_half_up_negative() -> None:
    assert round_half_up("-2.675") == Decimal("-2.68")


def test_round_half_up_rejects_negative_places() -> None:
    with pytest.raises(ValueError):
        round_half_up("1", -1)


def test_decimal_from_float_trap() -> None:
    """同一个"2.675", 从 float 构造舍出 2.67, 从字符串构造舍出 2.68。"""
    from_float = Decimal(2.675).quantize(Decimal("0.01"))
    from_str = Decimal("2.675").quantize(Decimal("0.01"))
    assert from_float == Decimal("2.67")
    assert from_str == Decimal("2.68")
    assert round_half_up(2.675) == Decimal("2.68")


def test_to_cents() -> None:
    assert to_cents("1.00") == 100
    assert to_cents("2.675") == 268
    assert to_cents("-0.005") == -1
    assert to_cents(0) == 0


def test_from_cents() -> None:
    assert from_cents(268) == Decimal("2.68")
    assert from_cents(-1) == Decimal("-0.01")


def test_from_cents_rejects_non_int() -> None:
    with pytest.raises(TypeError):
        from_cents(1.5)  # type: ignore[arg-type]


def test_float_accumulation_drifts_but_cents_do_not() -> None:
    assert sum([0.1] * 10) != 1.0
    assert sum_cents(["0.1"] * 10) == 100


def test_sum_cents_mixed_inputs() -> None:
    assert sum_cents(["1.005", 2, "0.10"]) == 311


def test_split_cents() -> None:
    assert split_cents(123456) == (1234, 5, 6)
    assert split_cents(-123456) == (1234, 5, 6)
    assert split_cents(0) == (0, 0, 0)


def test_format_basic() -> None:
    assert format_amount("1234.5") == "1,234.50"


def test_format_no_grouping() -> None:
    assert format_amount("1234567.891", grouping=False) == "1234567.89"


def test_format_negative() -> None:
    assert format_amount("-1234.5") == "-1,234.50"


def test_format_negative_parentheses() -> None:
    assert format_amount("-1234.5", paren_negative=True) == "(1,234.50)"


def test_format_currency_prefix() -> None:
    assert format_amount("1234.5", currency="\uffe5") == "\uffe51,234.50"


def test_format_zero_has_no_minus() -> None:
    assert format_amount("-0.004") == "0.00"


def test_format_rounds_half_up() -> None:
    assert format_amount("2.675") == "2.68"
    assert format_amount("1.005") == "1.01"


def test_format_on_already_broken_float() -> None:
    """0.1+0.2 已经坏了, 但舍到分之后仍是 0.30 —— 精度控制在这里救回来了。"""
    assert format_amount(0.1 + 0.2) == "0.30"


def test_format_large_amount() -> None:
    assert format_amount("9876543210.989") == "9,876,543,210.99"
