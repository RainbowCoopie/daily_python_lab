# 中文数字与金额大写。
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
