# 并查集聚类: 一次扫描把近似重复的文本归组。
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
