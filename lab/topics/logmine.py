'''日志模板挖掘: 把成千上万条相似日志压成 "<IP>" "<*>" 这样的模板, 带出现次数。

灵感来源:
- Drain3 的输出形态就是标准答案: `connected to <IP>` / `Hex number <HEX>` / `user <*> logged in`,
  靠固定深度解析树 + 位置相似度合并, 避免树越挖越深
  (https://pypi.org/project/drain3/0.7.7/)
- Drain 系列实现里"模板变了要落快照"的设计, 说明模板是有状态的、需要持久化的对象
  (https://github.com/yiyao-chen/Log-parser-Drain3)

为什么值得单独做一层: 排查线上问题的时候, 真正有用的不是"第 8 万 3 千条日志", 而是
"这 8 万条其实是 12 种情况, 其中第 3 种出现了 7 万次"。把变量位置抹成占位符之后,
日志才有统计意义; 而变量位置就是 IP、UUID、十六进制、纯数字这些老面孔。

本模块是 Drain 的简化版: 不做固定深度树, 改成"按 token 数分桶 + 桶内按位置相似度合并"。
少了一点性能优化, 但行为完全确定, 同样的输入永远得到同样的模板编号 —— 这样才能写测试。
'''

SLUG = "logmine"
TITLE = "日志模板挖掘"
TAGS = ["日志分析", "Drain 算法", "模板聚类", "运维"]
PKG = "logmine"
SUMMARY = '把海量相似日志压成模板: 变量位替换为 <IP>/<HEX>/<NUM>, 差异位替换为 <*>, 并统计出现次数。'
STACK_NOTES = [
    "先按 token 数分桶, 桶内按位置相似度合并, 避免全量两两比较",
    "变量识别用白名单正则(IP/UUID/HEX/数字), 认不出的差异位交给相似度判成 <*>",
    "模板编号按首次出现顺序发放, 同样输入永远得到同样的编号",
]
NOTES = """
两步走, 顺序不能反:

1. **先认变量**。`10.0.0.1`、`0xDEADBEAF`、`550e8400-e29b-41d4-a716-446655440000`、`12345`
   这些如果直接交给相似度判断, 会被误判成"每条日志都不一样", 因为它们在每个位置都不同。
   先抹成 `<IP>` `<HEX>` `<UUID>` `<NUM>`, 相似度才有意义。
2. **再判差异**。抹完变量还剩差异的, 才算"同一个模板的不同取值", 用 `<*>` 占位。

相似度的定义是"位置相同(或两边有一边已经是 `<*>` )的比例"。阈值默认 0.5,
意思是"一半以上位置对得上就认为是同一类"。调高阈值会更保守(模板更多更精确),
调低会更激进(模板更少更笼统) —— 两种都可能对, 取决于你要的是聚合还是精确。
"""

FILES = {
    "logmine/__init__.py": '''from .mask import PATTERNS, mask_line, mask_token, tokenize
from .miner import Miner, Template

__all__ = ["PATTERNS", "tokenize", "mask_token", "mask_line", "Template", "Miner"]
''',
    "logmine/mask.py": '''# 变量识别: 把老面孔换成占位符。
from __future__ import annotations

import re

IPV4 = re.compile(r"\\d{1,3}(?:\\.\\d{1,3}){3}")
UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
HEX = re.compile(r"0[xX][0-9a-fA-F]+")
NUMBER = re.compile(r"\\d+")

# 顺序有意义: IP 与 UUID 都比纯数字具体, 必须先匹配
PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (UUID, "<UUID>"),
    (IPV4, "<IP>"),
    (HEX, "<HEX>"),
    (NUMBER, "<NUM>"),
)


def tokenize(line: str) -> list[str]:
    """按空白切词, 连续空白压成一个。"""
    body = " ".join(str(line).split())
    return body.split(" ") if body else []


def mask_token(token: str) -> str:
    """整词匹配变量模式; 认不出就原样返回。"""
    for pattern, placeholder in PATTERNS:
        if pattern.fullmatch(token):
            return placeholder
    return token


def mask_line(line: str) -> str:
    return " ".join(mask_token(token) for token in tokenize(line))
''',
    "logmine/miner.py": '''# 模板挖掘: 分桶 + 相似度合并。
from __future__ import annotations

from dataclasses import dataclass, field

from .mask import mask_token, tokenize

WILDCARD = "<*>"


@dataclass
class Template:
    id: int
    tokens: tuple[str, ...]
    count: int = 0

    @property
    def text(self) -> str:
        return " ".join(self.tokens)

    def __str__(self) -> str:
        return self.text


def similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    """位置相同的比例; 任一侧已是 <*> 也算相同。"""
    if len(left) != len(right):
        return 0.0
    if not left:
        return 1.0
    same = sum(1 for a, b in zip(left, right) if a == b or a == WILDCARD or b == WILDCARD)
    return same / len(left)


def _merge(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(a if a == b else WILDCARD for a, b in zip(left, right))


class Miner:
    """按 token 数分桶, 桶内按相似度合并。"""

    def __init__(self, similarity_threshold: float = 0.5) -> None:
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("阈值必须在 0..1")
        self.similarity_threshold = similarity_threshold
        self._buckets: dict[int, list[Template]] = {}
        self._by_id: dict[int, Template] = {}
        self._next_id = 1

    def add(self, line: str) -> Template:
        tokens = tuple(mask_token(token) for token in tokenize(line))
        if not tokens:
            raise ValueError("空行没有模板")

        bucket = self._buckets.setdefault(len(tokens), [])
        best: Template | None = None
        best_score = -1.0
        for candidate in bucket:
            score = similarity(candidate.tokens, tokens)
            if score > best_score:
                best, best_score = candidate, score

        if best is not None and best_score >= self.similarity_threshold:
            best.tokens = _merge(best.tokens, tokens)
            best.count += 1
            return best

        template = Template(id=self._next_id, tokens=tokens, count=1)
        self._next_id += 1
        bucket.append(template)
        self._by_id[template.id] = template
        return template

    def get(self, template_id: int) -> Template:
        return self._by_id[template_id]

    def templates(self) -> list[Template]:
        """按模板编号(即首次出现顺序)返回。"""
        return [self._by_id[key] for key in sorted(self._by_id)]
''',
    "tests/test_mask.py": '''import pytest

from logmine import mask_line, mask_token, tokenize


def test_tokenize_collapses_whitespace() -> None:
    assert tokenize("  connected   to\\t10.0.0.1 ") == ["connected", "to", "10.0.0.1"]


def test_tokenize_empty() -> None:
    assert tokenize("") == []
    assert tokenize("   ") == []


@pytest.mark.parametrize(
    "token,expected",
    [
        ("10.0.0.1", "<IP>"),
        ("192.168.1.254", "<IP>"),
        ("0xDEADBEAF", "<HEX>"),
        ("0x10000", "<HEX>"),
        ("12345", "<NUM>"),
        ("550e8400-e29b-41d4-a716-446655440000", "<UUID>"),
    ],
)
def test_mask_token_recognises_variables(token: str, expected: str) -> None:
    assert mask_token(token) == expected


@pytest.mark.parametrize("token", ["davidoh", "connected", "10.0.0.1.5", "abc123", "<IP>"])
def test_mask_token_leaves_words_alone(token: str) -> None:
    assert mask_token(token) == token


def test_mask_line_end_to_end() -> None:
    assert mask_line("user 123 connected from 10.0.0.1") == "user <NUM> connected from <IP>"


def test_mask_line_keeps_punctuation_tokens() -> None:
    assert mask_line("retry=3 ok") == "retry=3 ok"
''',
    "tests/test_miner.py": '''import pytest

from logmine import Miner


def test_identical_lines_share_one_template() -> None:
    miner = Miner()
    for line in ("connected to 10.0.0.1", "connected to 10.0.0.2", "connected to 10.0.0.3"):
        miner.add(line)
    templates = miner.templates()
    assert len(templates) == 1
    assert templates[0].text == "connected to <IP>"
    assert templates[0].count == 3


def test_hex_and_number_masked() -> None:
    miner = Miner()
    miner.add("Hex number 0xDEADBEAF")
    miner.add("Hex number 0x10000")
    miner.add("count 42")
    miner.add("count 7")
    texts = sorted(t.text for t in miner.templates())
    assert texts == ["Hex number <HEX>", "count <NUM>"]


def test_unknown_variation_becomes_wildcard() -> None:
    miner = Miner()
    miner.add("user davidoh logged in")
    miner.add("user eranr logged in")
    templates = miner.templates()
    assert len(templates) == 1
    assert templates[0].text == "user <*> logged in"
    assert templates[0].count == 2


def test_different_shapes_stay_separate() -> None:
    miner = Miner()
    miner.add("connected to 10.0.0.1")
    miner.add("job finished")
    assert len(miner.templates()) == 2


def test_different_token_counts_never_merge() -> None:
    miner = Miner()
    miner.add("a b c")
    miner.add("a b c d")
    assert len(miner.templates()) == 2


def test_threshold_controls_aggressiveness() -> None:
    strict = Miner(similarity_threshold=0.9)
    strict.add("alpha beta gamma delta")
    strict.add("alpha beta gamma omega")
    assert len(strict.templates()) == 2     # 3/4 = 0.75 < 0.9

    loose = Miner(similarity_threshold=0.5)
    loose.add("alpha beta gamma delta")
    loose.add("alpha beta gamma omega")
    assert len(loose.templates()) == 1     # 0.75 >= 0.5


def test_template_ids_follow_first_seen_order() -> None:
    miner = Miner()
    first = miner.add("alpha beta")
    second = miner.add("gamma delta")
    assert (first.id, second.id) == (1, 2)
    assert [t.id for t in miner.templates()] == [1, 2]


def test_exactly_threshold_similarity_merges() -> None:
    """蒙掉数字后只剩一个词不同: 相似度正好 0.5, 而阈值是闭区间, 所以合并。

    这个边界是刻意选的: `a 1` 和 `b 2` 形状相同, 合成 `<*> <NUM>` 更符合"模板"的意义。
    想要更保守就把阈值调高。
    """
    miner = Miner()
    first = miner.add("a 1")
    merged = miner.add("b 2")
    assert merged.id == first.id
    assert merged.text == "<*> <NUM>"


def test_ids_are_stable_across_runs() -> None:
    def run() -> list[int]:
        miner = Miner()
        for line in ("alpha beta", "gamma delta", "alpha beta"):
            miner.add(line)
        return [t.id for t in miner.templates()]

    assert run() == run() == [1, 2]


def test_get_by_id() -> None:
    miner = Miner()
    tpl = miner.add("connected to 10.0.0.1")
    assert miner.get(tpl.id) is tpl


def test_get_unknown_id_raises() -> None:
    with pytest.raises(KeyError):
        Miner().get(99)


def test_empty_line_rejected() -> None:
    with pytest.raises(ValueError):
        Miner().add("   ")


def test_bad_threshold_rejected() -> None:
    with pytest.raises(ValueError):
        Miner(similarity_threshold=1.5)


def test_wildcard_positions_stay_wildcard() -> None:
    """合并成 <*> 之后再来的日志, 不应把通配位"填回去"。"""
    miner = Miner()
    miner.add("user davidoh logged in")
    miner.add("user eranr logged in")
    tpl = miner.add("user bob logged in")
    assert tpl.text == "user <*> logged in"
    assert tpl.count == 3


def test_similarity_helper() -> None:
    from logmine.miner import similarity

    assert similarity(("a", "b"), ("a", "b")) == 1.0
    assert similarity(("a", "b"), ("a", "<*>")) == 1.0
    assert similarity(("a", "b"), ("c", "d")) == 0.0
    assert similarity(("a", "b"), ("a",)) == 0.0
''',
}

CHALLENGE = {
    "target": "logmine/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 logmine/challenge.py 中实现 top_templates(miner, n=3) -> list[str]: "
        "按出现次数从多到少取前 n 个模板, 返回 '次数 x 模板文本' 形式的字符串列表; "
        "次数相同时按模板编号升序。复用 logmine.miner.Template, 不得修改其他模块。"
    ),
    "tests_content": '''from logmine import Miner
from logmine.challenge import top_templates


def test_sorted_by_count() -> None:
    miner = Miner()
    for _ in range(3):
        miner.add("connected to 10.0.0.1")
    miner.add("job done")
    assert top_templates(miner, n=2) == ["3 x connected to <IP>", "1 x job done"]


def test_limit_respected() -> None:
    miner = Miner()
    miner.add("a 1")
    miner.add("b 2")
    miner.add("c 3")
    assert len(top_templates(miner, n=2)) == 2
''',
}
