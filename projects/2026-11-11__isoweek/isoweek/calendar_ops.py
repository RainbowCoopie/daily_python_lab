# ISO 周、季度、工作日与 ISO 时长。
from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

_WEEK_RE = re.compile(r"^(\d{4})-?[Ww](\d{1,2})$")
_DURATION_RE = re.compile(
    r"^P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
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
