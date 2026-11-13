import pytest

from cnnum import (
    MAX_VALUE,
    NumError,
    parse_chinese,
    parse_cny,
    to_big,
    to_chinese,
    to_cny,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "零"),
        (1, "一"),
        (10, "十"),
        (12, "十二"),
        (20, "二十"),
        (101, "一百零一"),
        (110, "一百一十"),
        (1000, "一千"),
        (1001, "一千零一"),
        (1010, "一千零一十"),
        (10000, "一万"),
        (10001, "一万零一"),
        (110000, "十一万"),
        (1000000, "一百万"),
        (12345, "一万二千三百四十五"),
        (123456789, "一亿二千三百四十五万六千七百八十九"),
        (10 ** 8, "一亿"),
        (10 ** 8 + 1, "一亿零一"),
        (10 ** 12, "一万亿"),
    ],
)
def test_to_chinese(value: int, expected: str) -> None:
    assert to_chinese(value) == expected


def test_to_chinese_rejects_bad_input() -> None:
    with pytest.raises(NumError):
        to_chinese(-1)
    with pytest.raises(TypeError):
        to_chinese(1.5)
    with pytest.raises(TypeError):
        to_chinese(True)
    with pytest.raises(NumError):
        to_chinese(MAX_VALUE + 1)


@pytest.mark.parametrize("value", [0, 1, 10, 11, 99, 100, 1001, 10010, 99999, 123456789, 10 ** 8 + 7, 10 ** 12 + 1])
def test_roundtrip(value: int) -> None:
    assert parse_chinese(to_chinese(value)) == value


@pytest.mark.parametrize(
    "value,expected", [(0, "零"), (10, "壹拾"), (15, "壹拾伍"), (110, "壹佰壹拾"), (1001, "壹仟零壹")]
)
def test_to_big(value: int, expected: str) -> None:
    assert to_big(value) == expected


def test_to_big_keeps_yi_before_shi() -> None:
    assert to_big(10).startswith("壹拾")
    assert to_chinese(10) == "十"


@pytest.mark.parametrize(
    "yuan,cents,expected",
    [
        (0, 0, "零元整"),
        (123, 0, "壹佰贰拾叁元整"),
        (123, 45, "壹佰贰拾叁元肆角伍分"),
        (123, 40, "壹佰贰拾叁元肆角整"),
        (123, 5, "壹佰贰拾叁元零伍分"),
        (10, 0, "壹拾元整"),
    ],
)
def test_to_cny(yuan: int, cents: int, expected: str) -> None:
    assert to_cny(yuan, cents) == expected


def test_to_cny_validates() -> None:
    with pytest.raises(NumError):
        to_cny(-1)
    with pytest.raises(NumError):
        to_cny(1, 100)


@pytest.mark.parametrize("yuan,cents", [(0, 0), (1, 1), (123, 45), (123, 40), (123, 5), (9999, 99), (10, 0)])
def test_cny_roundtrip(yuan: int, cents: int) -> None:
    assert parse_cny(to_cny(yuan, cents)) == yuan * 100 + cents


@pytest.mark.parametrize(
    "text,expected",
    [
        ("零", 0),
        ("两", 2),
        ("十", 10),
        ("十二", 12),
        ("一百一十", 110),
        ("一万零一", 10001),
        ("十一万", 110000),
        ("一亿零一", 10 ** 8 + 1),
        ("壹佰贰拾叁", 123),
    ],
)
def test_parse_chinese(text: str, expected: int) -> None:
    assert parse_chinese(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "一二", "三斤"])
def test_parse_chinese_rejects(text: str) -> None:
    with pytest.raises(NumError):
        parse_chinese(text)


def test_parse_chinese_allows_zero_padding_digit() -> None:
    assert parse_chinese("零伍") == 5


@pytest.mark.parametrize(
    "text,expected",
    [
        ("零元整", 0),
        ("壹佰贰拾叁元肆角伍分", 12345),
        ("壹佰元零伍分", 10005),
        ("伍角整", 50),
        ("壹拾元整", 1000),
    ],
)
def test_parse_cny(text: str, expected: int) -> None:
    assert parse_cny(text) == expected
