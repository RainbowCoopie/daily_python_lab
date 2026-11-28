# 时间戳: 本地时间 + 偏移, 分开存。
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .offset import Offset, format_offset, parse_offset

# 只认 ±HH:MM / ±HHMM / Z 结尾, 避免把日期里的 "-28" 误当成偏移
_TAIL = re.compile(r"(?P<offset>[Zz]|[+-]\d{2}:?\d{2})$")


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
