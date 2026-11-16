# 统一社会信用代码: GB 32100-2015, 3^(i-1) mod 31 加权。
from __future__ import annotations

import unicodedata

ALPHABET = "0123456789ABCDEFGHJKLMNPQRTUWXY"
WEIGHTS = tuple(pow(3, index, 31) for index in range(17))


def normalize(value: str) -> str:
    body = unicodedata.normalize("NFKC", str(value))
    return "".join(body.split()).upper()


def check_digit(first_seventeen: str) -> str:
    body = normalize(first_seventeen)
    if len(body) != 17:
        raise ValueError("前 17 位长度不对, 收到 " + repr(first_seventeen))
    total = 0
    for ch, weight in zip(body, WEIGHTS):
        if ch not in ALPHABET:
            raise ValueError("字符 " + repr(ch) + " 不在信用代码字符集内")
        total += ALPHABET.index(ch) * weight
    remainder = total % 31
    code = 31 - remainder
    if code == 31:          # 31 - 0 要落回 0, 否则索引越界
        code = 0
    return ALPHABET[code]


def is_valid(value: str) -> bool:
    body = normalize(value)
    if len(body) != 18:
        return False
    try:
        return body[17] == check_digit(body[:17])
    except ValueError:
        return False
