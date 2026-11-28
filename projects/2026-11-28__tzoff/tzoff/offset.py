# 偏移解析与格式化。
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

MAX_OFFSET = timedelta(hours=18)

_SIGNED = re.compile(r"^(?P<sign>[+-])(?P<hours>\d{2}):?(?P<minutes>\d{2})$")
_PREFIXED = re.compile(r"^(?:UTC|GMT)(?P<rest>.*)$", re.IGNORECASE)
# 只在前缀形式里允许"只有小时"的写法: GMT+8 没有歧义, 裸 "+8" 会与日期片段混淆
_BARE_HOURS = re.compile(r"^(?P<sign>[+-])(?P<hours>\d{1,2})$")


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
