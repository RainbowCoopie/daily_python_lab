# 变量识别: 把老面孔换成占位符。
from __future__ import annotations

import re

IPV4 = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")
UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
HEX = re.compile(r"0[xX][0-9a-fA-F]+")
NUMBER = re.compile(r"\d+")

# 顺序有意义: IP 与 UUID 都比纯数字具体, 必须先匹配
PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (UUID, "<UUID>"),
    (IPV4, "<IP>"),
    (HEX, "<HEX>"),
    (NUMBER, "<NUM>"),
)


def tokenize(line: str) -> list[str]:
    """按空白切词, 连续空白压成一个。"""
    body = " ".join(str(line).split())
    return body.split(" ") if body else []


def mask_token(token: str) -> str:
    """整词匹配变量模式; 认不出就原样返回。"""
    for pattern, placeholder in PATTERNS:
        if pattern.fullmatch(token):
            return placeholder
    return token


def mask_line(line: str) -> str:
    return " ".join(mask_token(token) for token in tokenize(line))
