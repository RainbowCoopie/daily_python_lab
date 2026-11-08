'''表格地址解析: Excel 列名的"双射 26 进制"、A1 引用、区域展开与边界校验。

灵感来自一个常见误解: 很多人以为 XFD 是普通 26 进制算出来的, 其实 Excel 的列名没有 "0 位",
A=1 而不是 A=0, 所以 Z→AA 之间没有"归零"那一步。用普通 base-26 转会在 Z/AA 边界集体错位。
'''

SLUG = "sheetref"
TITLE = "Excel 地址与列名解析器"
TAGS = ["Excel", "RPA 场景", "双射进制", "A1 引用"]
PKG = "sheetref"
SUMMARY = "列名与序号互转（双射 26 进制）、A1/$A$1 引用解析、区域展开、行列上限校验, 全是 RPA 里手写烂的那部分。"
STACK_NOTES = [
    "双射 26 进制: A=1 … Z=26, AA=27, XFD=16384, 与普通 base-26 在 Z 之后就开始分叉",
    "引用支持四种绝对/相对组合, 解析后能原样格式化回去",
    "区域展开带单元格上限保护, 避免 A1:XFD1048576 这种写法把内存打爆",
    r"边界按 Excel 真实上限校验: 16384 列 / 1048576 行, 超界抛 InvalidRef",
]
NOTES = """
为什么值得单独写一层: RPA 里拿到的公式文本是 `SUM($B$2:$D$9)` 这种, 要么正则硬抠, 要么手工算列号,
一旦遇到 AA 列之后就开始出错。这里的约定是——列名用双射 26 进制(没有 0), 行号是普通十进制(从 1 开始),
`$` 只是绝对引用的标记, 解析时保留, 格式化时还原。所以 `parse_ref("$AB$12")` 再 `format_ref` 出来
一定还是 `$AB$12`, 不会悄悄丢掉美元号。
"""

FILES = {
    "sheetref/__init__.py": '''from .refs import (
    MAX_COL,
    MAX_ROW,
    InvalidRef,
    RangeTooLarge,
    Ref,
    col_to_index,
    expand_range,
    format_ref,
    index_to_col,
    parse_range,
    parse_ref,
)

__all__ = [
    "MAX_COL",
    "MAX_ROW",
    "InvalidRef",
    "RangeTooLarge",
    "Ref",
    "col_to_index",
    "index_to_col",
    "parse_ref",
    "format_ref",
    "parse_range",
    "expand_range",
]
''',
    "sheetref/refs.py": '''# Excel 地址解析: 双射 26 进制列名 + A1 引用 + 区域。
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_COL = 16384   # XFD
MAX_ROW = 1048576  # 最后一行

_REF_RE = re.compile(r"^(\\$?)([A-Za-z]{1,3})(\\$?)(\\d{1,7})$")


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
''',
    "tests/test_refs.py": '''import pytest

from sheetref import (
    MAX_COL,
    MAX_ROW,
    InvalidRef,
    RangeTooLarge,
    Ref,
    col_to_index,
    expand_range,
    format_ref,
    index_to_col,
    parse_range,
    parse_ref,
)


@pytest.mark.parametrize(
    "name,index",
    [("A", 1), ("B", 2), ("Z", 26), ("AA", 27), ("AZ", 52), ("BA", 53), ("ZZ", 702), ("AAA", 703), ("XFD", 16384)],
)
def test_col_to_index_known_values(name: str, index: int) -> None:
    assert col_to_index(name) == index
    assert index_to_col(index) == name


@pytest.mark.parametrize("index", [1, 25, 26, 27, 52, 53, 702, 703, 16384])
def test_roundtrip(index: int) -> None:
    assert col_to_index(index_to_col(index)) == index


def test_lowercase_accepted() -> None:
    assert col_to_index("xfd") == 16384


def test_col_limits() -> None:
    with pytest.raises(InvalidRef):
        col_to_index("XFE")          # 超出一列
    with pytest.raises(InvalidRef):
        col_to_index("ABCD")         # 四字母
    with pytest.raises(InvalidRef):
        col_to_index("")
    with pytest.raises(InvalidRef):
        index_to_col(0)
    with pytest.raises(InvalidRef):
        index_to_col(MAX_COL + 1)


def test_parse_relative() -> None:
    ref = parse_ref("B12")
    assert (ref.col, ref.row) == (2, 12)
    assert (ref.abs_col, ref.abs_row) == (False, False)


def test_parse_absolute() -> None:
    ref = parse_ref("$AB$12")
    assert (ref.col, ref.row) == (28, 12)
    assert (ref.abs_col, ref.abs_row) == (True, True)
    assert format_ref(ref) == "$AB$12"


def test_parse_mixed_and_roundtrip() -> None:
    for text in ("A1", "$A1", "A$1", "$A$1", "$XFD$1048576"):
        assert format_ref(parse_ref(text)) == text


@pytest.mark.parametrize("bad", ["", "1A", "A", "A0", "A1048577", "A1B", "$", "A1:A2:A3"])
def test_invalid_refs(bad: str) -> None:
    with pytest.raises(InvalidRef):
        parse_ref(bad)


def test_row_limit() -> None:
    assert parse_ref("A" + str(MAX_ROW)).row == MAX_ROW
    with pytest.raises(InvalidRef):
        parse_ref("A" + str(MAX_ROW + 1))


def test_parse_range_single_cell() -> None:
    start, end = parse_range("C3")
    assert start == end == Ref(col=3, row=3)


def test_expand_range_row_major() -> None:
    assert expand_range("A1:B2") == ["A1", "B1", "A2", "B2"]


def test_expand_range_normalizes_reversed_input() -> None:
    assert expand_range("B2:A1") == ["A1", "B1", "A2", "B2"]


def test_expand_range_guard() -> None:
    with pytest.raises(RangeTooLarge):
        expand_range("A1:XFD1048576", limit=1000)


def test_expand_range_keeps_absolute_markers_out_of_cells() -> None:
    assert expand_range("$A$1:$B$1") == ["A1", "B1"]
''',
}

CHALLENGE = {
    "target": "sheetref/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 sheetref/challenge.py 中实现 shift_ref(text: str, d_row: int, d_col: int) -> str: "
        "把 A1 形式的引用按行列偏移移动, 返回不带 $ 的普通引用。"
        "要求复用 sheetref.refs 里的 parse_ref / index_to_col / MAX_COL / MAX_ROW; "
        "结果越界(行<1 或 >MAX_ROW, 列<1 或 >MAX_COL)时抛 InvalidRef。"
    ),
    "tests_content": '''import pytest

from sheetref.challenge import shift_ref
from sheetref.refs import InvalidRef


def test_shift_basic() -> None:
    assert shift_ref("A1", 1, 0) == "A2"
    assert shift_ref("A1", 0, 1) == "B1"


def test_shift_across_columns() -> None:
    assert shift_ref("Z1", 0, 1) == "AA1"


def test_shift_drops_absolute_markers() -> None:
    assert shift_ref("$A$1", 1, 1) == "B2"


def test_shift_out_of_bounds() -> None:
    with pytest.raises(InvalidRef):
        shift_ref("A1", -1, 0)
    with pytest.raises(InvalidRef):
        shift_ref("XFD1", 0, 1)
''',
}
