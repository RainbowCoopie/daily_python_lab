# 显示宽度: 全部以"终端里占几列"为准。
from __future__ import annotations

import unicodedata

TAB_WIDTH = 4
AMBIGUOUS_WIDTH = 1

_ZERO_CATEGORIES = {"Mn", "Me", "Cf"}


def char_width(ch: str) -> int:
    """单个字符占几列。"""
    if len(ch) != 1:
        raise ValueError("char_width 只接受单个字符, 收到 " + repr(ch))
    if ch == "\t":
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
