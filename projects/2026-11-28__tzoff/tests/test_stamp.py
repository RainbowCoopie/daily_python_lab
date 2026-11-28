import pytest
from datetime import datetime

from tzoff import format_stamp, parse_stamp, same_instant


def test_parse_offset_timestamp_to_utc() -> None:
    stamp = parse_stamp("2026-11-28T09:30:00+08:00")
    assert stamp.naive == datetime(2026, 11, 28, 9, 30)
    assert stamp.utc == datetime(2026, 11, 28, 1, 30)


def test_parse_zulu() -> None:
    stamp = parse_stamp("2026-11-28T01:30:00Z")
    assert stamp.offset.unknown is False
    assert stamp.utc == datetime(2026, 11, 28, 1, 30)


def test_minus_zero_is_distinguishable_from_plus_zero() -> None:
    """这正是 datetime 自己做不到的事: 两者的 utcoffset 都是 0, 但语义不同。"""
    unknown = parse_stamp("2026-11-28T01:30:00-00:00")
    known = parse_stamp("2026-11-28T01:30:00+00:00")
    assert unknown.utc == known.utc
    assert unknown.offset.unknown is True
    assert known.offset.unknown is False


def test_fractional_seconds() -> None:
    stamp = parse_stamp("2026-11-28T09:30:00.250+08:00")
    assert stamp.naive.microsecond == 250000


def test_format_roundtrip() -> None:
    for text in (
        "2026-11-28T09:30:00+08:00",
        "2026-11-28T01:30:00Z",
        "2026-11-28T01:30:00-00:00",
    ):
        assert format_stamp(parse_stamp(text)) == text


def test_same_instant_across_offsets() -> None:
    a = parse_stamp("2026-11-28T09:30:00+08:00")
    b = parse_stamp("2026-11-28T01:30:00Z")
    assert same_instant(a, b) is True


def test_different_instant() -> None:
    a = parse_stamp("2026-11-28T09:30:00+08:00")
    b = parse_stamp("2026-11-28T09:30:00Z")
    assert same_instant(a, b) is False


@pytest.mark.parametrize(
    "text",
    [
        "2026-11-28T09:30:00",
        "2026-11-28",
        "",
        "not-a-date+08:00",
        "2026-11-28T09:30:00+8",
    ],
)
def test_invalid_stamps(text: str) -> None:
    with pytest.raises(ValueError):
        parse_stamp(text)


def test_date_only_is_not_mistaken_for_offset() -> None:
    """'2026-11-28' 末尾的 '-28' 不能被当成偏移。"""
    with pytest.raises(ValueError):
        parse_stamp("2026-11-28")
