# 时长: systemd 风格 1h30m。
from __future__ import annotations

import re

SPAN_UNITS: dict[str, float] = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
    "w": 604800.0,
}

# ms 必须排在 m 前面, 否则 "10ms" 会被切成 10m + s
_PIECE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h|d|w)")


def parse_span(text: object) -> float:
    """把 '1h30m' / '90s' / '1.5h' 解析成秒; 纯数字按秒。"""
    body = str(text).strip().lower().replace(" ", "")
    if not body:
        raise ValueError("空的时长字符串")
    if body.replace(".", "", 1).isdigit():
        return float(body)

    total = 0.0
    position = 0
    for match in _PIECE.finditer(body):
        if match.start() != position:
            raise ValueError("无法解析的时长: " + repr(text))
        total += float(match.group(1)) * SPAN_UNITS[match.group(2)]
        position = match.end()
    if position != len(body):
        raise ValueError("无法解析的时长: " + repr(text))
    return total


_ORDER = (("w", 604800000), ("d", 86400000), ("h", 3600000), ("m", 60000), ("s", 1000), ("ms", 1))


def format_span(seconds: float) -> str:
    """秒 -> '2h30m1s'; 支持毫秒(0.5 -> 500ms)。"""
    value = float(seconds)
    if value < 0:
        raise ValueError("时长不能为负")
    remaining = int(round(value * 1000))
    if remaining == 0:
        return "0s"

    parts: list[str] = []
    for suffix, unit_ms in _ORDER:
        if remaining >= unit_ms:
            count, remaining = divmod(remaining, unit_ms)
            parts.append(f"{count}{suffix}")
    return "".join(parts)
