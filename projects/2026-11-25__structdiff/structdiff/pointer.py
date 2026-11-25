# RFC 6901 JSON Pointer。
from __future__ import annotations

from typing import Iterable


def escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def pointer(parts: Iterable[str | int]) -> str:
    """把路径片段拼成 JSON Pointer; 根节点是空字符串。"""
    return "".join("/" + escape(str(part)) for part in parts)
