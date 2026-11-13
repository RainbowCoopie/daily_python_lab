'''中文数字与金额大写的双向转换: 零的省略、万亿进位、元角分、以及"壹拾"这类财务写法。

灵感来源:
- 财政部关于会计数字书写的规定: 金额写到角分, 无角分的可写 00 或破折号,
  有角无分的分位必须写 0 —— 这条直接决定了 to_cny 的输出形态
  (http://czt.hunan.gov.cn/ztzl/lwpf/lwpfjxs/flzd/202008/t20200828_13677156.html)
- 人民银行对支票大写金额的说明: 10 元要写"壹拾元整"而不是"拾元整"
  (https://chongqing.pbc.gov.cn/chongqing/107674/2927554/2773593/index.html)
- 北大关于汉语自然数表达的形式文法分析: 零的插入位置不是随意的, 有结构规律
  (https://ccl.pku.edu.cn/doubtfire/Course/Computational%20Linguistics/contents/Num_CFG.pdf)

为什么值得单独做一层: 合同金额、支票、财务导出都要求大写金额, 而"一千零一十"和"一千零十"
哪个对、"一万零一"和"一万零零一"哪个对, 这类判断没有库就得每次现场想。
本模块把 中文 -> 数字 和 数字 -> 中文 两个方向都实现, 并且用往返测试互相验证。
'''

SLUG = "cnnum"
TITLE = "中文数字与金额大写互转"
TAGS = ["中文数字", "金额大写", "财务场景", "往返验证"]
PKG = "cnnum"
SUMMARY = '中文数字与金额大写的双向转换: 零的省略、万亿进位、元角分, 以及「壹拾」这类必须带的写法。'
STACK_NOTES = [
    "万亿进位按四位一组处理, 组内用 千/百/十, 组间按需补零",
    "小写 10 读作「十」, 大写金额必须是「壹拾」——同一套算法两种输出策略",
    "反向解析严格校验: 连续两个数字字符视为非法, 但「零伍」这种补位允许",
]
NOTES = """
两个方向都做, 是为了让测试能互相验证: `parse(to_cn(n)) == n` 对一大批数成立,
比逐个手写期望值可靠得多。手写期望值只用在几个关键边界(10、10001、110000、一亿零一)。

零的规则集中在 `_four` 里: 组内遇到 0 先记一个"待补零"标记, 只有后面真的又冒出数字,
才把零补进去。这样 1000 读出"一千"(不是"一千零零零"), 1001 读出"一千零一"。

组间补零的条件是"本组小于 1000 且前面已有内容", 所以 10001 是"一万零一",
而 12345 是"一万二千三百四十五"(不需要零)。
"""

FILES = {
    "cnnum/__init__.py": '''from .convert import (
    MAX_VALUE,
    NumError,
    parse_chinese,
    parse_cny,
    to_big,
    to_chinese,
    to_cny,
)

__all__ = [
    "MAX_VALUE",
    "NumError",
    "to_chinese",
    "to_big",
    "to_cny",
    "parse_chinese",
    "parse_cny",
]
''',
    "cnnum/convert.py": '''# 中文数字与金额大写。
from __future__ import annotations

DIGITS = "零一二三四五六七八九"
BIG_DIGITS = "零壹贰叁肆伍陆柒捌玖"
SMALL_UNITS = ("千", "百", "十", "")
BIG_UNITS = ("仟", "佰", "拾", "")
GROUP_UNITS = ("", "万", "亿", "万亿")

MAX_VALUE = 9999 * 10 ** 12 + 9999 * 10 ** 8 + 9999 * 10 ** 4 + 9999

_NUM = {ch: value for value, ch in enumerate(DIGITS)}
_NUM.update({ch: value for value, ch in enumerate(BIG_DIGITS)})
_NUM["两"] = 2
_UNIT = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}
_GROUP = {"万": 10 ** 4, "亿": 10 ** 8}


class NumError(ValueError):
    """输入不是能识别的中文数字。"""


def _four(value: int, digits: str, units: tuple[str, str, str, str]) -> str:
    """0 < value < 10000 转成组内表示, 零按需补一位。"""
    out: list[str] = []
    pending_zero = False
    for divisor, unit in zip((1000, 100, 10, 1), units):
        digit = value // divisor % 10
        if digit == 0:
            pending_zero = True
            continue
        if pending_zero and out:
            out.append(digits[0])
        pending_zero = False
        out.append(digits[digit] + unit)
    return "".join(out)


def _to_cn(value: int, digits: str, units, group_units, strip_leading_one: bool) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("只接受 int, 收到 " + type(value).__name__)
    if value < 0:
        raise NumError("只支持非负整数, 收到 " + str(value))
    if value > MAX_VALUE:
        raise NumError(f"超出支持范围, 最大 {MAX_VALUE}")
    if value == 0:
        return digits[0]

    groups: list[int] = []
    rest = value
    while rest:
        groups.append(rest % 10000)
        rest //= 10000

    parts: list[str] = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if group == 0:
            continue
        if parts and group < 1000:
            parts.append(digits[0])
        parts.append(_four(group, digits, units) + group_units[index])

    text = "".join(parts)
    if strip_leading_one and text.startswith("一十"):
        text = text[1:]
    return text


def to_chinese(value: int) -> str:
    """阿拉伯数字 -> 中文小写读法。10 读作十, 110 读作一百一十。"""
    return _to_cn(value, DIGITS, SMALL_UNITS, GROUP_UNITS, strip_leading_one=True)


def to_big(value: int) -> str:
    """阿拉伯数字 -> 大写数字。保留「壹拾」而不是「拾」。"""
    return _to_cn(value, BIG_DIGITS, BIG_UNITS, GROUP_UNITS, strip_leading_one=False)


def to_cny(yuan: int, cents: int = 0) -> str:
    """金额大写。cents 是分, 0..99。"""
    if isinstance(yuan, bool) or not isinstance(yuan, int) or isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError("yuan 和 cents 必须是 int")
    if yuan < 0 or not 0 <= cents <= 99:
        raise NumError(f"金额非法: yuan={yuan} cents={cents}")

    yuan_text = to_big(yuan)
    if cents == 0:
        return yuan_text + "元整"
    jiao, fen = divmod(cents, 10)
    if fen == 0:
        return yuan_text + "元" + BIG_DIGITS[jiao] + "角整"
    if jiao == 0:
        return yuan_text + "元零" + BIG_DIGITS[fen] + "分"
    return yuan_text + "元" + BIG_DIGITS[jiao] + "角" + BIG_DIGITS[fen] + "分"


def parse_chinese(text: str) -> int:
    """中文数字 -> int。支持零/两/十百千/万/亿/万亿, 大小写混用也行。"""
    body = str(text).strip()
    if not body:
        raise NumError("空字符串")

    total = 0
    section = 0
    pending: int | None = None
    i = 0
    while i < len(body):
        # 「万亿」是双字复合单位, 必须先匹配, 否则会被拆成 万 + 亿
        if body[i : i + 2] == "万亿":
            section = (section + (0 if pending is None else pending)) * 10 ** 12
            total += section
            section = 0
            pending = None
            i += 2
            continue

        ch = body[i]
        if ch in _NUM:
            value = _NUM[ch]
            if pending is not None and pending != 0:
                raise NumError("连续两个数字字符, 无法解析: " + repr(text))
            pending = value
        elif ch in _UNIT:
            section += (1 if pending is None else pending) * _UNIT[ch]
            pending = None
        elif ch in _GROUP:
            section = (section + (0 if pending is None else pending)) * _GROUP[ch]
            total += section
            section = 0
            pending = None
        else:
            raise NumError("无法识别的字符 " + repr(ch) + " 于 " + repr(text))
        i += 1

    return total + section + (0 if pending is None else pending)


def parse_cny(text: str) -> int:
    """金额大写 -> 分。"""
    body = str(text).strip().replace("整", "")
    if not body:
        raise NumError("空字符串")
    if "元" in body:
        yuan_text, rest = body.split("元", 1)
    elif "角" in body or "分" in body:
        # 「伍角整」这种没有元位的写法: 整体都是角分部分
        yuan_text, rest = "", body
    else:
        yuan_text, rest = body, ""

    yuan = 0 if yuan_text in ("", "零") else parse_chinese(yuan_text)

    jiao = 0
    if "角" in rest:
        head, rest = rest.split("角", 1)
        jiao = 0 if head in ("", "零") else parse_chinese(head)

    fen = 0
    if "分" in rest:
        head = rest.split("分", 1)[0]
        fen = 0 if head in ("", "零") else parse_chinese(head)

    if not 0 <= jiao <= 9 or not 0 <= fen <= 9:
        raise NumError("角分超出 0..9: " + repr(text))
    return yuan * 100 + jiao * 10 + fen
''',
    "tests/test_convert.py": '''import pytest

from cnnum import (
    MAX_VALUE,
    NumError,
    parse_chinese,
    parse_cny,
    to_big,
    to_chinese,
    to_cny,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "零"),
        (1, "一"),
        (10, "十"),
        (12, "十二"),
        (20, "二十"),
        (101, "一百零一"),
        (110, "一百一十"),
        (1000, "一千"),
        (1001, "一千零一"),
        (1010, "一千零一十"),
        (10000, "一万"),
        (10001, "一万零一"),
        (110000, "十一万"),
        (1000000, "一百万"),
        (12345, "一万二千三百四十五"),
        (123456789, "一亿二千三百四十五万六千七百八十九"),
        (10 ** 8, "一亿"),
        (10 ** 8 + 1, "一亿零一"),
        (10 ** 12, "一万亿"),
    ],
)
def test_to_chinese(value: int, expected: str) -> None:
    assert to_chinese(value) == expected


def test_to_chinese_rejects_bad_input() -> None:
    with pytest.raises(NumError):
        to_chinese(-1)
    with pytest.raises(TypeError):
        to_chinese(1.5)
    with pytest.raises(TypeError):
        to_chinese(True)
    with pytest.raises(NumError):
        to_chinese(MAX_VALUE + 1)


@pytest.mark.parametrize("value", [0, 1, 10, 11, 99, 100, 1001, 10010, 99999, 123456789, 10 ** 8 + 7, 10 ** 12 + 1])
def test_roundtrip(value: int) -> None:
    assert parse_chinese(to_chinese(value)) == value


@pytest.mark.parametrize(
    "value,expected", [(0, "零"), (10, "壹拾"), (15, "壹拾伍"), (110, "壹佰壹拾"), (1001, "壹仟零壹")]
)
def test_to_big(value: int, expected: str) -> None:
    assert to_big(value) == expected


def test_to_big_keeps_yi_before_shi() -> None:
    assert to_big(10).startswith("壹拾")
    assert to_chinese(10) == "十"


@pytest.mark.parametrize(
    "yuan,cents,expected",
    [
        (0, 0, "零元整"),
        (123, 0, "壹佰贰拾叁元整"),
        (123, 45, "壹佰贰拾叁元肆角伍分"),
        (123, 40, "壹佰贰拾叁元肆角整"),
        (123, 5, "壹佰贰拾叁元零伍分"),
        (10, 0, "壹拾元整"),
    ],
)
def test_to_cny(yuan: int, cents: int, expected: str) -> None:
    assert to_cny(yuan, cents) == expected


def test_to_cny_validates() -> None:
    with pytest.raises(NumError):
        to_cny(-1)
    with pytest.raises(NumError):
        to_cny(1, 100)


@pytest.mark.parametrize("yuan,cents", [(0, 0), (1, 1), (123, 45), (123, 40), (123, 5), (9999, 99), (10, 0)])
def test_cny_roundtrip(yuan: int, cents: int) -> None:
    assert parse_cny(to_cny(yuan, cents)) == yuan * 100 + cents


@pytest.mark.parametrize(
    "text,expected",
    [
        ("零", 0),
        ("两", 2),
        ("十", 10),
        ("十二", 12),
        ("一百一十", 110),
        ("一万零一", 10001),
        ("十一万", 110000),
        ("一亿零一", 10 ** 8 + 1),
        ("壹佰贰拾叁", 123),
    ],
)
def test_parse_chinese(text: str, expected: int) -> None:
    assert parse_chinese(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "一二", "三斤"])
def test_parse_chinese_rejects(text: str) -> None:
    with pytest.raises(NumError):
        parse_chinese(text)


def test_parse_chinese_allows_zero_padding_digit() -> None:
    assert parse_chinese("零伍") == 5


@pytest.mark.parametrize(
    "text,expected",
    [
        ("零元整", 0),
        ("壹佰贰拾叁元肆角伍分", 12345),
        ("壹佰元零伍分", 10005),
        ("伍角整", 50),
        ("壹拾元整", 1000),
    ],
)
def test_parse_cny(text: str, expected: int) -> None:
    assert parse_cny(text) == expected
''',
}

CHALLENGE = {
    "target": "cnnum/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 cnnum/challenge.py 中实现 invoice_line(items: dict[str, int]) -> str: "
        "items 是 名称->分 的映射, 求和后返回一行 '合计: <金额大写>'; "
        "复用 cnnum.convert.to_cny, 金额为 0 时也要输出。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from cnnum.challenge import invoice_line


def test_sums_and_formats() -> None:
    assert invoice_line({"甲": 12345, "乙": 655}) == "合计: 壹佰贰拾玖元玖角伍分"


def test_empty_is_zero() -> None:
    assert invoice_line({}) == "合计: 零元整"
''',
}
