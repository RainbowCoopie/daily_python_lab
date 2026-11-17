# 文件名清洗: 只保证"能落盘", 不猜业务意图。
from __future__ import annotations

import re
import unicodedata

REPLACEMENT = "_"
ILLEGAL_RUN = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
TRAILING = re.compile(r"[ .]+$")
PATH_SEP = re.compile(r"[\\/]+")
MAX_EXT_LEN = 10

RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CLOCK$"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
    | {"COM\u00b9", "COM\u00b2", "COM\u00b3", "LPT\u00b9", "LPT\u00b2", "LPT\u00b3"}
)


def split_ext(name: str) -> tuple[str, str]:
    """拆主名与扩展名; 扩展名超过 10 个字符或含空格时视为没有扩展名。"""
    if "." not in name:
        return name, ""
    stem, ext = name.rsplit(".", 1)
    if not ext or len(ext) > MAX_EXT_LEN or " " in ext:
        return name, ""
    return stem, "." + ext


def is_reserved(name: str) -> bool:
    """按第一个点之前的部分判断, 所以 COM1.tar.gz 也算危险。"""
    base = name.split(".")[0].strip().upper()
    return base in RESERVED


def sanitize(
    name: str,
    replacement: str = REPLACEMENT,
    max_len: int = 120,
    fallback: str = "unnamed",
) -> str:
    """返回一个 Windows 上一定能落盘的文件名。"""
    if max_len < 1:
        raise ValueError("max_len 必须 >= 1")

    text = unicodedata.normalize("NFC", str(name))
    text = PATH_SEP.split(text)[-1]          # 只取最后一段, 防路径穿越
    if text in ("", ".", ".."):
        return fallback

    text = ILLEGAL_RUN.sub(replacement, text)
    text = text.strip(" ")

    stem, ext = split_ext(text)
    stem = TRAILING.sub("", stem)            # 主名尾部的空格与句点必须去掉
    if not stem:
        return fallback
    text = stem + ext

    if is_reserved(text):
        text = replacement + text

    if len(text) > max_len:
        stem, ext = split_ext(text)
        if len(ext) >= max_len:
            text = stem[:max_len]
        else:
            text = stem[: max_len - len(ext)] + ext

    text = TRAILING.sub("", text)            # 截断可能又造出尾部空格
    return text or fallback


def is_safe(name: str) -> bool:
    """这个字符串能不能原样落盘。"""
    return sanitize(name) == name
