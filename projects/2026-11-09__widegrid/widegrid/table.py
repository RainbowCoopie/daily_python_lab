# 表格渲染: 先算每列最大显示宽度, 再逐格填充。
from __future__ import annotations

from typing import Iterable, Sequence

from .width import pad, text_width, truncate

DEFAULT_SEP = " | "


def _cell_text(value: object) -> str:
    return "" if value is None else str(value)


def render(
    rows: Iterable[Sequence[object]],
    headers: Sequence[object] | None = None,
    aligns: Sequence[str] | None = None,
    sep: str = DEFAULT_SEP,
    max_width: int | None = None,
    separator_row: bool = True,
) -> str:
    """渲染等宽表格。返回的每一行显示宽度严格相等。"""
    body = [[_cell_text(c) for c in row] for row in rows]
    head = [_cell_text(c) for c in headers] if headers is not None else None

    columns = max([len(r) for r in body] + ([len(head)] if head else [0]), default=0)
    if columns == 0:
        return ""

    if max_width is not None:
        if max_width <= 0:
            raise ValueError("max_width 必须为正数")
        head = [truncate(c, max_width) for c in head] if head else head
        body = [[truncate(c, max_width) for c in row] for row in body]

    widths = [0] * columns
    for row in ([head] if head else []) + body:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], text_width(cell))

    if aligns is None:
        aligns = ["left"] * columns
    if len(aligns) != columns:
        raise ValueError(f"aligns 长度 {len(aligns)} 与列数 {columns} 不符")

    def line(cells: Sequence[str]) -> str:
        # 按列数遍历而不是按行长度: 参差的行要补空列, 否则整行会短一截
        parts = [
            pad(cells[i] if i < len(cells) else "", widths[i], aligns[i])
            for i in range(columns)
        ]
        # 注意: 这里不能 rstrip。去掉尾部补白, 最后一列的宽度就短了,
        # 整行宽度不再相等, 表格在终端里就会歪。
        return sep.join(parts)

    out: list[str] = []
    if head:
        out.append(line(head))
        if separator_row:
            out.append(sep.join("-" * w for w in widths))
    out.extend(line(row) for row in body)
    return "\n".join(out)
