from datetime import date, timedelta

import pytest

from isoweek import (
    DateMathError,
    add_workdays,
    format_duration,
    format_week,
    iso_week,
    parse_duration,
    parse_week,
    quarter,
    quarter_range,
    week_range,
    week_start,
    weekday_cn,
    weeks_in_year,
    workdays_between,
)


@pytest.mark.parametrize(
    "day,expected",
    [
        (date(2018, 12, 31), (2019, 1)),
        (date(2021, 1, 1), (2020, 53)),
        (date(2005, 1, 1), (2004, 53)),
        (date(2005, 1, 3), (2005, 1)),
        (date(2026, 11, 11), (2026, 46)),
    ],
)
def test_iso_week_known_values(day: date, expected: tuple[int, int]) -> None:
    assert iso_week(day) == expected


def test_format_week_is_not_strftime_percent_w() -> None:
    day = date(2018, 12, 31)
    assert format_week(day) == "2019-W01"
    assert day.strftime("%Y-W%W") == "2018-W53"   # 这就是那个坑
    assert day.strftime("%G-W%V") == format_week(day)


@pytest.mark.parametrize("text", ["2019-W01", "2019W01", "2019-w1", " 2019-W01 "])
def test_parse_week_accepts_variants(text: str) -> None:
    assert parse_week(text) == (2019, 1)


@pytest.mark.parametrize("text", ["2019-W00", "2019-W54", "abc", "", "2019-53"])
def test_parse_week_rejects(text: str) -> None:
    with pytest.raises(DateMathError):
        parse_week(text)


def test_week_start_crosses_year() -> None:
    assert week_start(2019, 1) == date(2018, 12, 31)
    assert week_start(2020, 53) == date(2020, 12, 28)
    assert week_start(2020, 53, 7) == date(2021, 1, 3)


def test_week_start_validates_week_and_weekday() -> None:
    with pytest.raises(DateMathError):
        week_start(2019, 53)          # 2019 只有 52 周
    with pytest.raises(DateMathError):
        week_start(2019, 1, 0)
    with pytest.raises(DateMathError):
        week_start(2019, 1, 8)


def test_week_range() -> None:
    assert week_range(date(2026, 11, 11)) == (date(2026, 11, 9), date(2026, 11, 15))


@pytest.mark.parametrize(
    "year,weeks", [(2004, 53), (2019, 52), (2020, 53), (2025, 52), (2026, 53)]
)
def test_weeks_in_year(year: int, weeks: int) -> None:
    assert weeks_in_year(year) == weeks


def test_weekday_cn() -> None:
    assert weekday_cn(date(2026, 11, 11)) == "周三"
    assert weekday_cn(date(2026, 11, 15)) == "周日"


@pytest.mark.parametrize(
    "day,q", [(date(2026, 1, 1), 1), (date(2026, 3, 31), 1), (date(2026, 4, 1), 2), (date(2026, 11, 11), 4)]
)
def test_quarter(day: date, q: int) -> None:
    assert quarter(day) == q


def test_quarter_range() -> None:
    assert quarter_range(2026, 1) == (date(2026, 1, 1), date(2026, 3, 31))
    assert quarter_range(2026, 4) == (date(2026, 10, 1), date(2026, 12, 31))


def test_quarter_range_invalid() -> None:
    with pytest.raises(DateMathError):
        quarter_range(2026, 0)
    with pytest.raises(DateMathError):
        quarter_range(2026, 5)


def test_add_workdays_skips_weekend() -> None:
    assert add_workdays(date(2026, 11, 13), 1) == date(2026, 11, 16)   # 周五 -> 周一
    assert add_workdays(date(2026, 11, 16), -1) == date(2026, 11, 13)  # 周一 -> 上周五
    assert add_workdays(date(2026, 11, 14), 1) == date(2026, 11, 16)   # 周六 -> 周一


def test_add_workdays_zero() -> None:
    assert add_workdays(date(2026, 11, 14), 0) == date(2026, 11, 14)


def test_workdays_between_half_open() -> None:
    assert workdays_between(date(2026, 11, 9), date(2026, 11, 14)) == 5   # 含周一, 不含周六


def test_workdays_between_full_week() -> None:
    assert workdays_between(date(2026, 11, 9), date(2026, 11, 16)) == 5


def test_workdays_between_same_day_and_reverse() -> None:
    day = date(2026, 11, 11)
    assert workdays_between(day, day) == 0
    assert workdays_between(date(2026, 11, 14), date(2026, 11, 9)) == -5


@pytest.mark.parametrize(
    "text,expected",
    [
        ("P1DT2H30M", timedelta(days=1, hours=2, minutes=30)),
        ("PT45S", timedelta(seconds=45)),
        ("P2W", timedelta(days=14)),
        ("P0D", timedelta(0)),
        ("p1dt2h", timedelta(days=1, hours=2)),
    ],
)
def test_parse_duration(text: str, expected: timedelta) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["1DT2H", "P", "PT", "P1Y", "P3M", ""])
def test_parse_duration_rejects(text: str) -> None:
    with pytest.raises(DateMathError):
        parse_duration(text)


@pytest.mark.parametrize(
    "delta,text",
    [
        (timedelta(0), "0s"),
        (timedelta(days=1, hours=2, minutes=30), "1d 2h 30m"),
        (timedelta(hours=3), "3h"),
        (timedelta(seconds=90), "1m 30s"),
        (timedelta(days=-1, hours=-2), "-1d 2h"),
    ],
)
def test_format_duration(delta: timedelta, text: str) -> None:
    assert format_duration(delta) == text


def test_parse_then_format_roundtrip() -> None:
    delta = parse_duration("P1DT2H30M")
    assert format_duration(delta) == "1d 2h 30m"


def test_parse_format_roundtrip_simple() -> None:
    delta = timedelta(days=2, hours=3, minutes=4, seconds=5)
    assert format_duration(delta) == "2d 3h 4m 5s"
