# 任意进制双向转换: 2 <= base <= 36, 支持负数, 不猜测前缀。
from __future__ import annotations

DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


class InvalidBase(ValueError):
    """base 不在 2..36 范围内。"""


class InvalidDigit(ValueError):
    """输入串里有当前进制下非法的字符。"""


def _check_base(base: int) -> None:
    if not isinstance(base, int):
        raise InvalidBase("进制必须是 int, 收到 " + type(base).__name__)
    if not 2 <= base <= 36:
        raise InvalidBase("进制必须在 2..36 之间, 收到 " + str(base))


def to_base(n: int, base: int) -> str:
    """十进制整数 -> 指定进制的字符串(小写, 负数带前导短横线)。"""
    _check_base(base)
    if not isinstance(n, int):
        raise TypeError("n 必须是 int, 收到 " + type(n).__name__)
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    rest = abs(n)
    out: list[str] = []
    while rest:
        rest, r = divmod(rest, base)
        out.append(DIGITS[r])
    return sign + "".join(reversed(out))


def parse_base(text: str, base: int) -> int:
    """指定进制的字符串 -> 十进制整数。允许首尾空白与正负号。"""
    _check_base(base)
    if not isinstance(text, str):
        raise TypeError("text 必须是 str, 收到 " + type(text).__name__)
    s = text.strip().lower()
    if not s:
        raise InvalidDigit("空字符串不是合法数值")
    sign = 1
    if s[0] in "+-":
        if s[0] == "-":
            sign = -1
        s = s[1:]
    if not s:
        raise InvalidDigit("只有符号, 没有数值")
    value = 0
    for ch in s:
        idx = DIGITS.find(ch)
        if idx < 0 or idx >= base:
            raise InvalidDigit("字符 " + repr(ch) + " 在 " + str(base) + " 进制下非法")
        value = value * base + idx
    return sign * value
