# 单元格级别的判定与保护。
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
    if body[0] in ("=", "+", "@", "\t", "\r"):
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
