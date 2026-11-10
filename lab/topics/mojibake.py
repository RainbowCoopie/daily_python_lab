'''乱码检测与修复: 给一段文本打分, 找出最可能的"原始编码", 并区分"能修"和"只能认出是坏的"。

灵感来源:
- ftfy 的 badness 思路: 用可疑字符的出现频率给文本打"坏度"分, 修完再比分数
  (https://ftfy.readthedocs.io/en/v6.3.0/heuristic.html)
- "锟斤拷"的成因: U+FFFD 替换符被按 GBK 编码后形成的固定串, 信息已丢, 只能识别不能还原
  (https://rivers.chaitin.cn/blog/cq94j790lnechd243gl0)
- 一个真实事故: Windows 上把 UTF-8 中文路径按 GBK 写坏, 落盘成幽灵目录树
  (https://atomgit.com/atomgit_atomcode/atomcode/issues/1765)

为什么值得单独做一层: 中文环境里"文件读出来是火星文"这件事每周都会遇到,
而 chardet 那类库解决的是"这些字节是什么编码", 不是"这段文本已经坏了该怎么办"。
本模块只做后者: 输入 str, 输出修复建议 + 坏度分数 + 是否可修。

判定策略: 每个候选编码做一次"反向解码" (str -> bytes -> str), 只接受
"坏度下降 且 结果里没有 U+FFFD" 的候选。这样既不会把正常法语 café 判成乱码,
也不会把已经丢了信息的 锟斤拷 硬掰成假的中文。
'''

SLUG = "mojibake"
TITLE = "乱码检测与修复建议"
TAGS = ["编码", "乱码修复", "GBK/UTF-8", "启发式打分"]
PKG = "mojibake"
SUMMARY = "给文本打坏度分, 反推最可能的原始编码并尝试还原, 同时明确区分「能修回来」和「信息已丢」。"
STACK_NOTES = [
    "坏度分由替换符、C1 控制符、私用区、可疑引导字符和假名混入共同构成",
    "只接受坏度下降且结果无 U+FFFD 的候选, 修不好就老实返回原文",
    "整串修不动时退化成按片段修, 处理「正常中文夹着一段火星文」这种真实情况",
]
NOTES = """
两种乱码的方向必须分清: **UTF-8 字节被按单字节编码读** (latin-1 方向) 和
**UTF-8 字节被按 GBK 读** (双字节方向)。前者得到 `ä½\\xa0å¥½`, 后者得到 `浣犲ソ`,
两者都能原路还原。而 `锟斤拷` 是 U+FFFD 再编码的产物 —— 原文在每个替换符的位置上
都已经丢了, 任何还原都只能得到替换符, 所以这一类只报"坏", 不报"可修"。

假名混入是个好信号: GBK 方向的乱码经常把汉字劈成"汉字 + 片假名"的组合,
而正常中文文本里几乎不会有片假名。所以对片假名计分能提高 GBK 方向的召回。
代价是对纯日文会误报坏度 —— 但纯日文过不了"坏度下降"这一关, 所以不会被当成可修。

已知限制: 分段修复只在"火星文片段是单字节可编码"时有效(ord < 0x100),
GBK 方向的乱码整串出现时走整串路径, 混排的 GBK 乱码暂不支持。
"""

FILES = {
    "mojibake/__init__.py": '''from .fix import Repair, candidates, is_mojibake, repair, score

__all__ = ["Repair", "score", "candidates", "repair", "is_mojibake"]
''',
    "mojibake/fix.py": '''# 乱码打分与修复: 反向解码 + 坏度比较。
from __future__ import annotations

from dataclasses import dataclass

REPLACEMENT = "\\ufffd"

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
    return "\\u3040" <= ch <= "\\u30ff"


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
''',
    "tests/test_fix.py": '''import pytest

from mojibake import Repair, candidates, is_mojibake, repair, score


def make_mojibake(text: str, encoding: str = "latin-1") -> str:
    """按指定编码把 UTF-8 字节流读坏, 得到火星文。"""
    return text.encode("utf-8").decode(encoding)


def test_clean_text_scores_zero() -> None:
    assert score("hello world") == 0
    assert score("你好，世界") == 0
    assert score("") == 0


def test_latin_mojibake_has_positive_score() -> None:
    assert score(make_mojibake("你好")) > 0


def test_artifact_token_scored() -> None:
    assert score("锟斤拷") >= 5


def test_replacement_char_heavily_penalised() -> None:
    assert score("\\ufffd") >= 10


def test_kana_penalised() -> None:
    assert score("ソ") == 1


def test_c1_and_private_use_penalised() -> None:
    assert score("\\x81") == 3
    assert score("\\ue000") == 4


@pytest.mark.parametrize("sample", ["你好", "数据管道", "RPA 流程", "中文路径"])
def test_repair_latin1_roundtrip(sample: str) -> None:
    broken = make_mojibake(sample)
    result = repair(broken)
    assert result.text == sample
    assert result.encoding == "latin-1"
    assert result.improved is True
    assert result.score_after < result.score_before


def test_repair_gbk_roundtrip() -> None:
    broken = make_mojibake("你好", "gbk")
    assert broken == "浣犲ソ"
    result = repair(broken)
    assert result.text == "你好"
    assert result.encoding == "gbk"


def test_repair_leaves_clean_text_alone() -> None:
    for text in ("hello", "你好", "café", "Ãlvaro", "こんにちは"):
        result = repair(text)
        assert result.text == text
        assert result.encoding is None
        assert result.improved is False


def test_unrecoverable_artifact_detected_but_not_repaired() -> None:
    result = repair("锟斤拷")
    assert result.improved is False
    assert result.text == "锟斤拷"
    assert is_mojibake("锟斤拷") is True


def test_result_never_contains_replacement_char() -> None:
    for text in (make_mojibake("你好"), make_mojibake("数据", "gbk"), "锟斤拷"):
        assert "\\ufffd" not in repair(text).text


def test_is_mojibake_positive_cases() -> None:
    assert is_mojibake(make_mojibake("你好")) is True
    assert is_mojibake(make_mojibake("你好", "gbk")) is True


def test_is_mojibake_negative_cases() -> None:
    for text in ("hello", "你好", "こんにちは", ""):
        assert is_mojibake(text) is False


def test_candidates_sorted_by_score() -> None:
    got = candidates(make_mojibake("你好"))
    assert got
    scores = [score(text) for _, text in got]
    assert scores == sorted(scores)


def test_candidates_empty_for_unencodable_text() -> None:
    assert candidates("😀") == []


def test_repair_dataclass_fields() -> None:
    result = Repair(text="x", encoding="latin-1", score_before=3, score_after=0)
    assert result.improved is True
    assert Repair(text="x", encoding=None, score_before=0, score_after=0).improved is False


def test_mixed_mojibake_and_clean_text() -> None:
    mixed = "文件名: " + make_mojibake("报表") + ".xlsx"
    assert is_mojibake(mixed) is True
    assert "报表" in repair(mixed).text
    assert repair(mixed).text.startswith("文件名: ")
''',
}

CHALLENGE = {
    "target": "mojibake/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 mojibake/challenge.py 中实现 explain(text: str) -> str: "
        "用 mojibake.fix 里的 repair / score, 返回一行人话说明: "
        "能修时给出 'X -> Y (经 <encoding>, 坏度 A -> B)'; "
        "命中已知不可逆产物时说明信息已丢失; 正常文本返回 '看起来正常'。"
        "不得修改其他模块。"
    ),
    "tests_content": '''from mojibake.challenge import explain


def broken(text: str, encoding: str = "latin-1") -> str:
    return text.encode("utf-8").decode(encoding)


def test_clean_text() -> None:
    assert explain("hello") == "看起来正常"


def test_repaired_text_mentions_encoding() -> None:
    line = explain(broken("你好"))
    assert "你好" in line
    assert "latin-1" in line
    assert "坏度" in line


def test_unrecoverable_text() -> None:
    assert "丢失" in explain("锟斤拷")
''',
}
