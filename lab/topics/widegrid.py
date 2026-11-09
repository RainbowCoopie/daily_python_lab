'''显示宽度与表格对齐: 一个中文算两列, 组合符算零列, 于是"按 len() 对齐"必然错。

灵感来源:
- 一个真实 bug 报告: 表格列宽按字符数计算, 含中文的单元格撑破右边框
  (https://atomgit.com/cann/oam-tools/issues/348)
- wcwidth 库把 East Asian Width 的 W/F 记两列、组合符记零列的做法
  (https://github.com/jquast/wcwidth)
- ftfy 对乱码给出"坏度"分数的思路, 说明"看起来对"和"列数对"是两件事

为什么值得单独做一层: 日志、CLI 报告、RPA 导出预览、聊天机器人回复, 全都要对齐。
只要有一列含中文, 用 len() 算出来的空格数就是错的, 错多少取决于那一列有几个汉字。
'''

SLUG = "widegrid"
TITLE = "显示宽度与表格对齐"
TAGS = ["终端渲染", "East Asian Width", "CJK 对齐", "stdlib"]
PKG = "widegrid"
SUMMARY = "按显示列宽而不是字符数计算: 中文/全角算 2、组合符算 0, 再做安全截断、填充和多列对齐渲染。"
STACK_NOTES = [
    "East Asian Width 的 W/F 记 2 列, Mn/Me/Cf 类别记 0 列, 其余 1 列",
    "截断不会把一个汉字劈成半个: 预算按列算, 塞不下就提前停, 再补省略号",
    "渲染出来的每一行显示宽度严格相等, 用属性测试逐行校验",
]
NOTES = """
核心约定只有一条: **一切以显示列宽为准, 不用 len()**。
`len("中文") == 2` 但显示占 4 列; `len("e\\u0301") == 2` 但显示占 1 列。
这两个方向相反的坑, 只要暴露在同一个 `text_width()` 里, 上层就不用再各自算一遍。

Ambiguous(不明确宽度)字符默认按 1 列处理 —— 这是大多数终端和等宽字体的行为,
若要贴到 CJK 环境的终端里, 可以自行把 AMBIGUOUS_WIDTH 调成 2。
"""

FILES = {
    "widegrid/__init__.py": '''from .table import render
from .width import char_width, pad, text_width, truncate

__all__ = ["char_width", "text_width", "truncate", "pad", "render"]
''',
    "widegrid/width.py": '''# 显示宽度: 全部以"终端里占几列"为准。
from __future__ import annotations

import unicodedata

TAB_WIDTH = 4
AMBIGUOUS_WIDTH = 1

_ZERO_CATEGORIES = {"Mn", "Me", "Cf"}


def char_width(ch: str) -> int:
    """单个字符占几列。"""
    if len(ch) != 1:
        raise ValueError("char_width 只接受单个字符, 收到 " + repr(ch))
    if ch == "\\t":
        return TAB_WIDTH
    if unicodedata.combining(ch):
        return 0
    if unicodedata.category(ch) in _ZERO_CATEGORIES:
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    if unicodedata.east_asian_width(ch) == "A":
        return AMBIGUOUS_WIDTH
    return 1


def text_width(text: str) -> int:
    """整串占几列。"""
    return sum(char_width(ch) for ch in text)


def truncate(text: str, limit: int, ellipsis: str = "…") -> str:
    """截到不超过 limit 列; 放得下就原样返回, 放不下则补省略号。"""
    if limit <= 0:
        return ""
    if text_width(text) <= limit:
        return text
    budget = limit - text_width(ellipsis)
    if budget <= 0:
        return ""
    used = 0
    kept: list[str] = []
    for ch in text:
        w = char_width(ch)
        if used + w > budget:
            break
        kept.append(ch)
        used += w
    return "".join(kept) + ellipsis


def pad(text: str, width: int, align: str = "left") -> str:
    """按显示列宽补空格; 已经够宽则原样返回。"""
    if align not in ("left", "right", "center"):
        raise ValueError("align 只能是 left / right / center, 收到 " + repr(align))
    gap = width - text_width(text)
    if gap <= 0:
        return text
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap
''',
    "widegrid/table.py": '''# 表格渲染: 先算每列最大显示宽度, 再逐格填充。
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
    return "\\n".join(out)
''',
    "tests/test_width.py": '''import pytest

from widegrid import char_width, pad, text_width, truncate


def test_ascii_width() -> None:
    assert text_width("hello") == 5
    assert char_width("a") == 1


def test_cjk_counts_two() -> None:
    assert char_width("中") == 2
    assert text_width("中文") == 4
    assert text_width("abc中文") == 7


def test_fullwidth_forms_count_two() -> None:
    assert char_width("Ａ") == 2        # 全角 A
    assert char_width("。") == 2        # 全角句号


def test_combining_mark_counts_zero() -> None:
    assert char_width("\\u0301") == 0
    assert text_width("e\\u0301") == 1


def test_zero_width_category_counts_zero() -> None:
    assert char_width("\\u200b") == 0   # 零宽空格


def test_emoji_counts_two() -> None:
    assert char_width("😀") == 2


def test_tab_is_four() -> None:
    assert char_width("\\t") == 4


def test_char_width_rejects_multi() -> None:
    with pytest.raises(ValueError):
        char_width("ab")


def test_truncate_noop_when_fits() -> None:
    assert truncate("abc", 5) == "abc"
    assert truncate("中文", 4) == "中文"


def test_truncate_respects_display_columns() -> None:
    assert truncate("中文字符", 5) == "中文…"
    assert truncate("中文字符", 4) == "中…"
    assert truncate("中文字符", 3) == "中…"
    assert truncate("中文字符", 2) == "…"


def test_truncate_zero_and_negative() -> None:
    assert truncate("abc", 0) == ""
    assert truncate("abc", -3) == ""


def test_truncate_custom_ellipsis() -> None:
    assert truncate("abcdef", 5, ellipsis="..") == "abc.."


def test_truncate_result_never_exceeds_limit() -> None:
    for limit in range(0, 12):
        assert text_width(truncate("中文abcdef混合", limit)) <= limit


def test_pad_aligns() -> None:
    assert pad("中", 4) == "中  "
    assert pad("中", 4, "right") == "  中"
    assert pad("中", 5, "center") == " 中  "
    assert pad("中", 4, "center") == " 中 "


def test_pad_noop_when_wide_enough() -> None:
    assert pad("中文", 2) == "中文"


def test_pad_rejects_bad_align() -> None:
    with pytest.raises(ValueError):
        pad("a", 3, "middle")
''',
    "tests/test_table.py": '''import pytest

from widegrid import render, text_width


def widths_of(text: str) -> set[int]:
    return {text_width(line) for line in text.splitlines()}


def test_render_plain_rows() -> None:
    out = render([["a", "bb"], ["cc", "d"]])
    assert out.splitlines() == ["a  | bb", "cc | d "]


def test_render_with_headers_and_separator() -> None:
    out = render([["1", "2"]], headers=["左", "右"])
    lines = out.splitlines()
    assert lines[0] == "左 | 右"
    assert set(lines[1].replace(" ", "")) == {"-", "|"}
    assert lines[2] == "1  | 2 "


def test_every_line_has_same_display_width_with_cjk() -> None:
    out = render(
        [["中文", "x"], ["a", "两个字"]],
        headers=["名称", "值"],
    )
    assert len(widths_of(out)) == 1


def test_right_alignment_for_numbers() -> None:
    out = render([["1", "10"], ["100", "2"]], aligns=["right", "right"])
    lines = out.splitlines()
    assert lines[0] == "  1 | 10"
    assert lines[1] == "100 |  2"


def test_ragged_rows_are_padded() -> None:
    out = render([["a", "b"], ["c"]])
    assert widths_of(out) == {5}


def test_empty_input() -> None:
    assert render([]) == ""
    assert render([], headers=[]) == ""


def test_max_width_truncates_cells() -> None:
    out = render([["中文字符很长", "b"]], max_width=5)
    assert out.splitlines()[0].startswith("中文…")
    assert len(widths_of(out)) == 1


def test_aligns_length_must_match() -> None:
    with pytest.raises(ValueError):
        render([["a", "b"]], aligns=["left"])


def test_max_width_must_be_positive() -> None:
    with pytest.raises(ValueError):
        render([["a"]], max_width=0)


def test_separator_row_can_be_disabled() -> None:
    out = render([["1"]], headers=["h"], separator_row=False)
    assert len(out.splitlines()) == 2
''',
}

CHALLENGE = {
    "target": "widegrid/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 widegrid/challenge.py 中实现 wrap(text: str, width: int) -> list[str]: "
        "按显示列宽折行, 每行显示宽度不超过 width; 遇到换行符强制断行; "
        "不能把一个宽字符劈开(放不下就换行); 空文本返回 ['']。"
        "复用 widegrid.width 里的 text_width 与 char_width, 不得修改其他模块。"
    ),
    "tests_content": '''import pytest

from widegrid.challenge import wrap
from widegrid.width import text_width


def test_ascii_wrap() -> None:
    assert wrap("abcdef", 3) == ["abc", "def"]


def test_cjk_wrap_respects_columns() -> None:
    assert wrap("中文字符", 4) == ["中文", "字符"]


def test_hard_break_on_newline() -> None:
    assert wrap("ab\\ncd", 10) == ["ab", "cd"]


def test_empty_text() -> None:
    assert wrap("", 5) == [""]


def test_never_exceeds_width() -> None:
    for w in range(1, 6):
        for line in wrap("中文abc混合", w):
            assert text_width(line) <= w
''',
}
