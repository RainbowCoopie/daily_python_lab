'''身份证、统一社会信用代码、银行卡号的校验与脱敏。纯标准库, 常数按国标逐位核对过。

灵感来源:
- 身份证校验码: GB 11643-1999, 即 ISO 7064:1983 MOD 11-2。
  加权因子 7 9 10 5 8 4 2 1 6 3 7 9 10 5 8 4 2, 余数查表 "10X98765432"
  (https://zh.wikipedia.org/zh-cn/%E6%A0%A1%E9%AA%8C%E7%A0%81)
- 统一社会信用代码: GB 32100-2015, 前 17 位各字符数值 × 3^(i-1) mod 31 求和,
  再用 31 减余数得到校验符; 字符集排除 I O Z S V, 共 31 个字符
  (https://hc.finecloud.com/app/zh_cn/doc/13974)
- 银行卡: Luhn (mod 10), 经典测试号 79927398713 有效、79927398710 无效
  (https://github.com/code-monkeys/TheAlgorithms-Python/blob/master/hashes/luhn.py)

为什么值得单独做一层: 数据管道和 RPA 导出的表里, 这三类号码到处都是, 但校验逻辑各自不同
(11 取模 / 31 取模 / 10 取模), 而且**长度差一位**、**大小写 X**、**中间夹空格**这些脏数据
在实际文件里全都出现过。写四遍不如写一次, 且必须能被测试钉住。
脱敏和校验放在一起, 是因为导出前的动作总是"先校验再打码", 两步拆开容易漏。
'''

SLUG = "cnvalid"
TITLE = "证件与卡号校验和脱敏"
TAGS = ["身份证校验", "统一社会信用代码", "Luhn", "数据脱敏"]
PKG = "cnvalid"
SUMMARY = "身份证(MOD 11-2)、统一社会信用代码(MOD 31)、银行卡(Luhn)三种校验, 外加导出前的打码。"
STACK_NOTES = [
    "三套取模各自独立实现, 常数按国标与公开算例逐位核对后再写进测试",
    "输入统一先做规范化: 去空格、全角转半角、字母转大写, 脏数据不至于静默判错",
    "脱敏与校验相邻: 导出前先校验再打码, 校验不过的不静默打码掩盖问题",
]
NOTES = """
三套算法长得像但互不通用, 混用是最常见的 bug 来源:

| 号码 | 位数 | 加权 | 取模 | 校验符表 |
|---|---|---|---|---|
| 公民身份号码 | 18 | 7 9 10 5 8 4 2 1 ... | 11 | 10X98765432 |
| 统一社会信用代码 | 18 | 3^0 3^1 ... mod 31 | 31 | 31 个字符, 无 I O Z S V |
| 银行卡号 | 12~19 | 从右往左隔位乘 2 | 10 | 数字 |

身份证的余数表里有 X: 余数为 2 时校验码是 X 而不是 10 —— 因为 18 位放不下两位数。
统一社会信用代码里 31 - 0 = 31 要落回 0, 这个边界最容易写错。
Luhn 的"隔位乘 2"要从**最右边**数起, 从左往右数会算错奇数长度的卡号。

顺带一条分层原则: `is_valid` 只校验校验码, 不查生日是否真实存在 ——
因为国标算例 123456789012345677 的校验码是对的, 中间却是"7890 年 12 月 34 日"。
要不要卡这一层, 取决于调用方: 入库校验码用 is_valid, 要做业务判断用 parse(它才会验日期)。
"""

FILES = {
    "cnvalid/__init__.py": '''from .id_card import check_digit as id_check_digit
from .id_card import is_valid as id_valid
from .id_card import parse as id_parse
from .luhn import check_digit as luhn_check_digit
from .luhn import is_valid as luhn_valid
from .masking import mask, mask_id_card
from .uscc import check_digit as uscc_check_digit
from .uscc import is_valid as uscc_valid

__all__ = [
    "id_check_digit",
    "id_valid",
    "id_parse",
    "uscc_check_digit",
    "uscc_valid",
    "luhn_check_digit",
    "luhn_valid",
    "mask",
    "mask_id_card",
]
''',
    "cnvalid/id_card.py": '''# 公民身份号码: GB 11643-1999 / ISO 7064 MOD 11-2。
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
''',
    "cnvalid/uscc.py": '''# 统一社会信用代码: GB 32100-2015, 3^(i-1) mod 31 加权。
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
''',
    "cnvalid/luhn.py": '''# 银行卡号: Luhn (mod 10)。
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
''',
    "cnvalid/masking.py": '''# 导出前的脱敏: 保留头尾, 中间打码。
from __future__ import annotations

DEFAULT_FILL = "*"


def mask(value: str, head: int = 3, tail: int = 4, fill: str = DEFAULT_FILL) -> str:
    """保留前 head 位与后 tail 位; 长度不够时整体替换为等长的填充符。"""
    if head < 0 or tail < 0:
        raise ValueError("head 和 tail 不能为负")
    body = str(value)
    if len(body) <= head + tail:
        return fill * len(body)
    return body[:head] + fill * (len(body) - head - tail) + body[-tail:]


def mask_id_card(value: str, head: int = 3, tail: int = 4) -> str:
    return mask(value, head, tail)


def mask_phone(value: str, head: int = 3, tail: int = 4) -> str:
    return mask(value, head, tail)


def mask_card(value: str, head: int = 4, tail: int = 4) -> str:
    return mask(value, head, tail)
''',
    "tests/test_id_card.py": '''import pytest
from datetime import date

from cnvalid import id_check_digit, id_parse, id_valid


def test_check_digit_matches_official_example() -> None:
    # 科普中国给的算例: 前 17 位 12345678901234567, 校验码应为 7
    assert id_check_digit("12345678901234567") == "7"


def test_check_digit_x_case() -> None:
    # 余数为 2 时校验码是 X, 不是 10
    assert id_check_digit("11010519491231002") == "X"


def test_valid_known_numbers() -> None:
    assert id_valid("123456789012345677") is True
    assert id_valid("11010519491231002X") is True


def test_lowercase_x_accepted() -> None:
    assert id_valid("11010519491231002x") is True


def test_spaces_and_fullwidth_normalised() -> None:
    assert id_valid(" 11010519491231002X ") is True
    assert id_valid("１１０１０５１９４９１２３１００２Ｘ") is True


def test_wrong_check_digit_rejected() -> None:
    assert id_valid("110105194912310021") is False


def test_wrong_length_or_chars_rejected() -> None:
    assert id_valid("1101051949123100") is False
    assert id_valid("11010519491231002Y") is False
    assert id_valid("1101051949123100AX") is False
    assert id_valid("") is False


def test_check_digit_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        id_check_digit("123")
    with pytest.raises(ValueError):
        id_check_digit("1234567890123456A")


def test_parse_fields() -> None:
    info = id_parse("11010519491231002X")
    assert info["region"] == "110105"
    assert info["birth"] == date(1949, 12, 31)
    assert info["gender"] == "女"          # 第 17 位是 2, 偶数
    assert info["check"] == "X"


def test_parse_gender_male() -> None:
    # 123456789012345677 是国标算例, 中间不是真生日, 不能用来测 parse
    body = "11010519900315001"        # 第 17 位是 1, 奇数 => 男
    info = id_parse(body + id_check_digit(body))
    assert info["gender"] == "男"
    assert info["birth"] == date(1990, 3, 15)


def test_parse_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        id_parse("110105194912310021")


def test_parse_rejects_impossible_date() -> None:
    # 构造一个校验码正确但日期不存在的号码
    body = "11010519900230" + "001"
    with pytest.raises(ValueError):
        id_parse(body + id_check_digit(body))
''',
    "tests/test_uscc.py": '''import pytest

from cnvalid import uscc_check_digit, uscc_valid


def test_check_digit_known_code() -> None:
    assert uscc_check_digit("91350100M000100Y4") == "3"


def test_valid_known_code() -> None:
    assert uscc_valid("91350100M000100Y43") is True


def test_tampered_code_rejected() -> None:
    assert uscc_valid("91350211M000100Y43") is False


def test_wrong_length_rejected() -> None:
    assert uscc_valid("91350100M000100Y4") is False
    assert uscc_valid("91350100M000100Y433") is False


def test_lowercase_normalised() -> None:
    assert uscc_valid("91350100m000100y43") is True


def test_forbidden_letters_rejected() -> None:
    for bad in ("I", "O", "Z", "S", "V"):
        assert uscc_valid(bad + "1350100M000100Y43") is False


def test_check_digit_validation() -> None:
    with pytest.raises(ValueError):
        uscc_check_digit("9135")
    with pytest.raises(ValueError):
        uscc_check_digit("91350100M000100YI")


def test_remainder_zero_lands_on_zero() -> None:
    """31 - 0 = 31 必须落回 0, 否则索引越界。"""
    assert uscc_check_digit("00000000000000000") == "0"
''',
    "tests/test_luhn.py": '''import pytest

from cnvalid import luhn_check_digit, luhn_valid


@pytest.mark.parametrize("number", ["79927398713", "4111111111111111", "5500005555555559"])
def test_known_valid(number: str) -> None:
    assert luhn_valid(number) is True


@pytest.mark.parametrize("number", ["79927398710", "79927398711", "4111111111111112"])
def test_known_invalid(number: str) -> None:
    assert luhn_valid(number) is False


def test_check_digit_recovers_last_digit() -> None:
    assert luhn_check_digit("7992739871") == "3"
    assert luhn_check_digit("411111111111111") == "1"


def test_every_prefix_gets_a_valid_digit() -> None:
    for prefix in ("7992739871", "411111111111111", "62"):
        assert luhn_valid(prefix + luhn_check_digit(prefix))


def test_rejects_non_digits_and_tiny_input() -> None:
    assert luhn_valid("4111-1111") is False
    assert luhn_valid("") is False
    assert luhn_valid("7") is False


def test_check_digit_rejects_bad_prefix() -> None:
    with pytest.raises(ValueError):
        luhn_check_digit("")
    with pytest.raises(ValueError):
        luhn_check_digit("12a4")


def test_spaces_ignored() -> None:
    assert luhn_valid("4111 1111 1111 1111") is True
''',
    "tests/test_masking.py": '''import pytest

from cnvalid import mask, mask_id_card


def test_mask_default_keeps_head_and_tail() -> None:
    assert mask("110101199003071234") == "110***********1234"


def test_mask_custom_widths() -> None:
    assert mask("110101199003071234", head=6, tail=4) == "110101********1234"
    assert mask("110101199003071234", head=0, tail=4) == "**************1234"


def test_mask_phone() -> None:
    assert mask("13800138000", head=3, tail=4) == "138****8000"


def test_mask_short_value_fully_hidden() -> None:
    assert mask("1234567", head=3, tail=4) == "*******"
    assert mask("", head=3, tail=4) == ""


def test_mask_length_preserved() -> None:
    for value in ("1234", "123456789012345678", "abc"):
        assert len(mask(value)) == len(value)


def test_mask_custom_fill() -> None:
    assert mask("13800138000", 3, 4, fill="#") == "138####8000"


def test_mask_rejects_negative_widths() -> None:
    with pytest.raises(ValueError):
        mask("123", head=-1)
    with pytest.raises(ValueError):
        mask("123", tail=-1)


def test_mask_id_card_helper() -> None:
    assert mask_id_card("11010519491231002X") == "110***********002X"
''',
}

CHALLENGE = {
    "target": "cnvalid/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 cnvalid/challenge.py 中实现 audit(values: list[str]) -> dict[str, int]: "
        "对每个值依次用 cnvalid.id_card.is_valid 与 cnvalid.uscc.is_valid 判断, "
        "返回 {'id_card': 有效身份证个数, 'uscc': 有效信用代码个数, 'unknown': 都不是的个数}。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from cnvalid.challenge import audit


def test_counts_each_kind() -> None:
    values = ["11010519491231002X", "91350100M000100Y43", "110105194912310021"]
    assert audit(values) == {"id_card": 1, "uscc": 1, "unknown": 1}


def test_empty() -> None:
    assert audit([]) == {"id_card": 0, "uscc": 0, "unknown": 0}
''',
}
