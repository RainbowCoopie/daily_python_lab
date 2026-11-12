import pytest

from xlsafe import (
    MODE_QUOTE,
    inspect,
    looks_like_date,
    looks_like_formula,
    looks_like_leading_zero,
    looks_like_long_number,
    sanitize,
    to_text_cell,
    unprotect,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("138001380001234567", True),
        ("123456789012345", True),      # 正好 15 位
        ("12345678901234", False),      # 14 位, Excel 吃得下
        ("-123456789012345", True),
        ("13800138000", False),         # 11 位手机号, 无风险
        ("123456789012345a", False),
    ],
)
def test_looks_like_long_number(value: str, expected: bool) -> None:
    assert looks_like_long_number(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [("007", True), ("00", True), ("0", False), ("0.5", False), ("700", False)],
)
def test_looks_like_leading_zero(value: str, expected: bool) -> None:
    assert looks_like_leading_zero(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [("3-5", True), ("3/5", True), ("2026-11-11", True), ("2026-11-11 10:00", False), ("abc-def", False), ("", False)],
)
def test_looks_like_date(value: str, expected: bool) -> None:
    assert looks_like_date(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("=1+1", True),
        ("@SUM(A1)", True),
        ("+8613800138000", True),
        ("-3+cmd", True),
        ("\t=1+1", True),
        ("-3", False),          # 纯负数是正常数据
        ("-3.5", False),
        ("hello", False),
        ("", False),
    ],
)
def test_looks_like_formula(value: str, expected: bool) -> None:
    assert looks_like_formula(value) is expected


def test_inspect_collects_reasons_in_order() -> None:
    # 以 = 开头时它首先是公式, 不是"长数字"; 保护动作已经由 formula 负责
    assert inspect("=1234567890123456") == ["formula"]
    assert inspect("1234567890123456") == ["long_number"]
    assert inspect("007") == ["leading_zero"]
    assert inspect("2026-11-11") == ["date"]
    assert inspect("hello") == []


def test_to_text_cell_formula_mode() -> None:
    assert to_text_cell("123") == '="123"'


def test_to_text_cell_escapes_inner_quotes() -> None:
    assert to_text_cell('a"b') == '="a""b"'


def test_to_text_cell_quote_mode() -> None:
    assert to_text_cell("123", MODE_QUOTE) == "'123"


def test_to_text_cell_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        to_text_cell("x", "weird")


@pytest.mark.parametrize("mode", ["formula", "quote"])
def test_protect_unprotect_roundtrip(mode: str) -> None:
    for value in ("123", 'a"b', "007", "-3+cmd"):
        assert unprotect(to_text_cell(value, mode)) == value


def test_unprotect_leaves_plain_text_alone() -> None:
    assert unprotect("hello") == "hello"
    assert unprotect("") == ""


def test_sanitize_only_touches_risky_values() -> None:
    assert sanitize("hello") == "hello"
    assert sanitize("138001380001234567") == '="138001380001234567"'
    assert sanitize("=cmd", MODE_QUOTE) == "'=cmd"
