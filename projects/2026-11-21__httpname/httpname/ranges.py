# Range: bytes=first-last / first- / -suffix。
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ByteRange:
    first: int | None
    last: int | None
    suffix: bool = False

    def resolve(self, size: int) -> tuple[int, int]:
        """按文件总大小落成具体的 (起始字节, 结束字节), 闭区间。"""
        if size < 0:
            raise ValueError("size 不能为负")
        if size == 0:
            return (0, -1)
        if self.suffix:
            length = min(self.last or 0, size)
            return (size - length, size - 1)
        start = self.first or 0
        end = size - 1 if self.last is None else min(self.last, size - 1)
        return (start, end)


def _digits(text: str) -> int | None:
    body = text.strip()
    if not body.isdigit():
        return None
    return int(body)


def parse_ranges(header: str) -> list[ByteRange] | None:
    """解析 Range 头。单位不是 bytes 或语法不合法时返回 None。"""
    body = str(header).strip()
    unit, _, spec = body.partition("=")
    if unit.strip().lower() != "bytes" or not spec.strip():
        return None

    parsed: list[ByteRange] = []
    for chunk in spec.split(","):
        part = chunk.strip()
        if not part or "-" not in part:
            return None
        left, _, right = part.partition("-")
        left, right = left.strip(), right.strip()

        if not left:
            length = _digits(right)
            if length is None or length == 0:
                return None
            parsed.append(ByteRange(first=None, last=length, suffix=True))
            continue

        start = _digits(left)
        if start is None:
            return None
        if not right:
            parsed.append(ByteRange(first=start, last=None))
            continue
        end = _digits(right)
        if end is None or end < start:
            return None
        parsed.append(ByteRange(first=start, last=end))

    return parsed or None
