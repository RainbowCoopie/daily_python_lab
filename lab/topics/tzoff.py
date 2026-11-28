'''时区偏移与时间戳解析: 保住 `-00:00` 这个"偏移未知"的语义, 别被 datetime 抹平。

灵感来源:
- RFC 3339 第 4.3 节: `-00:00` 表示"UTC 时间已知, 但到本地时间的偏移未知",
  这与 `Z` / `+00:00`(表示本地就以 UTC 为基准) 语义不同
  (https://mail.python.org/pipermail/python-bugs-list/2010-May/099384.html)
- RFC 9557 把这条改了, 现在推荐用 `Z` 表示"偏移未知"; `-00:00` 因为 ISO 8601:2000 不允许,
  互操作性较差 —— 但历史上发出的数据里它确实存在, 解析时不能当没看见
  (https://mailarchive.ietf.org/arch/msg/auth48archive/4T7QxtqpSVG1GWbstEeSZiageaw/)
- 偏移的合法范围在实践中取 ±18:00(Java 的 ZoneOffset 就是按这个范围校验)
  (https://developers.google.com/j2objc/javadoc/jre/reference/java/time/ZoneOffset.html)

为什么值得单独做一层: `datetime.fromisoformat("2026-11-28T09:30:00-00:00")` 和
`"...+00:00"` 得到的 `utcoffset()` 都是 0, 两者**无法区分**。业务上这个区别有意义:
前者说明"这个时间点在 UTC 上确定, 但不知道它在哪儿发生", 后者说明"它发生在 UTC 时区"。
另外 3.11 之前 `fromisoformat` 连 `Z` 都不认, 老代码里那堆字符串替换的补丁就是这么来的。
'''

SLUG = "tzoff"
TITLE = "时区偏移与时间戳解析"
TAGS = ["RFC 3339", "时区偏移", "-00:00 语义", "datetime"]
PKG = "tzoff"
SUMMARY = '解析 +08:00 / Z / GMT+8 / -00:00 各种偏移, 并把「偏移未知」这个语义与「偏移为零」分开保留。'
STACK_NOTES = [
    "`-00:00` 解析成「零偏移但未知」, 与 `Z`/`+00:00` 区分开 —— datetime 本身会丢这个信息",
    "偏移范围按 ±18:00 校验, 分钟数必须小于 60",
    "时间戳拆成「本地时间 + 偏移」两段存, 换算到 UTC 是显式动作而不是隐式发生",
]
NOTES = """
为什么不能直接 `datetime.fromisoformat` 了事:

```python
datetime.fromisoformat("2026-11-28T09:30:00-00:00").utcoffset()   # timedelta(0)
datetime.fromisoformat("2026-11-28T09:30:00+00:00").utcoffset()   # timedelta(0)
```

两者一模一样 —— 语义差别在构造时就丢了。所以本模块自己扫尾部的偏移串, 单独保留
一个 `unknown` 标记, 再把时间部分交给 `fromisoformat`。

支持的偏移写法: `Z` / `+08:00` / `-05:30` / `+0800` / `GMT+8` / `UTC+05:30` / `UTC` / `GMT`。
**不支持**裸的 `+08`(只有小时没有分钟) —— 因为它和日期里的 `-28` 这类片段太容易混淆,
宁可让调用方把数据洗干净。这是刻意的取舍, 不是遗漏。
"""

FILES = {
    "tzoff/__init__.py": '''from .offset import MAX_OFFSET, Offset, format_offset, parse_offset
from .stamp import Stamp, format_stamp, parse_stamp, same_instant

__all__ = [
    "MAX_OFFSET",
    "Offset",
    "parse_offset",
    "format_offset",
    "Stamp",
    "parse_stamp",
    "format_stamp",
    "same_instant",
]
''',
    "tzoff/offset.py": '''# 偏移解析与格式化。
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

MAX_OFFSET = timedelta(hours=18)

_SIGNED = re.compile(r"^(?P<sign>[+-])(?P<hours>\\d{2}):?(?P<minutes>\\d{2})$")
_PREFIXED = re.compile(r"^(?:UTC|GMT)(?P<rest>.*)$", re.IGNORECASE)
# 只在前缀形式里允许"只有小时"的写法: GMT+8 没有歧义, 裸 "+8" 会与日期片段混淆
_BARE_HOURS = re.compile(r"^(?P<sign>[+-])(?P<hours>\\d{1,2})$")


@dataclass(frozen=True)
class Offset:
    """UTC 偏移。unknown=True 表示 RFC 3339 的 `-00:00`: 偏移未知, 而不是偏移为零。"""

    delta: timedelta
    unknown: bool = False

    @property
    def minutes(self) -> int:
        return int(self.delta.total_seconds()) // 60


def parse_offset(text: str) -> Offset:
    body = str(text).strip()
    if not body:
        raise ValueError("空的偏移字符串")

    if body in ("Z", "z"):
        return Offset(timedelta(0), unknown=False)

    prefixed = _PREFIXED.match(body)
    if prefixed:
        rest = prefixed.group("rest").strip()
        if not rest:
            return Offset(timedelta(0), unknown=False)
        bare = _BARE_HOURS.match(rest)
        if bare:
            sign = -1 if bare.group("sign") == "-" else 1
            hours = int(bare.group("hours"))
            if hours > 18:
                raise ValueError("偏移超出 ±18:00 范围: " + repr(text))
            return Offset(sign * timedelta(hours=hours), unknown=(sign < 0 and hours == 0))
        body = rest

    match = _SIGNED.match(body)
    if not match:
        raise ValueError(
            "无法识别的偏移 " + repr(text) + ", 支持 Z / +08:00 / +0800 / GMT+8"
        )

    sign = -1 if match.group("sign") == "-" else 1
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    if minutes >= 60:
        raise ValueError("分钟数必须小于 60, 收到 " + repr(text))

    delta = sign * timedelta(hours=hours, minutes=minutes)
    if abs(delta) > MAX_OFFSET:
        raise ValueError("偏移超出 ±18:00 范围: " + repr(text))

    # 只有 "-00:00" 这一个写法带"未知"语义
    unknown = sign < 0 and hours == 0 and minutes == 0
    return Offset(delta, unknown=unknown)


def format_offset(offset: Offset) -> str:
    if offset.unknown:
        return "-00:00"
    if offset.delta == timedelta(0):
        return "Z"
    total = int(offset.delta.total_seconds()) // 60
    sign = "+" if total >= 0 else "-"
    hours, minutes = divmod(abs(total), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"
''',
    "tzoff/stamp.py": '''# 时间戳: 本地时间 + 偏移, 分开存。
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .offset import Offset, format_offset, parse_offset

# 只认 ±HH:MM / ±HHMM / Z 结尾, 避免把日期里的 "-28" 误当成偏移
_TAIL = re.compile(r"(?P<offset>[Zz]|[+-]\\d{2}:?\\d{2})$")


@dataclass(frozen=True)
class Stamp:
    naive: datetime
    offset: Offset

    @property
    def utc(self) -> datetime:
        """换算成 UTC 的 naive datetime。"""
        return self.naive - self.offset.delta


def parse_stamp(text: str) -> Stamp:
    body = str(text).strip()
    if not body:
        raise ValueError("空的时间戳")

    match = _TAIL.search(body)
    if not match:
        raise ValueError("时间戳缺少时区偏移: " + repr(text))

    offset = parse_offset(match.group("offset"))
    try:
        naive = datetime.fromisoformat(body[: match.start()])
    except ValueError as exc:
        raise ValueError("无法解析的时间部分: " + repr(text)) from exc
    return Stamp(naive=naive, offset=offset)


def format_stamp(stamp: Stamp) -> str:
    return stamp.naive.isoformat() + format_offset(stamp.offset)


def same_instant(left: Stamp, right: Stamp) -> bool:
    """不同偏移下的同一时刻。"""
    return left.utc == right.utc
''',
    "tests/test_offset.py": '''import pytest
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
''',
    "tests/test_stamp.py": '''import pytest
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
''',
}

CHALLENGE = {
    "target": "tzoff/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 tzoff/challenge.py 中实现 describe(text: str) -> str: "
        "解析时间戳, 返回 '2026-11-28T01:30:00Z (偏移未知)' 这种说明; "
        "偏移已知时只返回 UTC 时间, 未知时在末尾追加 ' (偏移未知)'。"
        "复用 tzoff.stamp.parse_stamp 与 tzoff.offset.format_offset, 不得修改其他模块。"
    ),
    "tests_content": '''from tzoff.challenge import describe


def test_known_offset() -> None:
    assert describe("2026-11-28T09:30:00+08:00") == "2026-11-28T01:30:00Z"


def test_unknown_offset_marked() -> None:
    assert describe("2026-11-28T01:30:00-00:00").endswith("(偏移未知)")
''',
}
