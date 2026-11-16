# 导出前的脱敏: 保留头尾, 中间打码。
from __future__ import annotations

DEFAULT_FILL = "*"


def mask(value: str, head: int = 3, tail: int = 4, fill: str = DEFAULT_FILL) -> str:
    """保留前 head 位与后 tail 位; 长度不够时整体替换为等长的填充符。"""
    if head < 0 or tail < 0:
        raise ValueError("head 和 tail 不能为负")
    body = str(value)
    if len(body) <= head + tail:
        return fill * len(body)
    return body[:head] + fill * (len(body) - head - tail) + body[-tail:]


def mask_id_card(value: str, head: int = 3, tail: int = 4) -> str:
    return mask(value, head, tail)


def mask_phone(value: str, head: int = 3, tail: int = 4) -> str:
    return mask(value, head, tail)


def mask_card(value: str, head: int = 4, tail: int = 4) -> str:
    return mask(value, head, tail)
