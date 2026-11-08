# Excel 地址解析: 双射 26 进制列名 + A1 引用 + 区域。
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_COL = 16384   # XFD
MAX_ROW = 1048576  # 最后一行

_REF_RE = re.compile(r"^(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})$")


class InvalidRef(ValueError):
    """不是合法的 A1 引用, 或者超出 Excel 的行列上限。"""


class RangeTooLarge(ValueError):
    """区域展开超过允许的单元格数量。"""


@dataclass(frozen=True)
class Ref:
    col: int          # 1-based
    row: int          # 1-based
    abs_col: bool = False
    abs_row: bool = False

    def __str__(self) -> str:
        return format_ref(self)


def col_to_index(name: str) -> int:
    """列名 -> 序号。双射 26 进制: A=1, Z=26, AA=27, XFD=16384。"""
    if not name or not name.isalpha() or len(name) > 3:
        raise InvalidRef("列名必须是 1~3 个字母, 收到 " + repr(name))
    total = 0
    for ch in name.upper():
        total = total * 26 + (ord(ch) - 64)
    if total > MAX_COL:
        raise InvalidRef(f"列 {name.upper()} 超出上限 XFD({MAX_COL})")
    return total


def index_to_col(index: int) -> str:
    """序号 -> 列名。注意这里不能用普通 divmod, 要先减 1 再取模。"""
    if not isinstance(index, int) or isinstance(index, bool):
        raise InvalidRef("列序号必须是 int")
    if not 1 <= index <= MAX_COL:
        raise InvalidRef(f"列序号必须在 1..{MAX_COL}, 收到 {index}")
    out: list[str] = []
    n = index
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out.append(chr(65 + rem))
    return "".join(reversed(out))


def parse_ref(text: str) -> Ref:
    """解析 A1 / $A$1 / A$1 / $A1。"""
    match = _REF_RE.match(text.strip())
    if not match:
        raise InvalidRef("无法解析的引用: " + repr(text))
    abs_col, letters, abs_row, digits = match.groups()
    col = col_to_index(letters)
    row = int(digits)
    if not 1 <= row <= MAX_ROW:
        raise InvalidRef(f"行号必须在 1..{MAX_ROW}, 收到 {row}")
    return Ref(col=col, row=row, abs_col=bool(abs_col), abs_row=bool(abs_row))


def format_ref(ref: Ref) -> str:
    col = ("$" if ref.abs_col else "") + index_to_col(ref.col)
    row = ("$" if ref.abs_row else "") + str(ref.row)
    return col + row


def parse_range(text: str) -> tuple[Ref, Ref]:
    """解析 A1:B2; 单格 A1 视作起止相同。"""
    parts = text.split(":")
    if len(parts) == 1:
        ref = parse_ref(parts[0])
        return ref, ref
    if len(parts) != 2:
        raise InvalidRef("区域最多只能有一个冒号: " + repr(text))
    return parse_ref(parts[0]), parse_ref(parts[1])


def expand_range(text: str, limit: int = 10000) -> list[str]:
    """把区域摊平成单元格列表(按行优先), 超过 limit 直接拒绝。"""
    start, end = parse_range(text)
    rows = abs(end.row - start.row) + 1
    cols = abs(end.col - start.col) + 1
    if rows * cols > limit:
        raise RangeTooLarge(f"区域 {text} 有 {rows * cols} 个单元格, 超过 limit={limit}")
    r_lo, r_hi = sorted((start.row, end.row))
    c_lo, c_hi = sorted((start.col, end.col))
    return [
        index_to_col(c) + str(r)
        for r in range(r_lo, r_hi + 1)
        for c in range(c_lo, c_hi + 1)
    ]
