import csv
from pathlib import Path

import pytest

from xlsafe import has_bom, read_csv, strip_bom, write_csv

ROWS = [
    {"姓名": "张三", "身份号": "110101199003071234", "工号": "007"},
    {"姓名": "李四", "身份号": "310101198512310001", "工号": "1234"},
]
FIELDS = ["姓名", "身份号", "工号"]


def test_has_bom_and_strip() -> None:
    assert has_bom(b"\xef\xbb\xbfabc") is True
    assert has_bom(b"abc") is False
    assert strip_bom("\ufeff姓名") == "姓名"
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
