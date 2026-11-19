'''金额解析、整数分表示、财务舍入与格式化 —— 把"钱算错一分"的三个源头一次堵住。

灵感来源:
- 财务实施里的真实抱怨: Python 的 round 用的是银行家舍入(四舍六入五取偶), 不适合金额场景
  (https://www.yingdao.com/community/detaildiscuss?id=765495356453453824)
- CPython 官方 issue 里的一句话道破要害: `Decimal(2.675) != Decimal("2.675")`,
  因为浮点存的其实是 2.67499999999999982236431605997495353221893310546875
  (https://mail.python.org/pipermail/python-bugs-list/2015-August/278309.html)
- Decimal 的三个边界: 字符串构造、舍入规则、quantize 精度
  (https://bbs.huaweicloud.com/blogs/521911)
- 最省事也最可靠的一条: 金额永远用整数"分"存, 别用 float
  (https://stackoverflow.com/revisions/ff75e36d-d534-4b8b-a0f5-8efefa83900b/view-source)

为什么值得单独做一层: 这三个坑的共同点是**单笔看不出来, 汇总才炸**。
一笔 0.01 的误差在大批量对账里能变成几百块的差额, 而且查不出是哪一笔错的。
本模块的策略是: 入口就转 Decimal(用字符串构造), 内部一律以"分"为整数单位, 出口再格式化。
'''

SLUG = "moneyfmt"
TITLE = "金额舍入与格式化"
TAGS = ["Decimal", "财务舍入", "整数分", "浮点陷阱"]
PKG = "moneyfmt"
SUMMARY = '金额解析与格式化: 用字符串构造 Decimal、整数分运算、ROUND_HALF_UP 财务舍入, 顺手避开三个浮点陷阱。'
STACK_NOTES = [
    "入口拒绝脏输入: NaN/inf/空串/带垃圾字符一律抛错, 不静默当 0",
    "内部以整数分为单位做加减, 出口才格式化, 累加不会漂",
    "舍入显式指定 ROUND_HALF_UP, 不用内置 round 的银行家舍入",
]
NOTES = """
三个陷阱, 逐个说明为什么本模块这么做:

1. **内置 round 是银行家舍入**。`round(2.5) == 2`、`round(3.5) == 4` —— 对统计是对的,
   对金额是错的。财务要的是"逢五进一", 所以这里统一 `ROUND_HALF_UP`。
2. **Decimal(float) 会把已经坏掉的近似值带进来**。`Decimal(2.675)` 是 2.6749999...,
   舍到两位得 2.67; 而 `Decimal("2.675")` 是精确的 2.675, 舍到两位得 2.68。
   所以入口一律先 `str()` 再构造。
3. **浮点累加会累积误差**。`sum([0.1] * 10)` 是 0.9999999999999999, 不是 1.0。
   所以加减只在整数分上做, 一次转成 float 的机会都不给。

注意一个边界: 如果 float 已经被算坏了(比如 0.1+0.2 得到的 0.30000000000000004),
`Decimal(str(x))` 也只能忠实继承那个坏值 —— 它不会凭空修好。修的办法是别让坏值产生:
从输入开始就用字符串或整数分。
"""

FILES = {
    "moneyfmt/__init__.py": '''from .amount import (
    CENTS,
    format_amount,
    from_cents,
    parse_amount,
    round_half_up,
    split_cents,
    sum_cents,
    to_cents,
)

__all__ = [
    "CENTS",
    "parse_amount",
    "to_cents",
    "from_cents",
    "round_half_up",
    "format_amount",
    "split_cents",
    "sum_cents",
]
''',
    "moneyfmt/amount.py": '''# 金额: 解析 -> 整数分 -> 格式化。
from __future__ import annotations

import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable

CENTS = Decimal("0.01")
CURRENCY_CHARS = "\\uffe5\\u00a5$\\u20ac\\u00a3"
ACCOUNTING_OPEN = "(\\uff08"
ACCOUNTING_CLOSE = ")\\uff09"


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
''',
    "tests/test_amount.py": '''from decimal import Decimal

import pytest

from moneyfmt import (
    format_amount,
    from_cents,
    parse_amount,
    round_half_up,
    split_cents,
    sum_cents,
    to_cents,
)


def test_parse_plain_string() -> None:
    assert parse_amount("1234.5") == Decimal("1234.5")


def test_parse_with_grouping_and_currency() -> None:
    assert parse_amount("\\uffe51,234.56") == Decimal("1234.56")
    assert parse_amount("$ 1,234.56") == Decimal("1234.56")


def test_parse_fullwidth_digits() -> None:
    assert parse_amount("\\uff11\\uff12\\uff13\\uff14.\\uff15") == Decimal("1234.5")


def test_parse_accounting_parentheses_is_negative() -> None:
    assert parse_amount("(1234.56)") == Decimal("-1234.56")


def test_parse_int_and_decimal() -> None:
    assert parse_amount(7) == Decimal(7)
    assert parse_amount(Decimal("0.1")) == Decimal("0.1")


def test_parse_float_goes_through_str() -> None:
    assert parse_amount(0.1) == Decimal("0.1")


def test_parse_rejects_junk() -> None:
    for bad in ("", "   ", "abc", "12abc", "NaN", "inf", "-inf"):
        with pytest.raises(ValueError):
            parse_amount(bad)


def test_parse_rejects_bool() -> None:
    with pytest.raises(TypeError):
        parse_amount(True)


def test_builtin_round_is_banker_rounding() -> None:
    # 这就是不能直接用 round 的原因
    assert round(2.5) == 2
    assert round(3.5) == 4


def test_round_half_up_differs_from_builtin() -> None:
    assert round_half_up("2.5", 0) == Decimal("3")
    assert round_half_up("2.675") == Decimal("2.68")


def test_round_half_up_negative() -> None:
    assert round_half_up("-2.675") == Decimal("-2.68")


def test_round_half_up_rejects_negative_places() -> None:
    with pytest.raises(ValueError):
        round_half_up("1", -1)


def test_decimal_from_float_trap() -> None:
    """同一个"2.675", 从 float 构造舍出 2.67, 从字符串构造舍出 2.68。"""
    from_float = Decimal(2.675).quantize(Decimal("0.01"))
    from_str = Decimal("2.675").quantize(Decimal("0.01"))
    assert from_float == Decimal("2.67")
    assert from_str == Decimal("2.68")
    assert round_half_up(2.675) == Decimal("2.68")


def test_to_cents() -> None:
    assert to_cents("1.00") == 100
    assert to_cents("2.675") == 268
    assert to_cents("-0.005") == -1
    assert to_cents(0) == 0


def test_from_cents() -> None:
    assert from_cents(268) == Decimal("2.68")
    assert from_cents(-1) == Decimal("-0.01")


def test_from_cents_rejects_non_int() -> None:
    with pytest.raises(TypeError):
        from_cents(1.5)  # type: ignore[arg-type]


def test_float_accumulation_drifts_but_cents_do_not() -> None:
    assert sum([0.1] * 10) != 1.0
    assert sum_cents(["0.1"] * 10) == 100


def test_sum_cents_mixed_inputs() -> None:
    assert sum_cents(["1.005", 2, "0.10"]) == 311


def test_split_cents() -> None:
    assert split_cents(123456) == (1234, 5, 6)
    assert split_cents(-123456) == (1234, 5, 6)
    assert split_cents(0) == (0, 0, 0)


def test_format_basic() -> None:
    assert format_amount("1234.5") == "1,234.50"


def test_format_no_grouping() -> None:
    assert format_amount("1234567.891", grouping=False) == "1234567.89"


def test_format_negative() -> None:
    assert format_amount("-1234.5") == "-1,234.50"


def test_format_negative_parentheses() -> None:
    assert format_amount("-1234.5", paren_negative=True) == "(1,234.50)"


def test_format_currency_prefix() -> None:
    assert format_amount("1234.5", currency="\\uffe5") == "\\uffe51,234.50"


def test_format_zero_has_no_minus() -> None:
    assert format_amount("-0.004") == "0.00"


def test_format_rounds_half_up() -> None:
    assert format_amount("2.675") == "2.68"
    assert format_amount("1.005") == "1.01"


def test_format_on_already_broken_float() -> None:
    """0.1+0.2 已经坏了, 但舍到分之后仍是 0.30 —— 精度控制在这里救回来了。"""
    assert format_amount(0.1 + 0.2) == "0.30"


def test_format_large_amount() -> None:
    assert format_amount("9876543210.989") == "9,876,543,210.99"
''',
}

CHALLENGE = {
    "target": "moneyfmt/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 moneyfmt/challenge.py 中实现 invoice_total(items: list[tuple[str, str]]) -> str: "
        "items 是 (名称, 金额字符串) 列表; 用 moneyfmt.amount.sum_cents 求和再"
        "用 moneyfmt.amount.format_amount 渲染成 '合计: 1,234.56'; 空列表返回 '合计: 0.00'。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from moneyfmt.challenge import invoice_total


def test_single_item() -> None:
    assert invoice_total([("A", "1234.56")]) == "合计: 1,234.56"


def test_multiple_items_sum_exactly() -> None:
    assert invoice_total([("A", "0.1"), ("B", "0.2")]) == "合计: 0.30"


def test_empty() -> None:
    assert invoice_total([]) == "合计: 0.00"
''',
}
