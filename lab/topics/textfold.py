'''文本等价归一: 让"看起来一样"的字符串变成"真的相等", 用于匹配与去重。

灵感来源:
- casefold 与 lower 不是一回事: `"ß".casefold()` 得到 "ss"(因为 ß 没有单字母大写),
  `"İ".casefold()` 得到 i + 组合点(长度 2) —— 大小写无关的匹配必须用 casefold
  (https://www.eklektix.com/Articles/741705/)
- 一份去不可见字符的工具列了该清哪几类: 零宽空格/零宽不连字/软连字符/BOM/双向控制符,
  同时强调**别误伤 emoji 与 keycap 序列**
  (https://www.npmjs.com/package/out-of-character)
- 引号与破折号的替换清单: U+2018-U+201B → ', U+201C-U+201F → ", U+2010-U+2015 与 U+2212 → -,
  U+00A0/2002-200A/202F/205F/3000 → 普通空格
  (https://github.com/earendil-works/pi/commit/0c135d01410e549e32a4ff89e6730cf5e27f271b)

为什么值得单独做一层: 从 PDF、网页、微信、Excel 里抠出来的同一个词, 常常在肉眼层面完全相同
而字节层面完全不同 —— 弯引号、全角字母、不间断空格、末尾一个零宽空格。
按原文比对会把它们当成不同的键, 去重和 join 就全错了。而清洗过头又会把 emoji 拆散。
本模块只做"等价归一", **不改语义**: 它把各种写法收敛到一种, 而不是删掉信息。
'''

SLUG = "textfold"
TITLE = "文本等价归一"
TAGS = ["Unicode 归一", "casefold", "不可见字符", "去重键"]
PKG = "textfold"
SUMMARY = "把弯引号、破折号、全角字母、不间断空格、零宽字符收敛成一种写法, 让等价文本真的相等。"
STACK_NOTES = [
    "大小写折叠用 casefold 而不是 lower: ß 折成 ss, 土耳其 İ 折成 i 加组合点",
    "不可见字符按白名单逐个清, 刻意保留 ZWJ(U+200D), 否则 emoji 家族序列会被拆散",
    "所有变换都是幂等的, 所以可以反复调用而不会持续改变文本",
]
NOTES = """
三个必须说清的边界:

1. **ZWJ 不能删**。零宽连接符 U+200D 和零宽空格 U+200B 同属 Unicode 类别 Cf,
   按类别整类删除会顺手把 "👨‍👩‍👧" 拆成三个独立的人。所以这里用显式集合逐个清,
   并且把 U+200D 明确排除在外。变体选择符 U+FE0F(类别 Mn)同理保留 —— 它决定 ❤ 显示成
   黑白心还是彩色心。
2. **casefold 不是 lower**。`"ß".lower()` 还是 "ß", 而 casefold 给 "ss";
   `"İ".casefold()` 是 "i" + U+0307 两个码位。拿 lower 做匹配会漏掉这类等价。
3. **NFKC 会改变字符本身**。"①" 变成 "1"、"Ａ" 变成 "A"、"，" 变成 ","。
   这是"兼容等价", 做键匹配正是想要的效果; 但如果你要保留原样显示, 就别用它。

`fold()` 的顺序是 NFKC → 去不可见 → 引号/破折号/空格统一 → casefold → 压缩空白。
放在最后压缩空白, 是因为前面的替换会把各种特殊空格变成普通空格, 那时才谈得上合并。
"""

FILES = {
    "textfold/__init__.py": '''from .fold import (
    fold,
    fold_dashes,
    fold_quotes,
    fold_spaces,
    nfkc,
    same,
    skeleton,
    strip_invisible,
)

__all__ = [
    "fold",
    "strip_invisible",
    "fold_quotes",
    "fold_dashes",
    "fold_spaces",
    "nfkc",
    "skeleton",
    "same",
]
''',
    "textfold/fold.py": '''# 等价归一: 只收敛写法, 不删信息。
from __future__ import annotations

import re
import unicodedata

# 显式列出要清的不可见字符 —— 不能按类别 Cf 整类删, 那会误伤 ZWJ
INVISIBLE = frozenset(
    {
        "\\u200b",  # 零宽空格
        "\\u200c",  # 零宽不连字
        "\\u00ad",  # 软连字符
        "\\ufeff",  # BOM / 零宽不换行空格
        "\\u2060",  # 单词连接符
        "\\u180e",  # 蒙古文元音分隔符
        "\\u200e", "\\u200f",                      # 左右到右/右到左标记
        "\\u202a", "\\u202b", "\\u202c", "\\u202d", "\\u202e",  # 双向嵌入与覆盖
        "\\u2066", "\\u2067", "\\u2068", "\\u2069",             # 双向隔离
    }
)

# 刻意保留: U+200D(ZWJ) 是 emoji 家族序列的连接符, 删了会把它们拆散
PRESERVED = frozenset({"\\u200d"})

QUOTES = {
    "\\u2018": "'", "\\u2019": "'", "\\u201a": "'", "\\u201b": "'", "\\u2032": "'",
    "\\u201c": '"', "\\u201d": '"', "\\u201e": '"', "\\u201f": '"', "\\u2033": '"',
    "\\u00ab": '"', "\\u00bb": '"',
}

DASHES = {ch: "-" for ch in "\\u2010\\u2011\\u2012\\u2013\\u2014\\u2015\\u2212\\u2043"}

SPACES = {ch: " " for ch in "\\u00a0\\u2000\\u2001\\u2002\\u2003\\u2004\\u2005\\u2006\\u2007\\u2008\\u2009\\u200a\\u202f\\u205f\\u3000"}

_MULTI_SPACE = re.compile(r"\\s+")


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
''',
    "tests/test_fold.py": '''import pytest

from textfold import (
    fold,
    fold_dashes,
    fold_quotes,
    fold_spaces,
    nfkc,
    same,
    skeleton,
    strip_invisible,
)


def test_strip_zero_width_and_soft_hyphen() -> None:
    assert strip_invisible("\\u200babc\\u00ad\\ufeff") == "abc"


def test_strip_bidi_controls() -> None:
    assert strip_invisible("a\\u202eb") == "ab"


def test_zwj_is_preserved() -> None:
    """emoji 家族序列靠 U+200D 连接, 删掉会变成三个独立的人。"""
    family = "\\U0001f468\\u200d\\U0001f469\\u200d\\U0001f467"
    assert strip_invisible(family) == family


def test_variation_selector_is_preserved() -> None:
    heart = "\\u2764\\ufe0f"
    assert strip_invisible(heart) == heart


def test_fold_smart_quotes() -> None:
    assert fold_quotes("\\u201c\\u4e2d\\u6587\\u201d") == '"\\u4e2d\\u6587"'
    assert fold_quotes("\\u2018a\\u2019") == "'a'"


def test_fold_dashes() -> None:
    assert fold_dashes("a\\u2013b\\u2014c\\u2212d\\u2010e") == "a-b-c-d-e"


def test_fold_special_spaces() -> None:
    assert fold_spaces("a\\u00a0b\\u3000c") == "a b c"


def test_nfkc_fullwidth_and_circled() -> None:
    assert nfkc("\\uff21\\uff22\\uff23\\u2460") == "ABC1"
    assert nfkc("\\uff0c") == ","


def test_fold_combines_everything() -> None:
    assert fold("\\uff21\\uff22\\uff23, \\u201cX\\u201d") == 'abc, "x"'


def test_casefold_not_lower() -> None:
    assert "\\u00df".casefold() == "ss"
    assert "\\u00df".lower() == "\\u00df"


def test_casefold_turkish_dotted_i() -> None:
    """İ 折叠成 i + 组合点, 两个码位 —— 这就是它和 lower 的区别之一。"""
    folded = fold("\\u0130")
    assert folded == "i\\u0307"
    assert len(folded) == 2


def test_case_can_be_kept() -> None:
    assert fold("\\uff21\\uff22\\uff23", case=False) == "ABC"


def test_whitespace_collapsed() -> None:
    assert fold("  a   b  ") == "a b"


def test_whitespace_kept_when_disabled() -> None:
    assert fold("a  b", collapse_ws=False) == "a  b"


def test_skeleton_drops_punctuation() -> None:
    assert skeleton("Hello, World!") == "helloworld"


def test_skeleton_keeps_cjk() -> None:
    assert skeleton("\\u4f60\\u597d\\uff0c\\u4e16\\u754c") == "\\u4f60\\u597d\\u4e16\\u754c"


def test_same_after_folding() -> None:
    assert same("\\uff21\\uff22\\uff23", "abc") is True
    assert same("Hello, World!", "hello world") is True


def test_same_precomposed_vs_combining() -> None:
    """café 的两种写法(NFC 与 NFD)在归一后相等。"""
    assert same("caf\\u00e9", "cafe\\u0301") is True
    assert same("caf\\u00e9", "cafe") is False


def test_same_rejects_different_words() -> None:
    assert same("abc", "abd") is False


@pytest.mark.parametrize("text", ["", "abc", "\\uff21\\uff22", "\\u201c\\u4f60\\u597d\\u201d"])
def test_fold_is_idempotent(text: str) -> None:
    once = fold(text)
    assert fold(once) == once


def test_skeleton_is_idempotent() -> None:
    once = skeleton("A, B! \\u4f60\\u597d")
    assert skeleton(once) == once


def test_empty_input() -> None:
    assert fold("") == ""
    assert skeleton("") == ""
    assert same("", "") is True


def test_nbsp_does_not_break_word() -> None:
    """不间断空格在展示上连在一起, 归一后应该变成一个普通空格。"""
    assert fold("hello\\u00a0world") == "hello world"
    assert skeleton("hello\\u00a0world") == "helloworld"
''',
}

CHALLENGE = {
    "target": "textfold/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 textfold/challenge.py 中实现 dedupe_keys(names: list[str]) -> dict[str, list[str]]: "
        "按 textfold.fold (保留大小写) 后的键分组, 返回 {归一后键: [原始写法...]}, 保持首次出现顺序。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from textfold.challenge import dedupe_keys


def test_groups_equivalent_spellings() -> None:
    got = dedupe_keys(["ABC", "\\uff21\\uff22\\uff23", "abd"])
    assert list(got) == ["ABC", "abd"]
    assert len(got["ABC"]) == 2


def test_empty() -> None:
    assert dedupe_keys([]) == {}
''',
}
