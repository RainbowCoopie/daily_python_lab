# CSV 读写: BOM 处理 + 逐格保护 + 读回还原。
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .cells import MODE_FORMULA, sanitize, unprotect

BOM_BYTES = b"\xef\xbb\xbf"
BOM_CHAR = "\ufeff"


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
