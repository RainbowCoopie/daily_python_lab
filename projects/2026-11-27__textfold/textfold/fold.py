# 等价归一: 只收敛写法, 不删信息。
from __future__ import annotations

import re
import unicodedata

# 显式列出要清的不可见字符 —— 不能按类别 Cf 整类删, 那会误伤 ZWJ
INVISIBLE = frozenset(
    {
        "\u200b",  # 零宽空格
        "\u200c",  # 零宽不连字
        "\u00ad",  # 软连字符
        "\ufeff",  # BOM / 零宽不换行空格
        "\u2060",  # 单词连接符
        "\u180e",  # 蒙古文元音分隔符
        "\u200e", "\u200f",                      # 左右到右/右到左标记
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # 双向嵌入与覆盖
        "\u2066", "\u2067", "\u2068", "\u2069",             # 双向隔离
    }
)

# 刻意保留: U+200D(ZWJ) 是 emoji 家族序列的连接符, 删了会把它们拆散
PRESERVED = frozenset({"\u200d"})

QUOTES = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u00ab": '"', "\u00bb": '"',
}

DASHES = {ch: "-" for ch in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u2043"}

SPACES = {ch: " " for ch in "\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"}

_MULTI_SPACE = re.compile(r"\s+")


def strip_invisible(text: str) -> str:
    """删掉不可见的格式字符, 保留 ZWJ 这类有语义的。"""
    return "".join(ch for ch in text if ch in PRESERVED or ch not in INVISIBLE)


def fold_quotes(text: str) -> str:
    return "".join(QUOTES.get(ch, ch) for ch in text)


def fold_dashes(text: str) -> str:
    return "".join(DASHES.get(ch, ch) for ch in text)


def fold_spaces(text: str) -> str:
    return "".join(SPACES.get(ch, ch) for ch in text)


def nfkc(text: str) -> str:
    """兼容归一: 全角字母变半角, 圈号数字变普通数字。"""
    return unicodedata.normalize("NFKC", text)


def fold(text: str, *, case: bool = True, collapse_ws: bool = True) -> str:
    """把等价写法收敛成一种。默认也做大小写折叠。"""
    body = nfkc(str(text))
    body = strip_invisible(body)
    body = fold_quotes(body)
    body = fold_dashes(body)
    body = fold_spaces(body)
    if case:
        body = body.casefold()
    if collapse_ws:
        body = _MULTI_SPACE.sub(" ", body).strip()
    return body


def skeleton(text: str) -> str:
    """只留字母数字与汉字, 用于"这俩说的是不是同一个东西"的判断。"""
    return "".join(ch for ch in fold(text) if ch.isalnum())


def same(left: str, right: str) -> bool:
    return skeleton(left) == skeleton(right)
