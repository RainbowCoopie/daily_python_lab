'''容量与时长换算: 1000 进制的 KB 和 1024 进制的 KiB 必须分开, 裸 K 要显式声明算哪一种。

灵感来源:
- IEC 对二进制前缀的说明: 标称 500GB 的硬盘在系统里显示约 488GB, 就是因为厂商用 1000、
  系统用 1024, 而单位名前缀撞了名
  (https://www.prd.iec.ch/prefixes-binary-multiples)
- 一个真实 bug: humanfriendly 的 `parse_size('1 KB')` 按 1024 算, 被指出违反 IEEE 1541,
  修复方向是"看前两个字母区分 KiB 与 KB"
  (https://github.com/xolox/python-humanfriendly/issues/4)
- bytesz 更进一步: `parse("1 KB")` 直接抛 AmbiguousUnitError, 拒绝替用户猜
  (https://pypi.org/project/bytesz/0.2.0/)
- 时长语法参考 systemd.time: `2h 30min`、空格可省、无单位默认按秒
  (https://manpages.debian.org/bookworm-backports/systemd/systemd.time.7.en.html)

为什么值得单独做一层: 这两个歧义每天都在制造 bug。"1.5GB 是 15 亿字节还是 16 亿字节"
决定了限流阈值差 7%; "1KB 到底是 1000 还是 1024" 决定了磁盘容量对不上账。
本模块不替用户猜: 带 i 的按 1024, 不带的按 1000, 裸 K/M/G 视为歧义 ——
默认沿用磁盘工具的习惯按 1024, 但加 strict=True 就要求调用方写清楚。
'''

SLUG = "unitconv"
TITLE = "容量与时长换算"
TAGS = ["单位换算", "IEC/SI 前缀", "歧义检测", "配置解析"]
PKG = "unitconv"
SUMMARY = '字节数与时间跨度互转: KiB 按 1024、KB 按 1000, 裸 K 视为歧义(strict 模式下直接报错)。'
STACK_NOTES = [
    "SI(KB=1000) 与 IEC(KiB=1024) 分表维护, 不共用一张乘法表",
    "裸 K/M/G 默认按 1024 兼容磁盘工具习惯, strict=True 时抛 AmbiguousUnitError 拒绝猜",
    "时长解析按 systemd 风格: 1h30m、空格可省、纯数字按秒",
]
NOTES = """
**容量**: 三档语义必须分清。
- `KB MB GB` = 1000 的幂(SI, 硬盘厂商标称用的就是它)
- `KiB MiB GiB` = 1024 的幂(IEC, 操作系统显示文件大小用的通常是它)
- 裸 `K M G` = 歧义。默认按 1024 处理(和 Windows、`du -h` 的老习惯一致),
  但 `strict=True` 会抛异常 —— 写配置解析时应该开严格模式, 让写配置的人自己表态。

**时长**: 只支持 `ms s m h d w`, 刻意不支持月和年。
因为"一个月"是 30 天还是 30.44 天、"一年"是 365 还是 365.25, 各家不一样;
这种歧义留在上层业务里解释, 不该埋在单位换算里。要月就自己乘 30.44 再传进来。

**格式化**两个方向都做, 是为了往返测试: `parse_size(format_size(n)) == n` 成立范围越广,
实现越可信。往返在"显示精度不足"时会失败(1024 字节格式化成 1KiB 再解析回来没问题,
但 1025 字节格式化成 1KiB 就丢了), 所以往返测试只覆盖精确值。
"""

FILES = {
    "unitconv/__init__.py": '''from .size import (
    SI_UNITS,
    IEC_UNITS,
    AmbiguousUnitError,
    format_size,
    parse_size,
)
from .span import format_span, parse_span

__all__ = [
    "SI_UNITS",
    "IEC_UNITS",
    "AmbiguousUnitError",
    "parse_size",
    "format_size",
    "parse_span",
    "format_span",
]
''',
    "unitconv/size.py": '''# 容量: SI(1000) 与 IEC(1024) 分表。
from __future__ import annotations

import re

SI_UNITS: dict[str, int] = {
    "b": 1,
    "kb": 1000,
    "mb": 1000 ** 2,
    "gb": 1000 ** 3,
    "tb": 1000 ** 4,
    "pb": 1000 ** 5,
}

IEC_UNITS: dict[str, int] = {
    "kib": 1024,
    "mib": 1024 ** 2,
    "gib": 1024 ** 3,
    "tib": 1024 ** 4,
    "pib": 1024 ** 5,
}

# 裸 K/M/G 是歧义: 默认按 1024, 严格模式下直接拒绝
AMBIGUOUS_UNITS: dict[str, int] = {
    "k": 1024,
    "m": 1024 ** 2,
    "g": 1024 ** 3,
    "t": 1024 ** 4,
    "p": 1024 ** 5,
}

_PATTERN = re.compile(r"^(\\d+(?:\\.\\d+)?)\\s*([a-z]*)$")

FORMAT_ORDER_SI = (("PB", 1000 ** 5), ("TB", 1000 ** 4), ("GB", 1000 ** 3), ("MB", 1000 ** 2), ("KB", 1000), ("B", 1))
FORMAT_ORDER_IEC = (("PiB", 1024 ** 5), ("TiB", 1024 ** 4), ("GiB", 1024 ** 3), ("MiB", 1024 ** 2), ("KiB", 1024), ("B", 1))


class AmbiguousUnitError(ValueError):
    """裸 K/M/G 之类的写法无法确定是 1000 还是 1024。"""


def parse_size(text: object, *, strict: bool = False) -> int:
    """把 '1.5GiB' / '1.5 GB' / '2048' 解析成字节数。"""
    body = str(text).strip().lower().replace(" ", "")
    if not body:
        raise ValueError("空的容量字符串")
    match = _PATTERN.match(body)
    if not match:
        raise ValueError("无法解析的容量: " + repr(text))
    number, unit = match.group(1), match.group(2)

    if unit == "":
        multiplier = 1
    elif unit in SI_UNITS:
        multiplier = SI_UNITS[unit]
    elif unit in IEC_UNITS:
        multiplier = IEC_UNITS[unit]
    elif unit in AMBIGUOUS_UNITS:
        if strict:
            raise AmbiguousUnitError(
                "单位 " + repr(unit) + " 有歧义: 写 KB(1000) 还是 KiB(1024)?"
            )
        multiplier = AMBIGUOUS_UNITS[unit]
    else:
        raise ValueError("不认识的单位 " + repr(unit))

    return int(round(float(number) * multiplier))


def _render(value: float, precision: int) -> str:
    text = f"{value:.{precision}f}" if precision > 0 else f"{value:.0f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_size(size: int, *, binary: bool = False, precision: int = 1) -> str:
    """字节数 -> '1.5KiB'(binary) 或 '1.5KB'(默认)。"""
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("size 必须是 int")
    if size < 0:
        raise ValueError("size 不能为负")
    if precision < 0:
        raise ValueError("precision 不能为负")

    order = FORMAT_ORDER_IEC if binary else FORMAT_ORDER_SI
    for suffix, scale in order:
        if size >= scale:
            return _render(size / scale, precision) + suffix
    return "0B"
''',
    "unitconv/span.py": '''# 时长: systemd 风格 1h30m。
from __future__ import annotations

import re

SPAN_UNITS: dict[str, float] = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
    "w": 604800.0,
}

# ms 必须排在 m 前面, 否则 "10ms" 会被切成 10m + s
_PIECE = re.compile(r"(\\d+(?:\\.\\d+)?)\\s*(ms|s|m|h|d|w)")


def parse_span(text: object) -> float:
    """把 '1h30m' / '90s' / '1.5h' 解析成秒; 纯数字按秒。"""
    body = str(text).strip().lower().replace(" ", "")
    if not body:
        raise ValueError("空的时长字符串")
    if body.replace(".", "", 1).isdigit():
        return float(body)

    total = 0.0
    position = 0
    for match in _PIECE.finditer(body):
        if match.start() != position:
            raise ValueError("无法解析的时长: " + repr(text))
        total += float(match.group(1)) * SPAN_UNITS[match.group(2)]
        position = match.end()
    if position != len(body):
        raise ValueError("无法解析的时长: " + repr(text))
    return total


_ORDER = (("w", 604800000), ("d", 86400000), ("h", 3600000), ("m", 60000), ("s", 1000), ("ms", 1))


def format_span(seconds: float) -> str:
    """秒 -> '2h30m1s'; 支持毫秒(0.5 -> 500ms)。"""
    value = float(seconds)
    if value < 0:
        raise ValueError("时长不能为负")
    remaining = int(round(value * 1000))
    if remaining == 0:
        return "0s"

    parts: list[str] = []
    for suffix, unit_ms in _ORDER:
        if remaining >= unit_ms:
            count, remaining = divmod(remaining, unit_ms)
            parts.append(f"{count}{suffix}")
    return "".join(parts)
''',
    "tests/test_size.py": '''import pytest

from unitconv import AmbiguousUnitError, format_size, parse_size


def test_plain_number_is_bytes() -> None:
    assert parse_size("2048") == 2048
    assert parse_size(2048) == 2048


def test_si_units_are_decimal() -> None:
    assert parse_size("1.5 GB") == 1500000000
    assert parse_size("1KB") == 1000


def test_iec_units_are_binary() -> None:
    assert parse_size("1.5GiB") == 1610612736
    assert parse_size("1KiB") == 1024


def test_case_insensitive_and_spaces_ignored() -> None:
    assert parse_size(" 1.5 gib ") == 1610612736


def test_kb_and_kib_differ() -> None:
    """这就是那个经典歧义: 同一个 '1.5', 差 7%。"""
    assert parse_size("1.5GB") != parse_size("1.5GiB")


def test_bare_unit_defaults_to_binary() -> None:
    assert parse_size("1G") == 1024 ** 3


def test_bare_unit_rejected_in_strict_mode() -> None:
    with pytest.raises(AmbiguousUnitError):
        parse_size("1G", strict=True)


def test_explicit_units_pass_strict_mode() -> None:
    assert parse_size("1GiB", strict=True) == 1024 ** 3
    assert parse_size("1GB", strict=True) == 1000 ** 3


@pytest.mark.parametrize("bad", ["", "abc", "-1GiB", "1.5ZiB", "1GiBx"])
def test_invalid_sizes(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_size(bad)


def test_format_default_is_si() -> None:
    assert format_size(1500) == "1.5KB"
    assert format_size(1000) == "1KB"


def test_format_binary() -> None:
    assert format_size(1536, binary=True) == "1.5KiB"
    assert format_size(1024, binary=True) == "1KiB"


def test_format_small_values() -> None:
    assert format_size(999) == "999B"
    assert format_size(0) == "0B"


def test_format_precision() -> None:
    assert format_size(1536, binary=True, precision=2) == "1.5KiB"
    assert format_size(1234567) == "1.2MB"


@pytest.mark.parametrize("value", [0, 1, 1000, 1_000_000, 1000 ** 3])
def test_roundtrip_exact_values(value: int) -> None:
    """只对"能被 SI 精确表示"的值做往返断言。"""
    assert parse_size(format_size(value)) == value


def test_si_formatting_is_lossy_for_binary_sizes() -> None:
    """1024 字节按 SI 显示成 1KB, 再解析回来是 1000 —— 这正是容量对不上的原因。"""
    assert format_size(1024) == "1KB"
    assert parse_size(format_size(1024)) == 1000
    # 想看真实字节数就用 IEC 输出
    assert parse_size(format_size(1024, binary=True)) == 1024


def test_roundtrip_binary() -> None:
    for value in (1024, 1024 ** 2, 1024 ** 3):
        assert parse_size(format_size(value, binary=True)) == value


def test_format_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        format_size(-1)
    with pytest.raises(TypeError):
        format_size(1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        format_size(10, precision=-1)
''',
    "tests/test_span.py": '''import pytest

from unitconv import format_span, parse_span


@pytest.mark.parametrize(
    "text,expected",
    [
        ("90s", 90.0),
        ("1h30m", 5400.0),
        ("1.5h", 5400.0),
        ("2d", 172800.0),
        ("1w", 604800.0),
        ("500ms", 0.5),
        ("1H30M", 5400.0),
        ("1h 30m", 5400.0),
        ("1h30m10s", 5410.0),
    ],
)
def test_parse_span(text: str, expected: float) -> None:
    assert parse_span(text) == pytest.approx(expected)


def test_bare_number_is_seconds() -> None:
    assert parse_span("90") == 90.0


def test_float_bare_number() -> None:
    assert parse_span("1.5") == 1.5


@pytest.mark.parametrize("bad", ["", "abc", "1x", "1h30", "30s1h?"])
def test_parse_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_span(bad)


def test_ms_not_confused_with_m() -> None:
    """ms 必须优先于 m 匹配, 否则 '10ms' 会被读成 10 分钟。"""
    assert parse_span("10ms") == pytest.approx(0.01)
    assert parse_span("10m") == 600.0


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "0s"),
        (1, "1s"),
        (90, "1m30s"),
        (5400, "1h30m"),
        (9001, "2h30m1s"),
        (604800, "1w"),
        (0.5, "500ms"),
    ],
)
def test_format_span(seconds: float, expected: str) -> None:
    assert format_span(seconds) == expected


def test_format_rejects_negative() -> None:
    with pytest.raises(ValueError):
        format_span(-1)


@pytest.mark.parametrize("seconds", [0, 1, 59, 60, 3599, 3600, 86400, 5400])
def test_roundtrip(seconds: int) -> None:
    assert parse_span(format_span(seconds)) == pytest.approx(seconds)


def test_month_and_year_units_unsupported() -> None:
    """'1y' 不支持; 注意 '1M' 因为大小写不敏感会被当成 1 分钟, 不是 1 个月。"""
    with pytest.raises(ValueError):
        parse_span("1y")
    assert parse_span("1M") == 60.0
''',
}

CHALLENGE = {
    "target": "unitconv/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 unitconv/challenge.py 中实现 rate_limit_desc(limit: str, window: str) -> str: "
        "把 '1.5GiB' 与 '1h' 渲染成 '1.5GiB/1h' 这种速率描述; "
        "复用 unitconv.size.parse_size 与 unitconv.span.parse_span, 任一解析失败就抛 ValueError。"
        "不得修改其他模块。"
    ),
    "tests_content": '''import pytest

from unitconv.challenge import rate_limit_desc


def test_desc() -> None:
    assert rate_limit_desc("1.5GiB", "1h") == "1.5GiB/1h"


def test_bad_input() -> None:
    with pytest.raises(ValueError):
        rate_limit_desc("abc", "1h")
''',
}
