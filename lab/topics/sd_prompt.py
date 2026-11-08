'''Stable Diffusion 提示词处理: 权重语法、去重合并、token 粗估, 用于批量出图前的 prompt 归一化。'''

SLUG = "sd_prompt"
TITLE = "SD 提示词归一化与权重渲染"
TAGS = ["stable diffusion", "prompt 工程", "文本处理", "去重"]
PKG = "sdprompt"
SUMMARY = "把散乱的提示词片段去重、合并权重、渲染成 A1111/forge 认识的 (word:1.2) 语法, 并粗估 token 量。"
STACK_NOTES = [
    "同名词忽略大小写去重, 保留最大权重",
    "权重为 1.0 时省略括号, 保持 prompt 干净",
    "token 粗估按短语与词数, 用于判断是否会超长截断",
]
NOTES = """
批量出图时 prompt 常常是拼接出来的, 于是同一个 tag 出现三四次, 权重还各不相同。
渲染前先 normalize: 去空白、按小写去重、取最大权重、保持首次出现顺序。
这样同一套语义不会因为拼接顺序不同而产出不同的图。
"""

FILES = {
    "sdprompt/__init__.py": '''from .prompt import estimate_tokens, format_prompt, format_weight, normalize

__all__ = ["normalize", "format_prompt", "format_weight", "estimate_tokens"]
''',
    "sdprompt/prompt.py": '''# 提示词归一化与渲染。
from __future__ import annotations

from typing import Iterable, Sequence

Token = tuple[str, float]


def _clean(text: str) -> str:
    return " ".join(str(text).split())


def normalize(tokens: Iterable[Token]) -> list[Token]:
    """去空白、忽略大小写去重、保留最大权重、维持首次出现顺序。"""
    bucket: dict[str, list] = {}
    for text, weight in tokens:
        cleaned = _clean(text)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in bucket:
            bucket[key][1] = max(bucket[key][1], float(weight))
        else:
            bucket[key] = [cleaned, float(weight), len(bucket)]
    return [(v[0], v[1]) for _, v in sorted(bucket.items(), key=lambda kv: kv[1][2])]


def format_weight(weight: float) -> str:
    """1.0 返回空串(不渲染括号), 其余保留至多两位小数。"""
    if abs(float(weight) - 1.0) < 1e-9:
        return ""
    text = f"{float(weight):.2f}".rstrip("0").rstrip(".")
    return text


def format_prompt(tokens: Iterable[Token]) -> str:
    parts: list[str] = []
    for text, weight in normalize(tokens):
        rendered = format_weight(weight)
        parts.append(text if rendered == "" else f"({text}:{rendered})")
    return ", ".join(parts)


def estimate_tokens(text: str) -> int:
    """粗估: 逗号切短语, 每个短语按空格分词计 1 token/词。"""
    chunks = [chunk.strip() for chunk in str(text).split(",")]
    chunks = [c for c in chunks if c]
    return sum(max(1, len(c.split())) for c in chunks)


def merge(*groups: Sequence[Token]) -> list[Token]:
    flat: list[Token] = []
    for group in groups:
        flat.extend(group)
    return normalize(flat)
''',
    "tests/test_prompt.py": '''import pytest

from sdprompt import estimate_tokens, format_prompt, format_weight, normalize


def test_normalize_dedupes_case_insensitive_and_keeps_max() -> None:
    out = normalize([("masterpiece", 1.0), ("Masterpiece ", 1.2), ("", 2.0), ("1girl", 1.0)])
    assert out == [("masterpiece", 1.2), ("1girl", 1.0)]


def test_normalize_keeps_first_seen_order() -> None:
    out = normalize([("b", 1.0), ("a", 1.0), ("b", 1.5)])
    assert [t for t, _ in out] == ["b", "a"]


def test_format_weight() -> None:
    assert format_weight(1.0) == ""
    assert format_weight(1.2) == "1.2"
    assert format_weight(0.8) == "0.8"
    assert format_weight(2.0) == "2"


def test_format_prompt() -> None:
    tokens = [("masterpiece", 1.2), ("1girl", 1.0), ("masterpiece", 1.0)]
    assert format_prompt(tokens) == "(masterpiece:1.2), 1girl"


def test_format_prompt_empty() -> None:
    assert format_prompt([]) == ""
    assert format_prompt([("   ", 1.0)]) == ""


def test_estimate_tokens() -> None:
    assert estimate_tokens("a b, c") == 3
    assert estimate_tokens("") == 0
    assert estimate_tokens(" , , ") == 0


def test_weight_zero_kept_but_not_equal_one() -> None:
    assert format_weight(0.0) == "0"
    assert format_prompt([("bad hands", 0.0)]) == "(bad hands:0)"
''',
}

CHALLENGE = {
    "target": "sdprompt/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 sdprompt/challenge.py 中实现 strip_weights(prompt: str) -> list[tuple[str, float]]: "
        "解析形如 'a, (b:1.2), ((c))' 的 prompt 字符串, 返回 [(文本, 权重)]。"
        "规则: 去掉每段首尾空白与成对圆括号; 有 ':' 时其右半部分转为 float 作为权重, 否则权重为 1.0; "
        "空段跳过; 复用标准库 re 实现, 不得修改 sdprompt/prompt.py。"
    ),
    "tests_content": '''import pytest

from sdprompt.challenge import strip_weights


def test_plain_tokens() -> None:
    assert strip_weights("a, b") == [("a", 1.0), ("b", 1.0)]


def test_weighted_tokens() -> None:
    assert strip_weights("(masterpiece:1.2), 1girl") == [("masterpiece", 1.2), ("1girl", 1.0)]


def test_nested_parens() -> None:
    assert strip_weights("((c))") == [("c", 1.0)]


def test_skips_empty_segments() -> None:
    assert strip_weights("a,,  ,b") == [("a", 1.0), ("b", 1.0)]
''',
}
