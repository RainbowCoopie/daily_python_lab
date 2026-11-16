# 公民身份号码: GB 11643-1999 / ISO 7064 MOD 11-2。
from __future__ import annotations

import unicodedata
from datetime import date

WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
CHECK_CHARS = "10X98765432"


def normalize(value: str) -> str:
    """去空白、全角转半角、字母转大写。"""
    body = unicodedata.normalize("NFKC", str(value))
    return "".join(body.split()).upper()


def check_digit(first_seventeen: str) -> str:
    """由前 17 位算出校验码。"""
    body = normalize(first_seventeen)
    if len(body) != 17 or not body.isdigit():
        raise ValueError("前 17 位必须都是数字, 收到 " + repr(first_seventeen))
    total = sum(int(ch) * weight for ch, weight in zip(body, WEIGHTS))
    return CHECK_CHARS[total % 11]


def is_valid(value: str) -> bool:
    body = normalize(value)
    if len(body) != 18:
        return False
    if not body[:17].isdigit():
        return False
    return body[17] == check_digit(body[:17])


def parse(value: str) -> dict[str, object]:
    """解析出生日期、性别与行政区划码; 校验不过直接抛错。"""
    body = normalize(value)
    if not is_valid(body):
        raise ValueError("身份证号校验不通过: " + repr(value))
    birth = date(int(body[6:10]), int(body[10:12]), int(body[12:14]))
    order = int(body[16])
    return {
        "region": body[:6],
        "birth": birth,
        "gender": "男" if order % 2 else "女",
        "check": body[17],
    }
