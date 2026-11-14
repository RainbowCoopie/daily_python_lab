'''导出给 Excel 的 CSV 保护层: 长数字、前导零、日期陷阱、公式注入、BOM 首列, 五个坑一次处理完。

灵感来源:
- Excel 会把超过 15 位的数字转成科学计数法, 且末几位直接变 0 —— 身份证/银行卡/订单号全中招
  (https://learn.microsoft.com/zh-cn/answers/questions/4969830/15-excel-n-0)
- CSV 公式注入是正式的 Web 安全问题, 以 = + - @ 开头的单元格会被当公式执行
  (https://wstg.owasp.org/latest/4-Web_Application_Security_Testing/07-Injection/21-CSV_Injection/)
- UTF-8 BOM 会让首列表头变成 "\\ufeff列名", 下游按列名取值就取不到
  (https://github.com/pyrite-wiki/pyrite/pull/1217)

为什么值得单独做一层: 这五个坑的共同点是"文件生成时完全正常, 只有被人用 Excel 打开才出错"。
测试跑在字符串层面永远发现不了, RPA 里表现为"字段明明有值, 但取出来是 1.23E+17 或者空"。
本模块把"生成时该不该转义"和"读回来怎么还原"两件事都实现, 并且保证往返一致。
'''

SLUG = "xlsafe"
TITLE = "导出表格的字段保护"
TAGS = ["CSV 注入", "BOM", "长数字", "数据管线"]
PKG = "xlsafe"
SUMMARY = '导出 CSV 前判定长数字、前导零、日期陷阱和公式注入, 用 ="..." 或单引号保护, 读回来能原样还原。'
STACK_NOTES = [
    "15 位以上数字、前导零、3-5 这种日期陷阱, 逐条独立判定, 不靠一个正则蒙",
    "公式注入单独识别: 纯负数 -3 不算危险, -3+cmd 才算",
    '写入可选 UTF-8 BOM, 读回时剥掉表头里的 BOM, 并支持把 ="..." 还原成原值',
]
NOTES = """
为什么用 `="..."` 而不是在前面加单引号: 在 Excel 直接打开 CSV 这个场景里,
`="123"` 是一个"返回字符串的公式", 单元格显示 123 且格式是文本, 后续不会变科学计数法;
而加单引号只在单元格编辑状态下才是文本标记, 导入 CSV 时那个引号会原样显示出来。
所以默认用 formula 模式, 单引号模式留给 Google Sheets 之类更认前缀的场景。

长度阈值取 15 是 Excel 的硬限制: 它用双精度浮点存数字, 有效位数 15 位,
第 16 位开始就不保证正确。所以 15 位及以上一律当文本处理。

字段名也要防: 表头里的 BOM 会让 `row["\\ufeff姓名"]` 静默取不到值,
这类 bug 在 RPA 里表现为"整列数据突然全空", 排查成本极高。
"""

FILES = {
    "xlsafe/__init__.py": '''from .cells import (
    MODE_FORMULA,
    MODE_QUOTE,
    inspect,
    looks_like_date,
    looks_like_formula,
    looks_like_leading_zero,
    looks_like_long_number,
    sanitize,
    to_text_cell,
    unprotect,
)
from .csvio import has_bom, read_csv, strip_bom, write_csv

__all__ = [
    "MODE_FORMULA",
    "MODE_QUOTE",
    "inspect",
    "looks_like_long_number",
    "looks_like_leading_zero",
    "looks_like_date",
    "looks_like_formula",
    "to_text_cell",
    "unprotect",
    "sanitize",
    "has_bom",
    "strip_bom",
    "write_csv",
    "read_csv",
]
''',
    "xlsafe/cells.py": '''# 单元格级别的判定与保护。
from __future__ import annotations

MODE_FORMULA = "formula"
MODE_QUOTE = "quote"
MODES = (MODE_FORMULA, MODE_QUOTE)

LONG_NUMBER_DIGITS = 15
DATE_TRAP_CHARS = "-/"


def looks_like_long_number(value: str) -> bool:
    """15 位及以上的纯数字: Excel 用双精度存, 第 16 位起不保证正确。"""
    body = value.strip()
    if body[:1] in ("+", "-"):
        body = body[1:]
    return body.isdigit() and len(body) >= LONG_NUMBER_DIGITS


def looks_like_leading_zero(value: str) -> bool:
    """007 这种前导零会被 Excel 吃掉成 7。"""
    body = value.strip()
    return len(body) > 1 and body.isdigit() and body[0] == "0"


def looks_like_date(value: str) -> bool:
    """3-5 / 3/5 / 2026-11-11 会被 Excel 自动转成日期。"""
    body = value.strip()
    if not body or " " in body:
        return False
    for sep in DATE_TRAP_CHARS:
        if sep in body:
            pieces = body.split(sep)
            return len(pieces) in (2, 3) and all(p.isdigit() and p for p in pieces)
    return False


def looks_like_formula(value: str) -> bool:
    """以 = + @ 或制表符/回车开头, 或以 - 开头但后面不是纯数字。"""
    body = value.strip()
    if not body:
        return False
    if body[0] in ("=", "+", "@", "\\t", "\\r"):
        return True
    if body[0] == "-":
        rest = body[1:]
        return not rest.replace(".", "", 1).isdigit()
    return False


def inspect(value: str) -> list[str]:
    """返回命中的风险类型, 顺序固定, 便于断言。"""
    reasons: list[str] = []
    if looks_like_formula(value):
        reasons.append("formula")
    if looks_like_long_number(value):
        reasons.append("long_number")
    if looks_like_leading_zero(value):
        reasons.append("leading_zero")
    if looks_like_date(value):
        reasons.append("date")
    return reasons


def to_text_cell(value: str, mode: str = MODE_FORMULA) -> str:
    """把值包装成 Excel 认定的文本。"""
    if mode == MODE_QUOTE:
        return "'" + value
    if mode != MODE_FORMULA:
        raise ValueError(f"未知模式 {mode!r}, 只支持 {MODES}")
    return '="' + value.replace('"', '""') + '"'


def unprotect(value: str) -> str:
    """把 to_text_cell 的结果还原成原值; 不像保护格式就原样返回。"""
    if value.startswith("'") and len(value) > 1:
        return value[1:]
    if value.startswith('="') and value.endswith('"') and len(value) >= 3:
        return value[2:-1].replace('""', '"')
    return value


def sanitize(value: str, mode: str = MODE_FORMULA) -> str:
    """有风险就包装, 没风险原样返回。"""
    return to_text_cell(value, mode) if inspect(value) else value
''',
    "xlsafe/csvio.py": '''# CSV 读写: BOM 处理 + 逐格保护 + 读回还原。
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .cells import MODE_FORMULA, sanitize, unprotect

BOM_BYTES = b"\\xef\\xbb\\xbf"
BOM_CHAR = "\\ufeff"


def has_bom(raw: bytes) -> bool:
    return raw.startswith(BOM_BYTES)


def strip_bom(text: str) -> str:
    return text[1:] if text.startswith(BOM_CHAR) else text


def write_csv(
    path: str | Path,
    rows: Iterable[Mapping[str, object]],
    fieldnames: Sequence[str],
    *,
    utf8_bom: bool = True,
    protect: bool = True,
    mode: str = MODE_FORMULA,
) -> int:
    """写 CSV。默认带 BOM(Excel 才不会把中文读成乱码)并逐格保护。"""
    pairs = list(rows)
    encoding = "utf-8-sig" if utf8_bom else "utf-8"
    with open(path, "w", newline="", encoding=encoding) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        written = 0
        for row in pairs:
            out = {
                key: (sanitize(str(row[key]), mode) if protect and row.get(key) is not None else row.get(key, ""))
                for key in fieldnames
            }
            writer.writerow(out)
            written += 1
    return written


def read_csv(path: str | Path, *, unprotect_cells: bool = True) -> list[dict[str, str]]:
    """读 CSV; 剥离表头里的 BOM, 并可选地把保护过的值还原。

    必须把文件对象直接交给 csv 模块, 不能用 splitlines() 先切行:
    引号字段里的换行是数据的一部分, 提前切行会把它吃掉。
    """
    source = Path(path)
    raw = source.read_bytes()
    encoding = "utf-8-sig" if has_bom(raw) else "utf-8"
    rows: list[dict[str, str]] = []
    with open(source, newline="", encoding=encoding) as fh:
        for row in csv.DictReader(fh):
            cleaned = {
                strip_bom(str(key)): (unprotect(str(value)) if unprotect_cells else str(value))
                for key, value in row.items()
                if key is not None
            }
            rows.append(cleaned)
    return rows
''',
    "tests/test_cells.py": '''import pytest

from xlsafe import (
    MODE_QUOTE,
    inspect,
    looks_like_date,
    looks_like_formula,
    looks_like_leading_zero,
    looks_like_long_number,
    sanitize,
    to_text_cell,
    unprotect,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("138001380001234567", True),
        ("123456789012345", True),      # 正好 15 位
        ("12345678901234", False),      # 14 位, Excel 吃得下
        ("-123456789012345", True),
        ("13800138000", False),         # 11 位手机号, 无风险
        ("123456789012345a", False),
    ],
)
def test_looks_like_long_number(value: str, expected: bool) -> None:
    assert looks_like_long_number(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [("007", True), ("00", True), ("0", False), ("0.5", False), ("700", False)],
)
def test_looks_like_leading_zero(value: str, expected: bool) -> None:
    assert looks_like_leading_zero(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [("3-5", True), ("3/5", True), ("2026-11-11", True), ("2026-11-11 10:00", False), ("abc-def", False), ("", False)],
)
def test_looks_like_date(value: str, expected: bool) -> None:
    assert looks_like_date(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("=1+1", True),
        ("@SUM(A1)", True),
        ("+8613800138000", True),
        ("-3+cmd", True),
        ("\\t=1+1", True),
        ("-3", False),          # 纯负数是正常数据
        ("-3.5", False),
        ("hello", False),
        ("", False),
    ],
)
def test_looks_like_formula(value: str, expected: bool) -> None:
    assert looks_like_formula(value) is expected


def test_inspect_collects_reasons_in_order() -> None:
    # 以 = 开头时它首先是公式, 不是"长数字"; 保护动作已经由 formula 负责
    assert inspect("=1234567890123456") == ["formula"]
    assert inspect("1234567890123456") == ["long_number"]
    assert inspect("007") == ["leading_zero"]
    assert inspect("2026-11-11") == ["date"]
    assert inspect("hello") == []


def test_to_text_cell_formula_mode() -> None:
    assert to_text_cell("123") == '="123"'


def test_to_text_cell_escapes_inner_quotes() -> None:
    assert to_text_cell('a"b') == '="a""b"'


def test_to_text_cell_quote_mode() -> None:
    assert to_text_cell("123", MODE_QUOTE) == "'123"


def test_to_text_cell_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        to_text_cell("x", "weird")


@pytest.mark.parametrize("mode", ["formula", "quote"])
def test_protect_unprotect_roundtrip(mode: str) -> None:
    for value in ("123", 'a"b', "007", "-3+cmd"):
        assert unprotect(to_text_cell(value, mode)) == value


def test_unprotect_leaves_plain_text_alone() -> None:
    assert unprotect("hello") == "hello"
    assert unprotect("") == ""


def test_sanitize_only_touches_risky_values() -> None:
    assert sanitize("hello") == "hello"
    assert sanitize("138001380001234567") == '="138001380001234567"'
    assert sanitize("=cmd", MODE_QUOTE) == "'=cmd"
''',
    "tests/test_csvio.py": '''import csv
from pathlib import Path

import pytest

from xlsafe import has_bom, read_csv, strip_bom, write_csv

ROWS = [
    {"姓名": "张三", "身份号": "110101199003071234", "工号": "007"},
    {"姓名": "李四", "身份号": "310101198512310001", "工号": "1234"},
]
FIELDS = ["姓名", "身份号", "工号"]


def test_has_bom_and_strip() -> None:
    assert has_bom(b"\\xef\\xbb\\xbfabc") is True
    assert has_bom(b"abc") is False
    assert strip_bom("\\ufeff姓名") == "姓名"
    assert strip_bom("姓名") == "姓名"


def test_write_csv_emits_bom_by_default(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    assert write_csv(path, ROWS, FIELDS) == 2
    assert has_bom(path.read_bytes()) is True


def test_write_csv_without_bom(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    write_csv(path, ROWS, FIELDS, utf8_bom=False)
    assert has_bom(path.read_bytes()) is False


def test_write_csv_protects_long_number_and_leading_zero(tmp_path: Path) -> None:
    """断言必须在"CSV 解析之后"这一层: ="..." 本身含引号, 落盘时会被再包一层转义。"""
    path = tmp_path / "out.csv"
    write_csv(path, ROWS, FIELDS, utf8_bom=False)
    with open(path, newline="", encoding="utf-8") as fh:
        cells = list(csv.DictReader(fh))
    assert cells[0]["身份号"] == '="110101199003071234"'
    assert cells[0]["工号"] == '="007"'
    assert cells[1]["工号"] == "1234"          # 4 位数没有风险, 不该被动


def test_read_csv_keeps_first_header_clean(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    write_csv(path, ROWS, FIELDS)
    rows = read_csv(path)
    assert set(rows[0]) == {"姓名", "身份号", "工号"}
    assert rows[0]["姓名"] == "张三"


def test_read_csv_unprotects_values(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    write_csv(path, ROWS, FIELDS)
    rows = read_csv(path)
    assert rows[0]["身份号"] == "110101199003071234"
    assert rows[0]["工号"] == "007"


def test_roundtrip_is_lossless(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    write_csv(path, ROWS, FIELDS)
    assert read_csv(path) == [dict(r) for r in ROWS]


def test_read_csv_can_skip_unprotect(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    write_csv(path, ROWS, FIELDS)
    rows = read_csv(path, unprotect_cells=False)
    assert rows[0]["工号"] == '="007"'


def test_formula_payload_is_neutralised_in_file(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    payload = {"姓名": "=cmd|' /C calc'!A0", "身份号": "1", "工号": "2"}
    write_csv(path, [payload], FIELDS, utf8_bom=False)
    body = path.read_text(encoding="utf-8")
    # 危险值必须以 ="..." 形式出现, 而不是裸公式
    assert '"=""=cmd' in body
    assert read_csv(path)[0]["姓名"] == "=cmd|' /C calc'!A0"


def test_protect_can_be_disabled(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    write_csv(path, ROWS, FIELDS, utf8_bom=False, protect=False)
    body = path.read_text(encoding="utf-8")
    assert "110101199003071234" in body
    assert '="' not in body


def test_quote_mode(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    write_csv(path, ROWS, FIELDS, utf8_bom=False, mode="quote")
    body = path.read_text(encoding="utf-8")
    assert "'007" in body
    assert read_csv(path)[0]["工号"] == "007"


def test_read_csv_keeps_newline_inside_quoted_field(tmp_path: Path) -> None:
    """引号字段里的换行是数据, 不能被当成行分隔符切掉。"""
    path = tmp_path / "multi.csv"
    path.write_text('姓名,备注\n张三,"第一行\n第二行"\n', encoding="utf-8")
    value = read_csv(path)[0]["备注"]
    assert value.replace("\r\n", "\n") == "第一行\n第二行"


def test_roundtrip_with_multiline_and_punctuation(tmp_path: Path) -> None:
    rows = [{"姓名": "张三", "备注": '第一行\n第二行, 带逗号 "引号"'}]
    path = tmp_path / "out.csv"
    write_csv(path, rows, ["姓名", "备注"])
    back = read_csv(path)
    assert back[0]["备注"].replace("\r\n", "\n") == '第一行\n第二行, 带逗号 "引号"'
''',
}

CHALLENGE = {
    "target": "xlsafe/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 xlsafe/challenge.py 中实现 audit(rows, fieldnames) -> dict[str, int]: "
        "统计每个字段触发风险保护的次数, 复用 xlsafe.cells.inspect; "
        "只返回计数大于 0 的字段, 按字段在 fieldnames 中的顺序输出。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from xlsafe.challenge import audit


def test_counts_only_risky_fields() -> None:
    rows = [
        {"id": "110101199003071234", "name": "张三"},
        {"id": "110101199003071235", "name": "李四"},
        {"id": "1", "name": "=cmd"},
    ]
    assert audit(rows, ["id", "name"]) == {"id": 2, "name": 1}


def test_empty_when_nothing_risky() -> None:
    assert audit([{"a": "hello"}], ["a"]) == {}
''',
}
