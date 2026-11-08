'''把简历里那段"递归进制转换"重写成工程实现: 去掉 sympy 依赖、修掉精度问题、补齐双向转换与入参校验。'''

SLUG = "algo_base_convert"
TITLE = "任意进制双向转换器"
TAGS = ["CPython", "算法", "stdlib", "边界值"]
PKG = "baseconv"
SUMMARY = "十进制 <-> 2~36 进制的双向转换, 用 divmod 迭代实现, 零第三方依赖, 负数和边界值全部纳入测试。"
STACK_NOTES = [
    "divmod 迭代替代 sympy.log 求位数——原实现的精度 bug 从根上消失",
    "双向转换 (to_base / parse_base) 互为往返验证, 7 个进制 × 11 个样本 = 77 组参数化用例",
    "自定义异常层次: InvalidBase / InvalidDigit, 让调用方能区分参数错和数据错",
]
NOTES = """
原版用 `int(sympy.log(num, base))` 预分配结果长度, 一旦浮点误差让 log 少 1, 最高位就丢了。
这里换成 `while rest: rest, r = divmod(rest, base)`, 位数由数据自己决定, 不需要预先算长度,
也不需要 decimal / sympy 这类重依赖。反向解析用 Horner 法, 逐位累乘。
"""

FILES = {
    "baseconv/__init__.py": '''from .convert import to_base, parse_base, InvalidBase, InvalidDigit

__all__ = ["to_base", "parse_base", "InvalidBase", "InvalidDigit"]
''',
    "baseconv/convert.py": '''# 任意进制双向转换: 2 <= base <= 36, 支持负数, 不猜测前缀。
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
''',
    "tests/test_convert.py": '''import pytest

from baseconv import parse_base, to_base
from baseconv.convert import InvalidBase, InvalidDigit

SAMPLES = [0, 1, 7, 8, 9, 255, 1000, 65535, 2 ** 31 - 1, -1, -1000]
BASES = [2, 3, 8, 10, 16, 32, 36]


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("n", SAMPLES)
def test_roundtrip(n: int, base: int) -> None:
    assert parse_base(to_base(n, base), base) == n


def test_known_values() -> None:
    assert to_base(9, 2) == "1001"
    assert to_base(1000, 3) == "1101001"
    assert to_base(1000, 16) == "3e8"
    assert to_base(-255, 16) == "-ff"
    assert to_base(35, 36) == "z"


def test_parse_tolerates_spaces_and_sign() -> None:
    assert parse_base("FF", 16) == 255
    assert parse_base("  ff  ", 16) == 255
    assert parse_base("-101", 2) == -5
    assert parse_base("+101", 2) == 5


def test_zero() -> None:
    assert to_base(0, 36) == "0"
    assert parse_base("0", 2) == 0


@pytest.mark.parametrize("base", [0, 1, 37, -2])
def test_invalid_base(base: int) -> None:
    with pytest.raises(InvalidBase):
        to_base(10, base)
    with pytest.raises(InvalidBase):
        parse_base("1", base)


@pytest.mark.parametrize(
    "text,base", [("2", 2), ("", 10), ("   ", 10), ("-", 10), ("1g", 16), ("z", 35)]
)
def test_invalid_digit(text: str, base: int) -> None:
    with pytest.raises(InvalidDigit):
        parse_base(text, base)


def test_type_errors() -> None:
    with pytest.raises(TypeError):
        to_base(3.5, 2)
    with pytest.raises(TypeError):
        parse_base(10, 2)
''',
}

CHALLENGE = {
    "target": "baseconv/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 baseconv/challenge.py 中实现 to_base_recursive(n: int, base: int) -> str。"
        "要求: 必须用递归(不能用 while/for 循环拼结果); 复用 baseconv.convert 里的 DIGITS 和 _check_base; "
        "结果必须与小写、负数带前导 '-' 的约定一致, 0 返回 '0'; "
        "base 非法时抛 baseconv.convert.InvalidBase, n 非 int 时抛 TypeError。"
    ),
    "tests_content": '''import pytest

from baseconv import to_base
from baseconv.challenge import to_base_recursive
from baseconv.convert import InvalidBase

CASES = [0, 1, 7, 9, 255, 1000, -1, -1000, 2 ** 31 - 1]
BASES = [2, 3, 8, 16, 36]


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("n", CASES)
def test_matches_iterative(n: int, base: int) -> None:
    assert to_base_recursive(n, base) == to_base(n, base)


def test_invalid_base() -> None:
    with pytest.raises(InvalidBase):
        to_base_recursive(10, 1)
''',
}
