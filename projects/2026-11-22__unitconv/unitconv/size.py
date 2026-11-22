# 容量: SI(1000) 与 IEC(1024) 分表。
from __future__ import annotations

import re

SI_UNITS: dict[str, int] = {
    "b": 1,
    "kb": 1000,
    "mb": 1000 ** 2,
    "gb": 1000 ** 3,
    "tb": 1000 ** 4,
    "pb": 1000 ** 5,
}

IEC_UNITS: dict[str, int] = {
    "kib": 1024,
    "mib": 1024 ** 2,
    "gib": 1024 ** 3,
    "tib": 1024 ** 4,
    "pib": 1024 ** 5,
}

# 裸 K/M/G 是歧义: 默认按 1024, 严格模式下直接拒绝
AMBIGUOUS_UNITS: dict[str, int] = {
    "k": 1024,
    "m": 1024 ** 2,
    "g": 1024 ** 3,
    "t": 1024 ** 4,
    "p": 1024 ** 5,
}

_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*([a-z]*)$")

FORMAT_ORDER_SI = (("PB", 1000 ** 5), ("TB", 1000 ** 4), ("GB", 1000 ** 3), ("MB", 1000 ** 2), ("KB", 1000), ("B", 1))
FORMAT_ORDER_IEC = (("PiB", 1024 ** 5), ("TiB", 1024 ** 4), ("GiB", 1024 ** 3), ("MiB", 1024 ** 2), ("KiB", 1024), ("B", 1))


class AmbiguousUnitError(ValueError):
    """裸 K/M/G 之类的写法无法确定是 1000 还是 1024。"""


def parse_size(text: object, *, strict: bool = False) -> int:
    """把 '1.5GiB' / '1.5 GB' / '2048' 解析成字节数。"""
    body = str(text).strip().lower().replace(" ", "")
    if not body:
        raise ValueError("空的容量字符串")
    match = _PATTERN.match(body)
    if not match:
        raise ValueError("无法解析的容量: " + repr(text))
    number, unit = match.group(1), match.group(2)

    if unit == "":
        multiplier = 1
    elif unit in SI_UNITS:
        multiplier = SI_UNITS[unit]
    elif unit in IEC_UNITS:
        multiplier = IEC_UNITS[unit]
    elif unit in AMBIGUOUS_UNITS:
        if strict:
            raise AmbiguousUnitError(
                "单位 " + repr(unit) + " 有歧义: 写 KB(1000) 还是 KiB(1024)?"
            )
        multiplier = AMBIGUOUS_UNITS[unit]
    else:
        raise ValueError("不认识的单位 " + repr(unit))

    return int(round(float(number) * multiplier))


def _render(value: float, precision: int) -> str:
    text = f"{value:.{precision}f}" if precision > 0 else f"{value:.0f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_size(size: int, *, binary: bool = False, precision: int = 1) -> str:
    """字节数 -> '1.5KiB'(binary) 或 '1.5KB'(默认)。"""
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("size 必须是 int")
    if size < 0:
        raise ValueError("size 不能为负")
    if precision < 0:
        raise ValueError("precision 不能为负")

    order = FORMAT_ORDER_IEC if binary else FORMAT_ORDER_SI
    for suffix, scale in order:
        if size >= scale:
            return _render(size / scale, precision) + suffix
    return "0B"
