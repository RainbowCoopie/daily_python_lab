# 金额: 解析 -> 整数分 -> 格式化。
from __future__ import annotations

import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable

CENTS = Decimal("0.01")
CURRENCY_CHARS = "\uffe5\u00a5$\u20ac\u00a3"
ACCOUNTING_OPEN = "(\uff08"
ACCOUNTING_CLOSE = ")\uff09"


def parse_amount(value: object) -> Decimal:
    """把各种写法解析成 Decimal 元。字符串走字符串构造, 不经过 float。"""
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, bool):
        raise TypeError("布尔值不是金额")
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, float):
        # 先转字符串: 0.1 这种能还原, 但已经是 0.30000000000000004 的修不好
        result = Decimal(str(value))
    else:
        body = unicodedata.normalize("NFKC", str(value)).strip()
        negative = False
        # 先判长度: 空串的 body[:1] 与 body[-1:] 都是 "", 而 "" in "(" 为 True
        if len(body) >= 2 and body[0] in ACCOUNTING_OPEN and body[-1] in ACCOUNTING_CLOSE:
            negative = True
            body = body[1:-1]
        body = body.strip(CURRENCY_CHARS)
        body = body.replace(",", "").replace("_", "").replace(" ", "")
        if not body:
            raise ValueError("空字符串不是金额")
        try:
            result = Decimal(body)
        except InvalidOperation as exc:
            raise ValueError("无法解析的金额: " + repr(value)) from exc
        if negative:
            result = -result

    if not result.is_finite():
        raise ValueError("金额必须是有限值, 收到 " + repr(value))
    return result


def round_half_up(value: object, places: int = 2) -> Decimal:
    """财务四舍五入(逢五进一), 不用内置 round 的银行家舍入。"""
    if places < 0:
        raise ValueError("places 不能为负")
    quantum = Decimal(1).scaleb(-places)
    return parse_amount(value).quantize(quantum, rounding=ROUND_HALF_UP)


def to_cents(value: object) -> int:
    """转成整数分, 四舍五入到分。"""
    return int(round_half_up(value) * 100)


def from_cents(cents: int) -> Decimal:
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError("分必须是 int")
    return Decimal(cents) / 100


def split_cents(cents: int) -> tuple[int, int, int]:
    """拆成(元, 角, 分), 取绝对值。"""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError("分必须是 int")
    total = abs(cents)
    yuan, rest = divmod(total, 100)
    jiao, fen = divmod(rest, 10)
    return yuan, jiao, fen


def sum_cents(values: Iterable[object]) -> int:
    """逐个转成分再整数相加 —— 累加不会漂。"""
    total = 0
    for item in values:
        total += to_cents(item)
    return total


def format_amount(
    value: object,
    *,
    grouping: bool = True,
    paren_negative: bool = False,
    currency: str = "",
) -> str:
    """格式化成 1,234.56 / (1,234.56) / ￥1,234.56。"""
    cents = to_cents(value)
    negative = cents < 0
    yuan, jiao, fen = split_cents(cents)
    integer_part = f"{yuan:,}" if grouping else str(yuan)
    body = f"{integer_part}.{jiao}{fen}"
    if negative:
        body = f"({body})" if paren_negative else "-" + body
    return currency + body
