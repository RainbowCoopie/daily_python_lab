# 文本规范化、字符 shingle 与精确 Jaccard。
from __future__ import annotations

import re
import unicodedata

_SPACES = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """全角转半角、去多余空白、统一小写。"""
    body = unicodedata.normalize("NFKC", str(text))
    return _SPACES.sub(" ", body).strip().lower()


def shingles(text: str, k: int = 3) -> set[str]:
    """按字符切 k-gram; 文本比 k 短时整体作为一个 shingle。"""
    if k < 1:
        raise ValueError("k 必须 >= 1")
    body = normalize_text(text)
    if not body:
        return set()
    if len(body) <= k:
        return {body}
    return {body[i : i + k] for i in range(len(body) - k + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    """交集除以并集; 两边都空时视为完全相似(1.0)。"""
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)
