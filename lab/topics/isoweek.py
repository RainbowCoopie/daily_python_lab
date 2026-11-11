'''ISO 周 / 季度 / 工作日 的边界计算, 顺手把 strftime 那个著名的坑钉在测试里。

灵感来源:
- `strftime('%Y-W%W')` 在年末年初既错年份又错周数: 实测 2018-12-31 的真 ISO 周是 2019-W01,
  而 %Y-%W 给出 2018-W53; 2021-01-01 真值是 2020-W53, 而 %Y-%W 给出 2021-W00
  (ISO 8601 没有第 0 周)。年中也会偏一周: 2026-11-11 真值 2026-W46, %W 给出 2026-W45。
  正确写法是 %G-%V。
- libstdc++ 在 r16 专门重构过 ISO 周历与周序号格式化
  (https://gcc.gnu.org/pipermail/libstdc++-cvs/2025q3/043785.html)
- ISO 8601 时长写法 P1DT2H30M 的解析边界, W3C XML Schema 里对词法有明确规定
  (https://www.w3.org/TR/xmlschema-2/)

为什么值得单独做一层: 按周出报表、按季度归档、SLA 只算工作日 —— 这三件事只要用
strftime 硬凑就会在跨年那两周出错, 而且错得很隐蔽(少一周的数据, 报表看不出来)。
本模块把所有边界都收敛到显式函数里, 并用测试把 2004/2019/2020/2026 这些
"53 周年"和"年初落在上一 ISO 年"的情况全部固定下来。
'''

SLUG = "isoweek"
TITLE = "ISO 周与工作日边界计算"
TAGS = ["日期边界", "ISO 8601", "报表周期", "62 周年"]
PKG = "isoweek"
SUMMARY = "ISO 周 / 周区间 / 季度 / 工作日 / ISO 时长解析, 把 strftime 在跨年时的错位问题用测试钉死。"
STACK_NOTES = [
    "format_week 永远给出 2026-W46 这种正确写法, 并有测试证明它与 %Y-%W 的结果不同",
    "weeks_in_year 用 12-28 落点法判定 52/53, 覆盖 2004/2019/2020/2026 四个边界年",
    "workdays_between 用整周除法 + 余数计数, 不逐天遍历; 区间左闭右开, 反向返回负数",
]
NOTES = """
两条容易混的坐标轴:

1. **日历年 vs ISO 周年**。ISO 周从周一开始, 且"第 1 周"是含 1 月 4 日的那一周。
   于是 1 月 1 日可能属于上一年的最后一周, 12 月 31 日也可能属于下一年第 1 周。
2. **周数 vs 周序号**。`%W` 是"从 1 月 1 日起数第几个周一", 不是 ISO 周,
   所以它在年中也会与 ISO 周差 1。要 ISO 周必须用 `%G-%V`, 或者直接用本模块。

时长解析只支持 W/D/H/M/S: 年月长度不固定(月和闰年), 硬解析会给出错误结果,
所以显式拒绝 `P1Y`、`P3M` 这类写法, 让调用方自己想清楚。
"""

FILES = {
    "isoweek/__init__.py": '''from .calendar_ops import (
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

__all__ = [
    "DateMathError",
    "iso_week",
    "format_week",
    "parse_week",
    "week_start",
    "week_range",
    "weeks_in_year",
    "weekday_cn",
    "quarter",
    "quarter_range",
    "add_workdays",
    "workdays_between",
    "parse_duration",
    "format_duration",
]
''',
    "isoweek/calendar_ops.py": '''# ISO 周、季度、工作日与 ISO 时长。
from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

_WEEK_RE = re.compile(r"^(\\d{4})-?[Ww](\\d{1,2})$")
_DURATION_RE = re.compile(
    r"^P(?:(?P<weeks>\\d+)W)?(?:(?P<days>\\d+)D)?"
    r"(?:T(?:(?P<hours>\\d+)H)?(?:(?P<minutes>\\d+)M)?(?:(?P<seconds>\\d+(?:\\.\\d+)?)S)?)?$"
)
_TIME_PARTS = ("hours", "minutes", "seconds")


class DateMathError(ValueError):
    """日期参数不合法。"""


def iso_week(day: date) -> tuple[int, int]:
    """ISO 周年与周数。注意不是 day.year。"""
    result = day.isocalendar()
    return result[0], result[1]


def weeks_in_year(year: int) -> int:
    """一年有 52 还是 53 个 ISO 周: 看 12-28 落在第几周。"""
    return iso_week(date(year, 12, 28))[1]


def format_week(day: date) -> str:
    """正确的周年-周写法, 与 strftime('%G-W%V') 等价, 与 '%Y-W%W' 不等价。"""
    year, week = iso_week(day)
    return f"{year:04d}-W{week:02d}"


def parse_week(text: str) -> tuple[int, int]:
    match = _WEEK_RE.match(text.strip())
    if not match:
        raise DateMathError("无法解析的周: " + repr(text) + ", 期望 2019-W01 或 2019W01")
    year, week = int(match.group(1)), int(match.group(2))
    total = weeks_in_year(year)
    if not 1 <= week <= total:
        raise DateMathError(f"{year} 年只有 {total} 个 ISO 周, 收到第 {week} 周")
    return year, week


def week_start(year: int, week: int, weekday: int = 1) -> date:
    """该周的某一天, weekday 1=周一 .. 7=周日。"""
    if not 1 <= weekday <= 7:
        raise DateMathError(f"weekday 必须在 1..7, 收到 {weekday}")
    total = weeks_in_year(year)
    if not 1 <= week <= total:
        raise DateMathError(f"{year} 年只有 {total} 个 ISO 周, 收到第 {week} 周")
    return date.fromisocalendar(year, week, weekday)


def week_range(day: date) -> tuple[date, date]:
    """所在周的周一到周日。"""
    year, week = iso_week(day)
    return week_start(year, week), week_start(year, week, 7)


def weekday_cn(day: date) -> str:
    return WEEKDAYS_CN[day.isoweekday() - 1]


def quarter(day: date) -> int:
    return (day.month - 1) // 3 + 1


def quarter_range(year: int, q: int) -> tuple[date, date]:
    if not 1 <= q <= 4:
        raise DateMathError(f"季度必须是 1..4, 收到 {q}")
    start_month = 3 * (q - 1) + 1
    start = date(year, start_month, 1)
    nxt = date(year + (1 if start_month == 10 else 0), (start_month + 3 - 1) % 12 + 1, 1)
    return start, nxt - timedelta(days=1)


def add_workdays(day: date, n: int) -> date:
    """往后(或往前)推 n 个工作日; 不处理节假日。"""
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    current = day
    while remaining:
        current += timedelta(days=step)
        if current.isoweekday() <= 5:
            remaining -= 1
    return current


def workdays_between(start: date, end: date) -> int:
    """[start, end) 之间的工作日数; end 早于 start 时返回负数。"""
    sign = 1
    if end < start:
        start, end = end, start
        sign = -1
    days = (end - start).days
    full_weeks, rest = divmod(days, 7)
    total = full_weeks * 5
    for offset in range(rest):
        if (start + timedelta(days=full_weeks * 7 + offset)).isoweekday() <= 5:
            total += 1
    return sign * total


def parse_duration(text: str) -> timedelta:
    """解析 ISO 8601 时长, 只支持 W/D/H/M/S。"""
    raw = text.strip().upper()
    match = _DURATION_RE.match(raw)
    if not match:
        raise DateMathError("无法解析的时长: " + repr(text))
    parts = match.groupdict()
    if not any(parts.values()):
        raise DateMathError("时长里至少要有一个分量: " + repr(text))
    if "T" in raw and not any(parts[name] for name in _TIME_PARTS):
        raise DateMathError("T 后面必须跟时间分量: " + repr(text))
    return timedelta(
        weeks=int(parts["weeks"] or 0),
        days=int(parts["days"] or 0),
        hours=int(parts["hours"] or 0),
        minutes=int(parts["minutes"] or 0),
        seconds=float(parts["seconds"] or 0),
    )


def format_duration(delta: timedelta) -> str:
    """把时长写成 1d 2h 30m 这种人读形式。"""
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    pieces: list[str] = []
    if days:
        pieces.append(f"{days}d")
    if hours:
        pieces.append(f"{hours}h")
    if minutes:
        pieces.append(f"{minutes}m")
    if seconds or not pieces:
        pieces.append(f"{seconds}s")
    return sign + " ".join(pieces)
''',
    "tests/test_calendar_ops.py": '''from datetime import date, timedelta

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
''',
}

CHALLENGE = {
    "target": "isoweek/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 isoweek/challenge.py 中实现 summarise(day: date) -> str: "
        "复用 isoweek.calendar_ops 里的 format_week / weekday_cn / quarter / week_range, "
        "返回一行形如 '2026-W46 周三 Q4 2026-11-09~2026-11-15' 的说明。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from datetime import date

from isoweek.challenge import summarise


def test_summary_shape() -> None:
    assert summarise(date(2026, 11, 11)) == "2026-W46 周三 Q4 2026-11-09~2026-11-15"


def test_year_boundary() -> None:
    line = summarise(date(2018, 12, 31))
    assert line.startswith("2019-W01")
    assert line.endswith("2018-12-31~2019-01-06")
''',
}
