# 乱码打分与修复: 反向解码 + 坏度比较。
from __future__ import annotations

from dataclasses import dataclass

REPLACEMENT = "\ufffd"

# 常见"UTF-8 被当单字节编码读"时冒出来的引导字符
SUSPECT_LATIN = set("ÃÂãâÄÅäå")

# 已知的不可逆产物
ARTIFACTS = ("锟斤拷", "烫烫烫", "屯屯屯", "ï¿½")

ENCODINGS = ("latin-1", "cp1252", "gbk", "big5", "shift_jis")


@dataclass(frozen=True)
class Repair:
    text: str
    encoding: str | None
    score_before: int
    score_after: int

    @property
    def improved(self) -> bool:
        return self.encoding is not None and self.score_after < self.score_before


def _is_kana(ch: str) -> bool:
    return "\u3040" <= ch <= "\u30ff"


def score(text: str) -> int:
    """坏度分: 越高越像乱码。正常文本应为 0。"""
    total = 0
    for token in ARTIFACTS:
        total += text.count(token) * 5
    for ch in text:
        code = ord(ch)
        if ch == REPLACEMENT:
            total += 10
        elif ch in SUSPECT_LATIN:
            total += 2
        elif 0x80 <= code <= 0x9F:      # C1 控制符, 正常文本里不该出现
            total += 3
        elif 0xE000 <= code <= 0xF8FF:  # 私用区
            total += 4
        elif _is_kana(ch):              # 假名混进中文, 多半是 GBK 方向劈坏的
            total += 1
    return total


def candidates(text: str) -> list[tuple[str, str]]:
    """所有能成功反向解码、且不含替换符的候选, 按坏度升序。"""
    out: list[tuple[str, str]] = []
    for encoding in ENCODINGS:
        try:
            raw = text.encode(encoding)
            decoded = raw.decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if REPLACEMENT in decoded or decoded == text:
            continue
        out.append((encoding, decoded))
    out.sort(key=lambda item: (score(item[1]), len(item[1])))
    return out


def _best(text: str) -> tuple[str | None, str]:
    """整串最优候选; 没有改善则返回 (None, text)。"""
    before = score(text)
    for encoding, decoded in candidates(text):
        if score(decoded) < before:
            return encoding, decoded
    return None, text


def _split_latin_runs(text: str) -> list[tuple[bool, str]]:
    """按"是否单字节可编码"切片段, 用来处理正常中文里夹一段火星文。"""
    pieces: list[tuple[bool, str]] = []
    buf: list[str] = []
    flag: bool | None = None
    for ch in text:
        is_latin = ord(ch) < 0x100
        if flag is None or is_latin == flag:
            buf.append(ch)
            flag = is_latin
        else:
            pieces.append((bool(flag), "".join(buf)))
            buf = [ch]
            flag = is_latin
    if buf:
        pieces.append((bool(flag), "".join(buf)))
    return pieces


def repair(text: str) -> Repair:
    """给出最佳修复; 修不好就原样返回。"""
    before = score(text)

    encoding, fixed = _best(text)
    if encoding is not None:
        return Repair(text=fixed, encoding=encoding, score_before=before, score_after=score(fixed))

    # 整串修不动: 试试只修其中的单字节片段
    used: list[str] = []
    rebuilt: list[str] = []
    for is_latin, piece in _split_latin_runs(text):
        if is_latin and len(piece) >= 2:
            enc, sub = _best(piece)
            if enc is not None:
                used.append(enc)
                rebuilt.append(sub)
                continue
        rebuilt.append(piece)

    joined = "".join(rebuilt)
    if joined != text and score(joined) < before:
        tag = "+".join(sorted(set(used)))
        return Repair(text=joined, encoding=tag, score_before=before, score_after=score(joined))
    return Repair(text=text, encoding=None, score_before=before, score_after=before)


def is_mojibake(text: str) -> bool:
    """能修 或 命中已知不可逆产物, 都算乱码。"""
    if any(token in text for token in ARTIFACTS):
        return True
    return repair(text).improved
