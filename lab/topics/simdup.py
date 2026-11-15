'''近似重复检测: 字符 shingle + Jaccard + SimHash + MinHash, 纯标准库, 结果可复现。

灵感来源:
- Data-Juicer 的 document_simhash_deduplicator: 用 simhash + 海明距离做语料去重的工业做法
  (https://datajuicer.github.io/data-juicer/zh_CN/v1.4.0/_modules/data_juicer/ops/deduplicator/document_simhash_deduplicator.html)
- minhash 的"多次最小哈希近似 Jaccard"实现, 说明置换次数与误差的关系
  (https://github.com/docxology/codomyrmex/blob/main/src/codomyrmex/data_curation/minhash.py)
- RAG 检索结果里同时返回三份同义文档, 是知识库没做去重的典型症状
  (https://github.com/pubalisen/ai-ml-interview-deep-dives/blob/main/rag/29-scenario-duplicate-results.md)

为什么值得单独做一层: 知识库入库前要判重, 但逐对比对 O(n^2) 全文本相似度太慢,
而且"改了两个字"的同一篇文档用精确匹配根本抓不到。这里给两层工具:
SimHash 用来做"粗略指纹" (64 位整数, 比对仅需异或), MinHash 用来估算 Jaccard
(签名长度可控, 误差随长度下降)。两者都不依赖分词, 中文按字符切 shingle 就行。

确定性很重要: 所有哈希都走 blake2b 加盐, 不用 Python 内置 hash() ——
后者每个进程带随机种子, 同一段文本换个进程就得到不同指纹, 去重结果会前后不一致。
'''

SLUG = "simdup"
TITLE = "近似重复检测（SimHash / MinHash）"
TAGS = ["SimHash", "MinHash", "去重", "RAG 预处理"]
PKG = "simdup"
SUMMARY = '字符 shingle + Jaccard + SimHash 指纹 + MinHash 签名, 判断「改了几个字」的两段文本是不是同一份。'
STACK_NOTES = [
    "所有哈希走 blake2b 加盐, 不用内置 hash(), 跨进程结果稳定",
    "MinHash 用 signature 逐位相等比例估 Jaccard, 签名长度可换精度",
    "聚类用并查集, 一次扫描把近似重复的文本归到同一组",
]
NOTES = """
三层设计, 越往下越慢、越准:

1. `jaccard(a, b)`: 精确值, 用来看"到底像到什么程度"。测试里当基准。
2. `minhash_similarity(sig1, sig2)`: 用 128 个最小哈希近似 Jaccard, 误差约 ±0.05。
   适合大规模两两比较, 只需比整数。
3. `simhash` + `hamming`: 把整段文本压成 64 位整数, 海明距离 <= 3 通常视为近似重复。
   最便宜, 适合先粗筛。

中文不需要分词: 按字符切 3-gram 对"改几个字"这类改动很敏感, 而分词反而会把
"用户名"和"用名户"这类乱序当成相同。
"""

FILES = {
    "simdup/__init__.py": '''from .cluster import dedupe, near_duplicates
from .fingerprint import hamming, minhash_signature, minhash_similarity, simhash, simhash_similarity
from .shingle import jaccard, normalize_text, shingles

__all__ = [
    "normalize_text",
    "shingles",
    "jaccard",
    "simhash",
    "hamming",
    "simhash_similarity",
    "minhash_signature",
    "minhash_similarity",
    "near_duplicates",
    "dedupe",
]
''',
    "simdup/shingle.py": '''# 文本规范化、字符 shingle 与精确 Jaccard。
from __future__ import annotations

import re
import unicodedata

_SPACES = re.compile(r"\\s+")


def normalize_text(text: str) -> str:
    """全角转半角、去多余空白、统一小写。"""
    body = unicodedata.normalize("NFKC", str(text))
    return _SPACES.sub(" ", body).strip().lower()


def shingles(text: str, k: int = 3) -> set[str]:
    """按字符切 k-gram; 文本比 k 短时整体作为一个 shingle。"""
    if k < 1:
        raise ValueError("k 必须 >= 1")
    body = normalize_text(text)
    if not body:
        return set()
    if len(body) <= k:
        return {body}
    return {body[i : i + k] for i in range(len(body) - k + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    """交集除以并集; 两边都空时视为完全相似(1.0)。"""
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)
''',
    "simdup/fingerprint.py": '''# 稳定哈希、SimHash 指纹与 MinHash 签名。
from __future__ import annotations

import hashlib
from typing import Iterable

BITS = 64


def _hash64(token: str, salt: int = 0) -> int:
    """blake2b 加盐取 8 字节 —— 不用内置 hash(), 保证跨进程稳定。"""
    person = b"simdup" + salt.to_bytes(4, "big")
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8, person=person).digest()
    return int.from_bytes(digest, "big")


def simhash(tokens: Iterable[str], bits: int = BITS) -> int:
    """把一组 token 压成一个 bits 位整数指纹。"""
    vector = [0] * bits
    for token in tokens:
        value = _hash64(token)
        for index in range(bits):
            vector[index] += 1 if (value >> index) & 1 else -1
    out = 0
    for index, weight in enumerate(vector):
        if weight > 0:
            out |= 1 << index
    return out


def hamming(left: int, right: int) -> int:
    """两个指纹差多少位。"""
    return bin(left ^ right).count("1")


def simhash_similarity(left: int, right: int, bits: int = BITS) -> float:
    return 1.0 - hamming(left, right) / bits


def minhash_signature(tokens: Iterable[str], num_perm: int = 128, bits: int = BITS) -> tuple[int, ...]:
    """每个"置换"取一个最小哈希值, 组成签名。"""
    if num_perm < 1:
        raise ValueError("num_perm 必须 >= 1")
    items = list(tokens)
    signature: list[int] = []
    for salt in range(num_perm):
        best = None
        for token in items:
            value = _hash64(token, salt)
            if best is None or value < best:
                best = value
        signature.append(0 if best is None else best)
    return tuple(signature)


def minhash_similarity(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    """签名逐位相等的比例, 即 Jaccard 的估计值。"""
    if len(left) != len(right):
        raise ValueError("两个签名长度必须相同")
    if not left:
        return 1.0
    same = sum(1 for a, b in zip(left, right) if a == b)
    return same / len(left)
''',
    "simdup/cluster.py": '''# 并查集聚类: 一次扫描把近似重复的文本归组。
from __future__ import annotations

from typing import Sequence

from .fingerprint import minhash_signature, minhash_similarity
from .shingle import shingles


def near_duplicates(
    texts: Sequence[str], threshold: float = 0.8, k: int = 3, num_perm: int = 128
) -> list[list[int]]:
    """返回分组(下标列表), 组内两两相似度不低于 threshold; 组间按最小下标排序。"""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold 必须在 0..1")
    count = len(texts)
    parent = list(range(count))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)

    signatures = [
        minhash_signature(shingles(text, k), num_perm=num_perm) for text in texts
    ]
    for i in range(count):
        for j in range(i + 1, count):
            if minhash_similarity(signatures[i], signatures[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for index in range(count):
        groups.setdefault(find(index), []).append(index)
    return sorted(groups.values(), key=lambda group: group[0])


def dedupe(texts: Sequence[str], threshold: float = 0.8, k: int = 3, num_perm: int = 128) -> list[int]:
    """每组只保留第一次出现的下标。"""
    return [group[0] for group in near_duplicates(texts, threshold, k, num_perm)]
''',
    "tests/test_shingle.py": '''import pytest

from simdup import jaccard, normalize_text, shingles


def test_normalize_collapses_and_lowercases() -> None:
    assert normalize_text("  Hello   World  ") == "hello world"


def test_normalize_fullwidth_to_halfwidth() -> None:
    assert normalize_text("ＡＢＣ　１２３") == "abc 123"


def test_shingles_basic() -> None:
    assert shingles("abcdef", 3) == {"abc", "bcd", "cde", "def"}


def test_shingles_short_text() -> None:
    assert shingles("ab", 3) == {"ab"}


def test_shingles_empty() -> None:
    assert shingles("", 3) == set()
    assert shingles("   ", 3) == set()


def test_shingles_honours_normalization() -> None:
    assert shingles("ABC DEF", 3) == shingles("abc   def", 3)


def test_shingles_rejects_bad_k() -> None:
    with pytest.raises(ValueError):
        shingles("abc", 0)


def test_jaccard_identical() -> None:
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint() -> None:
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial() -> None:
    assert jaccard({"a", "b", "c"}, {"b", "c", "d"}) == pytest.approx(2 / 4)


def test_jaccard_both_empty() -> None:
    assert jaccard(set(), set()) == 1.0


def test_jaccard_cjk_text() -> None:
    left = shingles("知识库入库前要去重", 3)
    right = shingles("知识库入库前需要去重", 3)
    assert 0.3 < jaccard(left, right) < 1.0
''',
    "tests/test_fingerprint.py": '''import pytest

from simdup import (
    hamming,
    minhash_signature,
    minhash_similarity,
    shingles,
    simhash,
    simhash_similarity,
)

TEXT_A = "数据管道每天跑一次批处理任务"
TEXT_B = "数据管道每天跑一次批处理作业"
TEXT_C = "完全不相干的内容，讲的是别的事情"


def test_simhash_is_deterministic() -> None:
    first = simhash(shingles(TEXT_A))
    second = simhash(shingles(TEXT_A))
    assert first == second
    assert isinstance(first, int)


def test_simhash_identical_text_equal() -> None:
    assert simhash(shingles(TEXT_A)) == simhash(shingles(TEXT_A))


def test_simhash_near_text_closer_than_far_text() -> None:
    near = hamming(simhash(shingles(TEXT_A)), simhash(shingles(TEXT_B)))
    far = hamming(simhash(shingles(TEXT_A)), simhash(shingles(TEXT_C)))
    assert near < far


def test_simhash_empty_tokens() -> None:
    assert simhash(set()) == 0


def test_hamming_symmetric_and_zero() -> None:
    assert hamming(0b1010, 0b0011) == 2
    assert hamming(7, 7) == 0
    assert hamming(0b1010, 0b0011) == hamming(0b0011, 0b1010)


def test_simhash_similarity_range() -> None:
    value = simhash_similarity(1, 2)
    assert 0.0 <= value <= 1.0
    assert simhash_similarity(5, 5) == 1.0


def test_minhash_signature_shape_and_determinism() -> None:
    tokens = shingles(TEXT_A)
    sig = minhash_signature(tokens, num_perm=16)
    assert len(sig) == 16
    assert sig == minhash_signature(tokens, num_perm=16)


def test_minhash_rejects_bad_perm() -> None:
    with pytest.raises(ValueError):
        minhash_signature({"a"}, num_perm=0)


def test_minhash_similarity_identical() -> None:
    sig = minhash_signature(shingles(TEXT_A), num_perm=32)
    assert minhash_similarity(sig, sig) == 1.0


def test_minhash_length_mismatch() -> None:
    with pytest.raises(ValueError):
        minhash_similarity((1, 2), (1, 2, 3))


def test_minhash_approximates_jaccard() -> None:
    """两边各 100 个 token, 交集 50: 真实 Jaccard = 50/150 ≈ 0.333。"""
    left = {"t" + str(i) for i in range(100)}
    right = {"t" + str(i) for i in range(50, 150)}
    sig_left = minhash_signature(left, num_perm=256)
    sig_right = minhash_signature(right, num_perm=256)
    estimate = minhash_similarity(sig_left, sig_right)
    assert estimate == pytest.approx(1 / 3, abs=0.1)


def test_minhash_near_duplicate_high() -> None:
    sig_a = minhash_signature(shingles(TEXT_A), num_perm=64)
    sig_b = minhash_signature(shingles(TEXT_B), num_perm=64)
    sig_c = minhash_signature(shingles(TEXT_C), num_perm=64)
    assert minhash_similarity(sig_a, sig_b) > minhash_similarity(sig_a, sig_c)
''',
    "tests/test_cluster.py": '''import pytest

from simdup import dedupe, jaccard, near_duplicates, shingles

BASE = (
    "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖关系、失败重试策略、"
    "每日跑批的时间窗口安排，以及上游数据延迟时的降级方案和告警阈值设置。"
)
TWEAK = (
    "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖关系、失败重试策略、"
    "每日跑批的时间窗口安排，以及上游数据延迟时的降级方案和告警阈值处理。"
)
OTHER = (
    "完全不同的主题：讲的是前端动画性能优化的若干技巧，包括合成层与重绘的取舍、"
    "requestAnimationFrame 的调度时机，以及离屏画布的使用边界。"
)


def test_groups_identical_texts() -> None:
    groups = near_duplicates([BASE, BASE, OTHER])
    assert groups == [[0, 1], [2]]


def test_near_duplicate_clusters_together() -> None:
    groups = near_duplicates([BASE, OTHER, TWEAK])
    assert groups[0] == [0, 2]
    assert groups[1] == [1]


def test_dedupe_keeps_first_of_each_group() -> None:
    assert dedupe([BASE, BASE, OTHER]) == [0, 2]


def test_threshold_one_requires_exact() -> None:
    groups = near_duplicates([BASE, TWEAK], threshold=1.0)
    assert groups == [[0], [1]]


def test_short_text_edit_moves_jaccard_a_lot() -> None:
    """短文本 + 字符 3-gram: 改两个字就能把 Jaccard 从 1.0 拉到 0.8 附近。

    所以阈值不要设在正好等于理论相似度的位置 —— MinHash 是估计器,
    128 个置换在 0.8 附近的波动足以让结果左右翻转。
    """
    short_a = "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖关系。"
    short_b = "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖处理。"
    value = jaccard(shingles(short_a), shingles(short_b))
    assert 0.75 < value < 0.85


def test_threshold_zero_merges_everything() -> None:
    groups = near_duplicates([BASE, OTHER], threshold=0.0)
    assert groups == [[0, 1]]


def test_empty_input() -> None:
    assert near_duplicates([]) == []
    assert dedupe([]) == []


def test_single_item() -> None:
    assert near_duplicates([BASE]) == [[0]]


def test_groups_sorted_by_first_index() -> None:
    groups = near_duplicates([BASE, OTHER, BASE, OTHER])
    assert [group[0] for group in groups] == sorted(group[0] for group in groups)


def test_threshold_validation() -> None:
    with pytest.raises(ValueError):
        near_duplicates([BASE], threshold=1.5)
''',
}

CHALLENGE = {
    "target": "simdup/challenge.py",
    "tests": "tests/test_challenge.py",
    "prompt": (
        "在 simdup/challenge.py 中实现 report(texts) -> str: "
        "用 simdup.cluster.dedupe 得到保留的下标, 返回一行 "
        "'共 N 条, 去重后 M 条, 合并 K 条'; 复用已有函数, 不得修改其他模块。"
    ),
    "tests_content": '''from simdup.challenge import report

BASE = "这是一篇关于数据管道调度的说明文档，讲批处理任务的依赖关系。"
OTHER = "完全不同的主题：讲的是前端动画性能优化的若干技巧和取舍。"


def test_all_unique() -> None:
    assert report([BASE, OTHER]) == "共 2 条, 去重后 2 条, 合并 0 条"


def test_with_duplicate() -> None:
    assert report([BASE, BASE, OTHER]) == "共 3 条, 去重后 2 条, 合并 1 条"
''',
}
