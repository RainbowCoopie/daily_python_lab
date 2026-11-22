import pytest

from unitconv import format_span, parse_span


@pytest.mark.parametrize(
    "text,expected",
    [
        ("90s", 90.0),
        ("1h30m", 5400.0),
        ("1.5h", 5400.0),
        ("2d", 172800.0),
        ("1w", 604800.0),
        ("500ms", 0.5),
        ("1H30M", 5400.0),
        ("1h 30m", 5400.0),
        ("1h30m10s", 5410.0),
    ],
)
def test_parse_span(text: str, expected: float) -> None:
    assert parse_span(text) == pytest.approx(expected)


def test_bare_number_is_seconds() -> None:
    assert parse_span("90") == 90.0


def test_float_bare_number() -> None:
    assert parse_span("1.5") == 1.5


@pytest.mark.parametrize("bad", ["", "abc", "1x", "1h30", "30s1h?"])
def test_parse_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_span(bad)


def test_ms_not_confused_with_m() -> None:
    """ms 必须优先于 m 匹配, 否则 '10ms' 会被读成 10 分钟。"""
    assert parse_span("10ms") == pytest.approx(0.01)
    assert parse_span("10m") == 600.0


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "0s"),
        (1, "1s"),
        (90, "1m30s"),
        (5400, "1h30m"),
        (9001, "2h30m1s"),
        (604800, "1w"),
        (0.5, "500ms"),
    ],
)
def test_format_span(seconds: float, expected: str) -> None:
    assert format_span(seconds) == expected


def test_format_rejects_negative() -> None:
    with pytest.raises(ValueError):
        format_span(-1)


@pytest.mark.parametrize("seconds", [0, 1, 59, 60, 3599, 3600, 86400, 5400])
def test_roundtrip(seconds: int) -> None:
    assert parse_span(format_span(seconds)) == pytest.approx(seconds)


def test_month_and_year_units_unsupported() -> None:
    """'1y' 不支持; 注意 '1M' 因为大小写不敏感会被当成 1 分钟, 不是 1 个月。"""
    with pytest.raises(ValueError):
        parse_span("1y")
    assert parse_span("1M") == 60.0
