# 银行卡号: Luhn (mod 10)。
from __future__ import annotations

import unicodedata


def normalize(value: str) -> str:
    body = unicodedata.normalize("NFKC", str(value))
    return "".join(body.split())


def _digits(value: str) -> list[int]:
    body = normalize(value)
    if not body.isdigit():
        raise ValueError("卡号必须都是数字, 收到 " + repr(value))
    return [int(ch) for ch in body]


def is_valid(value: str) -> bool:
    try:
        digits = _digits(value)
    except ValueError:
        return False
    if len(digits) < 2:
        return False
    total = 0
    # 从最右边往左数, 隔一位乘 2 —— 从左往右数会把奇数长度算错
    for offset, digit in enumerate(reversed(digits)):
        if offset % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def check_digit(partial: str) -> str:
    """给定前缀, 补出使号码合法的最后一位。"""
    body = normalize(partial)
    if not body.isdigit() or not body:
        raise ValueError("前缀必须是非空数字串, 收到 " + repr(partial))
    for candidate in "0123456789":
        if is_valid(body + candidate):
            return candidate
    raise ValueError("无法为 " + repr(partial) + " 找到校验位")
