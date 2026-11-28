import pytest
from datetime import timedelta

from tzoff import Offset, format_offset, parse_offset


@pytest.mark.parametrize(
    "text,expected",
    [
        ("+08:00", timedelta(hours=8)),
        ("-05:30", -timedelta(hours=5, minutes=30)),
        ("+0800", timedelta(hours=8)),
        ("+00:00", timedelta(0)),
        ("GMT+8", timedelta(hours=8)),
        ("UtC+05:30", timedelta(hours=5, minutes=30)),
    ],
)
def test_parse_signed_offsets(text: str, expected: timedelta) -> None:
    offset = parse_offset(text)
    assert offset.delta == expected
    assert offset.unknown is False


def test_parse_z_is_zero_and_known() -> None:
    offset = parse_offset("Z")
    assert offset.delta == timedelta(0)
    assert offset.unknown is False


def test_parse_bare_utc_and_gmt() -> None:
    assert parse_offset("UTC").delta == timedelta(0)
    assert parse_offset("GMT").delta == timedelta(0)


def test_minus_zero_means_unknown() -> None:
    """RFC 3339: -00:00 表示偏移未知, 与 +00:00 不同。"""
    offset = parse_offset("-00:00")
    assert offset.delta == timedelta(0)
    assert offset.unknown is True


def test_plus_zero_is_known() -> None:
    assert parse_offset("+00:00").unknown is False


def test_format_roundtrip() -> None:
    for text in ("+08:00", "-05:30", "Z", "-00:00"):
        assert format_offset(parse_offset(text)) == text


def test_format_unknown_offset() -> None:
    assert format_offset(Offset(timedelta(0), unknown=True)) == "-00:00"


def test_max_offset_allowed() -> None:
    assert parse_offset("+18:00").delta == timedelta(hours=18)


@pytest.mark.parametrize("text", ["+19:00", "-18:01"])
def test_offset_out_of_range(text: str) -> None:
    with pytest.raises(ValueError):
        parse_offset(text)


@pytest.mark.parametrize("text", ["", "+08:60", "abc", "+8", "08:00"])
def test_invalid_offsets(text: str) -> None:
    with pytest.raises(ValueError):
        parse_offset(text)


def test_minutes_property() -> None:
    assert parse_offset("+05:30").minutes == 330
    assert parse_offset("-05:30").minutes == -330
