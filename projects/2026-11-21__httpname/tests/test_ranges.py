import pytest

from httpname import ByteRange, parse_ranges


def test_closed_range() -> None:
    ranges = parse_ranges("bytes=0-499")
    assert ranges == [ByteRange(first=0, last=499)]


def test_open_ended_range() -> None:
    ranges = parse_ranges("bytes=500-")
    assert ranges == [ByteRange(first=500, last=None)]


def test_suffix_range() -> None:
    ranges = parse_ranges("bytes=-500")
    assert ranges == [ByteRange(first=None, last=500, suffix=True)]


def test_multiple_ranges() -> None:
    assert len(parse_ranges("bytes=0-1, 5-6")) == 2


def test_unit_must_be_bytes() -> None:
    assert parse_ranges("items=0-1") is None


def test_invalid_syntax_returns_none() -> None:
    for bad in ("", "bytes=", "bytes=abc", "bytes=5", "bytes=5-1", "bytes=-0", "bytes=0-" + "x"):
        assert parse_ranges(bad) is None, bad


def test_resolve_closed_range() -> None:
    assert parse_ranges("bytes=0-499")[0].resolve(1000) == (0, 499)


def test_resolve_open_ended_uses_size() -> None:
    assert parse_ranges("bytes=500-")[0].resolve(1000) == (500, 999)


def test_resolve_suffix_counts_from_end() -> None:
    """-500 表示"最后 500 字节", 不是"第 -500 字节"。"""
    assert parse_ranges("bytes=-500")[0].resolve(1000) == (500, 999)


def test_resolve_suffix_larger_than_file() -> None:
    assert parse_ranges("bytes=-500")[0].resolve(100) == (0, 99)


def test_resolve_clamps_end() -> None:
    assert parse_ranges("bytes=0-9999")[0].resolve(1000) == (0, 999)


def test_resolve_empty_file() -> None:
    assert parse_ranges("bytes=0-10")[0].resolve(0) == (0, -1)


def test_resolve_rejects_negative_size() -> None:
    with pytest.raises(ValueError):
        parse_ranges("bytes=0-1")[0].resolve(-1)


def test_zero_length_closed_range() -> None:
    assert parse_ranges("bytes=0-0")[0].resolve(10) == (0, 0)
