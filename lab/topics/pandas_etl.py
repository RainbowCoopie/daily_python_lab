'''纯标准库的 CSV 清洗 + 聚合管道, 不装 pandas 也能跑, 装了就少写代码。'''

SLUG = "pandas_etl"
TITLE = "CSV 清洗聚合管道"
TAGS = ["pandas 思路", "stdlib csv", "数据工程", "tmp_path 测试"]
PKG = "etl"
SUMMARY = "读 CSV -> 去空白与空行 -> 数值字段安全转型 -> 分组求和 -> 回写, 全流程用标准库实现并覆盖脏数据。"
STACK_NOTES = [
    "脏数据优先: 空行、前后空格、非数字文本、缺失分组键逐个有测试",
    "数值转型失败降级为 None 而不是抛异常, 汇总时按 0 处理",
    "聚合结果排序固定, 输出可 diff",
]
NOTES = """
真实的业务 CSV 从来不长成训练集的样子。这里的策略是: 清洗阶段只做无损变换 (去空白/丢全空行),
转型失败保留 None 让上层决定; 聚合阶段再把 None 当 0。这样排查时能分清"数据缺"和"算错"。
"""

FILES = {
    "etl/__init__.py": '''from .pipeline import aggregate, build_summary, clean_rows, read_rows, write_rows

__all__ = ["read_rows", "clean_rows", "aggregate", "build_summary", "write_rows"]
''',
    "etl/pipeline.py": '''# CSV 清洗与聚合: 只用标准库 csv, 逻辑与 IO 分离。
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Sequence

Row = dict[str, Any]


def read_rows(path: str | Path) -> list[Row]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def clean_rows(rows: Iterable[Row], numeric_fields: Sequence[str] = ()) -> list[Row]:
    """去空白、丢全空行、按需把字段转成 float(失败则为 None)。"""
    numeric = set(numeric_fields)
    out: list[Row] = []
    for row in rows:
        cleaned: Row = {}
        for key, value in row.items():
            if isinstance(value, str):
                value = value.strip()
            if key in numeric and value not in ("", None):
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    value = None
            cleaned[key] = value
        if any(v not in ("", None) for v in cleaned.values()):
            out.append(cleaned)
    return out


def aggregate(
    rows: Iterable[Row], group_by: str, sum_field: str, default_key: str = "(unknown)"
) -> dict[str, float]:
    """按 group_by 分组, 对 sum_field 求和; 非数值一律按 0 计。"""
    totals: dict[str, float] = {}
    for row in rows:
        key = row.get(group_by) or default_key
        value = row.get(sum_field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            value = 0.0
        totals[str(key)] = totals.get(str(key), 0.0) + float(value)
    return dict(sorted(totals.items()))


def build_summary(rows: Iterable[Row], group_by: str, sum_field: str) -> list[Row]:
    totals = aggregate(rows, group_by, sum_field)
    return [{group_by: k, sum_field: v} for k, v in totals.items()]


def write_rows(path: str | Path, rows: Sequence[Row], fieldnames: Sequence[str]) -> int:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
''',
    "tests/test_pipeline.py": '''from pathlib import Path

import pytest

from etl import aggregate, build_summary, clean_rows, read_rows, write_rows

RAW = """region,amount,note
 north , 12.5 ,ok
south,abc,
north,7.5,fine

south,3,
"""


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    p = tmp_path / "raw.csv"
    p.write_text(RAW, encoding="utf-8")
    return p


def test_read_rows_skips_nothing_yet(csv_file: Path) -> None:
    rows = read_rows(csv_file)
    assert len(rows) == 4          # 含一行 "全是空字符串"
    assert rows[0]["region"] == " north "


def test_clean_rows_strips_and_drops_empty(csv_file: Path) -> None:
    rows = clean_rows(read_rows(csv_file), numeric_fields=["amount"])
    assert all(r["region"] != "" for r in rows)
    assert rows[0]["region"] == "north"
    assert rows[0]["amount"] == 12.5
    assert rows[1]["amount"] is None       # "abc" 转型失败 -> None


def test_aggregate_sums_non_numeric_as_zero(csv_file: Path) -> None:
    rows = clean_rows(read_rows(csv_file), numeric_fields=["amount"])
    totals = aggregate(rows, group_by="region", sum_field="amount")
    assert totals == {"north": 20.0, "south": 3.0}


def test_build_summary_shape(csv_file: Path) -> None:
    rows = clean_rows(read_rows(csv_file), numeric_fields=["amount"])
    summary = build_summary(rows, group_by="region", sum_field="amount")
    assert summary == [{"region": "north", "amount": 20.0}, {"region": "south", "amount": 3.0}]


def test_write_and_roundtrip(tmp_path: Path, csv_file: Path) -> None:
    rows = clean_rows(read_rows(csv_file), numeric_fields=["amount"])
    summary = build_summary(rows, group_by="region", sum_field="amount")
    out = tmp_path / "out.csv"
    assert write_rows(out, summary, ["region", "amount"]) == 2
    back = read_rows(out)
    assert back[0] == {"region": "north", "amount": "20.0"}
''',
}
